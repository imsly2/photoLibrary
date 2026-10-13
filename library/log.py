"""Append-only server log lines."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def append_error(root: Path, request_path: str, error: str) -> None:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "server.log"
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line = f"{ts}\t{request_path}\t{error}\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
