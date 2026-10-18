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
    "done": 0,
    "total": 0,
    "at": 0.0,
}


def note(
    phase: str,
    *,
    detail: str = "",
    file: str = "",
    done: int = 0,
    total: int = 0,
) -> None:
    with _lock:
        _state["phase"] = phase or "idle"
        _state["detail"] = detail or ""
        _state["file"] = file or ""
        _state["done"] = int(done or 0)
        _state["total"] = int(total or 0)
        _state["at"] = time.time()


def note_item(phase: str, detail: str, item: dict[str, Any] | None) -> None:
    name = ""
    if isinstance(item, dict):
        raw = item.get("filename") or item.get("name") or ""
        name = raw if type(raw) is str else ""
    note(phase, detail=detail, file=name)


def clear() -> None:
    note("idle")


def snapshot() -> dict[str, Any]:
    with _lock:
        data = dict(_state)
    data["ok"] = True
    data["at"] = round(float(data.get("at") or 0), 3)
    return data
