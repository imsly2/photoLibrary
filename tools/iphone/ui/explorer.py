"""Read the iPhone the way File Explorer shows Internal Storage.

The phone stays read-only. Listing reports folder and file names Explorer
uses, such as 201508_a/IMG_0519.JPG. Pull copies one of those files onto
the PC and refuses to replace a file that is already there.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ui.match import PhoneFile

_SCRIPT = Path(__file__).resolve().parents[1] / "ExplorerLayout.ps1"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ExplorerError(Exception):
    """A phone or copy problem the dialog can show as a sentence."""


def _run(action: str, relative: str = "", dest: str = "") -> subprocess.CompletedProcess[str]:
    if not _SCRIPT.is_file():
        raise ExplorerError("The Explorer phone reader is missing from this Library copy.")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(_SCRIPT),
        "-Action",
        action,
    ]
    if relative:
        command.extend(["-Relative", relative])
    if dest:
        command.extend(["-Dest", dest])
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_NO_WINDOW,
    )


def _failure(proc: subprocess.CompletedProcess[str]) -> str:
    text = (proc.stderr or "").strip() or (proc.stdout or "").strip()
    if text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return f"The Explorer phone reader exited with code {proc.returncode}."


def list_layout() -> tuple[str, list[PhoneFile]]:
    """Return the Explorer phone name and every Internal Storage file."""
    proc = _run("list")
    if proc.returncode != 0:
        raise ExplorerError(_failure(proc))
    phone = "Apple iPhone"
    files: list[PhoneFile] = []
    seen: set[str] = set()
    for line in proc.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExplorerError("The Explorer phone reader returned a line that is not JSON.") from exc
        if not isinstance(row, dict):
            raise ExplorerError("The Explorer phone reader returned a line that is not JSON.")
        if "phone" in row and "rel" not in row:
            name = row.get("phone")
            if isinstance(name, str) and name.strip():
                phone = name.strip()
            continue
        rel = row.get("rel")
        size = row.get("size")
        if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
            raise ExplorerError("The Explorer phone reader returned a path that is not a backup file.")
        if isinstance(size, bool) or not isinstance(size, int):
            raise ExplorerError(f"The Explorer phone reader returned a bad size for {rel}.")
        key = rel.casefold()
        if key in seen:
            raise ExplorerError(f"Explorer listed {rel} more than once.")
        seen.add(key)
        files.append(PhoneFile(rel, size, datetime.fromtimestamp(0, timezone.utc)))
    if not files:
        raise ExplorerError("Internal Storage did not list any files. Unlock the phone and tap Trust.")
    return phone, files


def pull_file(relative: str, dest: Path) -> None:
    """Copy one Explorer file to dest. dest must not already exist."""
    proc = _run("pull", relative, str(dest))
    if proc.returncode != 0:
        raise ExplorerError(_failure(proc))
    if not dest.is_file():
        raise ExplorerError(f"Explorer did not create {dest.name}.")
