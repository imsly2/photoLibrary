"""Temp-sibling atomic writes and multi-file transactions."""

from __future__ import annotations

import contextvars
import json
import os
import re
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from library.folder_library import SourceUnavailable
from library.paths import library_path, normalize_root


def dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


_sync_payloads: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "library_sync_payloads", default=True
)
_tx_seq = 0
_tx_seq_lock = threading.Lock()
_open_tx_roots: dict[str, int] = {}
_open_tx_lock = threading.Lock()
# A committed manifest never changes again, so a read during a long scan only
# opens each one once instead of once per status request.
_committed_seen: dict[str, set[str]] = {}
_TX_PREFIX = re.compile(r"^(\d{20})-(\d{08})-")


@contextmanager
def relaxed_durability():
    """Fsync transaction manifests only. Call `checkpoint_transactions` before returning.

    Catalog files are still replaced atomically. A crash replays the committed
    manifest, so each file does not need its own flush during a long scan.
    """
    token = _sync_payloads.set(False)
    try:
        yield
    finally:
        _sync_payloads.reset(token)


@contextmanager
def holding_open_transactions(root: Path):
    """Keep this root's relaxed manifests in place until the scan checkpoints them.

    Other threads may call `recover` while a scan is appending. They must not
    replay or delete those manifests.
    """
    key = str(normalize_root(root))
    with _open_tx_lock:
        _open_tx_roots[key] = _open_tx_roots.get(key, 0) + 1
    try:
        yield
    finally:
        with _open_tx_lock:
            left = _open_tx_roots.get(key, 1) - 1
            if left <= 0:
                _open_tx_roots.pop(key, None)
            else:
                _open_tx_roots[key] = left


def transactions_held(root: Path) -> bool:
    key = str(normalize_root(root))
    with _open_tx_lock:
        return _open_tx_roots.get(key, 0) > 0


def _new_transaction_id() -> str:
    """Lexicographic order matches commit order. The sequence breaks same-ns ties."""
    global _tx_seq
    with _tx_seq_lock:
        _tx_seq += 1
        seq = _tx_seq
    return f"{time.time_ns():020d}-{seq:08d}-{uuid.uuid4().hex[:8]}"


def _transaction_sort_key(tdir: Path) -> tuple[int, int, str]:
    match = _TX_PREFIX.match(tdir.name)
    if match:
        return (int(match.group(1)), int(match.group(2)), tdir.name)
    manifest = tdir / "manifest.json"
    try:
        mtime = manifest.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return (mtime, 0, tdir.name)


def atomic_write_bytes(path: Path, data: bytes, *, sync: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            if sync:
                os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_write_text(path: Path, text: str, *, sync: bool = True) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), sync=sync)


def atomic_write_json(path: Path, obj: Any, *, sync: bool = True) -> None:
    atomic_write_text(path, dumps_canonical(obj), sync=sync)


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def apply_payload(root: Path, relative: str, payload: Any, *, sync: bool = True) -> None:
    from library import item_store

    item_id = item_store.item_id_of(relative)
    if item_id is not None:
        item_store.write(root, item_id, payload, sync=sync)
        return
    path = library_path(root, relative)
    if payload is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write_json(path, payload, sync=sync)
    if relative.startswith("catalog/sources/"):
        from library.catalog_io import note_source_write

        note_source_write(root, relative, payload)


def fsync_file(path: Path) -> None:
    if not path.is_file():
        return
    with open(path, "r+b") as handle:
        os.fsync(handle.fileno())


def _transaction_root(root: Path) -> Path:
    return root / ".transactions"


def write_manifest(tdir: Path, manifest: dict[str, Any]) -> None:
    atomic_write_json(tdir / "manifest.json", manifest, sync=True)


def maybe_test_barrier(name: str) -> None:
    import sys

    if os.environ.get("LIBRARY_TEST") != "1":
        return
    if os.environ.get("LIBRARY_TEST_BARRIER") != name:
        return
    sys.stderr.write(
        json.dumps({"error": "test-barrier", "barrier": name}, separators=(",", ":"))
        + "\n"
    )
    sys.stderr.flush()
    raise SystemExit(86)


