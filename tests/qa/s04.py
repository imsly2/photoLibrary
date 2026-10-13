"""Slice S04 / Check F9 / Check F11 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    copy_committed_fixtures,
    find_free_port,
    run_library,
    start_server,
    stop_owned,
    wait_health,
    write_isolated_port,
)
from tests.qa.s01 import load_items, load_sources, parse_summary
from tests.qa.s02 import copy_rels, item_for_rel, items_by_id
from tests.qa.s03 import ensure_playwright, library_no_forbidden, original_hashes

TWO_YEAR = (
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/far.jpg",
    "b/created.jpg",
    "b/oriented.jpg",
)
F11_RELS = ("a/IMG_1042.jpg", "b/far.jpg", "b/no-exif.jpg")
LEVELS = ("years", "months", "days", "all")


def write_result(
    ident: str,
    kind: str,
    checks: Checks,
    artifacts: Path,
    commands: list[str],
    extra_paths: dict[str, str] | None = None,
) -> int:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest_hash = (
        sha256_file(COMMITTED_FIXTURES / "manifest.json")
        if (COMMITTED_FIXTURES / "manifest.json").is_file()
        else ""
    )
    paths = {
        "result.json": str(artifacts / "result.json"),
        "stdout.log": str(artifacts / "stdout.log"),
    }
    if extra_paths:
        paths.update(extra_paths)
    result = {
        kind: ident,
        "pass": checks.ok(),
        "assertions": checks.assertions,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version,
        },
        "fixtureManifestHash": manifest_hash,
        "revision": revision,
        "commands": commands,
        "artifactPaths": paths,
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def request_groups(base: str, level: str, extra: str = "") -> tuple[int, Any]:
    url = base.rstrip("/") + "/api/groups?level=" + level + extra
    return request_json(url, timeout=10)


def flatten_ids(groups: Any) -> list[str]:
    ids: list[str] = []
    if not isinstance(groups, list):
        return ids
    for group in groups:
        if isinstance(group, dict):
            for item_id in group.get("itemIds") or []:
                ids.append(item_id)
    return ids


def groups_ok_shape(groups: Any) -> bool:
    if not isinstance(groups, list):
        return False
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            return False
        if set(group.keys()) != {"key", "itemIds"}:
            return False
        if type(group["key"]) is not str or not isinstance(group["itemIds"], list):
            return False
        for item_id in group["itemIds"]:
            if type(item_id) is not str or item_id in seen:
                return False
            seen.add(item_id)
    return True


def wait_items(base: str, timeout: float = 30) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, listed = request_json(base.rstrip("/") + "/api/items", timeout=5)
        if status == 200 and isinstance(listed, list) and listed:
            last = listed
            return listed
        time.sleep(0.2)
    return last


def wait_jpeg_ready(base: str, item_id: str, timeout: float = 90) -> dict[str, Any] | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, listed = request_json(base.rstrip("/") + "/api/items", timeout=5)
        if status == 200 and isinstance(listed, list):
            item = next((row for row in listed if row.get("id") == item_id), None)
            rend = (item or {}).get("renditions") or {}
            st = rend.get("status") or {}
            if st.get("thumb") == "ready" and st.get("preview") == "ready":
                return item
        time.sleep(0.25)
    return None


def filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") for item in items]


def attach_page(page: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    console: list[dict[str, Any]] = []
    network: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    def on_console(msg: Any) -> None:
        console.append({"type": msg.type, "text": msg.text})

    def on_pageerror(err: Any) -> None:
        console.append({"type": "pageerror", "text": str(err)})

    def on_request(req: Any) -> None:
        network.append({"method": req.method, "url": req.url, "kind": "request"})

    def on_response(resp: Any) -> None:
        network.append({"method": resp.request.method, "url": resp.url, "status": resp.status, "kind": "response"})

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("request", on_request)
    page.on("response", on_response)
    return console, network, trace


def launch_browser(sync_playwright: Any):
    browser = None
    last = None
    for kwargs in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
        try:
            browser = sync_playwright.chromium.launch(**kwargs)
            break
        except Exception as exc:
            last = exc
    if browser is None:
        raise RuntimeError(f"chromium launch failed: {last}")
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    return browser, page


def set_zoom_slider(page: Any, value: str) -> None:
    page.evaluate(
        """(v) => {
            const el = document.getElementById('zoom-slider');
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        value,
    )


