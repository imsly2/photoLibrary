"""Import iPhone dialog backend.

The phone helper and match rules live in tools/iphone inside this repo.
This module finds that tool, asks it to look or copy, and reports progress.
It never writes to the phone.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

_MISSING = (
    "The iPhone import tool is missing from this Library copy. "
    "Re-run Setup.bat or pull the latest code from the photoLibrary repo."
)

_lock = threading.Lock()
_stop = threading.Event()
_job: dict = {
    "phase": "idle",
    "running": False,
    "path": "",
    "phone": "",
    "onPhone": 0,
    "skip": 0,
    "willCopy": 0,
    "copied": 0,
    "current": "",
    "message": "",
    "error": "",
}


def tool_root() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("LIBRARY_IPHONE_TOOL", "").strip()
    if env:
        candidates.append(Path(env))
    library_dir = Path(__file__).resolve().parents[1]
    candidates.append(library_dir / "tools" / "iphone")
    candidates.append(library_dir.parent / "iphonePhotos")
    for path in candidates:
        host = _host_exe(path)
        match = path / "ui" / "match.py"
        if host.is_file() and match.is_file():
            return path
    return None


def _host_exe(root: Path) -> Path:
    return (
        root
        / "ui-host"
        / "bin"
        / "Release"
        / "net10.0"
        / "win-x64"
        / "iphone-photos-host.exe"
    )


def _load(root: Path):
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    from ui.explorer import ExplorerError, list_layout, pull_file  # type: ignore
    from ui.match import (  # type: ignore
        ACTION_COPY,
        ACTION_KEEP,
        ACTION_SKIP,
        completed_pairs,
        copy_item,
        file_name,
        folder_text,
        log_skip_if_new,
        look_status,
        phone_text,
        plan_mirror,
    )

    return {
        "ExplorerError": ExplorerError,
        "list_layout": list_layout,
        "pull_file": pull_file,
        "ACTION_COPY": ACTION_COPY,
        "ACTION_KEEP": ACTION_KEEP,
        "ACTION_SKIP": ACTION_SKIP,
        "completed_pairs": completed_pairs,
        "copy_item": copy_item,
        "file_name": file_name,
        "folder_text": folder_text,
        "log_skip_if_new": log_skip_if_new,
        "look_status": look_status,
        "phone_text": phone_text,
        "plan_mirror": plan_mirror,
    }


def status() -> dict:
    root = tool_root()
    if root is None:
        return {"installed": False, "message": _MISSING}
    script = root / "ExplorerLayout.ps1"
    if not script.is_file():
        return {"installed": False, "message": _MISSING, "tool": str(root)}
    return {"installed": True, "message": "", "tool": str(root)}


def _destination(path: str) -> Path:
    text = (path or "").strip()
    if not text:
        raise ValueError("Choose a folder first.")
    dest = Path(text)
    if dest.exists() and not dest.is_dir():
        raise ValueError("That path is a file. Choose a folder.")
    if not dest.exists():
        dest.mkdir(parents=True)
    return dest


def _snapshot() -> dict:
    with _lock:
        return dict(_job)


def job() -> dict:
    return _snapshot()


def _set(**values) -> None:
    with _lock:
        _job.update(values)


def look(path: str) -> dict:
    with _lock:
        if _job["running"]:
            return {"ok": False, "message": "A copy is already running."}
    root = tool_root()
    if root is None:
        return {"ok": False, "installed": False, "message": _MISSING}
    try:
        dest = _destination(path)
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}
    api = _load(root)
    phone_error = api["ExplorerError"]
    try:
        name, files, repeated = api["list_layout"]()
    except phone_error as exc:
        return {"ok": False, "message": str(exc)}
    items = api["plan_mirror"](files, dest)
    rows = []
    skip = 0
    will_copy = 0
    kept = 0
    for item in items:
        if item.action == api["ACTION_SKIP"]:
            skip += 1
        elif item.action == api["ACTION_COPY"]:
            will_copy += 1
        else:
            kept += 1
        rows.append(
            {
                "phone": api["phone_text"](item.source_path, item.size),
                "folder": api["folder_text"](item),
                "status": api["look_status"](item),
                "action": item.action,
            }
        )
    return {
        "ok": True,
        "installed": True,
        "phone": name,
        "path": str(dest),
        "onPhone": len(items),
        "skip": skip,
        "willCopy": will_copy,
        "kept": kept,
        "repeated": repeated,
        "rows": rows,
    }


def start_copy(path: str) -> dict:
    with _lock:
        if _job["running"]:
            return {"ok": False, "message": "A copy is already running."}
        _job.update(
            {
                "phase": "starting",
                "running": True,
                "path": path,
                "phone": "",
                "onPhone": 0,
                "skip": 0,
                "willCopy": 0,
                "copied": 0,
                "current": "",
                "message": "Reading the camera roll…",
                "error": "",
            }
        )
    _stop.clear()
    threading.Thread(target=_copy_worker, args=(path,), name="iphone-import", daemon=True).start()
    return {"ok": True, **_snapshot()}


def stop_copy() -> dict:
    _stop.set()
    _set(message="Stopping after the current file.")
    return _snapshot()


def _copy_worker(path: str) -> None:
    root = tool_root()
    if root is None:
        _set(running=False, phase="error", error=_MISSING, message=_MISSING)
        return
    try:
        dest = _destination(path)
    except ValueError as exc:
        _set(running=False, phase="error", error=str(exc), message=str(exc))
        return
    api = _load(root)
    phone_error = api["ExplorerError"]
    try:
        name, files, repeated = api["list_layout"]()
        items = api["plan_mirror"](files, dest)
        skip = sum(1 for item in items if item.action == api["ACTION_SKIP"])
        will_copy = sum(1 for item in items if item.action == api["ACTION_COPY"])
        kept = len(items) - skip - will_copy
        message = "Copying what is missing."
        if repeated:
            message = (
                f"Explorer listed {repeated} pictures twice. Each was counted once. "
                + message
            )
        _set(
            phone=name,
            path=str(dest),
            onPhone=len(items),
            skip=skip,
            willCopy=will_copy,
            kept=kept,
            phase="copying",
            message=message,
        )
        done = api["completed_pairs"](dest)
        copied = 0
        for item in items:
            if _stop.is_set():
                _set(
                    running=False,
                    phase="stopped",
                    copied=copied,
                    message="Stopped. Files already copied stay copied.",
                )
                return
            if item.action == api["ACTION_SKIP"]:
                api["log_skip_if_new"](dest, item, done)
                continue
            if item.action != api["ACTION_COPY"] or not item.dest_relative:
                continue
            label = item.dest_relative
            _set(current=label, message="Copying " + label)
            directory = Path(tempfile.mkdtemp(prefix="iphone-explorer-"))
            staged = directory / Path(item.dest_relative).name
            try:
                api["pull_file"](item.source_path, staged)

                def chunks():
                    with staged.open("rb") as handle:
                        while True:
                            block = handle.read(1024 * 1024)
                            if not block:
                                break
                            yield block

                api["copy_item"](dest, item, chunks())
            except Exception as exc:
                _set(
                    running=False,
                    phase="error",
                    copied=copied,
                    current=label,
                    error=str(exc),
                    message="Stopped on " + label + ". Files already copied stay copied.",
                )
                return
            finally:
                shutil.rmtree(directory, ignore_errors=True)
            copied += 1
            _set(copied=copied)
    except phone_error as exc:
        _set(running=False, phase="error", error=str(exc), message=str(exc))
        return
    if _stop.is_set():
        _set(running=False, phase="stopped", message="Stopped. Files already copied stay copied.")
        return
    _set(
        running=False,
        phase="done",
        current="",
        message="Copy finished. Adding the folder to the library.",
    )