def transact(
    root: Path,
    changes: list[dict[str, Any]],
    *,
    use_settings_barriers: bool = False,
    durable: bool | None = None,
) -> str:
    """Write a prepared manifest, apply `after` payloads, then commit.

    Settings-change order (CONTRACTS Foundation locks):
    prepared → barrier settings-prepared → atomic replace →
    history already in `changes` → committed → barrier settings-committed →
    delete the transaction directory.
    """
    tid = _new_transaction_id()
    tdir = _transaction_root(root) / tid
    tdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "id": tid,
        "state": "prepared",
        "changes": changes,
    }
    write_manifest(tdir, manifest)
    if use_settings_barriers:
        maybe_test_barrier("settings-prepared")
    sync_payloads = _sync_payloads.get() if durable is None else durable
    for change in changes:
        apply_payload(root, change["path"], change["after"], sync=sync_payloads)
    manifest = {
        "schemaVersion": 1,
        "id": tid,
        "state": "committed",
        "changes": changes,
    }
    write_manifest(tdir, manifest)
    if use_settings_barriers:
        maybe_test_barrier("settings-committed")
    if sync_payloads:
        shutil.rmtree(tdir, ignore_errors=False)
        remaining = _transaction_root(root)
        if remaining.exists() and not any(remaining.iterdir()):
            remaining.rmdir()
    purge_orphan_undo_files(root)
    if sync_payloads:
        try:
            from library.portable import mirror_changes

            mirror_changes(root, changes)
        except Exception:
            pass
    return tid


def purge_orphan_undo_files(root: Path) -> None:
    files_dir = root / "undo" / "files"
    if not files_dir.exists():
        return
    kept: set[str] = set()
    state_file = root / "undo" / "state.json"
    if state_file.exists():
        try:
            state = load_json(state_file)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(state, dict):
            for entry_id in state.get("entries") or []:
                if type(entry_id) is str:
                    kept.add(entry_id)
    for child in list(files_dir.iterdir()):
        if child.is_dir() and child.name not in kept:
            shutil.rmtree(child, ignore_errors=True)


def _transaction_dirs(root: Path) -> list[Path]:
    base = _transaction_root(root)
    try:
        with os.scandir(base) as entries:
            dirs = [Path(entry.path) for entry in entries if entry.is_dir()]
    except FileNotFoundError:
        return []
    dirs.sort(key=_transaction_sort_key)
    return dirs


def _committed_dirs(root: Path) -> list[Path]:
    found: list[Path] = []
    for tdir in _transaction_dirs(root):
        manifest_path = tdir / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = load_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("state") == "committed":
            found.append(tdir)
    return found


def checkpoint_transactions(root: Path) -> None:
    """Flush catalog files already written by relaxed transactions, then drop manifests.

    Disk already has the latest replace/unlink. Replaying an older manifest would
    resurrect a file a later transaction removed.
    """
    dirs = _committed_dirs(root)
    seen: set[str] = set()
    for tdir in dirs:
        manifest = load_json(tdir / "manifest.json")
        for change in manifest.get("changes") or []:
            relative = change.get("path")
            if type(relative) is not str or change.get("after") is None or relative in seen:
                continue
            seen.add(relative)
            try:
                fsync_file(library_path(root, relative))
            except SourceUnavailable:
                pass
    for tdir in dirs:
        shutil.rmtree(tdir, ignore_errors=False)
    base = _transaction_root(root)
    if base.exists() and not any(base.iterdir()):
        base.rmdir()


def _leave_scan_transactions(root: Path) -> bool:
    """True while this thread, or any thread, still owns an in-progress scan."""
    from library.history import history_batching

    return history_batching() or transactions_held(root)


def recover_transactions(root: Path) -> dict[str, Any]:
    """Roll prepared changes back and committed changes forward, oldest first."""
    from library.history import seal_open_entries

    base = _transaction_root(root)
    recovered: list[dict[str, Any]] = []
    if not base.exists():
        if not _leave_scan_transactions(root):
            from library.catalog_io import fold_open_journals

            fold_open_journals(root)
            seal_open_entries(root)
        return {"recovered": recovered}
    leave_committed = _leave_scan_transactions(root)
    dirs = _transaction_dirs(root)
    with _open_tx_lock:
        seen = _committed_seen.setdefault(str(normalize_root(root)), set())
        seen.intersection_update(tdir.name for tdir in dirs)
    for tdir in dirs:
        if leave_committed and tdir.name in seen:
            continue
        manifest_path = tdir / "manifest.json"
        try:
            manifest = load_json(manifest_path)
        except FileNotFoundError:
            shutil.rmtree(tdir, ignore_errors=True)
            continue
        state = manifest.get("state")
        changes = manifest.get("changes") or []
        if state == "committed" and leave_committed:
            with _open_tx_lock:
                seen.add(tdir.name)
            continue
        if state not in {"prepared", "committed"}:
            continue
        side = "before" if state == "prepared" else "after"
        try:
            for change in changes:
                apply_payload(root, change["path"], change[side])
        except SourceUnavailable:
            # Replays are idempotent; retry once that folder is reachable again.
            continue
        shutil.rmtree(tdir, ignore_errors=False)
        recovered.append({"id": manifest.get("id"), "state": state})
    if base.exists() and not any(base.iterdir()):
        base.rmdir()
    if not _leave_scan_transactions(root):
        from library.catalog_io import fold_open_journals

        fold_open_journals(root)
        seal_open_entries(root)
    return {"recovered": recovered}
