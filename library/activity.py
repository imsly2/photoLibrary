"""In-memory note of the file Library is working on. Not catalog state."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, Any] = {
    "phase": "idle",
    "detail": "",
    "file": "",
    "derivative": "",
    "done": 0,
    "total": 0,
    "at": 0.0,
}
_scan: dict[str, Any] = dict(_state, derivative="")


def note(
    phase: str,
    *,
    detail: str = "",
    file: str = "",
    done: int = 0,
    total: int = 0,
    derivative: str = "",
) -> None:
    with _lock:
        state = _scan if phase == "scan" else _state
        state.update(phase=phase or "idle", detail=detail or "", file=file or "",
                     done=int(done or 0), total=int(total or 0), at=time.time(),
                     derivative=derivative or "")


def note_item(phase: str, detail: str, item: dict[str, Any] | None, *, derivative: str = "") -> None:
    name = ""
    if isinstance(item, dict):
        raw = item.get("filename") or item.get("name") or ""
        name = raw if type(raw) is str else ""
    note(phase, detail=detail, file=name, derivative=derivative)


def clear(phase: str | None = None) -> None:
    if phase == "scan":
        with _lock:
            _scan.clear()
            _scan.update(phase="idle", detail="", file="", derivative="", done=0, total=0, at=0.0)
    else:
        note("idle")


def snapshot() -> dict[str, Any]:
    with _lock:
        data = dict(_state)
        data["scan"] = dict(_scan)
    for state in (data, data["scan"]):
        state["elapsedSeconds"] = round(max(0, time.time() - float(state.get("at") or time.time())), 1)
    data["ok"] = True
    data["at"] = round(float(data.get("at") or 0), 3)
    return data