def wait_filename_visible(page: Any, filename: str, timeout: float = 180000) -> None:
    page.wait_for_function(
        """(name) => {
            const cell = document.querySelector('[data-filename="' + name + '"]');
            const img = cell && cell.querySelector('img');
            return !!(img && !img.hidden && img.complete && img.naturalWidth > 0);
        }""",
        arg=filename,
        timeout=timeout,
    )


def console_errors(console: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in console if row.get("type") in {"error", "pageerror"}]


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra_paths: dict[str, str] = {}
    server = None
    library_no_forbidden(checks)

    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    before_originals = original_hashes(media)

    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    port = find_free_port()
    write_isolated_port(isolated, port)
    url = f"http://127.0.0.1:{port}/"
    commands.append("python -m library serve")

    try:
        server = start_server(isolated)
        wait_health(url, server, timeout=20)

        missing_level = request_json(url.rstrip("/") + "/api/groups", timeout=5)
        checks.check(
            "groups-missing-level",
            missing_level[0] == 400 and missing_level[1] == {"error": "invalid-argument"},
            str(missing_level),
        )
        bad_level = request_json(url.rstrip("/") + "/api/groups?level=weeks", timeout=5)
        checks.check(
            "groups-bad-level",
            bad_level[0] == 400 and bad_level[1] == {"error": "invalid-argument"},
            str(bad_level),
        )

        console: list[dict[str, Any]] = []
        network: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        measurements: dict[str, Any] = {}
        try:
            sync_playwright = ensure_playwright()
            with sync_playwright() as p:
                browser, page = launch_browser(p)
                console, network, trace = attach_page(page)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                add_btn = page.locator("#add-folder")
                checks.check("add-folder-enabled", add_btn.is_enabled())
                empty_visible = page.locator("#empty").is_visible()
                checks.check("empty-library", empty_visible is True)

                add_btn.click()
                page.wait_for_selector("#add-dialog", timeout=5000)
                title = page.locator("#add-title").inner_text()
                checks.check("dialog-title", title == "Add folder", title)
                checks.check("add-submit-disabled-empty", page.locator("#add-submit").is_disabled())
                page.fill("#add-path", str(media))
                checks.check("add-submit-disabled-path-only", page.locator("#add-submit").is_disabled())
                page.keyboard.press("Escape")
                page.wait_for_function(
                    "() => !document.getElementById('add-dialog').open",
                    timeout=5000,
                )
                sources_status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=5)
                checks.check(
                    "esc-writes-nothing",
                    sources_status == 200 and sources == [],
                    str(sources),
                )
                trace.append({"action": "esc-add-dialog"})

                add_btn.click()
                page.fill("#add-path", str(media))
                page.locator("#add-cancel").click()
                page.wait_for_function(
                    "() => !document.getElementById('add-dialog').open",
                    timeout=5000,
                )
                sources_status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=5)
                checks.check("cancel-writes-nothing", sources_status == 200 and sources == [])
                trace.append({"action": "cancel-add-dialog"})

                add_btn.click()
                page.fill("#add-path", str(media))
                page.locator("text=Copy onto this drive").click()
                checks.check("add-submit-enabled-copy", page.locator("#add-submit").is_enabled())
                page.locator("#add-submit").click()
                page.wait_for_selector("#add-error:not([hidden])", timeout=20000)
                err_text = page.locator("#add-error").inner_text()
                checks.check("copy-here-error", err_text == "not-found", err_text)
                sources_status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=5)
                checks.check("copy-here-no-source", sources_status == 200 and sources == [])
                originals = isolated / "originals"
                copied = originals.exists() and any(originals.rglob("*"))
                checks.check("copy-here-no-files", copied is False)
                after_copy_attempt = original_hashes(media)
                checks.check("copy-here-originals-untouched", before_originals == after_copy_attempt)
                trace.append({"action": "copy-here", "error": err_text})
                page.keyboard.press("Escape")

                add_btn.click()
                page.fill("#add-path", str(media))
                page.locator("text=Serve from that folder").click()
                page.locator("#add-submit").click()
                commands.append("POST /api/sources serve-from-there")
                wait_filename_visible(page, "oriented.jpg", timeout=180000)
                status_text = page.locator("#status").inner_text()
                checks.check("status-has-added", "added" in status_text, status_text)
                checks.check("status-has-skipped", "skipped" in status_text, status_text)
                checks.check("status-has-errors", "errors" in status_text, status_text)
                empty_after = page.locator("#empty").is_visible()
                checks.check("empty-hidden-after-scan", empty_after is False)
                trace.append({"action": "serve-from-there", "status": status_text})

                page.wait_for_function(
                    "() => document.body.dataset.zoomLevel === 'years'",
                    timeout=5000,
                )
                years_png = artifacts / "years.png"
                page.screenshot(path=str(years_png), full_page=False)
                extra_paths["years.png"] = str(years_png)
                checks.check("years-png", years_png.is_file() and years_png.stat().st_size > 0)

                page.fill("#zoom-slider", "3")
                page.wait_for_function(
                    "() => document.body.dataset.zoomLevel === 'all'",
                    timeout=5000,
                )
                all_png = artifacts / "all.png"
                page.screenshot(path=str(all_png), full_page=False)
                extra_paths["all.png"] = str(all_png)
                checks.check("all-png", all_png.is_file() and all_png.stat().st_size > 0)
                all_cells = page.locator("#grid .cell").count()
                checks.check("all-has-cells", all_cells > 0, str(all_cells))

                scroll_before = page.evaluate("() => document.getElementById('library-main').scrollTop")
                page.evaluate("() => { const m = document.getElementById('library-main'); m.scrollTop = Math.min(m.scrollHeight, 240); }")
                scrolled = page.evaluate("() => document.getElementById('library-main').scrollTop")
                page.locator('[data-filename="oriented.jpg"]').first.click()
                page.wait_for_function(
                    """() => {
                        const img = document.getElementById('viewer-image');
                        const viewer = document.getElementById('viewer');
                        return !!(viewer && !viewer.hidden && img && img.complete && img.naturalWidth > 0);
                    }""",
                    timeout=30000,
                )
                src = page.locator("#viewer-image").get_attribute("src") or ""
                checks.check("viewer-preview", "which=preview" in src, src)
                viewer_png = artifacts / "viewer.png"
                page.screenshot(path=str(viewer_png), full_page=False)
                extra_paths["viewer.png"] = str(viewer_png)
                checks.check("viewer-png", viewer_png.is_file() and viewer_png.stat().st_size > 0)
                trace.append({"action": "open-viewer", "src": src})

                box = page.evaluate(
                    """() => {
                        const img = document.getElementById('viewer-image');
                        const r = img.getBoundingClientRect();
                        return {
                            left: r.left, top: r.top, width: r.width, height: r.height,
                            nw: img.naturalWidth, nh: img.naturalHeight
                        };
                    }"""
                )
                cx = box["left"] + box["width"] * 0.4
                cy = box["top"] + box["height"] * 0.4
                before_frac = page.evaluate(
                    """([x, y]) => {
                        const img = document.getElementById('viewer-image');
                        const r = img.getBoundingClientRect();
                        return { fx: (x - r.left) / r.width, fy: (y - r.top) / r.height };
                    }""",
                    [cx, cy],
                )
                page.mouse.move(cx, cy)
                page.keyboard.down("Control")
                page.mouse.wheel(0, -100)
                page.keyboard.up("Control")
                time.sleep(0.15)
                after_rect = page.evaluate(
                    """() => {
                        const img = document.getElementById('viewer-image');
                        const r = img.getBoundingClientRect();
                        return { left: r.left, top: r.top, width: r.width, height: r.height };
                    }"""
                )
                after_x = after_rect["left"] + before_frac["fx"] * after_rect["width"]
                after_y = after_rect["top"] + before_frac["fy"] * after_rect["height"]
                zoom_drift = ((after_x - cx) ** 2 + (after_y - cy) ** 2) ** 0.5
                measurements["zoomAnchorPx"] = zoom_drift
                measurements["zoomBefore"] = box
                measurements["zoomAfter"] = after_rect
                checks.check("viewer-zoom-anchor", zoom_drift <= 2, str(zoom_drift))
                checks.check(
                    "viewer-zoom-in",
                    after_rect["width"] > box["width"],
                    f"{box['width']} -> {after_rect['width']}",
                )
                trace.append({"action": "ctrl-wheel-viewer", "drift": zoom_drift})

                pan_before = page.evaluate(
                    """() => {
                        const r = document.getElementById('viewer-image').getBoundingClientRect();
                        return { left: r.left, top: r.top };
                    }"""
                )
                page.mouse.move(cx, cy)
                page.mouse.down(button="middle")
                page.mouse.move(cx + 40, cy + 24)
                page.mouse.up(button="middle")
                time.sleep(0.05)
                pan_after = page.evaluate(
                    """() => {
                        const r = document.getElementById('viewer-image').getBoundingClientRect();
                        return { left: r.left, top: r.top };
                    }"""
                )
                pan_dx = pan_after["left"] - pan_before["left"]
                pan_dy = pan_after["top"] - pan_before["top"]
                measurements["panDx"] = pan_dx
                measurements["panDy"] = pan_dy
                checks.check("viewer-pan-x", abs(pan_dx - 40) <= 2, str(pan_dx))
                checks.check("viewer-pan-y", abs(pan_dy - 24) <= 2, str(pan_dy))
                trace.append({"action": "middle-drag", "dx": pan_dx, "dy": pan_dy})

                items_status, item_rows = request_json(url.rstrip("/") + "/api/items", timeout=5)
                checks.check("items-200", items_status == 200 and isinstance(item_rows, list))
                ids = [row.get("id") for row in item_rows] if isinstance(item_rows, list) else []
                current_src = page.locator("#viewer-image").get_attribute("src") or ""
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(200)
                right_src = page.locator("#viewer-image").get_attribute("src") or ""
                if len(ids) >= 2:
                    checks.check("arrow-right-changes", right_src != current_src, right_src)
                    page.keyboard.press("ArrowLeft")
                    page.wait_for_timeout(200)
                    left_src = page.locator("#viewer-image").get_attribute("src") or ""
                    checks.check("arrow-left-restores", current_src.split("?")[0] in left_src or left_src == current_src, left_src)
                trace.append({"action": "arrows", "before": current_src, "right": right_src})

                page.keyboard.press("Escape")
                page.wait_for_function(
                    "() => document.getElementById('viewer') && document.getElementById('viewer').hidden === true",
                    timeout=5000,
                )
                scroll_after = page.evaluate("() => document.getElementById('library-main').scrollTop")
                zoom_after_esc = page.evaluate("() => document.body.dataset.zoomLevel")
                checks.check("esc-restores-scroll", abs(scroll_after - scrolled) <= 2, f"{scroll_after} vs {scrolled}")
                checks.check("esc-keeps-all-zoom", zoom_after_esc == "all", str(zoom_after_esc))
                measurements["scrollBefore"] = scroll_before
                measurements["scrollOpened"] = scrolled
                measurements["scrollAfterEsc"] = scroll_after
                trace.append({"action": "esc", "scroll": scroll_after, "zoom": zoom_after_esc})

                page.fill("#zoom-slider", "0")
                page.wait_for_function(
                    "() => document.body.dataset.zoomLevel === 'years'",
                    timeout=5000,
                )
                cell_box = page.locator('[data-filename="oriented.jpg"]').first.bounding_box()
                if cell_box:
                    hx = cell_box["x"] + cell_box["width"] / 2
                    hy = cell_box["y"] + cell_box["height"] / 2
                    page.mouse.move(hx, hy)
                    page.keyboard.down("Control")
                    for _ in range(5):
                        page.mouse.wheel(0, -80)
                    page.keyboard.up("Control")
                    page.wait_for_timeout(200)
                zoom_after_burst = page.evaluate("() => document.body.dataset.zoomLevel")
                checks.check("ctrl-wheel-one-stop", zoom_after_burst == "months", str(zoom_after_burst))
                settings_status, settings = request_json(url.rstrip("/") + "/api/settings", timeout=5)
                checks.check(
                    "zoom-saved",
                    settings_status == 200 and isinstance(settings, dict) and settings.get("zoomLevel") == "months",
                    str((settings or {}).get("zoomLevel") if isinstance(settings, dict) else settings),
                )
                still_visible = page.evaluate(
                    """() => {
                        const cell = document.querySelector('[data-filename="oriented.jpg"]');
                        if (!cell) return false;
                        const r = cell.getBoundingClientRect();
                        const m = document.getElementById('library-main').getBoundingClientRect();
                        return r.bottom > m.top && r.top < m.bottom;
                    }"""
                )
                checks.check("anchor-stays-in-view", still_visible is True)
                trace.append({"action": "ctrl-wheel-grid", "zoom": zoom_after_burst})

                page.select_option("#sort", "name")
                page.wait_for_timeout(400)
                page.select_option("#dir", "asc")
                page.wait_for_timeout(400)
                settings_status, settings = request_json(url.rstrip("/") + "/api/settings", timeout=5)
                checks.check(
                    "sort-saved",
                    settings_status == 200
                    and isinstance(settings, dict)
                    and settings.get("sort") == "name"
                    and settings.get("dir") == "asc",
                    str(settings),
                )
                name_status, name_items = request_json(
                    url.rstrip("/") + "/api/items?sort=name&dir=asc", timeout=5
                )
                names = filenames(name_items) if name_status == 200 and isinstance(name_items, list) else []
                folded = [n.casefold() for n in names if type(n) is str]
                checks.check("name-asc-order", folded == sorted(folded), str(names[:8]))
                trace.append({"action": "sort-name-asc"})

                errors = console_errors(console)
                checks.check("no-console-error", errors == [], json.dumps(errors)[:500])
                browser.close()
        except Exception as exc:
            checks.check("browser-slice", False, str(exc))

        dump_json(artifacts / "console.json", console)
        dump_json(artifacts / "network.json", network)
        dump_json(artifacts / "input-trace.json", trace)
        dump_json(artifacts / "measurements.json", measurements)
        extra_paths["console.json"] = str(artifacts / "console.json")
        extra_paths["network.json"] = str(artifacts / "network.json")
        extra_paths["input-trace.json"] = str(artifacts / "input-trace.json")
        extra_paths["measurements.json"] = str(artifacts / "measurements.json")

        listed_status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
        listed_ids = [row["id"] for row in listed] if listed_status == 200 and isinstance(listed, list) else []
        for level in LEVELS:
            status, payload = request_groups(url, level)
            dump_json(artifacts / f"groups-{level}.json", payload)
            extra_paths[f"groups-{level}.json"] = str(artifacts / f"groups-{level}.json")
            checks.check(f"groups-{level}-200", status == 200, str(status))
            checks.check(f"groups-{level}-shape", groups_ok_shape(payload), str(type(payload)))
            flat = flatten_ids(payload)
            checks.check(
                f"groups-{level}-ids-once",
                sorted(flat) == sorted(listed_ids) and len(flat) == len(set(flat)),
                f"n={len(flat)} items={len(listed_ids)}",
            )
            if isinstance(payload, list):
                for group in payload:
                    if level == "years":
                        checks.check(
                            f"years-key:{group.get('key')}",
                            type(group.get("key")) is str and len(group.get("key") or "") == 4,
                        )
                    elif level == "months":
                        checks.check(
                            f"months-key:{group.get('key')}",
                            type(group.get("key")) is str and len(group.get("key") or "") == 7,
                        )
                    else:
                        checks.check(
                            f"{level}-key:{group.get('key')}",
                            type(group.get("key")) is str and len(group.get("key") or "") == 10,
                        )
        days_status, days = request_groups(url, "days")
        all_status, all_groups = request_groups(url, "all")
        if days_status == 200 and all_status == 200 and isinstance(days, list) and isinstance(all_groups, list):
            checks.check(
                "days-all-same-keys",
                [g.get("key") for g in days] == [g.get("key") for g in all_groups],
            )

        loc_status, loc_desc = request_json(url.rstrip("/") + "/api/items?sort=location&dir=desc", timeout=5)
        loc_asc_status, loc_asc = request_json(url.rstrip("/") + "/api/items?sort=location&dir=asc", timeout=5)
        checks.check("location-sort-200", loc_status == 200 and loc_asc_status == 200)

        def category(item: dict[str, Any]) -> int:
            places = ((item.get("entities") or {}).get("places")) or []
            place = places[0] if places else None
            name = place.get("name") if isinstance(place, dict) else None
            lat = place.get("latitude") if isinstance(place, dict) else None
            lon = place.get("longitude") if isinstance(place, dict) else None
            if isinstance(place, dict) and type(name) is str and name:
                return 0
            if isinstance(place, dict) and lat is not None and lon is not None:
                return 1
            return 2

        if loc_status == 200 and isinstance(loc_desc, list) and loc_asc_status == 200 and isinstance(loc_asc, list):
            cats_desc = [category(item) for item in loc_desc]
            cats_asc = [category(item) for item in loc_asc]
            checks.check("location-desc-categories", cats_desc == sorted(cats_desc), str(cats_desc[:12]))
            checks.check("location-asc-categories", cats_asc == sorted(cats_asc), str(cats_asc[:12]))
            checks.check(
                "location-category-order-locked",
                cats_asc == sorted(cats_asc) and cats_desc == sorted(cats_desc),
            )

        after_originals = original_hashes(media)
        checks.check("originals-unchanged", before_originals == after_originals)
    finally:
        stop_owned(server)

    return write_result("S04", "slice", checks, artifacts, commands, extra_paths)


