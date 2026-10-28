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
import time
from pathlib import Path

_MISSING = (
    "The iPhone import tool is missing from this Library copy. "
    "Re-run Setup.bat or pull the latest code from the photoLibrary repo."
)

_lock = threading.Lock()
_stop = threading.Event()
_last_look: dict | None = None
_job: dict = {
    "phase": "idle",
    "running": False,
    "path": "",
    "phone": "",
    "onPhone": 0,
    "skip": 0,
    "willCopy": 0,
    "copied": 0,
    "kept": 0,
    "current": "",
    "comparing": False,
    "startedAt": None,
    "updatedAt": None,
    "folderFound": 0,
    "waitingMs": 0,
    "picturesPerSec": 0,
    "pace": None,
    "fromLook": False,
    "message": "",
    "error": "",
}


def _same_folder(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _saved_look(dest: Path, layout: str) -> dict | None:
    """The last finished Look for this folder and this read, if Copy can skip the phone."""
    saved = _last_look
    if not saved or not saved.get("files") or saved.get("layout") != layout:
        return None
    try:
        if not _same_folder(Path(saved["path"]), dest):
            return None
    except OSError:
        return None
    return saved


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
        mirror_action,
        phone_text,
        plan,
        plan_mirror,
        _mirror_locals,
    )
    from ui.phone import Phone, PhoneError, stream_list  # type: ignore

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
        "mirror_action": mirror_action,
        "mirror_locals": _mirror_locals,
        "phone_text": phone_text,
        "plan": plan,
        "plan_mirror": plan_mirror,
        "PhoneError": PhoneError,
        "stream_list": stream_list,
        "iter_file": lambda source, size: Phone().iter_file(source, size),
    }


def _layout(value: str) -> str:
    return "explorer" if value == "explorer" else "month"


def status() -> dict:
    root = tool_root()
    if root is None:
        return {"installed": False, "message": _MISSING}
    script = root / "ExplorerLayout.ps1"
    if not script.is_file():
        return {"installed": False, "message": _MISSING, "tool": str(root)}
    return {"installed": True, "message": "", "tool": str(root), "layouts": ["month", "explorer"]}


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


def _pictures_per_sec(pictures: int) -> float:
    with _lock:
        started = _job.get("startedAt")
    if isinstance(started, bool) or not isinstance(started, (int, float)):
        return 0.0
    elapsed = time.time() - float(started)
    if elapsed <= 0 or pictures <= 0:
        return 0.0
    return round(pictures / elapsed, 1)


def _roll_message(
    folder: str,
    pictures: int,
    folders: int,
    folder_found: int,
    *,
    comparing: bool,
    skip: int,
    will_copy: int,
    kept: int,
) -> str:
    where = folder or "Internal Storage"
    text = (
        f"Reading the camera roll. {where}. "
        f"{pictures:,} pictures in {folders:,} folders."
    )
    if folder_found:
        text += f" This folder has {folder_found:,} items so far."
    if comparing:
        text += " Checking this folder."
    elif pictures:
        text += (
            f" Compared {skip + will_copy + kept:,}:"
            f" {skip:,} already here, {will_copy:,} not here yet"
        )
        if kept:
            text += f", {kept:,} left alone"
        text += "."
    return text


