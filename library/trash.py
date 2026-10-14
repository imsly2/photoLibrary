"""Send a file to the OS trash / Recycle Bin. Never unlink as a fallback."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def trash_file(path: Path) -> bool:
    """Move *path* to Recycle Bin / trash. False if the file stays put."""
    if not path.is_file():
        return False
    try:
        if os.name == "nt":
            return _trash_windows(path)
        if sys.platform == "darwin":
            return _trash_macos(path)
        return _trash_linux(path)
    except OSError:
        return False


def _trash_windows(path: Path) -> bool:
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400
    flags = FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = str(path) + "\0"
    op.pTo = None
    op.fFlags = flags
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return result == 0 and not path.exists()


def _trash_macos(path: Path) -> bool:
    script = (
        'tell application "Finder" to delete '
        + "(POSIX file "
        + json_quote(str(path))
        + ")"
    )
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _trash_xdg(path)
    return proc.returncode == 0 and not path.exists()


def json_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _trash_linux(path: Path) -> bool:
    for cmd in (("gio", "trash"), ("trash-put",), ("gvfs-trash",)):
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        try:
            proc = subprocess.run(
                [exe, *cmd[1:], str(path)],
                check=False,
                capture_output=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0 and not path.exists():
            return True
    return _trash_xdg(path)


def _trash_xdg(path: Path) -> bool:
    home = Path.home()
    trash = Path(os.environ.get("XDG_DATA_HOME") or (home / ".local" / "share")) / "Trash"
    files_dir = trash / "files"
    info_dir = trash / "info"
    try:
        files_dir.mkdir(parents=True, exist_ok=True)
        info_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    dest = files_dir / path.name
    if dest.exists():
        stem = path.stem
        suffix = path.suffix
        n = 2
        while dest.exists():
            dest = files_dir / f"{stem}_{n}{suffix}"
            n += 1
    info = info_dir / (dest.name + ".trashinfo")
    try:
        os.replace(path, dest)
    except OSError:
        try:
            shutil.move(str(path), str(dest))
        except OSError:
            return False
    from datetime import datetime, timezone

    stamped = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    body = "[Trash Info]\nPath=" + str(path) + "\nDeletionDate=" + stamped + "\n"
    try:
        info.write_text(body, encoding="utf-8")
    except OSError:
        pass
    return not path.exists()
