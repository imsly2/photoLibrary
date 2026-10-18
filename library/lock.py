"""Process-lifetime exclusive write lock, enforced by the OS."""

from __future__ import annotations

import os
import threading
from collections import deque
from pathlib import Path

from library.errors import fail


class WriteLock:
    """Non-blocking exclusive lock on ``write.lock``.

    Presence of a stale file is not ownership. The open handle + OS lock is.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "write.lock"
        self._fd: int | None = None

    def acquire(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR)
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                if os.path.getsize(self.path) == 0:
                    os.write(fd, b"0\n")
                    os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            raise fail("busy") from exc
        self._fd = fd

    def release(self) -> None:
        fd = self._fd
        if fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
            self._fd = None

    def __enter__(self) -> WriteLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class FairLock:
    """In-process mutex handed over in arrival order, foreground first.

    ``threading.Lock`` lets the thread that just released it take it straight
    back, so with several encoder threads a status request could wait through
    many holds. Here waiters queue in arrival order, and threads marked
    background (the encoders) get the lock only when no request or scan step
    is waiting. Blocking acquire only.
    """

    _thread = threading.local()

    @classmethod
    def mark_background(cls) -> None:
        """Every later acquire from this thread waits behind foreground ones."""
        cls._thread.background = True

    def __init__(self) -> None:
        self._turn = threading.Condition(threading.Lock())
        self._held = False
        self._lanes: tuple[deque, deque] = (deque(), deque())

    def _first(self) -> object | None:
        foreground, background = self._lanes
        return foreground[0] if foreground else (background[0] if background else None)

    def acquire(self) -> bool:
        lane = self._lanes[1 if getattr(self._thread, "background", False) else 0]
        ticket = object()
        with self._turn:
            lane.append(ticket)
            while self._held or self._first() is not ticket:
                self._turn.wait()
            lane.popleft()
            self._held = True
        return True

    def release(self) -> None:
        with self._turn:
            self._held = False
            self._turn.notify_all()

    def __enter__(self) -> FairLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
