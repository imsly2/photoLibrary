"""Family install: Update tracks main, shortcut script, safe restart. Not an F-id."""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from library.restart import is_this_library_serve, listen_target, skip_restart
from library.update import PUBLIC_ARCHIVE, PUBLIC_HTTPS, overlay_zip_tree, pull_latest, rewrite_https
from tests.qa.s00 import PRODUCT_ROOT, Checks, assert_no_pillow_in_server
from tests.qa.s08 import write_result
from tests.qa.setup_portable import _read, ps51_encoding_safe


def _git(folder: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["GIT_AUTHOR_NAME"] = "Library Test"
    run_env["GIT_AUTHOR_EMAIL"] = "test@library.local"
    run_env["GIT_COMMITTER_NAME"] = "Library Test"
    run_env["GIT_COMMITTER_EMAIL"] = "test@library.local"
    if env:
        run_env.update(env)
    return subprocess.run(
        ["git", "-C", str(folder), *args],
        capture_output=True,
        text=True,
        env=run_env,
        check=True,
    )


def _init_pair(tmp: Path) -> dict[str, Path]:
    remote = tmp / "remote.git"
    work = tmp / "seed"
    app = tmp / "app"
    remote.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    work.mkdir()
    _git(work, ["init", "-b", "main"])
    _git(work, ["remote", "add", "origin", str(remote)])
    (work / "README.txt").write_text("one\n", encoding="utf-8")
    _git(work, ["add", "README.txt"])
    _git(work, ["commit", "-m", "first"])
    _git(work, ["push", "-u", "origin", "main"])
    subprocess.run(
        ["git", "clone", str(remote), str(app)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(app, ["checkout", "-b", "tip/feature"])
    (app / "README.txt").write_text("feature\n", encoding="utf-8")
    _git(app, ["add", "README.txt"])
    _git(app, ["commit", "-m", "feature work"])
    return {"remote": remote, "app": app}


def prove_update_main(checks: Checks, artifacts: Path) -> dict[str, Any]:
    tmp = artifacts / "git-pair"
    tmp.mkdir(parents=True, exist_ok=True)
    pair = _init_pair(tmp)
    app = pair["app"]
    before = _git(app, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    checks.check("isolated-starts-on-feature", before != "main", before)
    env_was = os.environ.pop("LIBRARY_UPDATE_BRANCH", None)
    try:
        result = pull_latest(str(app))
    finally:
        if env_was is not None:
            os.environ["LIBRARY_UPDATE_BRANCH"] = env_was
    after_branch = _git(app, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    record = {"before": before, "result": result, "after": after_branch}
    checks.check("update-ok", bool(result.get("ok")), json.dumps(result, default=str))
    checks.check("update-on-main", after_branch == "main", after_branch)
    checks.check(
        "update-branch-field",
        result.get("branch") == "main" or result.get("git_branch") == "main",
        json.dumps(result, default=str),
    )
    checks.check("update-has-sha", bool(result.get("git_sha") or result.get("revision")), json.dumps(result, default=str))
    checks.check(
        "update-message-names-main",
        "main" in str(result.get("message") or ""),
        str(result.get("message")),
    )

    _git(app, ["commit", "--allow-empty", "-m", "local-only"])
    seed = tmp / "seed"
    (seed / "README.txt").write_text("origin moved\n", encoding="utf-8")
    _git(seed, ["add", "README.txt"])
    _git(seed, ["commit", "-m", "origin-moved"])
    _git(seed, ["push", "origin", "main"])
    env_was = os.environ.pop("LIBRARY_UPDATE_BRANCH", None)
    try:
        diverged = pull_latest(str(app))
    finally:
        if env_was is not None:
            os.environ["LIBRARY_UPDATE_BRANCH"] = env_was
    record["diverged"] = diverged
    checks.check("diverged-not-ok", diverged.get("ok") is False, json.dumps(diverged, default=str))
    checks.check(
        "diverged-reason",
        diverged.get("reason") in {"diverged", "pull-failed"},
        json.dumps(diverged, default=str),
    )
    checks.check(
        "diverged-mentions-main",
        "main" in str(diverged.get("message") or "").lower(),
        str(diverged.get("message")),
    )
    still = _git(app, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    checks.check("diverged-stays-main", still == "main", still)
    return record


def prove_restart_guard(checks: Checks) -> dict[str, Any]:
    app = PRODUCT_ROOT
    serve = str(app / ".venv" / "Scripts" / "python.exe") + " -m library serve"
    other = "C:\\Python312\\python.exe -m http.server 8765"
    update = str(app / ".venv" / "Scripts" / "python.exe") + " -m library update"
    setup = str(app) + "\\python.exe -m library setup-geo"
    foreign = "D:\\otherApp\\.venv\\Scripts\\python.exe -m library serve"
    record = {
        "serve": is_this_library_serve(serve, app),
        "other": is_this_library_serve(other, app),
        "update": is_this_library_serve(update, app),
        "setup": is_this_library_serve(setup, app),
        "foreign": is_this_library_serve(foreign, app),
        "listen": listen_target(app / "library-data"),
        "skip": skip_restart(),
    }
    checks.check("matcher-this-serve", record["serve"] is True, serve)
    checks.check("matcher-rejects-http-server", record["other"] is False, other)
    checks.check("matcher-rejects-update", record["update"] is False, update)
    checks.check("matcher-rejects-setup", record["setup"] is False, setup)
    checks.check("matcher-rejects-other-app", record["foreign"] is False, foreign)
    host, port = record["listen"]
    checks.check("listen-host-loopback", host in {"127.0.0.1", "0.0.0.0"}, host)
    checks.check("listen-port-int", isinstance(port, int) and 1 <= port <= 65535, str(port))
    return record


def prove_zip_overlay(checks: Checks, artifacts: Path) -> dict[str, Any]:
    root = artifacts / "zip-app"
    incoming = artifacts / "zip-incoming" / "photoLibrary-main"
    incoming.mkdir(parents=True)
    (root / "library-data").mkdir(parents=True)
    (root / ".venv").mkdir(parents=True)
    (root / "library-data" / "keep.txt").write_text("catalog-secret\n", encoding="utf-8")
    (root / ".venv" / "keep.txt").write_text("venv-secret\n", encoding="utf-8")
    (root / "old.txt").write_text("old\n", encoding="utf-8")
    (incoming / "library-data").mkdir()
    (incoming / "library-data" / "keep.txt").write_text("SHOULD-NOT-WRITE\n", encoding="utf-8")
    (incoming / "README.txt").write_text("from-zip\n", encoding="utf-8")
    (incoming / "old.txt").write_text("new-old\n", encoding="utf-8")
    written = overlay_zip_tree(root, incoming)
    record = {
        "written": written,
        "catalog": (root / "library-data" / "keep.txt").read_text(encoding="utf-8"),
        "venv": (root / ".venv" / "keep.txt").read_text(encoding="utf-8"),
        "readme": (root / "README.txt").read_text(encoding="utf-8"),
        "old": (root / "old.txt").read_text(encoding="utf-8"),
    }
    checks.check("zip-preserves-library-data", record["catalog"] == "catalog-secret\n", record["catalog"])
    checks.check("zip-preserves-venv", record["venv"] == "venv-secret\n", record["venv"])
    checks.check("zip-writes-app-files", record["readme"] == "from-zip\n", record["readme"])
    checks.check("zip-overlays-non-data", record["old"] == "new-old\n", record["old"])

    zpath = artifacts / "main.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(incoming / "README.txt", "photoLibrary-main/README.txt")
        zf.write(incoming / "old.txt", "photoLibrary-main/old.txt")
    zip_app = artifacts / "zip-pull"
    zip_app.mkdir()
    (zip_app / "library-data").mkdir()
    (zip_app / "library-data" / "keep.txt").write_text("stay\n", encoding="utf-8")
    env_save = {key: os.environ.get(key) for key in ("LIBRARY_UPDATE_ARCHIVE", "LIBRARY_UPDATE_SHA", "LIBRARY_UPDATE_BRANCH")}
    os.environ["LIBRARY_UPDATE_ARCHIVE"] = zpath.resolve().as_uri()
    os.environ["LIBRARY_UPDATE_SHA"] = "abc1234dead"
    os.environ.pop("LIBRARY_UPDATE_BRANCH", None)
    try:
        result = pull_latest(str(zip_app))
    finally:
        for key, value in env_save.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    record["pull"] = result
    checks.check("zip-pull-ok", bool(result.get("ok")), json.dumps(result, default=str))
    checks.check("zip-pull-source", result.get("source") == "zip", json.dumps(result, default=str))
    checks.check("zip-pull-sha", (result.get("git_sha") or "").startswith("abc1234"), json.dumps(result, default=str))
    checks.check(
        "zip-pull-keeps-data",
        (zip_app / "library-data" / "keep.txt").read_text(encoding="utf-8") == "stay\n",
        "",
    )
    return record


def prove_no_github_login(checks: Checks) -> dict[str, Any]:
    names = (
        "library/update.py",
        "setup.ps1",
        "launch.ps1",
        "Update.bat",
        "Setup.bat",
        "create-shortcut.ps1",
        "CreateShortcut.bat",
    )
    texts = {name: _read(name) for name in names}
    joined = "\n".join(texts.values())
    checks.check("no-gh-exe", "gh.exe" not in joined and "gh auth" not in joined and "gh pr" not in joined, "")
    checks.check("public-https", PUBLIC_HTTPS.startswith("https://github.com/") and PUBLIC_HTTPS.endswith(".git"), PUBLIC_HTTPS)
    checks.check("public-archive", "archive/refs/heads/main.zip" in PUBLIC_ARCHIVE, PUBLIC_ARCHIVE)
    checks.check(
        "rewrite-ssh-to-https",
        rewrite_https("git@github.com:imsly2/photoLibrary.git") == PUBLIC_HTTPS,
        rewrite_https("git@github.com:imsly2/photoLibrary.git"),
    )
    checks.check(
        "rewrite-strips-token",
        rewrite_https("https://x-access-token:secret@github.com/imsly2/photoLibrary.git") == PUBLIC_HTTPS,
        "",
    )
    checks.check("git-disables-credential-helper", 'credential.helper=' in texts["library/update.py"], "")
    checks.check("setup-optional-git", "Git.Git" in texts["setup.ps1"] and "zip of main" in texts["setup.ps1"], "")
    checks.check("setup-says-no-github-account", "No GitHub account" in texts["setup.ps1"] or "no GitHub login" in texts["setup.ps1"], "")
    return {"https": PUBLIC_HTTPS, "archive": PUBLIC_ARCHIVE}


def prove_i18n_update(checks: Checks) -> dict[str, Any]:
    text = _read("library/web/assets/i18n.js")
    needed = (
        "updateAlready",
        "updateDone",
        "updateRestarting",
        "updateGitMissing",
        "updateNotGit",
        "updateFailed",
        "updateDiverged",
        "updateUnavailable",
        "updateNeedPublic",
        "familyHint",
        "updating",
    )
    missing = [key for key in needed if key not in text]
    checks.check("i18n-update-keys", missing == [], json.dumps(missing))
    checks.check("i18n-zh-restart", "正在重新打开图库" in text, "")
    js = _read("library/web/assets/library.js")
    checks.check("js-uses-i18n-update", "updateStatusText" in js and 't("updating")' in js, "")
    checks.check("js-family-hint", "familyHint" in js, "")
    return {"missing": missing}


def prove_scripts(checks: Checks) -> dict[str, Any]:
    files = {
        "CreateShortcut.bat": _read("CreateShortcut.bat"),
        "create-shortcut.ps1": _read("create-shortcut.ps1"),
        "Update.bat": _read("Update.bat"),
        "Launch.bat": _read("Launch.bat"),
        "launch.ps1": _read("launch.ps1"),
        "setup.ps1": _read("setup.ps1"),
    }
    for name, text in files.items():
        checks.check(f"{name}-ascii", all(ord(ch) < 128 for ch in text), name)
    ps51 = ps51_encoding_safe((PRODUCT_ROOT / "create-shortcut.ps1").read_bytes())
    checks.check("create-shortcut-ps51", bool(ps51.get("ok")), json.dumps(ps51))
    launch_ps51 = ps51_encoding_safe((PRODUCT_ROOT / "launch.ps1").read_bytes())
    checks.check("launch-ps51", bool(launch_ps51.get("ok")), json.dumps(launch_ps51))
    setup_ps51 = ps51_encoding_safe((PRODUCT_ROOT / "setup.ps1").read_bytes())
    checks.check("setup-ps51", bool(setup_ps51.get("ok")), json.dumps(setup_ps51))
    checks.check("shortcut-icon", (PRODUCT_ROOT / "library.ico").is_file() and (PRODUCT_ROOT / "library.ico").stat().st_size > 64)
    checks.check("update-bat-calls-launch", "launch.ps1" in files["Update.bat"] and "-Update" in files["Update.bat"], "")
    checks.check("launch-update-relaunch", "--relaunch" in files["launch.ps1"], "")
    return {"ps51": {"shortcut": ps51, "launch": launch_ps51, "setup": setup_ps51}}


def run_slice(root: Path, artifacts: Path) -> int:
    del root
    artifacts.mkdir(parents=True, exist_ok=True)
    checks = Checks()
    assert_no_pillow_in_server(checks)
    update = prove_update_main(checks, artifacts)
    restart = prove_restart_guard(checks)
    zip_record = prove_zip_overlay(checks, artifacts)
    no_login = prove_no_github_login(checks)
    i18n = prove_i18n_update(checks)
    scripts = prove_scripts(checks)
    (artifacts / "update-main.json").write_text(json.dumps(update, indent=2, default=str) + "\n", encoding="utf-8")
    (artifacts / "restart-guard.json").write_text(json.dumps(restart, indent=2) + "\n", encoding="utf-8")
    (artifacts / "zip-overlay.json").write_text(json.dumps(zip_record, indent=2, default=str) + "\n", encoding="utf-8")
    extra = {
        "update-main.json": str(artifacts / "update-main.json"),
        "restart-guard.json": str(artifacts / "restart-guard.json"),
        "zip-overlay.json": str(artifacts / "zip-overlay.json"),
    }
    code = write_result(
        "TASTE-INSTALL",
        "slice",
        checks,
        artifacts,
        ["python -m tests.qa slice TASTE-INSTALL"],
        extra,
    )
    print(json.dumps({"pass": checks.ok(), "assertions": checks.assertions, "i18n": i18n, "scripts": scripts, "noLogin": no_login}, indent=2, default=str), flush=True)
    return code
