"""Pull a newer app folder when this copy is a git checkout."""

from __future__ import annotations

import os
import subprocess
from shutil import which
from typing import Any

from library.errors import fail
from library.paths import APP_FOLDER
from library.version import attach_identity, checkout_identity


def pull_latest() -> dict[str, Any]:
    before = checkout_identity()
    if not before.get("ok") or not before.get("git_sha"):
        raise fail("update-unavailable")
    git = which("git")
    if not git:
        raise fail("update-unavailable")
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
    after = checkout_identity()
    tip = after if after.get("ok") else before
    revision = tip.get("git_sha") or before.get("git_sha")
    message = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        return attach_identity(
            {
                "ok": False,
                "updated": False,
                "alreadyCurrent": False,
                "revision": revision,
                "message": message or "pull-failed",
            },
            tip,
        )
    already = "already up to date" in message.lower() or "already up-to-date" in message.lower()
    if not already and before.get("git_sha") and revision == before.get("git_sha"):
        already = True
    updated = bool(revision and before.get("git_sha") and revision != before.get("git_sha")) or (
        bool(message) and not already
    )
    return attach_identity(
        {
            "ok": True,
            "updated": updated,
            "alreadyCurrent": already,
            "revision": revision,
            "message": message or ("Updated" if updated else "Already up to date"),
        },
        tip,
    )
