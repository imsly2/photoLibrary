"""Temp-sibling atomic writes and multi-file transactions."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from library.paths import library_path


def dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, dumps_canonical(obj))


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def apply_payload(root: Path, relative: str, payload: Any) -> None:
    path = library_path(root, relative)
    if payload is None:
        if path.exists():
            path.unlink()
        return
    atomic_write_json(path, payload)


def _transaction_root(root: Path) -> Path:
    return root / ".transactions"


def write_manifest(tdir: Path, manifest: dict[str, Any]) -> None:
    atomic_write_json(tdir / "manifest.json", manifest)


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
) -> str:
    """Write a prepared manifest, apply `after` payloads, then commit.

    Settings-change order (CONTRACTS Foundation locks):
    prepared → barrier settings-prepared → atomic replace →
    history already in `changes` → committed → barrier settings-committed →
    delete the transaction directory.
    """
    tid = uuid.uuid4().hex[:12]
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
    for change in changes:
        apply_payload(root, change["path"], change["after"])
    manifest = {
        "schemaVersion": 1,
        "id": tid,
        "state": "committed",
        "changes": changes,
    }
    write_manifest(tdir, manifest)
    if use_settings_barriers:
        maybe_test_barrier("settings-committed")
    shutil.rmtree(tdir, ignore_errors=False)
    remaining = _transaction_root(root)
    if remaining.exists() and not any(remaining.iterdir()):
        remaining.rmdir()
    purge_orphan_undo_files(root)
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


def recover_transactions(root: Path) -> dict[str, Any]:
    """Roll prepared changes back and committed changes forward."""
    base = _transaction_root(root)
    recovered: list[dict[str, Any]] = []
    if not base.exists():
        return {"recovered": recovered}
    for tdir in sorted(p for p in base.iterdir() if p.is_dir()):
        manifest_path = tdir / "manifest.json"
        if not manifest_path.exists():
            shutil.rmtree(tdir, ignore_errors=True)
            continue
        manifest = load_json(manifest_path)
        state = manifest.get("state")
        changes = manifest.get("changes") or []
        if state == "prepared":
            for change in changes:
                apply_payload(root, change["path"], change["before"])
        elif state == "committed":
            for change in changes:
                apply_payload(root, change["path"], change["after"])
        shutil.rmtree(tdir, ignore_errors=False)
        recovered.append({"id": manifest.get("id"), "state": state})
    if base.exists() and not any(base.iterdir()):
        base.rmdir()
    return {"recovered": recovered}
