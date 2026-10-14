"""Windows video + zoom taste. Diagnostic log, not an F-id grade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.qa.launch_ps1_args import run_assertions as launch_arglist_assertions
from tests.qa.s00 import Checks, assert_no_pillow_in_server
from tests.qa.s03 import find_item
from tests.qa.s06 import playing_cell_videos, set_settings, wait_level
from tests.qa.s08 import write_result
from tests.qa.s09 import (
    copy_s09_media,
    hash_tree,
    prepare_media,
    scan_library,
    start_owned,
    stop_owned,
    wait_catalog,
    wait_viewer_closed,
)


def collect_console(page: Any) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


def media_box(page: Any, selector: str) -> dict[str, float]:
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el) {
            return { left: 0, top: 0, width: 0, height: 0 };
          }
          const r = el.getBoundingClientRect();
          return { left: r.left, top: r.top, width: r.width, height: r.height };
        }""",
        selector,
    )


def box_delta(before: dict[str, float], after: dict[str, float]) -> float:
    return max(
        abs((after.get("left") or 0) - (before.get("left") or 0)),
        abs((after.get("top") or 0) - (before.get("top") or 0)),
        abs((after.get("width") or 0) - (before.get("width") or 0)),
        abs((after.get("height") or 0) - (before.get("height") or 0)),
    )


