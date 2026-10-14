"""Taste-Windows diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from library.httpjson import request_json
from tests.qa.s00 import (
    PRODUCT_ROOT,
    Checks,
    assert_no_pillow_in_server,
    stop_owned,
)
from tests.qa.s01 import hash_tree
from tests.qa.s05 import pin_media_from_manifest, start_isolated
from tests.qa.s06 import set_settings, wait_level
from tests.qa.s08 import copy_rels, fresh_root, prepare_media, run_library, write_result
from tests.qa.s09 import start_owned, wait_catalog, wait_viewer_closed, wait_viewer_still


def _drain_stdout(proc: subprocess.Popen[str]) -> str:
    if proc.stdout is None:
        return ""
    try:
        os.set_blocking(proc.stdout.fileno(), False)
    except Exception:
        pass
    chunks: list[str] = []
    deadline = time.time() + 1.5
    while time.time() < deadline:
        try:
            data = proc.stdout.read()
        except Exception:
            break
        if data:
            chunks.append(data)
        else:
            time.sleep(0.05)
    return "".join(chunks)


def _abort_json_read(host: str, port: int, path: str) -> None:
    sock = socket.create_connection((host, port), timeout=2)
    try:
        sock.settimeout(2)
        req = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        sock.sendall(req.encode("ascii"))
        sock.recv(32)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def prove_add_progress(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {}
    server, url, port, pids = start_isolated(artifacts / "add-root")
    folder = copy_rels(media_src, artifacts / "add-media", ("a/IMG_1042.jpg", "b/no-exif.jpg"))
    slow = artifacts / "slow-copy"
    if slow.exists():
        shutil.rmtree(slow)
    slow.mkdir(parents=True)
    src_jpeg = media_src / "a" / "IMG_1042.jpg"
    shutil.copy2(src_jpeg, slow / "photo.jpg")
    big = slow / "big.jpg"
    big.write_bytes(src_jpeg.read_bytes() + os.urandom(12 * 1024 * 1024))
    pin_media_from_manifest(slow)
    try:
        t0 = time.monotonic()
        status, body = request_json(
            url.rstrip("/") + "/api/sources",
            method="POST",
            body={"path": str(slow), "mode": "copy-here"},
            timeout=30,
        )
        elapsed = time.monotonic() - t0
        commands.append("POST /api/sources copy-here slow")
        record["copyStatus"] = status
        record["copyElapsedSec"] = elapsed
        record["copyBodyScan"] = (body or {}).get("scan") if isinstance(body, dict) else None
        checks.check("copy-202", status == 202, str(status))
        mid_status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=2)
        running = (
            mid_status == 200
            and isinstance(sources, list)
            and any((src.get("scan") or {}).get("state") == "running" for src in sources)
        )
        record["sawRunningAfter202"] = running
        checks.check("copy-202-while-running", running or elapsed < 2.0, f"running={running} elapsed={elapsed:.3f}")
        idle_deadline = time.time() + 180
        while time.time() < idle_deadline:
            idle_status, idle_sources = request_json(url.rstrip("/") + "/api/sources", timeout=2)
            still = (
                idle_status == 200
                and isinstance(idle_sources, list)
                and any((src.get("scan") or {}).get("state") == "running" for src in idle_sources)
            )
            if not still:
                break
            time.sleep(0.1)
        serve_folder = artifacts / "slow-serve"
        if serve_folder.exists():
            shutil.rmtree(serve_folder)
        serve_folder.mkdir(parents=True)
        shutil.copy2(src_jpeg, serve_folder / "linked.jpg")
        (serve_folder / "linked-big.jpg").write_bytes(src_jpeg.read_bytes() + os.urandom(8 * 1024 * 1024))
        pin_media_from_manifest(serve_folder)
        t1 = time.monotonic()
        serve_status, serve_body = request_json(
            url.rstrip("/") + "/api/sources",
            method="POST",
            body={"path": str(serve_folder), "mode": "serve-from-there"},
            timeout=30,
        )
        serve_elapsed = time.monotonic() - t1
        commands.append("POST /api/sources serve-from-there")
        record["serveStatus"] = serve_status
        record["serveElapsedSec"] = serve_elapsed
        record["serveBodyScan"] = (serve_body or {}).get("scan") if isinstance(serve_body, dict) else None
        checks.check("serve-202", serve_status == 202, str(serve_status))
        serve_mid, serve_sources = request_json(url.rstrip("/") + "/api/sources", timeout=2)
        serve_running = (
            serve_mid == 200
            and isinstance(serve_sources, list)
            and any((src.get("scan") or {}).get("state") == "running" for src in serve_sources)
        )
        record["sawServeRunningAfter202"] = serve_running
        checks.check(
            "serve-202-while-running",
            serve_running or serve_elapsed < 2.0,
            f"running={serve_running} elapsed={serve_elapsed:.3f}",
        )
        picker_status, picker_body = request_json(
            url.rstrip("/") + "/api/pick-folder",
            method="POST",
            body={},
            timeout=5,
        )
        commands.append("POST /api/pick-folder")
        record["picker"] = {"status": picker_status, "body": picker_body}
        checks.check(
            "picker-unavailable",
            picker_status == 404 and picker_body == {"error": "picker-unavailable"},
            str(picker_body),
        )
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import-add", False, str(exc))
            return record
        checks.check("playwright-import-add", True)
        page_root = artifacts / "add-page-root"
        page_server, page_url, _pport, page_pids = start_isolated(page_root)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(page_url, wait_until="domcontentloaded")
                page.get_by_role("button", name="Add folder").click()
                page.wait_for_selector("dialog#add-folder[open]", timeout=5000)
                page.locator("#add-path").fill(str(folder))
                page.locator('input[name="add-mode"][value="serve-from-there"]').check()
                checks.check("typed-path-add-enabled", page.locator("#add-submit").is_enabled())
                page.locator("#add-submit").click()
                page.wait_for_function("() => !document.getElementById('add-folder').open", timeout=15000)
                checks.check("dialog-closed-on-202", True)
                page.wait_for_function(
                    """() => {
                      const el = document.getElementById('scan-status');
                      return el && !el.hidden && (el.textContent || '').length > 0;
                    }""",
                    timeout=15000,
                )
                checks.check("scan-status-visible", True, page.locator("#scan-status").inner_text())
                page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=60000)
                checks.check("typed-path-added-items", True)
                browser.close()
        except Exception as exc:
            checks.check("add-dialog-flow", False, str(exc))
        finally:
            stop_owned(page_server, extra_pids=page_pids)
        console_text = _drain_stdout(server)
        (artifacts / "scan-console.log").write_text(console_text, encoding="utf-8")
        record["scanConsoleChars"] = len(console_text)
        checks.check(
            "scan-console-progress",
            "added" in console_text or "skipped" in console_text or "photo.jpg" in console_text,
            console_text[:400],
        )
    finally:
        stop_owned(server, extra_pids=pids)
    (artifacts / "add-progress.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def prove_disconnect(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "disconnect-root")
    folder = copy_rels(media_src, artifacts / "disconnect-media", ("a/IMG_1042.jpg", "b/no-exif.jpg"))
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    commands.append("scan disconnect fixtures")
    checks.check("disconnect-scan-exit", scanned.returncode == 0, scanned.stderr)
    server, url, pids = start_owned(root)
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 8765)
    try:
        _abort_json_read(host, port, "/api/items")
        commands.append("abort GET /api/items")
        health_status, health = request_json(url.rstrip("/") + "/api/health", timeout=3)
        record["healthAfterAbort"] = {"status": health_status, "body": health}
        checks.check("health-after-abort", health_status == 200 and health == {"ok": True}, str(health))
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import-disconnect", False, str(exc))
            return record
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
            grid_before = page.locator("#grid .cell").count()
            stop_owned(server, extra_pids=pids)
            server = None
            pids = []
            page.wait_for_function(
                """() => {
                  const el = document.getElementById('disconnected-banner');
                  return el && !el.hidden && el.textContent === 'Library is not responding';
                }""",
                timeout=8000,
            )
            banner = page.locator("#disconnected-banner").inner_text()
            record["banner"] = banner
            checks.check("disconnected-banner-text", banner == "Library is not responding", banner)
            checks.check("grid-kept", page.locator("#grid .cell").count() == grid_before, str(grid_before))
            time.sleep(0.4)
            server, url, pids = start_owned(root)
            page.wait_for_function(
                """() => {
                  const el = document.getElementById('disconnected-banner');
                  return el && el.hidden;
                }""",
                timeout=8000,
            )
            checks.check("banner-cleared-on-health", True)
            browser.close()
    except Exception as exc:
        checks.check("disconnect-flow", False, str(exc))
    finally:
        if server is not None:
            stop_owned(server, extra_pids=pids)
    (artifacts / "disconnect.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def prove_live_origin(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "origin-root")
    folder = copy_rels(media_src, artifacts / "origin-media", ("a/IMG_1042.jpg",))
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    commands.append("scan live-origin fixtures")
    checks.check("origin-scan-exit", scanned.returncode == 0, scanned.stderr)
    server, url, pids = start_owned(root)
    parsed = urlparse(url)
    live_origin = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    record["liveOrigin"] = live_origin
    try:
        wait_catalog(url.rstrip("/"), ("IMG_1042.jpg",), timeout=90)
        set_settings(url, {"zoomLevel": "all"})
        page_js = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
        page_html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
        stale = "http://127.0.0.1:18765" in page_js or "http://127.0.0.1:18765" in page_html
        checks.check("no-stale-18765-link", not stale)
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import-origin", False, str(exc))
            return record
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto("about:blank")
            page.goto(url, wait_until="domcontentloaded")
            wait_level(page, "all")
            page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
            page.locator('[data-filename="IMG_1042.jpg"]').click()
            wait_viewer_still(page)
            after_open = page.evaluate("() => ({origin: location.origin, href: location.href})")
            record["afterOpen"] = after_open
            checks.check("open-stays-live-origin", after_open.get("origin") == live_origin, str(after_open))
            page.locator("#viewer-back").click()
            wait_viewer_closed(page)
            after_back = page.evaluate("() => ({origin: location.origin, href: location.href, viewerHidden: document.getElementById('viewer').hidden})")
            record["afterInAppBack"] = after_back
            checks.check("in-app-back-live-origin", after_back.get("origin") == live_origin, str(after_back))
            page.locator('[data-filename="IMG_1042.jpg"]').click()
            wait_viewer_still(page)
            page.go_back()
            page.wait_for_timeout(200)
            after_history = page.evaluate("() => ({origin: location.origin, href: location.href, viewerHidden: document.getElementById('viewer').hidden})")
            record["afterHistoryBack"] = after_history
            checks.check("history-back-live-origin", after_history.get("origin") == live_origin, str(after_history))
            checks.check("history-back-not-blank", page.url.startswith(live_origin), page.url)
            page.go_back()
            page.wait_for_timeout(200)
            trapped = page.evaluate("() => ({origin: location.origin, href: location.href})")
            record["afterSecondHistoryBack"] = trapped
            checks.check("second-back-stays-live", trapped.get("origin") == live_origin and page.url.startswith(live_origin), page.url)
            browser.close()
    except Exception as exc:
        checks.check("live-origin-flow", False, str(exc))
    finally:
        stop_owned(server, extra_pids=pids)
    (artifacts / "live-origin.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def prove_launcher(checks: Checks, artifacts: Path) -> None:
    bat = PRODUCT_ROOT / "Library.bat"
    checks.check("library-bat-exists", bat.is_file(), str(bat))
    if bat.is_file():
        text = bat.read_text(encoding="utf-8")
        checks.check("library-bat-invokes-launch-ps1", "launch.ps1" in text, text)
        checks.check("library-bat-visible-console", "WindowStyle Hidden" not in text and "-WindowStyle" not in text, text)
        checks.check("library-bat-pauses-on-error", "if errorlevel 1 pause" in text.lower(), text)
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--", "launch.sh"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
    )
    checks.check("launch-sh-unchanged", diff.returncode == 0 and diff.stdout == b"", diff.stdout.decode("utf-8", "replace"))


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {
        "add-progress.json": str(artifacts / "add-progress.json"),
        "disconnect.json": str(artifacts / "disconnect.json"),
        "live-origin.json": str(artifacts / "live-origin.json"),
        "scan-console.log": str(artifacts / "scan-console.log"),
    }
    try:
        media = prepare_media(artifacts)
        before = hash_tree(media)
        prove_add_progress(checks, artifacts, media, commands)
        prove_disconnect(checks, artifacts, media, commands)
        prove_live_origin(checks, artifacts, media, commands)
        prove_launcher(checks, artifacts)
        from tests.qa.launch_ps1_args import run_assertions
        arglist = run_assertions()
        (artifacts / "launch-arglist.json").write_text(
            json.dumps(arglist, indent=2) + "\n", encoding="utf-8"
        )
        for item in arglist["assertions"]:
            checks.check(str(item["name"]), bool(item["pass"]), str(item.get("detail") or ""))
        extra["launch-arglist.json"] = str(artifacts / "launch-arglist.json")
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == before)
    except Exception as exc:
        checks.check("taste-win-runner", False, str(exc))
    return write_result("TASTE-WIN", "slice", checks, artifacts, commands, extra)
