"""Visible checkout SHA next to Update Library. Not an F-id grade."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.version import checkout_identity, version_payload
from tests.qa.s00 import PRODUCT_ROOT, Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s05 import start_isolated
from tests.qa.s08 import write_result


def _live_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def prove_identity(checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    expected = _live_sha()
    ident = checkout_identity()
    payload = version_payload()
    record["liveSha"] = expected
    record["identity"] = ident
    record["payload"] = payload
    checks.check("identity-ok", ident.get("ok") is True, json.dumps(ident, default=str))
    checks.check("identity-sha", ident.get("git_sha") == expected, str(ident.get("git_sha")))
    checks.check("identity-label", ident.get("label") == expected, str(ident.get("label")))
    checks.check("payload-sha", payload.get("git_sha") == expected, str(payload.get("git_sha")))
    checks.check("payload-label", payload.get("label") == expected, str(payload.get("label")))

    with tempfile.TemporaryDirectory() as tmp:
        blank = checkout_identity(Path(tmp))
    record["fallback"] = blank
    checks.check("fallback-not-git", blank.get("reason") == "not-a-git-copy", str(blank.get("reason")))
    checks.check("fallback-label-local", blank.get("label") == "local", str(blank.get("label")))
    checks.check("fallback-sha-null", blank.get("git_sha") is None, str(blank.get("git_sha")))
    return record


def prove_http(checks: Checks, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    expected = _live_sha()
    server, url, port, owned = start_isolated(artifacts / "version-root")
    record["url"] = url
    record["port"] = port
    try:
        health_status, health = request_json(url.rstrip("/") + "/api/health", timeout=5)
        record["health"] = health
        checks.check(
            "health-liveness",
            health_status == 200 and health == {"ok": True},
            str(health),
        )

        ver_status, version = request_json(url.rstrip("/") + "/api/version", timeout=5)
        record["version"] = version
        checks.check("version-http", ver_status == 200 and isinstance(version, dict), str(version))
        checks.check(
            "version-sha",
            isinstance(version, dict) and version.get("git_sha") == expected,
            json.dumps(version, default=str),
        )

        get_status, update_get = request_json(url.rstrip("/") + "/api/update", timeout=10)
        record["updateGet"] = update_get
        checks.check("update-get", get_status == 200 and isinstance(update_get, dict), str(update_get))
        checks.check(
            "update-get-sha",
            isinstance(update_get, dict) and update_get.get("git_sha") == expected,
            json.dumps(update_get, default=str),
        )

        post_status, update_post = request_json(
            url.rstrip("/") + "/api/update",
            method="POST",
            body={},
            timeout=90,
        )
        record["updatePost"] = update_post
        checks.check("update-post", post_status == 200 and isinstance(update_post, dict), str(update_post))
        if isinstance(update_post, dict):
            checks.check(
                "update-post-sha",
                bool(update_post.get("git_sha")),
                json.dumps(update_post, default=str),
            )
            checks.check(
                "update-post-revision",
                update_post.get("revision") == update_post.get("git_sha"),
                json.dumps({"revision": update_post.get("revision"), "git_sha": update_post.get("git_sha")}),
            )
    finally:
        stop_owned(server, extra_pids=owned)
    return record


def prove_browser(checks: Checks, artifacts: Path, expected: str) -> dict[str, Any]:
    record: dict[str, Any] = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        checks.check("playwright-import", False, str(exc))
        return record
    checks.check("playwright-import", True)
    server, url, _port, owned = start_isolated(artifacts / "version-ui-root")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => { const el = document.getElementById('library-version'); return el && !el.hidden && (el.textContent || '').trim().length > 0; }",
                timeout=10000,
            )
            shown = page.evaluate(
                """() => {
                  const el = document.getElementById('library-version');
                  const btn = document.getElementById('update-library');
                  return {
                    text: el ? (el.textContent || '').trim() : '',
                    hidden: el ? el.hidden : true,
                    button: btn ? (btn.textContent || '').trim() : ''
                  };
                }"""
            )
            record["shown"] = shown
            checks.check(
                "header-sha",
                shown.get("text") == expected and shown.get("hidden") is False,
                json.dumps(shown),
            )
            checks.check("header-update-label", shown.get("button") == "Update Library", json.dumps(shown))

            with page.expect_response(
                lambda res: res.url.endswith("/api/update") and res.request.method == "POST"
            ) as update_info:
                page.locator("#update-library").click()
            update_res = update_info.value
            update_body = update_res.json()
            record["updateHttp"] = {"status": update_res.status, "body": update_body}
            checks.check(
                "update-button-sha",
                update_res.status == 200
                and isinstance(update_body, dict)
                and bool(update_body.get("git_sha")),
                json.dumps(record["updateHttp"], default=str),
            )
            page.wait_for_function(
                "() => { const el = document.getElementById('update-status'); return el && el.getAttribute('data-ok') != null; }",
                timeout=60000,
            )
            after = page.evaluate(
                """() => ({
                  version: ((document.getElementById('library-version') || {}).textContent || '').trim(),
                  status: ((document.getElementById('update-status') || {}).textContent || '').trim()
                })"""
            )
            record["afterUpdate"] = after
            tip = (update_body.get("git_sha") if isinstance(update_body, dict) else None) or expected
            checks.check("header-sha-after-update", after.get("version") == tip, json.dumps(after))
            page.screenshot(path=str(artifacts / "version-header.png"), full_page=False)
            browser.close()
    finally:
        stop_owned(server, extra_pids=owned)
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    commands = [
        "GET /api/health",
        "GET /api/version",
        "GET /api/update",
        "POST /api/update",
    ]
    identity = prove_identity(checks)
    expected = str(identity.get("liveSha") or _live_sha())
    http = prove_http(checks, artifacts)
    try:
        ui = prove_browser(checks, artifacts, expected)
    except Exception as exc:
        checks.check("browser-proof", False, str(exc))
        ui = {"error": str(exc)}
    extra = {
        "identity": json.dumps(identity, default=str),
        "http": json.dumps(http, default=str),
        "ui": json.dumps(ui, default=str),
    }
    if (artifacts / "version-header.png").is_file():
        extra["version-header.png"] = str(artifacts / "version-header.png")
    try:
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("no-pillow-server", False, str(exc))
    return write_result("TASTE-VERSION", "slice", checks, artifacts, commands, extra)
