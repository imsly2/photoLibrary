"""One plain-text timeline per Add folder or rescan, under logs/processing/."""

from __future__ import annotations

import re
import threading
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

INTERVAL_SEC = 2.0
MAX_SEC = 600.0
_VIDEO_SLOTS = ("poster", "proxy", "playback")

_guard = threading.Lock()
_run: "_Run | None" = None


class _Run:
    def __init__(self, root: Path, folder: str, encoders: int) -> None:
        stamp = datetime.now()
        name = re.sub(r'[<>:"/\\|?*]+', "_", Path(folder).name or "folder").strip() or "folder"
        self.path = root / "logs" / "processing" / f"{stamp:%Y%m%d-%H%M%S} {name}.log"
        self.t0 = time.monotonic()
        self.next_line = self.t0 + INTERVAL_SEC
        self.scanning = True
        self.read = Counter()
        self.done = Counter()
        self.window = Counter()
        self.encode_sec: dict[str, list[float]] = defaultdict(list)
        self.failed = 0
        self.wait_max = 0.0
        self.milestones: dict[str, float] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write(
            f"Library processing log - {folder}\n"
            f"Started {stamp:%Y-%m-%d %H:%M:%S}, {encoders} encoders at once\n\n"
            "   sec   read  +thumb +preview +video  waiting thumb/preview/video  lock wait max\n"
        )

    def since(self) -> float:
        return time.monotonic() - self.t0

    def mark(self, name: str) -> None:
        self.milestones.setdefault(name, round(self.since(), 1))

    def _write(self, text: str) -> None:
        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def line(self, waiting: dict[str, int]) -> None:
        video = sum(self.window[slot] for slot in _VIDEO_SLOTS)
        wait_video = sum(waiting.get(slot, 0) for slot in _VIDEO_SLOTS)
        waits = f"{waiting.get('thumb', 0)} / {waiting.get('preview', 0)} / {wait_video}"
        self._write(
            f"{self.since():6.1f} {sum(self.read.values()):6d} {self.window['thumb']:7d} "
            f"{self.window['preview']:8d} {video:6d}  {waits:<27} {self.wait_max * 1000:8.0f} ms\n"
        )
        self.window.clear()
        self.wait_max = 0.0

    def close(self, reason: str) -> None:
        self.mark("everything done" if reason == "idle" else f"stopped ({reason})")
        read = sum(self.read.values())
        rows = ["", "Milestones (seconds from start)"]
        for name, sec in sorted(self.milestones.items(), key=lambda row: row[1]):
            extra = ""
            if name == "every picture read" and sec > 0:
                extra = f"  ({read} files, {read / sec:.0f}/s; {self.read['skipped']} unchanged)"
            rows.append(f"  {name:<20} {sec:7.1f}{extra}")
        rows.append("")
        rows.append("Average encode (ffmpeg, per file)")
        for slot, values in sorted(self.encode_sec.items()):
            rows.append(f"  {slot:<9} {1000 * sum(values) / len(values):6.0f} ms  x{len(values)}")
        if self.failed:
            rows.append(f"  failed    {self.failed}")
        self._write("\n".join(rows) + "\n")


@contextmanager
def scan(root: Path, folder: str):
    """Wrap one Add folder or rescan; the log stays open until processing is idle."""
    global _run
    from library.renditions import encoder_count

    with _guard:
        if _run is not None:
            _run.close("another scan started")
        _run = _Run(root, folder, encoder_count())
        run = _run
    try:
        yield
    finally:
        with _guard:
            run.scanning = False
            run.mark("every picture read")


def note_read(kind: str) -> None:
    with _guard:
        if _run is not None:
            _run.read[kind] += 1


def note_slot(slot: str, outcome: str, encode_sec: float | None) -> None:
    with _guard:
        if _run is None:
            return
        if outcome in {"ready", "existing", "not-applicable"}:
            _run.done[slot] += 1
            _run.window[slot] += 1
            if slot in {"thumb", "preview"}:
                _run.mark(f"first {slot}")
        else:
            _run.failed += 1
        if outcome == "ready" and encode_sec is not None:
            _run.encode_sec[slot].append(encode_sec)


def note_lock_wait(seconds: float) -> None:
    run = _run
    if run is not None and seconds > run.wait_max:
        run.wait_max = seconds


def tick(root: Path) -> None:
    """Called often by the drain thread; writes at most one line per interval."""
    global _run
    run = _run
    if run is None:
        return
    from library.item_index import queued_counts

    waiting = queued_counts(root)
    with _guard:
        if _run is not run:
            return
        if not run.scanning and not waiting.get("thumb") and not waiting.get("poster"):
            run.mark("every thumb")
        if time.monotonic() < run.next_line:
            return
        run.next_line = time.monotonic() + INTERVAL_SEC
        run.line(waiting)
        if not run.scanning and not any(waiting.values()):
            run.close("idle")
            _run = None
        elif run.since() > MAX_SEC:
            run.close("10 minutes")
            _run = None