class _RollProgress:
    """Counts pictures as Explorer lists them, and compares each one that arrives."""

    def __init__(self, ready: threading.Event, box: dict, action) -> None:
        self.pictures = 0
        self.folders: set[str] = set()
        self.current = ""
        self.folder_found = 0
        self.waiting_ms = 0
        self.pace: dict | None = None
        self.skip = 0
        self.will_copy = 0
        self.kept = 0
        self._ready = ready
        self._box = box
        self._action = action
        self._seen: set[str] = set()
        self._pending: list[tuple[str, int]] = []
        self._last = 0.0
        self._last_file = 0.0

    def on_row(self, row: dict) -> None:
        self._drain()
        reading = row.get("reading")
        if isinstance(reading, str) and "rel" not in row:
            self.current = reading or "Internal Storage"
            self.folders.add(self.current)
            if "found" in row:
                found = row.get("found")
                self.folder_found = found if isinstance(found, int) and not isinstance(found, bool) else 0
            waiting = row.get("waitingMs")
            if isinstance(waiting, int) and not isinstance(waiting, bool):
                if time.monotonic() - self._last_file < 0.5:
                    return
                self.waiting_ms = waiting
            if any(key in row for key in ("listMs", "sizeMs", "files")):
                pace = dict(self.pace or {})
                pace["folder"] = self.current
                for key in ("listMs", "sizeMs", "files"):
                    value = row.get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        pace[key] = value
                self.pace = pace
                self.waiting_ms = 0
            self._publish(force=("found" not in row or "listMs" in row or "sizeMs" in row or "waitingMs" in row))
            return
        rel = row.get("rel")
        size = row.get("size")
        if not isinstance(rel, str) or not rel or isinstance(size, bool) or not isinstance(size, int):
            return
        key = rel.replace("\\", "/").casefold()
        if key in self._seen:
            return
        self._seen.add(key)
        self.pictures += 1
        self.waiting_ms = 0
        self._last_file = time.monotonic()
        parent = str(Path(rel).parent).replace("\\", "/")
        if parent not in {"", "."}:
            self.folders.add(parent)
            self.current = parent
        if self._locals() is None:
            self._pending.append((rel, size))
        else:
            self._count(rel, size)
        self._publish(force=True)

    def flush(self) -> None:
        self._drain()
        self._publish(force=True)

    def _locals(self):
        if not self._ready.is_set():
            return None
        return self._box.get("locals")

    def _drain(self) -> None:
        locals_by_path = self._locals()
        if locals_by_path is None or not self._pending:
            return
        pending = self._pending
        self._pending = []
        for rel, size in pending:
            self._count(rel, size)

    def _count(self, rel: str, size: int) -> None:
        locals_by_path = self._locals()
        if locals_by_path is None:
            return
        action = self._action(rel, size, locals_by_path)
        if action == "skip":
            self.skip += 1
        elif action == "keep":
            self.kept += 1
        else:
            self.will_copy += 1

    def _publish(self, force: bool) -> None:
        now = time.monotonic()
        if not force and now - self._last < 0.2:
            return
        self._last = now
        comparing = self._locals() is None
        _set(
            current=self.current,
            onPhone=self.pictures,
            skip=self.skip,
            willCopy=self.will_copy,
            kept=self.kept,
            comparing=comparing,
            folderFound=self.folder_found,
            waitingMs=self.waiting_ms,
            updatedAt=time.time(),
            picturesPerSec=_pictures_per_sec(self.pictures),
            pace=dict(self.pace) if self.pace else None,
            message=_roll_message(
                self.current,
                self.pictures,
                len(self.folders),
                self.folder_found,
                comparing=comparing,
                skip=self.skip,
                will_copy=self.will_copy,
                kept=self.kept,
            ),
        )


def look(path: str, layout: str = "month") -> dict:
    """Start a Look. The dialog polls `/api/iphone` while the phone is still being read."""
    global _last_look
    layout = _layout(layout)
    _last_look = None
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
    _stop.clear()
    _set(
        phase="reading",
        running=True,
        path=str(dest),
        phone="",
        onPhone=0,
        skip=0,
        willCopy=0,
        copied=0,
        kept=0,
        current="",
        comparing=True,
        startedAt=time.time(),
        updatedAt=time.time(),
        folderFound=0,
        waitingMs=0,
        picturesPerSec=0,
        pace=None,
        layout=layout,
        rows=[],
        repeated=0,
        skipped=0,
        message=(
            "Reading the camera roll directly."
            if layout == "month"
            else _roll_message(
                "Internal Storage", 0, 0, 0,
                comparing=True, skip=0, will_copy=0, kept=0,
            )
        ),
        error="",
    )
    threading.Thread(
        target=_look_worker, args=(dest, layout), name="iphone-look", daemon=True
    ).start()
    return {"ok": True, **_snapshot()}


def _read_roll(api, dest: Path):
    """List the phone and compare each file with dest while the list is still running."""
    ready = threading.Event()
    box: dict = {}

    def scan() -> None:
        try:
            box["locals"] = api["mirror_locals"](dest)
        except Exception as exc:
            box["error"] = exc
        finally:
            ready.set()

    threading.Thread(target=scan, name="iphone-compare", daemon=True).start()
    progress = _RollProgress(ready, box, api["mirror_action"])
    try:
        listed = api["list_layout"](progress.on_row, _stop.is_set)
    finally:
        ready.wait(timeout=120)
    if box.get("error") is not None:
        raise box["error"]
    progress.flush()
    return listed


def _read_month(api):
    """List /DCIM over Apple's file channel and count each file as it arrives."""
    found = {"n": 0}

    def on_row(row: dict) -> None:
        if "path" not in row:
            phone = row.get("phone")
            if isinstance(phone, str) and phone.strip():
                _set(phone=phone.strip(), layout="month")
            return
        path = row.get("path")
        size = row.get("size")
        if not isinstance(path, str) or isinstance(size, bool) or not isinstance(size, int):
            return
        found["n"] += 1
        parent = str(Path(path).parent).replace("\\", "/")
        _set(
            onPhone=found["n"],
            current=parent,
            comparing=True,
            layout="month",
            message=f"Reading the camera roll. {parent}. {found['n']:,} pictures.",
        )

    return api["stream_list"](on_row, _stop.is_set)


def _publish_month(api, dest: Path, name: str, files) -> None:
    items = api["plan"](files, dest)
    skip = sum(1 for item in items if item.action == api["ACTION_SKIP"])
    will_copy = sum(1 for item in items if item.action == api["ACTION_COPY"])
    global _last_look
    _last_look = {
        "path": str(dest.resolve()),
        "name": name,
        "files": files,
        "repeated": 0,
        "skipped": 0,
        "layout": "month",
    }
    _set(
        running=False,
        phase="looked",
        phone=name,
        path=str(dest),
        onPhone=len(items),
        skip=skip,
        willCopy=will_copy,
        kept=0,
        repeated=0,
        skipped=0,
        rows=[],
        current="",
        comparing=False,
        layout="month",
        folderFound=0,
        waitingMs=0,
        updatedAt=time.time(),
        picturesPerSec=_pictures_per_sec(len(items)),
        message=(
            "Nothing was copied. Pictures go into month folders like 2026-10. "
            "A file already there is never replaced. "
            f"{skip:,} already here, {will_copy:,} not here yet."
        ),
        error="",
    )


