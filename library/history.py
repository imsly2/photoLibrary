"""Undo files, 500-entry cap, and cursor."""

from __future__ import annotations

import json
import secrets
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
        "settings",
        "relocate",
        "remove",
        "delete-file",
        "analyze-places",
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


def load_entry(root: Path, entry_id: str) -> dict[str, Any]:
    path = library_path(root, f"undo/entries/{entry_id}.json")
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        raise fail("invalid-catalog") from exc
    except OSError as exc:
        raise fail("io-error") from exc
    return data


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
    entry = load_entry(root, entry_id)
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
    entry = load_entry(root, entry_id)
    if entry.get("operation") in operations:
        return plan_extend_entry(root, entry_id, changes)
    return changes


def plan_extend_entry(
    root: Path,
    entry_id: str,
    extra_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entry = load_entry(root, entry_id)
    before = json.loads(json.dumps(entry))
    after = json.loads(json.dumps(entry))
    after["changes"] = list(entry.get("changes") or []) + extra_changes
    return [
        {
            "path": f"undo/entries/{entry_id}.json",
            "before": before,
            "after": after,
        },
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
