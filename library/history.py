"""Undo files, 500-entry cap, and cursor."""

from __future__ import annotations

import contextvars
import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from library.atomic import load_json
from library.errors import fail
from library.paths import library_path
from library.settings import ordered

HISTORY_CAP = 500
OPERATIONS = frozenset(
    {
        "scan",
        "copy-here",
        "annotate",
        "favorite",
        "people-merge",
        "people-split",
        "person-update",
        "settings",
        "relocate",
        "remove",
        "remove-source",
        "delete-file",
        "move",
        "analyze-places",
        "faces-infer",
        "faces-cleanup",
        "tags",
        "rate",
    }
)


def entries_dir(root: Path) -> Path:
    return root / "undo" / "entries"


def state_path(root: Path) -> Path:
    return root / "undo" / "state.json"


def default_state() -> dict[str, Any]:
    return {"schemaVersion": 1, "entries": [], "cursor": 0}


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return default_state()
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        raise fail("invalid-catalog") from exc
    if not isinstance(data, dict):
        raise fail("invalid-catalog")
    entries = data.get("entries")
    cursor = data.get("cursor")
    if data.get("schemaVersion") != 1 or not isinstance(entries, list):
        raise fail("invalid-catalog")
    if type(cursor) is not int or cursor < 0 or cursor > len(entries):
        raise fail("invalid-catalog")
    for item in entries:
        if type(item) is not str:
            raise fail("invalid-catalog")
    return {"schemaVersion": 1, "entries": list(entries), "cursor": cursor}


def load_entry_raw(root: Path, entry_id: str) -> dict[str, Any]:
    path = library_path(root, f"undo/entries/{entry_id}.json")
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        raise fail("invalid-catalog") from exc
    except OSError as exc:
        raise fail("io-error") from exc
    return data


def load_entry(root: Path, entry_id: str) -> dict[str, Any]:
    """Logical history entry: base file plus any append-only segments."""
    raw = load_entry_raw(root, entry_id)
    changes = _coalesced_changes(root, entry_id, raw)
    out = dict(raw)
    out["changes"] = [
        {"path": change["path"], "before": change.get("before"), "after": change.get("after")}
        for change in changes
    ]
    return out


def new_entry_id(root: Path) -> str:
    existing = set()
    folder = entries_dir(root)
    if folder.exists():
        existing = {p.stem for p in folder.glob("*.json")}
    for _ in range(32):
        candidate = secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise fail("internal-error")


def make_settings_entry(
    root: Path,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "id": new_entry_id(root),
        "operation": "settings",
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "changes": [
            {
                "path": "settings.json",
                "before": ordered(before),
                "after": ordered(after),
            }
        ],
    }