def _look_worker(dest: Path, layout: str) -> None:
    root = tool_root()
    if root is None:
        _set(running=False, phase="error", error=_MISSING, message=_MISSING)
        return
    api = _load(root)
    phone_error = api["PhoneError"] if layout == "month" else api["ExplorerError"]
    try:
        if layout == "month":
            name, files = _read_month(api)
            _publish_month(api, dest, name, files)
            return
        name, files, repeated, skipped = _read_roll(api, dest)
    except phone_error as exc:
        text = str(exc)
        phase = "stopped" if text == "Look stopped." else "error"
        _set(running=False, phase=phase, error="" if phase == "stopped" else text, message=text)
        return
    _publish_look(api, dest, name, files, repeated, skipped)


def _publish_look(api, dest: Path, name: str, files, repeated: int, skipped: int) -> None:
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
    notes = ["Nothing was copied."]
    if repeated:
        notes.append(f"Explorer listed {repeated} pictures twice. Each was counted once.")
    if skipped:
        notes.append(f"Explorer had {skipped} items with no usable name. Those were skipped.")
    global _last_look
    _last_look = {
        "path": str(dest.resolve()),
        "name": name,
        "files": files,
        "repeated": repeated,
        "skipped": skipped,
        "layout": "explorer",
    }
    _set(
        running=False,
        phase="looked",
        phone=name,
        path=str(dest),
        onPhone=len(items),
        skip=skip,
        willCopy=will_copy,
        kept=kept,
        repeated=repeated,
        skipped=skipped,
        rows=rows,
        current="",
        comparing=False,
        folderFound=0,
        waitingMs=0,
        updatedAt=time.time(),
        picturesPerSec=_pictures_per_sec(len(items)),
        message=" ".join(notes),
        error="",
    )


def start_copy(path: str, layout: str = "month") -> dict:
    layout = _layout(layout)
    saved = None
    try:
        saved = _saved_look(_destination(path), layout)
    except ValueError:
        saved = None
    with _lock:
        if _job["running"]:
            return {"ok": False, "message": "A copy is already running."}
        if saved:
            _job.update(
                {
                    "phase": "copying",
                    "running": True,
                    "fromLook": True,
                    "copied": 0,
                    "current": "",
                    "comparing": False,
                    "startedAt": time.time(),
                    "updatedAt": time.time(),
                    "folderFound": 0,
                    "waitingMs": 0,
                    "pace": None,
                    "layout": layout,
                    "message": "Using the list from Look. Copying what is missing.",
                    "error": "",
                }
            )
        else:
            _job.update(
                {
                    "phase": "reading",
                    "running": True,
                    "path": path,
                    "phone": "",
                    "onPhone": 0,
                    "skip": 0,
                    "willCopy": 0,
                    "copied": 0,
                    "current": "",
                    "comparing": True,
                    "startedAt": time.time(),
                    "updatedAt": time.time(),
                    "folderFound": 0,
                    "waitingMs": 0,
                    "picturesPerSec": 0,
                    "pace": None,
                    "fromLook": False,
                    "layout": layout,
                    "kept": 0,
                    "message": "Reading the camera roll. Checking this folder.",
                    "error": "",
                }
            )
    _stop.clear()
    threading.Thread(
        target=_copy_worker, args=(path, layout), name="iphone-import", daemon=True
    ).start()
    return {"ok": True, **_snapshot()}


def stop_copy() -> dict:
    _stop.set()
    _set(message="Stopping after the current file.")
    return _snapshot()


def _copy_worker(path: str, layout: str) -> None:
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
    phone_error = api["PhoneError"] if layout == "month" else api["ExplorerError"]
    try:
        saved = _saved_look(dest, layout)
        if layout == "month":
            if saved:
                name = saved["name"]
                files = saved["files"]
            else:
                name, files = _read_month(api)
            repeated = 0
            skipped = 0
            items = api["plan"](files, dest)
        elif saved:
            name = saved["name"]
            files = saved["files"]
            repeated = saved["repeated"]
            skipped = saved["skipped"]
            items = api["plan_mirror"](files, dest)
        else:
            name, files, repeated, skipped = _read_roll(api, dest)
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
        if skipped:
            message = (
                f"Explorer had {skipped} items with no usable name. Those were skipped. "
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
            fromLook=saved is not None,
            message=("Using the list from Look. " if saved else "") + message,
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
                if layout == "month":
                    api["copy_item"](
                        dest,
                        item,
                        api["iter_file"](item.source_path, item.size),
                    )
                else:
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
