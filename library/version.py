"""Live app-folder checkout identity. Short SHA is enough for Steve."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from library.paths import APP_FOLDER

REVISION_NAME = ".library-revision.json"


def app_folder() -> Path:
    return APP_FOLDER


def revision_path(folder: Path | None = None) -> Path:
    return (Path(folder) if folder is not None else app_folder()) / REVISION_NAME


def read_revision_stamp(folder: Path | None = None) -> dict[str, Any] | None:
    path = revision_path(folder)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    sha = str(data.get("git_sha") or data.get("revision") or "").strip()
    if not sha:
        return None
    branch = str(data.get("git_branch") or data.get("branch") or "main")
    return {
        "ok": True,
        "reason": None,
        "git_sha": sha,
        "git_branch": branch,
        "git_date": data.get("git_date"),
        "git_subject": data.get("git_subject") or "zip main",
        "revision": sha,
        "branch": branch,
        "dirty": False,
        "label": sha,
        "source": data.get("source") or "zip",
        "message": "This copy is " + sha + " on " + branch + ".",
    }


def write_revision_stamp(
    folder: Path,
    sha: str,
    *,
    branch: str = "main",
    source: str = "zip",
) -> dict[str, Any]:
    payload = {
        "git_sha": sha,
        "git_branch": branch,
        "revision": sha,
        "branch": branch,
        "source": source,
    }
    path = revision_path(folder)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    ident = read_revision_stamp(folder) or {}
    ident.update({"ok": True, "git_sha": sha, "git_branch": branch, "revision": sha, "branch": branch, "label": sha, "source": source})
    return ident


def _git_exe() -> str | None:
    return shutil.which("git")


def _run_git(folder: Path, args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    git = _git_exe()
    if not git:
        raise FileNotFoundError("git")
    return subprocess.run(
        [git, "-C", str(folder), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _blank(reason: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "reason": reason,
        "git_sha": None,
        "git_branch": None,
        "git_date": None,
        "git_subject": None,
        "revision": None,
        "branch": None,
        "dirty": False,
        "label": "local",
        "message": message,
    }


def checkout_identity(folder: Path | None = None) -> dict[str, Any]:
    """Read the live checkout. Safe when this copy is not git."""
    root = Path(folder) if folder is not None else app_folder()
    if not (root / ".git").exists() or not _git_exe():
        stamp = read_revision_stamp(root)
        if stamp:
            return stamp
        if not (root / ".git").exists():
            return _blank(
                "not-a-git-copy",
                "This Library folder is not a git copy. Update can still download a zip of main. No GitHub login.",
            )
        return _blank(
            "git-missing",
            "Git is not installed. Update can still download a zip of main. No GitHub login.",
        )
    try:
        sha_p = _run_git(root, ["rev-parse", "--short", "HEAD"])
        branch_p = _run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
        date_p = _run_git(root, ["log", "-1", "--format=%cs"])
        subject_p = _run_git(root, ["log", "-1", "--format=%s"])
        dirty_p = _run_git(root, ["status", "--porcelain"])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return _blank(
            "git-missing",
            "Git is not installed on this computer. Install Git, then try Update again.",
        )
    if sha_p.returncode != 0:
        return _blank("git-failed", "Could not read this Library copy's version.")
    git_sha = (sha_p.stdout or "").strip() or None
    git_branch = (branch_p.stdout or "").strip() or None
    git_date = (date_p.stdout or "").strip() or None
    git_subject = (subject_p.stdout or "").strip() or None
    dirty = bool((dirty_p.stdout or "").strip())
    if not git_sha:
        return _blank("git-failed", "Could not read this Library copy's version.")
    where = (" on " + git_branch) if git_branch else ""
    return {
        "ok": True,
        "reason": None,
        "git_sha": git_sha,
        "git_branch": git_branch,
        "git_date": git_date,
        "git_subject": git_subject,
        "revision": git_sha,
        "branch": git_branch,
        "dirty": dirty,
        "label": git_sha,
        "message": "This copy is " + git_sha + where + ".",
    }


def version_payload(folder: Path | None = None) -> dict[str, Any]:
    ident = checkout_identity(folder)
    return {
        "ok": ident["ok"],
        "git_sha": ident["git_sha"],
        "git_branch": ident["git_branch"],
        "git_date": ident["git_date"],
        "git_subject": ident["git_subject"],
        "label": ident["label"],
        "reason": ident["reason"],
    }


def attach_identity(payload: dict[str, Any], ident: dict[str, Any] | None = None) -> dict[str, Any]:
    """Copy git_* fields onto an update payload without dropping existing keys."""
    tip = ident if ident is not None else checkout_identity()
    payload["git_sha"] = tip.get("git_sha") or payload.get("revision")
    payload["git_branch"] = tip.get("git_branch") or payload.get("branch")
    payload["git_date"] = tip.get("git_date")
    payload["git_subject"] = tip.get("git_subject")
    if payload.get("revision") in {None, ""}:
        payload["revision"] = payload.get("git_sha")
    if payload.get("branch") in {None, ""}:
        payload["branch"] = payload.get("git_branch")
    return payload