def video_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const video = document.getElementById('viewer-video');
          if (!video) {
            return {};
          }
          const src = video.currentSrc || video.getAttribute('src') || '';
          const r = video.getBoundingClientRect();
          return {
            src: src,
            paused: video.paused,
            hidden: video.hidden,
            currentTime: video.currentTime,
            duration: video.duration || 0,
            usingProxy: video.getAttribute('data-using-proxy') === '1',
            left: r.left,
            top: r.top,
            width: r.width,
            height: r.height,
          };
        }"""
    )


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="clip.mp4"]', timeout=30000)
    set_settings(url, {"zoomLevel": "all", "playProxies": "days-and-all"})
    wait_level(page, "all")
    page.wait_for_selector('[data-filename="clip.mp4"]', timeout=15000)

    sliders = page.evaluate(
        """() => {
          function labelFor(id) {
            const el = document.querySelector('label[for="' + id + '"]');
            return el ? (el.textContent || '').trim() : '';
          }
          return {
            levelLabel: labelFor('zoom-slider'),
            sizeLabel: labelFor('size-slider'),
            levelAria: (document.getElementById('zoom-slider') || {}).getAttribute('aria-label') || '',
            sizeAria: (document.getElementById('size-slider') || {}).getAttribute('aria-label') || '',
            viewerZoom: !!document.getElementById('viewer-zoom-slider'),
            gridHasViewerZoom: !!document.querySelector('#grid #viewer-zoom-slider, .levels #viewer-zoom-slider'),
            rangeCount: document.querySelectorAll('#zoom-slider, #size-slider, #viewer-zoom-slider').length,
          };
        }"""
    )
    record["sliders"] = sliders
    checks.check("level-label", sliders.get("levelLabel") == "Level", json.dumps(sliders))
    checks.check("size-label", sliders.get("sizeLabel") == "Size", json.dumps(sliders))
    checks.check("viewer-zoom-present", sliders.get("viewerZoom") is True, json.dumps(sliders))
    checks.check("no-viewer-zoom-on-grid", sliders.get("gridHasViewerZoom") is False, json.dumps(sliders))
    checks.check("three-intentional-sliders", sliders.get("rangeCount") == 3, json.dumps(sliders))

    page.locator("#size-slider").evaluate(
        """(el) => {
          el.value = '0';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.size === '72'",
        timeout=5000,
    )
    page.locator('.cell[data-slot="grid"][data-kind="video"]').first.hover()
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('.cell video')).some(function (v) {
          return !v.paused && !v.ended;
        })""",
        timeout=8000,
    )
    small = page.evaluate(
        """() => {
          const cell = document.querySelector('.cell[data-slot="grid"][data-kind="video"]');
          const video = cell ? cell.querySelector('video') : null;
          const scrub = cell ? cell.querySelector('.tile-scrub') : null;
          if (!cell || !video) {
            return { ok: false };
          }
          const cr = cell.getBoundingClientRect();
          const vr = video.getBoundingClientRect();
          return {
            ok: true,
            cell: { width: cr.width, height: cr.height },
            video: { width: vr.width, height: vr.height, left: vr.left, top: vr.top },
            fillDx: Math.abs(vr.width - cr.width),
            fillDy: Math.abs(vr.height - cr.height),
            playing: video.paused === false,
            hasScrub: !!scrub,
            size: document.getElementById('grid').dataset.size,
          };
        }"""
    )
    record["smallHover"] = small
    checks.check("hover-at-size-72", small.get("playing") is True and small.get("size") == "72", json.dumps(small))
    checks.check(
        "hover-fills-small-tile",
        (small.get("fillDx") or 99) <= 2 and (small.get("fillDy") or 99) <= 2,
        json.dumps(small),
    )
    checks.check("tile-scrub-present", small.get("hasScrub") is True, json.dumps(small))
    if small.get("hasScrub"):
        before_t = page.evaluate(
            "() => { const v = document.querySelector('.cell video'); return v ? v.currentTime : 0; }"
        )
        page.locator(".tile-scrub").evaluate(
            """(el) => {
              el.value = '600';
              el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        after_t = page.evaluate(
            "() => { const v = document.querySelector('.cell video'); return v ? v.currentTime : 0; }"
        )
        record["tileScrub"] = {"before": before_t, "after": after_t}
        checks.check("tile-scrub-seeks", after_t > before_t + 0.05, json.dumps(record["tileScrub"]))

    page.locator("#group-dates").click()
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.groupDates === 'off'",
        timeout=5000,
    )
    set_settings(url, {"zoomLevel": "years"})
    wait_level(page, "years")
    page.locator('.cell[data-slot="grid"][data-kind="video"]').first.hover()
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('.cell video')).some(function (v) {
          return !v.paused && !v.ended;
        })""",
        timeout=8000,
    )
    wall = playing_cell_videos(page)
    record["wallYearsHover"] = wall
    checks.check("wall-years-hover-plays", wall.get("playingCount") == 1, json.dumps(wall))
    page.locator("#group-dates").click()
    set_settings(url, {"zoomLevel": "all"})
    wait_level(page, "all")

    page.locator('#grid .cell[data-slot="grid"][data-filename="clip.mp4"]').click()
    page.wait_for_function(
        """() => {
          const viewer = document.getElementById('viewer');
          const video = document.getElementById('viewer-video');
          return viewer && !viewer.hidden && video && !video.hidden
            && (video.getAttribute('poster') || '').indexOf('which=poster') !== -1;
        }""",
        timeout=10000,
    )
    page.wait_for_function(
        """() => {
          const video = document.getElementById('viewer-video');
          const r = video.getBoundingClientRect();
          return r.width > 40 && r.height > 40;
        }""",
        timeout=8000,
    )
    before_play = media_box(page, "#viewer-video")
    record["beforePlay"] = before_play
    page.keyboard.press("Space")
    page.wait_for_function(
        """() => {
          const video = document.getElementById('viewer-video');
          if (!video) return false;
          const src = video.currentSrc || video.getAttribute('src') || '';
          return src.indexOf('which=proxy') !== -1 && video.paused === false;
        }""",
        timeout=15000,
    )
    proxy_state = video_state(page)
    record["proxyPlay"] = proxy_state
    after_play = {
        "left": proxy_state.get("left"),
        "top": proxy_state.get("top"),
        "width": proxy_state.get("width"),
        "height": proxy_state.get("height"),
    }
    play_jump = box_delta(before_play, after_play)
    record["playJumpPx"] = play_jump
    checks.check("play-starts-proxy", "which=proxy" in (proxy_state.get("src") or ""), json.dumps(proxy_state))
    checks.check("play-keeps-fit", play_jump <= 2, json.dumps({"before": before_play, "after": after_play, "delta": play_jump}))

    page.wait_for_timeout(400)
    later = video_state(page)
    record["afterSwap"] = later
    swap_box = {"left": later.get("left"), "top": later.get("top"), "width": later.get("width"), "height": later.get("height")}
    swap_jump = box_delta(before_play, swap_box)
    checks.check("swap-keeps-fit", swap_jump <= 2, json.dumps({"before": before_play, "after": swap_box, "delta": swap_jump}))
    if "which=original" in (later.get("src") or ""):
        checks.check("swap-keeps-time", (later.get("currentTime") or 0) > 0.05, json.dumps(later))
    else:
        checks.check("stayed-on-proxy-or-original", "which=proxy" in (later.get("src") or ""), json.dumps(later))

    scrub = page.evaluate(
        """() => {
          const wrap = document.getElementById('viewer-scrub-wrap');
          const bar = document.getElementById('viewer-scrub');
          return {
            present: !!wrap && !!bar,
            hidden: !wrap || wrap.hidden,
            value: bar ? bar.value : '',
          };
        }"""
    )
    record["viewerScrub"] = scrub
    checks.check("viewer-scrub-visible", scrub.get("present") is True and scrub.get("hidden") is False, json.dumps(scrub))
    page.locator("#viewer-scrub").evaluate(
        """(el) => {
          el.value = '700';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    sought = page.evaluate("() => document.getElementById('viewer-video').currentTime")
    record["viewerScrubSeek"] = sought
    checks.check("viewer-scrub-seeks", (sought or 0) > 0.4, str(sought))

    pre_wheel = media_box(page, "#viewer-video")
    page.mouse.move(pre_wheel["left"] + pre_wheel["width"] / 2, pre_wheel["top"] + pre_wheel["height"] / 2)
    page.mouse.wheel(0, -240)
    page.wait_for_function(
        """(fit) => {
          const video = document.getElementById('viewer-video');
          const r = video.getBoundingClientRect();
          return r.width > fit.width + 2 && r.height > fit.height + 2;
        }""",
        arg=pre_wheel,
        timeout=5000,
    )
    post_wheel = media_box(page, "#viewer-video")
    record["wheelZoom"] = {"before": pre_wheel, "after": post_wheel}
    checks.check(
        "plain-wheel-zooms",
        post_wheel["width"] > pre_wheel["width"] + 2 and post_wheel["height"] > pre_wheel["height"] + 2,
        json.dumps(record["wheelZoom"]),
    )

    page.screenshot(path=str(artifacts / "video-viewer.png"), full_page=False)
    page.locator("#viewer-back").click()
    wait_viewer_closed(page)
    page.screenshot(path=str(artifacts / "video-grid.png"), full_page=False)
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library scan <folder> --serve-from-there",
        "python -m tests.qa.launch_ps1_args",
    ]
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        isolated = artifacts / "library-root"
        from tests.qa.s08 import fresh_root

        fresh_root(isolated)
        folder = copy_s09_media(media_src, artifacts / "scan-media")
        scanned = scan_library(isolated, folder, commands)
        checks.check("scan-ok", scanned["proc"].returncode == 0, scanned["proc"].stderr[-200:])
        arglist = launch_arglist_assertions()
        (artifacts / "launch-arglist.json").write_text(json.dumps(arglist, indent=2) + "\n", encoding="utf-8")
        extra["launch-arglist.json"] = str(artifacts / "launch-arglist.json")
        for item in arglist["assertions"]:
            checks.check("launch-" + str(item["name"]), bool(item["pass"]), str(item.get("detail") or ""))
        server, url, pids = start_owned(isolated)
        try:
            items = wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "clip.mp4"))
            checks.check("has-clip", find_item(items, "clip.mp4") is not None)
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks)
                unexpected = [message for message in errors if "status of 400" not in message]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "video-zoom.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["video-zoom.json"] = str(artifacts / "video-zoom.json")
            extra["video-viewer.png"] = str(artifacts / "video-viewer.png")
            extra["video-grid.png"] = str(artifacts / "video-grid.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-video-runner", False, str(exc))
    return write_result("TASTE-VIDEO", "slice", checks, artifacts, commands, extra)
