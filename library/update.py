"""Update this app folder to main. No gh, no GitHub login."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from shutil import which
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from library.paths import APP_FOLDER
from library.version import (
    REVISION_NAME,
    attach_identity,
    checkout_identity,
    write_revision_stamp,
)

TRACK_ENV = "LIBRARY_UPDATE_BRANCH"
URL_ENV = "LIBRARY_UPDATE_URL"
ARCHIVE_ENV = "LIBRARY_UPDATE_ARCHIVE"
SHA_ENV = "LIBRARY_UPDATE_SHA"
DEFAULT_TRACK = "main"
PUBLIC_HTTPS = "https://github.com/imsly2/photoLibrary.git"
PUBLIC_ARCHIVE = "https://github.com/imsly2/photoLibrary/archive/refs/heads/main.zip"
PUBLIC_SHA_API = "https://api.github.com/repos/imsly2/photoLibrary/commits/main"
USER_AGENT = "Library-Update"
PRESERVE_TOP = frozenset({"library-data", ".venv", ".git", REVISION_NAME})


def tracked_branch() -> str:
    raw = (os.environ.get(TRACK_ENV) or "").strip()
    if raw and raw != "HEAD":
        return raw
    return DEFAULT_TRACK


def _git_exe() -> str | None:
    return which("git")


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    env["GIT_ASKPASS"] = ""
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_HOST", None)
    return env


def _run_git(folder: str, args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    git = _git_exe()
    if not git:
        raise FileNotFoundError("git")
    # credential.helper= turns off Git Credential Manager popups.
    cmd = [git, "-C", folder, "-c", "credential.helper=", "-c", "core.askPass="] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_git_env())


def _text(proc: subprocess.CompletedProcess[str]) -> str:
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if out and err:
        return out + "\n" + err
    return out or err


def _looks_like_auth(text: str) -> bool:
    low = (text or "").lower()
    return any(
        token in low
        for token in (
            "authentication failed",
            "could not read username",
            "terminal prompts disabled",
            "permission denied",
            "403",
            "401",
            "repository not found",
            "access denied",
        )
    )


def rewrite_https(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw
    if "github.com" in raw.lower():
        return PUBLIC_HTTPS
    return raw


def fetch_url(folder: str) -> str:
    override = (os.environ.get(URL_ENV) or "").strip()
    if override:
        return rewrite_https(override)
    if _git_exe() and (Path(folder) / ".git").exists():
        try:
            origin = _run_git(folder, ["remote", "get-url", "origin"], timeout=10)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            origin = None
        if origin is not None and origin.returncode == 0:
            url = rewrite_https((origin.stdout or "").strip())
            if url:
                return url
    return PUBLIC_HTTPS


def archive_url() -> str:
    return (os.environ.get(ARCHIVE_ENV) or "").strip() or PUBLIC_ARCHIVE


def _fail_payload(
    before: dict[str, Any],
    reason: str,
    message: str,
    *,
    tip: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ident = tip if tip is not None else before
    return attach_identity(
        {
            "ok": False,
            "updated": False,
            "alreadyCurrent": False,
            "reason": reason,
            "code": reason,
            "branch": ident.get("branch") or before.get("branch") or DEFAULT_TRACK,
            "revision": ident.get("revision") or before.get("revision"),
            "message": message,
            "source": ident.get("source") or before.get("source"),
        },
        ident,
    )


def _ok_payload(before: dict[str, Any], tip: dict[str, Any], *, already: bool, source: str) -> dict[str, Any]:
    revision = tip.get("git_sha") or before.get("git_sha")
    branch = tip.get("git_branch") or tip.get("branch") or DEFAULT_TRACK
    if already:
        message = "Already up to date (" + str(revision) + " on " + str(branch) + ")."
        code = "already-current"
    else:
        message = "Updated to " + str(revision) + " on " + str(branch) + "."
        code = "updated"
    return attach_identity(
        {
            "ok": True,
            "updated": not already,
            "alreadyCurrent": already,
            "reason": None,
            "code": code,
            "branch": branch,
            "revision": revision,
            "message": message,
            "source": source,
        },
        tip,
    )


def _checkout_track(folder: str, before: dict[str, Any], target: str) -> dict[str, Any] | None:
    current = (before.get("git_branch") or before.get("branch") or "").strip()
    if current == target:
        return None
    first = _run_git(folder, ["checkout", target])
    if first.returncode != 0:
        created = _run_git(folder, ["checkout", "-B", target, "FETCH_HEAD"])
        if created.returncode != 0:
            created = _run_git(folder, ["checkout", "-B", target])
        if created.returncode != 0:
            detail = _text(created) or _text(first) or "checkout failed"
            return _fail_payload(
                before,
                "diverged",
                "This copy is on "
                + (current or "another branch")
                + ", not "
                + target
                + ". Could not switch: "
                + detail
                + ". Steve: move or commit local changes, then Update again.",
            )
    after = checkout_identity(folder)
    now = (after.get("git_branch") or after.get("branch") or "").strip()
    if now != target:
        return _fail_payload(
            before,
            "diverged",
            "Update must stay on "
            + target
            + ". This copy is still on "
            + (now or current or "another branch")
            + ".",
            tip=after if after.get("ok") else before,
        )
    return None


def _http_get(url: str, timeout: float = 60.0) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=timeout) as resp:  # noqa: S310 -- fixed public GitHub or test file URL
        return resp.read()


def remote_main_sha() -> str | None:
    override = (os.environ.get(SHA_ENV) or "").strip()
    if override:
        return override[:12]
    try:
        raw = _http_get(PUBLIC_SHA_API, timeout=20)
        data = json.loads(raw.decode("utf-8"))
        sha = str(data.get("sha") or "")
        return sha[:12] if sha else None
    except (OSError, URLError, HTTPError, TimeoutError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _zip_inner_root(unpacked: Path) -> Path:
    children = [p for p in unpacked.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(children) == 1:
        return children[0]
    return unpacked


def overlay_zip_tree(app_folder: Path, incoming: Path) -> list[str]:
    """Copy incoming files over the app folder. Never touch library-data/."""
    written: list[str] = []
    for src in incoming.rglob("*"):
        rel = src.relative_to(incoming)
        parts = rel.parts
        if not parts or parts[0] in PRESERVE_TOP:
            continue
        dest = app_folder.joinpath(*parts)
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        written.append(rel.as_posix())
    return written


def apply_zip_bytes(app_folder: Path, blob: bytes, sha: str | None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="library-update-") as tmp:
        zpath = Path(tmp) / "main.zip"
        zpath.write_bytes(blob)
        unpacked = Path(tmp) / "unpacked"
        unpacked.mkdir()
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(unpacked)
        inner = _zip_inner_root(unpacked)
        written = overlay_zip_tree(app_folder, inner)
    short = (sha or "main")[:12]
    stamp = write_revision_stamp(app_folder, short, branch=DEFAULT_TRACK, source="zip")
    return {"written": written, "stamp": stamp}


def pull_via_zip(folder: str, before: dict[str, Any]) -> dict[str, Any]:
    tip_sha = remote_main_sha()
    current = (before.get("git_sha") or "").strip()
    if tip_sha and current and tip_sha == current:
        return _ok_payload(before, before, already=True, source="zip")
    url = archive_url()
    try:
        blob = _http_get(url, timeout=90)
    except HTTPError as exc:
        if exc.code in {401, 403, 404}:
            return _fail_payload(
                before,
                "need-public",
                "Could not download main as a zip. Family Update uses a public HTTPS "
                "address and never asks for a GitHub login. Steve: make "
                "imsly2/photoLibrary public, then try Update again.",
            )
        return _fail_payload(
            before,
            "fetch-failed",
            "Could not download the latest Library zip. Check the internet, then try Update again.",
        )
    except (OSError, URLError, TimeoutError) as exc:
        return _fail_payload(
            before,
            "fetch-failed",
            "Could not download the latest Library zip. Check the internet, then try Update again. "
            + str(exc),
        )
    try:
        apply_zip_bytes(Path(folder), blob, tip_sha)
    except (OSError, zipfile.BadZipFile) as exc:
        return _fail_payload(
            before,
            "pull-failed",
            "The downloaded zip could not be applied. library-data was not changed. " + str(exc),
        )
    after = checkout_identity(folder)
    if not after.get("ok") and tip_sha:
        after = write_revision_stamp(Path(folder), tip_sha, branch=DEFAULT_TRACK, source="zip")
    already = bool(current and (after.get("git_sha") == current))
    return _ok_payload(before, after if after.get("ok") else before, already=already, source="zip")


def pull_via_git(folder: str, before: dict[str, Any]) -> dict[str, Any]:
    target = tracked_branch()
    url = fetch_url(folder)
    try:
        fetch_p = _run_git(folder, ["fetch", "--prune", url, target], timeout=60)
        if fetch_p.returncode != 0:
            detail = _text(fetch_p)
            reason = "need-public" if _looks_like_auth(detail) else "fetch-failed"
            if reason == "need-public":
                message = (
                    "Could not fetch "
                    + target
                    + " over anonymous HTTPS. No GitHub account or gh tool is used. "
                    "Steve: make imsly2/photoLibrary public, then try Update again. "
                    + detail
                )
            else:
                message = (
                    "Could not check for a newer version on "
                    + target
                    + ". Check the internet, then try Update again. "
                    + (detail or "Fetch failed.")
                )
            return _fail_payload(before, reason, message)
        switched = _checkout_track(folder, before, target)
        if switched is not None:
            return switched
        merge_p = _run_git(folder, ["merge", "--ff-only", "FETCH_HEAD"], timeout=60)
    except subprocess.TimeoutExpired:
        return _fail_payload(
            before,
            "timeout",
            "Update timed out. Check the internet, then try Update again.",
        )
    except (FileNotFoundError, OSError):
        return _fail_payload(
            before,
            "git-missing",
            "Git is not installed. Update will try a zip download of main instead.",
        )
    after = checkout_identity(folder)
    tip = after if after.get("ok") else before
    if merge_p.returncode != 0:
        detail = _text(merge_p)
        return _fail_payload(
            before,
            "diverged" if "not possible to fast-forward" in detail.lower() or "diverged" in detail.lower() else "pull-failed",
            "Could not fast-forward "
            + target
            + ". Local commits would be rewritten. Steve: keep this folder on main only. "
            + (detail or "Fast-forward pull failed."),
            tip=tip,
        )
    revision = tip.get("git_sha") or before.get("git_sha")
    already = bool(before.get("git_sha") and revision == before.get("git_sha"))
    if not already:
        combined = _text(merge_p).lower()
        already = "already up to date" in combined or "already up-to-date" in combined
    return _ok_payload(before, tip, already=already, source="git")


def can_use_git(folder: str) -> bool:
    return bool(_git_exe()) and (Path(folder) / ".git").exists()


def pull_latest(folder: str | None = None) -> dict[str, Any]:
    """Track main. Prefer anonymous git HTTPS. Zip overlay if git is missing."""
    root = str(folder) if folder is not None else str(APP_FOLDER)
    before = checkout_identity(root)
    if can_use_git(root):
        return pull_via_git(root, before)
    return pull_via_zip(root, before)