def run_check_f9(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra_paths: dict[str, str] = {}
    server = None
    library_no_forbidden(checks)

    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = artifacts / "two-year-media"
    if media.exists():
        shutil.rmtree(media)
    copy_rels(sandbox / "media", media, TWO_YEAR)

    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    port = find_free_port()
    write_isolated_port(isolated, port)
    scan = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=180)
    commands.append("python -m library scan <two-year> --serve-from-there")
    summary = parse_summary(scan.stdout) if scan.stdout.strip() else {}
    checks.check(
        "two-year-scan",
        scan.returncode == 0 and summary.get("added") == len(TWO_YEAR),
        f"exit={scan.returncode} {summary}",
    )

    url = f"http://127.0.0.1:{port}/"
    try:
        server = start_server(isolated)
        wait_health(url, server, timeout=20)
        commands.append("python -m library serve")
        sources = load_sources(isolated)
        items_disk = load_items(isolated)
        by_id = items_by_id(items_disk)
        source = sources[0] if sources else {}
        oriented = item_for_rel(source, by_id, "b/oriented.jpg")
        oriented_id = oriented["id"] if oriented else ""
        ready = wait_jpeg_ready(url, oriented_id) if oriented_id else None
        checks.check("oriented-ready", ready is not None)

        listed = wait_items(url)
        listed_ids = [row["id"] for row in listed]
        years_keys: list[str] = []
        for level in LEVELS:
            status, payload = request_groups(url, level)
            dump_json(artifacts / f"groups-{level}.json", payload)
            extra_paths[f"groups-{level}.json"] = str(artifacts / f"groups-{level}.json")
            checks.check(f"groups-{level}-200", status == 200, str(status))
            checks.check(f"groups-{level}-shape", groups_ok_shape(payload))
            flat = flatten_ids(payload)
            checks.check(
                f"groups-{level}-all-items",
                sorted(flat) == sorted(listed_ids),
                f"{len(flat)} vs {len(listed_ids)}",
            )
            if level == "years" and isinstance(payload, list):
                years_keys = [g.get("key") for g in payload]
                checks.check("years-two-groups", len(payload) == 2, str(years_keys))
            if level == "months" and isinstance(payload, list):
                months = [g.get("key") for g in payload]
                checks.check("months-unique", len(months) == len(set(months)), str(months))
                checks.check("months-has-items", all(g.get("itemIds") for g in payload))
        days_status, days = request_groups(url, "days")
        all_status, all_groups = request_groups(url, "all")
        if isinstance(days, list) and isinstance(all_groups, list):
            checks.check(
                "days-all-same-keys",
                [g.get("key") for g in days] == [g.get("key") for g in all_groups],
            )

        try:
            sync_playwright = ensure_playwright()
            with sync_playwright() as p:
                browser, page = launch_browser(p)
                console, network, trace = attach_page(page)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                wait_filename_visible(page, "oriented.jpg", timeout=60000)
                checks.check(
                    "default-years",
                    page.evaluate("() => document.body.dataset.zoomLevel") == "years",
                )
                page.screenshot(path=str(artifacts / "years.png"), full_page=False)
                extra_paths["years.png"] = str(artifacts / "years.png")
                page.fill("#zoom-slider", "3")
                page.wait_for_function("() => document.body.dataset.zoomLevel === 'all'", timeout=5000)
                page.screenshot(path=str(artifacts / "all.png"), full_page=False)
                extra_paths["all.png"] = str(artifacts / "all.png")
                all_count = page.locator("#grid .cell").count()
                checks.check("all-retains-items", all_count == len(listed_ids), f"{all_count} vs {len(listed_ids)}")
                page.fill("#zoom-slider", "0")
                page.wait_for_function("() => document.body.dataset.zoomLevel === 'years'", timeout=5000)
                box = page.locator('[data-filename="oriented.jpg"]').first.bounding_box()
                if box:
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.keyboard.down("Control")
                    page.mouse.wheel(0, -120)
                    page.keyboard.up("Control")
                    page.wait_for_timeout(250)
                zoom = page.evaluate("() => document.body.dataset.zoomLevel")
                checks.check("slider-ctrl-wheel-months", zoom == "months", str(zoom))
                settings_status, settings = request_json(url.rstrip("/") + "/api/settings", timeout=5)
                checks.check(
                    "zoom-setting-saved",
                    settings_status == 200 and isinstance(settings, dict) and settings.get("zoomLevel") == "months",
                    str(settings),
                )
                visible = page.evaluate(
                    """() => {
                        const cell = document.querySelector('[data-filename="oriented.jpg"]');
                        if (!cell) return false;
                        const r = cell.getBoundingClientRect();
                        const m = document.getElementById('library-main').getBoundingClientRect();
                        return r.bottom > m.top && r.top < m.bottom && r.right > m.left && r.left < m.right;
                    }"""
                )
                checks.check("f9-anchor-visible", visible is True)
                dump_json(artifacts / "console.json", console)
                dump_json(artifacts / "network.json", network)
                dump_json(artifacts / "input-trace.json", trace)
                extra_paths["console.json"] = str(artifacts / "console.json")
                extra_paths["network.json"] = str(artifacts / "network.json")
                extra_paths["input-trace.json"] = str(artifacts / "input-trace.json")
                errors = console_errors(console)
                checks.check("f9-no-console-error", errors == [], json.dumps(errors)[:400])
                browser.close()
        except Exception as exc:
            checks.check("f9-browser", False, str(exc))
    finally:
        stop_owned(server)

    return write_result("F9", "check", checks, artifacts, commands, extra_paths)