def make_history_entry(root: Path, operation: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise fail("invalid-catalog")
    return {
        "schemaVersion": 1,
        "id": new_entry_id(root),
        "operation": operation,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "changes": changes,
    }


def latest_entry_id(root: Path) -> str | None:
    state = load_state(root)
    if state["cursor"] == 0:
        return None
    return state["entries"][state["cursor"] - 1]


def scan_entry_id(root: Path) -> str | None:
    return operation_entry_id(root, "scan")


def operation_entry_id(root: Path, operation: str) -> str | None:
    entry_id = latest_entry_id(root)
    if entry_id is None:
        return None
    entry = load_entry_raw(root, entry_id)
    if entry.get("operation") != operation:
        return None
    return entry_id


def extend_current_operation(
    root: Path,
    changes: list[dict[str, Any]],
    operations: tuple[str, ...] = ("scan", "copy-here"),
) -> list[dict[str, Any]]:
    entry_id = latest_entry_id(root)
    if entry_id is None:
        return changes
    entry = load_entry_raw(root, entry_id)
    if entry.get("operation") in operations:
        return plan_extend_entry(root, entry_id, changes)
    return changes


def plan_extend_entry(
    root: Path,
    entry_id: str,
    extra_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append this step's changes. The entry file is folded once when the operation ends.

    Undo keeps the first before per path and redo the last after. Rewriting that
    whole entry on every file copies a growing snapshot, so an in-progress scan
    stores each step as its own small segment instead.
    """
    load_entry_raw(root, entry_id)
    seq = _allocate_seq(root, entry_id)
    rel = f"undo/segments/{entry_id}/{seq}.json"
    segment = {"schemaVersion": 1, "changes": list(extra_changes)}
    return [
        {"path": rel, "before": None, "after": segment},
        *extra_changes,
    ]


def plan_append(root: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    """History + state file changes for a new committed user operation."""
    state = load_state(root)
    kept_ids = state["entries"][: state["cursor"]]
    dropped_ids = state["entries"][state["cursor"] :]
    kept_ids = kept_ids + [entry["id"]]
    drop_files: list[str] = list(dropped_ids)
    while len(kept_ids) > HISTORY_CAP:
        drop_files.append(kept_ids.pop(0))
    new_state = {
        "schemaVersion": 1,
        "entries": kept_ids,
        "cursor": len(kept_ids),
    }
    changes: list[dict[str, Any]] = [
        {
            "path": f"undo/entries/{entry['id']}.json",
            "before": None,
            "after": entry,
        },
        {
            "path": "undo/state.json",
            "before": state if state_path(root).exists() else None,
            "after": new_state,
        },
    ]
    for old_id in drop_files:
        entry_rel = f"undo/entries/{old_id}.json"
        path = library_path(root, entry_rel)
        before = load_json(path) if path.exists() else None
        changes.append({"path": entry_rel, "before": before, "after": None})
        changes.extend(segment_drop_changes(root, old_id))
    return changes


def plan_cursor_move(
    root: Path,
    new_cursor: int,
    file_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    state = load_state(root)
    after_state = {
        "schemaVersion": 1,
        "entries": list(state["entries"]),
        "cursor": new_cursor,
    }
    changes = [
        {
            "path": "undo/state.json",
            "before": state if state_path(root).exists() else None,
            "after": after_state,
        }
    ]
    changes.extend(file_changes)
    return changes


_batch_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "history_batch_depth", default=0
)
_SEQ: dict[tuple[str, str], int] = {}
_MERGE: dict[tuple[str, str], dict[str, Any]] = {}


@contextmanager
def batching_history():
    """Hold this thread's entry file still while a scan appends one segment per step.

    Other threads keep their own undo steps. A scan's relaxed manifests are
    protected separately by `holding_open_transactions`.
    """
    token = _batch_depth.set(_batch_depth.get() + 1)
    try:
        yield
    finally:
        _batch_depth.reset(token)


def history_batching() -> bool:
    return _batch_depth.get() > 0


def segments_dir(root: Path, entry_id: str) -> Path:
    return root / "undo" / "segments" / entry_id


def _allocate_seq(root: Path, entry_id: str) -> str:
    key = (str(root.resolve()), entry_id)
    if key not in _SEQ:
        folder = segments_dir(root, entry_id)
        highest = 0
        if folder.is_dir():
            for path in folder.glob("*.json"):
                try:
                    highest = max(highest, int(path.stem))
                except ValueError:
                    continue
        _SEQ[key] = highest
    _SEQ[key] += 1
    return f"{_SEQ[key]:06d}"


def _segment_files(root: Path, entry_id: str) -> list[Path]:
    folder = segments_dir(root, entry_id)
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.json") if path.is_file())


def segment_drop_changes(root: Path, entry_id: str) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for path in _segment_files(root, entry_id):
        rel = f"undo/segments/{entry_id}/{path.name}"
        changes.append({"path": rel, "before": load_json(path), "after": None})
    return changes


def _apply_extra(
    changes: list[dict[str, Any]],
    index: dict[str, int],
    extra: list[dict[str, Any]],
) -> None:
    for change in extra:
        path = change["path"]
        if path not in index:
            index[path] = len(changes)
            changes.append(
                {"path": path, "before": change.get("before"), "after": change.get("after")}
            )
        else:
            changes[index[path]]["after"] = change.get("after")


def _coalesced_changes(root: Path, entry_id: str, raw: dict[str, Any]) -> list[dict[str, Any]]:
    files = _segment_files(root, entry_id)
    entry_path = library_path(root, f"undo/entries/{entry_id}.json")
    try:
        mtime = entry_path.stat().st_mtime_ns
    except OSError:
        mtime = 0
    key = (str(root.resolve()), entry_id)
    names = [path.name for path in files]
    slot = _MERGE.get(key)
    if slot is not None and slot["mtime"] == mtime and names[: slot["count"]] == slot["names"]:
        for path in files[slot["count"] :]:
            body = load_json(path)
            extra = body.get("changes") if isinstance(body, dict) else None
            _apply_extra(slot["changes"], slot["index"], extra or [])
            slot["names"].append(path.name)
        slot["count"] = len(files)
        return slot["changes"]
    changes = [
        {"path": change["path"], "before": change.get("before"), "after": change.get("after")}
        for change in (raw.get("changes") or [])
        if isinstance(change, dict) and type(change.get("path")) is str
    ]
    index = {change["path"]: pos for pos, change in enumerate(changes)}
    applied: list[str] = []
    for path in files:
        body = load_json(path)
        extra = body.get("changes") if isinstance(body, dict) else None
        _apply_extra(changes, index, extra or [])
        applied.append(path.name)
    _MERGE[key] = {
        "mtime": mtime,
        "count": len(files),
        "names": applied,
        "changes": changes,
        "index": index,
    }
    return changes


def _net_noop(change: dict[str, Any]) -> bool:
    return change.get("before") is None and change.get("after") is None


def _invalidate_entry(root: Path, entry_id: str) -> None:
    key = (str(root.resolve()), entry_id)
    _MERGE.pop(key, None)
    _SEQ.pop(key, None)


def seal_entry(root: Path, entry_id: str) -> None:
    """Fold segments into the one entry file and drop the segment directory contents."""
    files = _segment_files(root, entry_id)
    if not files:
        return
    from library.atomic import checkpoint_transactions, transact

    checkpoint_transactions(root)
    raw = load_entry_raw(root, entry_id)
    logical = [change for change in _coalesced_changes(root, entry_id, raw) if not _net_noop(change)]
    after = dict(raw)
    after["changes"] = logical
    changes: list[dict[str, Any]] = [
        {
            "path": f"undo/entries/{entry_id}.json",
            "before": raw,
            "after": after,
        }
    ]
    for path in files:
        changes.append(
            {
                "path": f"undo/segments/{entry_id}/{path.name}",
                "before": load_json(path),
                "after": None,
            }
        )
    transact(root, changes, durable=True)
    _invalidate_entry(root, entry_id)


def seal_latest(root: Path) -> None:
    entry_id = latest_entry_id(root)
    if entry_id is not None:
        seal_entry(root, entry_id)


def seal_open_entries(root: Path) -> None:
    """Fold leftover segments after a crash. Skipped while a scan is still appending."""
    if history_batching():
        return
    from library.atomic import transactions_held

    if transactions_held(root):
        return
    base = root / "undo" / "segments"
    if not base.is_dir():
        return
    for child in sorted(path for path in base.iterdir() if path.is_dir()):
        if any(child.glob("*.json")):
            seal_entry(root, child.name)
