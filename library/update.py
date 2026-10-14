"""Pull a newer app folder when this copy is a git checkout."""

from __future__ import annotations

import os
import subprocess
from shutil import which
from typing import Any

from library.errors import fail
from library.paths import APP_FOLDER


def _revision(git: str) -> str:
    try:
        proc = subprocess.run(
            [git, "-C", str(APP_FOLDER), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def pull_latest() -> dict[str, Any]:
    if not (APP_FOLDER / ".git").exists():
        raise fail("update-unavailable")
    git = which("git")
    if not git:
        raise fail("update-unavailable")
    before = _revision(git)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.run(
            [git, "-C", str(APP_FOLDER), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise fail("io-error") from exc
    except OSError as exc:
        raise fail("io-error") from exc
    after = _revision(git) or before
    message = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "updated": False,
            "revision": after,
            "message": message or "pull-failed",
        }
    already = "already up to date" in message.lower() or "already up-to-date" in message.lower()
    updated = bool(after and before and after != before) or (bool(message) and not already)
    return {
        "ok": True,
        "updated": updated,
        "revision": after,
        "message": message or ("Updated" if updated else "Already up to date"),
    }
