"""Read-only phone access through the helper exe. Nothing here writes to the phone."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from ui.match import PhoneFile

_HOST = (
    Path(__file__).resolve().parents[1]
    / "ui-host"
    / "bin"
    / "Release"
    / "net10.0"
    / "win-x64"
    / "iphone-photos-host.exe"
)
_MISSING = "The phone helper is not built yet."
_CHUNK = 1024 * 1024
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PhoneError(Exception):
    """A phone problem the window can show as a sentence."""


def _stderr_text(proc: subprocess.CompletedProcess[str]) -> str:
    text = (proc.stderr or "").strip()
    if text:
        return text
    return f"The phone helper exited with code {proc.returncode}."


def _parse_mtime(value: object) -> datetime:
    if value is None:
        return datetime.now()
    if not isinstance(value, str) or not value.strip():
        raise PhoneError(f"Unexpected file time from the phone: {value!r}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # .NET round-trip ("o") uses 7 fractional digits. fromisoformat keeps 6.
    dot = text.find(".")
    if dot != -1:
        end = dot + 1
        while end < len(text) and text[end].isdigit():
            end += 1
        if end - (dot + 1) > 6:
            text = text[: dot + 7] + text[end:]
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise PhoneError(f"Unexpected file time from the phone: {value!r}") from exc


class Phone:
    """One look or copy. The helper exe is the only thing that talks to the phone."""

    def __init__(self) -> None:
        self.name = ""
        self._files: list[PhoneFile] | None = None

    def __enter__(self) -> "Phone":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        return None

    def _require_host(self) -> None:
        if not _HOST.is_file():
            raise PhoneError(_MISSING)

    def connect(self) -> str:
        self._require_host()
        self._files = self._read_list()
        return self.name

    def list_dcim(self) -> list[PhoneFile]:
        self._require_host()
        if self._files is None:
            self._files = self._read_list()
        return list(self._files)

    def iter_file(self, source_path: str, size: int):
        del size  # the helper copies the whole file; the match step checks the length
        self._require_host()
        directory = Path(tempfile.mkdtemp(prefix="iphone-photos-"))
        dest = directory / "pull.bin"
        try:
            proc = self._run("pull", source_path, str(dest))
            if proc.returncode != 0:
                raise PhoneError(_stderr_text(proc))
            with dest.open("rb") as handle:
                while True:
                    chunk = handle.read(_CHUNK)
                    if not chunk:
                        break
                    yield chunk
        finally:
            dest.unlink(missing_ok=True)
            shutil.rmtree(directory, ignore_errors=True)

    def _read_list(self) -> list[PhoneFile]:
        proc = self._run("list")
        if proc.returncode != 0:
            raise PhoneError(_stderr_text(proc))
        files: list[PhoneFile] = []
        saw_phone = False
        for line in proc.stdout.splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise PhoneError(f"The phone helper returned invalid JSON: {text}") from exc
            if not isinstance(row, dict):
                raise PhoneError(f"The phone helper returned invalid JSON: {text}")
            if not saw_phone:
                saw_phone = True
                phone = row.get("phone")
                self.name = phone.strip() if isinstance(phone, str) and phone.strip() else "iPhone"
                continue
            path = row.get("path")
            if not isinstance(path, str) or not path:
                raise PhoneError("The phone helper returned a file with no path.")
            size = row.get("size")
            if isinstance(size, bool) or not isinstance(size, (int, float)):
                raise PhoneError(f"The phone helper returned a bad size for {path}.")
            files.append(PhoneFile(path, int(size), _parse_mtime(row.get("mtime"))))
        if not saw_phone:
            raise PhoneError("The phone helper did not report a phone name.")
        return files

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(_HOST), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )


def stream_list(on_row=None, should_stop=None) -> tuple[str, list[PhoneFile]]:
    """List /DCIM as the helper prints each file. The phone stays read-only."""
    if not _HOST.is_file():
        raise PhoneError(_MISSING)
    proc = subprocess.Popen(
        [str(_HOST), "list"],
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

    err_thread = threading.Thread(target=_stderr, name="iphone-month-err", daemon=True)
    err_thread.start()
    name = ""
    files: list[PhoneFile] = []
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if should_stop is not None and should_stop():
                proc.kill()
                raise PhoneError("Look stopped.")
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise PhoneError(f"The phone helper returned invalid JSON: {text}") from exc
            if not isinstance(row, dict):
                raise PhoneError(f"The phone helper returned invalid JSON: {text}")
            if on_row is not None:
                on_row(row)
            if "path" not in row:
                phone = row.get("phone")
                if isinstance(phone, str) and phone.strip():
                    name = phone.strip()
                continue
            path = row.get("path")
            size = row.get("size")
            if not isinstance(path, str) or not path:
                raise PhoneError("The phone helper returned a file with no path.")
            if isinstance(size, bool) or not isinstance(size, (int, float)):
                raise PhoneError(f"The phone helper returned a bad size for {path}.")
            files.append(PhoneFile(path, int(size), _parse_mtime(row.get("mtime"))))
    finally:
        proc.wait()
        err_thread.join(timeout=2)
    if should_stop is not None and should_stop() and proc.returncode not in {0, None}:
        raise PhoneError("Look stopped.")
    if proc.returncode not in {0, None}:
        text = "".join(errors).strip() or f"The phone helper exited with code {proc.returncode}."
        raise PhoneError(text.splitlines()[0])
    if not name:
        raise PhoneError("The phone helper did not report a phone name.")
    if not files:
        raise PhoneError("The phone helper did not list any camera files.")
    return name, files
