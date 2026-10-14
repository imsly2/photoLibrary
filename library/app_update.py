"""Family update status and pull. Pull always tracks main."""

from __future__ import annotations

from typing import Any

from library.paths import APP_FOLDER
from library.version import attach_identity, checkout_identity


def app_folder():
    return APP_FOLDER


def update_status() -> dict[str, Any]:
    ident = checkout_identity()
    if ident.get("reason") == "not-a-git-copy":
        ident["message"] = "This Library folder is not a git copy, so it cannot pull an update."
    ident.setdefault("code", ident.get("reason"))
    return ident


def pull_latest() -> dict[str, Any]:
    from library.update import pull_latest as pull_main

    try:
        return pull_main()
    except Exception:
        before = update_status()
        if not before.get("ok"):
            return attach_identity(
                {
                    "ok": False,
                    "alreadyCurrent": False,
                    "updated": False,
                    "reason": before.get("reason") or "update-unavailable",
                    "code": before.get("reason") or "update-unavailable",
                    "branch": before.get("branch"),
                    "revision": before.get("revision"),
                    "message": before.get("message"),
                },
                before,
            )
        raise
