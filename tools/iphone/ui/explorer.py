"""Read the iPhone the way File Explorer shows Internal Storage.

The phone stays read-only. Listing reports folder and file names Explorer
uses, such as 201508_a/IMG_0519.JPG. Pull copies one of those files onto
the PC and refuses to replace a file that is already there.
"""

from __future__ import annotations

import json
import subprocess
import threading
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
        for line in lines:
            if line.startswith(("+", "At ", "CategoryInfo")) or "FullyQualifiedErrorId" in line:
                continue
            return line
        if lines:
            return lines[0]
    return f"The Explorer phone reader exited with code {proc.returncode}."


def _files_from_lines(lines: list[str]) -> tuple[str, list[PhoneFile], int, int]:
    """Parse Explorer listing lines. A repeated path is counted once."""
    phone = "Apple iPhone"
    files: list[PhoneFile] = []
    seen: dict[str, int] = {}
    repeated = 0
    skipped = 0
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExplorerError("The Explorer phone reader returned a line that is not JSON.") from exc
        if not isinstance(row, dict):
            raise ExplorerError("The Explorer phone reader returned a line that is not JSON.")
        if "rel" not in row and "skipped" in row:
            count = row.get("skipped")
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                skipped = count
            continue
        if "reading" in row and "rel" not in row:
            continue
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
            repeated += 1
            continue
        seen[key] = size
        files.append(PhoneFile(rel, size, datetime.fromtimestamp(0, timezone.utc)))
    if not files:
        raise ExplorerError(
            "Internal Storage opened empty. Unplug the phone, plug it back in, unlock it, and try Look again."
        )
    return phone, files, repeated, skipped


def list_layout(on_row=None, should_stop=None) -> tuple[str, list[PhoneFile], int, int]:
    """Return the phone name, each Internal Storage file once, and repeat and skip counts.

    ``on_row`` sees each JSON object as Explorer writes it, including
    ``{"reading": "202510_a"}`` when a folder is opened. ``should_stop``
    ends the read early.
    """
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
        "list",
    ]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_NO_WINDOW,
    )
    errors: list[str] = []

    def _stderr() -> None:
        if proc.stderr is None:
            return
        errors.append(proc.stderr.read())

    err_thread = threading.Thread(target=_stderr, name="iphone-list-err", daemon=True)
    err_thread.start()
    lines: list[str] = []
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if should_stop is not None and should_stop():
                proc.kill()
                raise ExplorerError("Look stopped.")
            text = line.strip()
            if not text:
                continue
            lines.append(text)
            if on_row is None:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                on_row(row)
    finally:
        proc.wait()
        err_thread.join(timeout=2)
    if proc.returncode not in {0, None} and not (should_stop is not None and should_stop()):
        class _Done:
            returncode = proc.returncode
            stderr = "".join(errors)
            stdout = "\n".join(lines)

        raise ExplorerError(_failure(_Done()))  # type: ignore[arg-type]
    if should_stop is not None and should_stop() and proc.returncode not in {0, None}:
        raise ExplorerError("Look stopped.")
    return _files_from_lines(lines)


def pull_file(relative: str, dest: Path) -> None:
    """Copy one Explorer file to dest. dest must not already exist."""
    proc = _run("pull", relative, str(dest))
    if proc.returncode != 0:
        raise ExplorerError(_failure(proc))
    if not dest.is_file():
        raise ExplorerError(f"Explorer did not create {dest.name}.")
