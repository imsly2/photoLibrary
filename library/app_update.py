"""Pull the current git branch from the app folder. No command prompt."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


APP_FOLDER = Path(__file__).resolve().parents[1]


def app_folder() -> Path:
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
    if not (app_folder() / ".git").exists():
        return {
            "ok": False,
            "reason": "not-a-git-copy",
            "branch": None,
            "revision": None,
            "dirty": False,
            "message": "This Library folder is not a git copy, so it cannot pull an update.",
        }
    if not _git_exe():
        return {
            "ok": False,
            "reason": "git-missing",
            "branch": None,
            "revision": None,
            "dirty": False,
            "message": "Git is not installed on this computer. Install Git, then try Update again.",
        }
    try:
        branch_p = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
        rev_p = _run_git(["rev-parse", "--short", "HEAD"], timeout=10)
        dirty_p = _run_git(["status", "--porcelain"], timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {
            "ok": False,
            "reason": "git-missing",
            "branch": None,
            "revision": None,
            "dirty": False,
            "message": "Git is not installed on this computer. Install Git, then try Update again.",
        }
    if branch_p.returncode != 0 or rev_p.returncode != 0:
        return {
            "ok": False,
            "reason": "git-failed",
            "branch": None,
            "revision": None,
            "dirty": False,
            "message": "Could not read this Library copy's version.",
        }
    branch = (branch_p.stdout or "").strip()
    revision = (rev_p.stdout or "").strip()
    dirty = bool((dirty_p.stdout or "").strip())
    return {
        "ok": True,
        "reason": None,
        "branch": branch,
        "revision": revision,
        "dirty": dirty,
        "message": "This copy is " + revision + " on " + branch + ".",
    }


def pull_latest() -> dict[str, Any]:
    before = update_status()
    if not before.get("ok"):
        return {
            "ok": False,
            "alreadyCurrent": False,
            "reason": before.get("reason"),
            "branch": before.get("branch"),
            "revision": before.get("revision"),
            "message": before.get("message"),
        }
    try:
        fetch_p = _run_git(["fetch", "--prune"], timeout=60)
        if fetch_p.returncode != 0:
            return {
                "ok": False,
                "alreadyCurrent": False,
                "reason": "fetch-failed",
                "branch": before.get("branch"),
                "revision": before.get("revision"),
                "message": "Could not check for a newer version. " + (_text(fetch_p) or "Fetch failed."),
            }
        pull_p = _run_git(["pull", "--ff-only"], timeout=60)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "alreadyCurrent": False,
            "reason": "timeout",
            "branch": before.get("branch"),
            "revision": before.get("revision"),
            "message": "Update timed out. Check the network and try again.",
        }
    except (FileNotFoundError, OSError):
        return {
            "ok": False,
            "alreadyCurrent": False,
            "reason": "git-missing",
            "branch": before.get("branch"),
            "revision": before.get("revision"),
            "message": "Git is not installed on this computer. Install Git, then try Update again.",
        }
    after = update_status()
    if pull_p.returncode != 0:
        detail = _text(pull_p)
        return {
            "ok": False,
            "alreadyCurrent": False,
            "reason": "pull-failed",
            "branch": after.get("branch") or before.get("branch"),
            "revision": after.get("revision") or before.get("revision"),
            "message": "Could not pull the latest version without changing branches. "
            + (detail or "Fast-forward pull failed."),
        }
    combined = _text(pull_p).lower()
    already = "already up to date" in combined or before.get("revision") == after.get("revision")
    revision = after.get("revision") or before.get("revision")
    branch = after.get("branch") or before.get("branch")
    if already:
        message = "Already up to date (" + str(revision) + " on " + str(branch) + ")."
    else:
        message = "Updated to " + str(revision) + " on " + str(branch) + "."
    return {
        "ok": True,
        "alreadyCurrent": already,
        "reason": None,
        "branch": branch,
        "revision": revision,
        "message": message,
    }
