"""Process-lifetime exclusive write lock, enforced by the OS."""

from __future__ import annotations

import os
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
