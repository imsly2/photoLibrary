"""Pull the current git branch from the app folder. No command prompt."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from library.paths import APP_FOLDER
from library.version import attach_identity, checkout_identity


def app_folder():
    return APP_FOLDER


def _git_exe() -> str | None:
    return shutil.which("git")


def _run_git(args: list[str], timeout: float = 45.0) -> subprocess.CompletedProcess[str]:
    git = _git_exe()
    if not git:
        raise FileNotFoundError("git")
    return subprocess.run(
        [git, "-C", str(app_folder()), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _text(proc: subprocess.CompletedProcess[str]) -> str:
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if out and err:
        return out + "\n" + err
    return out or err


def update_status() -> dict[str, Any]:
    ident = checkout_identity()
    if ident.get("reason") == "not-a-git-copy":
        ident["message"] = "This Library folder is not a git copy, so it cannot pull an update."
    return ident


def pull_latest() -> dict[str, Any]:
    before = update_status()
    if not before.get("ok"):
        return attach_identity(
            {
                "ok": False,
                "alreadyCurrent": False,
                "reason": before.get("reason"),
                "branch": before.get("branch"),
                "revision": before.get("revision"),
                "message": before.get("message"),
            },
            before,
        )
    try:
        fetch_p = _run_git(["fetch", "--prune"], timeout=60)
        if fetch_p.returncode != 0:
            return attach_identity(
                {
                    "ok": False,
                    "alreadyCurrent": False,
                    "reason": "fetch-failed",
                    "branch": before.get("branch"),
                    "revision": before.get("revision"),
                    "message": "Could not check for a newer version. " + (_text(fetch_p) or "Fetch failed."),
                },
                before,
            )
        pull_p = _run_git(["pull", "--ff-only"], timeout=60)
    except subprocess.TimeoutExpired:
        return attach_identity(
            {
                "ok": False,
                "alreadyCurrent": False,
                "reason": "timeout",
                "branch": before.get("branch"),
                "revision": before.get("revision"),
                "message": "Update timed out. Check the network and try again.",
            },
            before,
        )
    except (FileNotFoundError, OSError):
        return attach_identity(
            {
                "ok": False,
                "alreadyCurrent": False,
                "reason": "git-missing",
                "branch": before.get("branch"),
                "revision": before.get("revision"),
                "message": "Git is not installed on this computer. Install Git, then try Update again.",
            },
            before,
        )
    after = update_status()
    if pull_p.returncode != 0:
        detail = _text(pull_p)
        return attach_identity(
            {
                "ok": False,
                "alreadyCurrent": False,
                "reason": "pull-failed",
                "branch": after.get("branch") or before.get("branch"),
                "revision": after.get("revision") or before.get("revision"),
                "message": "Could not pull the latest version without changing branches. "
                + (detail or "Fast-forward pull failed."),
            },
            after if after.get("ok") else before,
        )
    combined = _text(pull_p).lower()
    already = "already up to date" in combined or before.get("revision") == after.get("revision")
    revision = after.get("revision") or before.get("revision")
    branch = after.get("branch") or before.get("branch")
    if already:
        message = "Already up to date (" + str(revision) + " on " + str(branch) + ")."
    else:
        message = "Updated to " + str(revision) + " on " + str(branch) + "."
    return attach_identity(
        {
            "ok": True,
            "alreadyCurrent": already,
            "updated": not already,
            "reason": None,
            "branch": branch,
            "revision": revision,
            "message": message,
        },
        after if after.get("ok") else before,
    )
