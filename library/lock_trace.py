"""How long catalog reads hold the server lock. Never writes a log line.

Set LIBRARY_LOCK_TRACE to a file path to drop a JSON report after each sample.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

_guard = threading.Lock()
_samples: dict[str, list[float]] = {}
_MAX = 48


def note(route: str, seconds: float) -> None:
    with _guard:
        row = _samples.setdefault(route, [])
        row.append(seconds)
        if len(row) > _MAX:
            del row[: len(row) - _MAX]
        snapshot = {key: list(values) for key, values in _samples.items()}
    path = os.environ.get("LIBRARY_LOCK_TRACE", "")
    if not path or path in {"0", "1"}:
        return
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report_from(snapshot), handle, indent=2)
            handle.write("\n")
    except OSError:
        return


def report() -> dict[str, Any]:
    with _guard:
        snapshot = {key: list(values) for key, values in _samples.items()}
    return report_from(snapshot)


def report_from(samples: dict[str, list[float]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for route, values in samples.items():
        ordered = sorted(values)
        count = len(ordered)
        out[route] = {
            "n": count,
            "lastMs": round(values[-1] * 1000.0, 2),
            "p50Ms": round(ordered[count // 2] * 1000.0, 2),
            "p95Ms": round(ordered[min(count - 1, int(round((count - 1) * 0.95)))] * 1000.0, 2),
            "maxMs": round(ordered[-1] * 1000.0, 2),
        }
    return out


class Hold:
    """Acquire a lock and record how long this thread kept it."""

    def __init__(self, lock: threading.Lock, route: str) -> None:
        self._lock = lock
        self._route = route
        self._started = 0.0

    def __enter__(self) -> "Hold":
        self._lock.acquire()
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        held = time.perf_counter() - self._started
        self._lock.release()
        note(self._route, held)