def run_check_f11(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra_paths: dict[str, str] = {}
    server = None
    library_no_forbidden(checks)

    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    src_no_exif = sandbox / "media" / "b" / "no-exif.jpg"
    before_mtime = src_no_exif.stat().st_mtime if src_no_exif.is_file() else None
    media = artifacts / "f11-media"
    if media.exists():
        shutil.rmtree(media)
    copy_rels(sandbox / "media", media, F11_RELS)
    copied_no_exif = media / "b" / "no-exif.jpg"
    checks.check(
        "no-exif-mtime-unedited",
        copied_no_exif.is_file() and before_mtime is not None and copied_no_exif.stat().st_mtime == before_mtime,
        str(copied_no_exif.stat().st_mtime if copied_no_exif.is_file() else None),
    )

    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    port = find_free_port()
    write_isolated_port(isolated, port)
    scan = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=120)
    commands.append("python -m library scan <f11> --serve-from-there")
    summary = parse_summary(scan.stdout) if scan.stdout.strip() else {}
    checks.check("f11-scan", scan.returncode == 0 and summary.get("added") == 3, str(summary))

    url = f"http://127.0.0.1:{port}/"
    try:
        server = start_server(isolated)
        wait_health(url, server, timeout=20)
        commands.append("python -m library serve")
        sources = load_sources(isolated)
        items_disk = load_items(isolated)
        source = sources[0] if sources else {}
        by_id = items_by_id(items_disk)
        img = item_for_rel(source, by_id, "a/IMG_1042.jpg")
        far = item_for_rel(source, by_id, "b/far.jpg")
        no_exif = item_for_rel(source, by_id, "b/no-exif.jpg")
        checks.check("img-present", img is not None)
        checks.check("far-present", far is not None)
        checks.check("no-exif-present", no_exif is not None)
        if no_exif:
            checks.check(
                "no-exif-mtime-source",
                no_exif.get("capturedAtSource") == "mtime",
                str(no_exif.get("capturedAtSource")),
            )
            checks.check(
                "no-exif-captured-at",
                no_exif.get("capturedAt") == "2022-02-03T04:05:06Z",
                str(no_exif.get("capturedAt")),
            )

        status, desc = request_json(url.rstrip("/") + "/api/items?sort=date&dir=desc", timeout=5)
        dump_json(artifacts / "items.json", desc)
        extra_paths["items.json"] = str(artifacts / "items.json")
        checks.check("date-desc-200", status == 200 and isinstance(desc, list) and len(desc) == 3, str(status))
        if isinstance(desc, list) and img and far and no_exif and len(desc) == 3:
            checks.check(
                "date-desc-order",
                [row.get("id") for row in desc] == [img["id"], far["id"], no_exif["id"]],
                filenames(desc),
            )
            checks.check("date-desc-first-2024", desc[0].get("id") == img["id"])

        status, asc = request_json(url.rstrip("/") + "/api/items?sort=date&dir=asc", timeout=5)
        if isinstance(asc, list) and img and far and no_exif and len(asc) == 3:
            checks.check(
                "date-asc-order",
                [row.get("id") for row in asc] == [no_exif["id"], far["id"], img["id"]],
                filenames(asc),
            )

        status, name_asc = request_json(url.rstrip("/") + "/api/items?sort=name&dir=asc", timeout=5)
        status_d, name_desc = request_json(url.rstrip("/") + "/api/items?sort=name&dir=desc", timeout=5)
        if isinstance(name_asc, list) and img and far and no_exif:
            checks.check(
                "name-asc-order",
                [row.get("id") for row in name_asc] == [far["id"], img["id"], no_exif["id"]],
                filenames(name_asc),
            )
        if isinstance(name_desc, list) and img and far and no_exif:
            checks.check(
                "name-desc-order",
                [row.get("id") for row in name_desc] == [no_exif["id"], img["id"], far["id"]],
                filenames(name_desc),
            )

        loc_asc_s, loc_asc = request_json(url.rstrip("/") + "/api/items?sort=location&dir=asc", timeout=5)
        loc_desc_s, loc_desc = request_json(url.rstrip("/") + "/api/items?sort=location&dir=desc", timeout=5)
        if isinstance(loc_asc, list) and img and far and no_exif:
            checks.check(
                "location-asc-order",
                [row.get("id") for row in loc_asc] == [img["id"], far["id"], no_exif["id"]],
                filenames(loc_asc),
            )
            labels = []
            for row in loc_asc:
                places = ((row.get("entities") or {}).get("places")) or []
                place = places[0] if places else None
                if place and place.get("name"):
                    labels.append(place["name"])
                elif place and place.get("latitude") is not None:
                    labels.append(f"{place['latitude']:.2f},{place['longitude']:.2f}")
                else:
                    labels.append("No location")
            checks.check("location-last-no-location", labels[-1] == "No location", str(labels))
            checks.check("location-gps-before-none", labels.index("No location") == 2, str(labels))
        if isinstance(loc_desc, list) and img and far and no_exif:
            checks.check(
                "location-desc-order",
                [row.get("id") for row in loc_desc] == [far["id"], img["id"], no_exif["id"]],
                filenames(loc_desc),
            )
            checks.check(
                "location-desc-still-no-location-last",
                loc_desc[-1].get("id") == no_exif["id"],
            )

        loc_groups_s, loc_groups = request_groups(url, "years", "&sort=location&dir=desc")
        date_groups_s, date_groups = request_groups(url, "years", "&sort=date&dir=desc")
        if isinstance(loc_groups, list) and isinstance(date_groups, list):
            loc_keys = {g.get("key") for g in loc_groups}
            date_keys = {g.get("key") for g in date_groups}
            checks.check("calendar-keys-stable", loc_keys == date_keys, f"{loc_keys} vs {date_keys}")

        img_id = img["id"] if img else ""
        ready = wait_jpeg_ready(url, img_id) if img_id else None
        checks.check("f11-thumb-ready", ready is not None)
        try:
            sync_playwright = ensure_playwright()
            with sync_playwright() as p:
                browser, page = launch_browser(p)
                console, network, trace = attach_page(page)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                wait_filename_visible(page, "IMG_1042.jpg", timeout=60000)
                page.select_option("#sort", "location")
                page.select_option("#dir", "desc")
                page.wait_for_timeout(500)
                settings_status, settings = request_json(url.rstrip("/") + "/api/settings", timeout=5)
                checks.check(
                    "toolbar-writes-sort",
                    settings_status == 200
                    and isinstance(settings, dict)
                    and settings.get("sort") == "location"
                    and settings.get("dir") == "desc",
                    str(settings),
                )
                dump_json(artifacts / "console.json", console)
                dump_json(artifacts / "network.json", network)
                dump_json(artifacts / "input-trace.json", trace)
                extra_paths["console.json"] = str(artifacts / "console.json")
                extra_paths["network.json"] = str(artifacts / "network.json")
                extra_paths["input-trace.json"] = str(artifacts / "input-trace.json")
                errors = console_errors(console)
                checks.check("f11-no-console-error", errors == [], json.dumps(errors)[:400])
                browser.close()
        except Exception as exc:
            checks.check("f11-browser", False, str(exc))
    finally:
        stop_owned(server)

    return write_result("F11", "check", checks, artifacts, commands, extra_paths)
