"""Import iPhone dialog backend.

The phone helper and the match rules stay in the sibling iphonePhotos
tool. This module only finds that tool, asks it to look or copy, and
reports progress. It never writes to the phone.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

_MISSING = (
    "The iPhone tool is not next to Library. "
    "Copy the iphonePhotos folder beside this folder and run its Setup.bat."
)
_RUNTIME = (
    "The phone helper needs the .NET 10 runtime. "
    "Run Setup.bat again, then try Import iPhone."
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
    from ui.match import (  # type: ignore
        ACTION_COPY,
        ACTION_SKIP,
        completed_pairs,
        copy_item,
        file_name,
        folder_text,
        log_skip_if_new,
        look_status,
        phone_text,
        plan,
    )
    from ui.phone import Phone, PhoneError  # type: ignore

    return {
        "ACTION_COPY": ACTION_COPY,
        "ACTION_SKIP": ACTION_SKIP,
        "completed_pairs": completed_pairs,
        "copy_item": copy_item,
        "file_name": file_name,
        "folder_text": folder_text,
        "log_skip_if_new": log_skip_if_new,
        "look_status": look_status,
        "phone_text": phone_text,
        "plan": plan,
        "Phone": Phone,
        "PhoneError": PhoneError,
    }


def status() -> dict:
    root = tool_root()
    if root is None:
        return {"installed": False, "message": _MISSING}
    host = _host_exe(root)
    try:
        proc = subprocess.run(
            [str(host)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        return {"installed": False, "message": str(exc), "tool": str(root)}
    text = (proc.stdout or "") + (proc.stderr or "")
    if "You must install or update .NET" in text:
        return {"installed": False, "message": _RUNTIME, "tool": str(root)}
    if "Usage:" not in text:
        detail = text.strip() or "The phone helper did not start."
        return {"installed": False, "message": detail, "tool": str(root)}
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
    phone_error = api["PhoneError"]
    try:
        with api["Phone"]() as phone:
            name = phone.connect()
            files = phone.list_dcim()
    except phone_error as exc:
        return {"ok": False, "message": str(exc)}
    items = api["plan"](files, dest)
    rows = []
    skip = 0
    will_copy = 0
    for item in items:
        if item.action == api["ACTION_SKIP"]:
            skip += 1
        else:
            will_copy += 1
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
    phone_error = api["PhoneError"]
    try:
        with api["Phone"]() as phone:
            try:
                name = phone.connect()
                files = phone.list_dcim()
            except phone_error as exc:
                _set(running=False, phase="error", error=str(exc), message=str(exc))
                return
            items = api["plan"](files, dest)
            skip = sum(1 for item in items if item.action == api["ACTION_SKIP"])
            will_copy = len(items) - skip
            _set(
                phone=name,
                path=str(dest),
                onPhone=len(items),
                skip=skip,
                willCopy=will_copy,
                phase="copying",
                message="Copying what is missing.",
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
                label = api["file_name"](item.source_path)
                _set(current=label, message="Copying " + label)
                try:
                    api["copy_item"](dest, item, phone.iter_file(item.source_path, item.size))
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
