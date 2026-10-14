"""Windows video + zoom taste. Diagnostic log, not an F-id grade."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.launch_ps1_args import run_assertions as launch_arglist_assertions
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree
from tests.qa.s03 import find_item
from tests.qa.s06 import (
    copy_rels,
    playing_cell_videos,
    prepare_media,
    set_settings,
    start_owned,
    wait_level,
)
from tests.qa.s08 import fresh_root, run_library, write_result

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "a/clip.mp4",
)


def wait_catalog(base: str, names: tuple[str, ...] | list[str], timeout: float = 90) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            have = {item.get("filename") for item in payload}
            if not all(name in have for name in names):
                time.sleep(0.25)
                continue
            ready = True
            for name in names:
                item = find_item(payload, name)
                if item is None:
                    ready = False
                    break
                rend = ((item.get("renditions") or {}).get("status") or {})
                if item.get("kind") == "video":
                    if rend.get("poster") != "ready" or rend.get("proxy") != "ready":
                        ready = False
                        break
                elif rend.get("thumb") != "ready" and rend.get("preview") != "ready":
                    ready = False
                    break
            if ready:
                return payload
        time.sleep(0.25)
    raise RuntimeError("catalog timeout " + json.dumps([item.get("filename") for item in last]))


def wait_viewer_closed(page: Any) -> None:
    page.wait_for_function(
        "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
        timeout=8000,
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
    set_settings(url, {"zoomLevel": "years", "playProxies": "days-and-all"})
    wait_level(page, "years")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'years'",
        timeout=5000,
    )
    page.locator('.cell[data-slot="grid"][data-kind="video"]').first.hover()
    page.wait_for_timeout(600)
    years_dated = playing_cell_videos(page)
    record["datedYearsHover"] = years_dated
    checks.check(
        "dated-years-stay-still",
        years_dated.get("playingCount") == 0 and years_dated.get("videoCount") == 0,
        json.dumps(years_dated),
    )
    set_settings(url, {"zoomLevel": "all", "playProxies": "days-and-all"})
    wait_level(page, "all")
    page.wait_for_selector('[data-filename="clip.mp4"]', timeout=15000)

    sliders = page.evaluate(
        """() => {
          function labelFor(id) {
            const el = document.querySelector('label[for="' + id + '"]');
            return el ? (el.textContent || '').trim() : '';
          }
          const date = document.getElementById('date-group');
          const options = date
            ? Array.from(date.options).map(function (opt) { return opt.value; })
            : [];
          return {
            hasLevelSlider: !!document.getElementById('zoom-slider'),
            sizeLabel: labelFor('size-slider'),
            sizeAria: (document.getElementById('size-slider') || {}).getAttribute('aria-label') || '',
            sizeMax: (document.getElementById('size-slider') || {}).max || '',
            dateGroup: !!date,
            dateOptions: options,
            viewerZoom: !!document.getElementById('viewer-zoom-slider'),
            viewerZoomPct: !!document.getElementById('viewer-zoom-pct'),
            zoomInBottom: !!document.querySelector('#viewer-bottom #viewer-zoom-slider'),
            gridHasViewerZoom: !!document.querySelector('#grid #viewer-zoom-slider, .levels #viewer-zoom-slider'),
            rangeCount: document.querySelectorAll('#size-slider, #viewer-zoom-slider').length,
          };
        }"""
    )
    record["sliders"] = sliders
    checks.check("no-level-slider", sliders.get("hasLevelSlider") is False, json.dumps(sliders))
    checks.check("size-label", sliders.get("sizeLabel") == "Size", json.dumps(sliders))
    checks.check("size-has-eight-stops", sliders.get("sizeMax") == "7", json.dumps(sliders))
    checks.check("date-group-present", sliders.get("dateGroup") is True, json.dumps(sliders))
    checks.check(
        "date-group-modes",
        sliders.get("dateOptions") == ["years", "months", "days", "off"],
        json.dumps(sliders),
    )
    checks.check("viewer-zoom-present", sliders.get("viewerZoom") is True, json.dumps(sliders))
    checks.check("viewer-zoom-pct-present", sliders.get("viewerZoomPct") is True, json.dumps(sliders))
    checks.check("viewer-zoom-not-in-bottom", sliders.get("zoomInBottom") is False, json.dumps(sliders))
    checks.check("no-viewer-zoom-on-grid", sliders.get("gridHasViewerZoom") is False, json.dumps(sliders))
    checks.check("two-intentional-sliders", sliders.get("rangeCount") == 2, json.dumps(sliders))

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
    date_before_wheel = page.evaluate("() => document.getElementById('grid').dataset.dateGroup")
    level_before_wheel = page.evaluate("() => document.getElementById('grid').dataset.level")
    cell_box = page.locator('.cell[data-slot="grid"][data-kind="video"]').first.bounding_box()
    if cell_box:
        page.mouse.move(cell_box["x"] + cell_box["width"] / 2, cell_box["y"] + cell_box["height"] / 2)
        page.keyboard.down("Control")
        page.mouse.wheel(0, -120)
        page.keyboard.up("Control")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.size === '104'",
        timeout=5000,
    )
    after_wheel = page.evaluate(
        """() => ({
          size: document.getElementById('grid').dataset.size,
          dateGroup: document.getElementById('grid').dataset.dateGroup,
          level: document.getElementById('grid').dataset.level,
        })"""
    )
    record["ctrlWheelSize"] = {"dateBefore": date_before_wheel, "levelBefore": level_before_wheel, "after": after_wheel}
    checks.check("ctrl-wheel-steps-size", after_wheel.get("size") == "104", json.dumps(record["ctrlWheelSize"]))
    checks.check(
        "ctrl-wheel-keeps-dates",
        after_wheel.get("dateGroup") == date_before_wheel and after_wheel.get("level") == level_before_wheel,
        json.dumps(record["ctrlWheelSize"]),
    )
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
        tile_time = after_t
        page.locator('.cell[data-slot="grid"][data-kind="video"]').first.click()
        page.wait_for_function(
            """() => {
              const viewer = document.getElementById('viewer');
              const video = document.getElementById('viewer-video');
              if (!viewer || viewer.hidden || !video || video.hidden) return false;
              const src = video.currentSrc || video.getAttribute('src') || '';
              return src.indexOf('which=proxy') !== -1 && video.paused === false;
            }""",
            timeout=15000,
        )
        opened = video_state(page)
        record["openFromTile"] = {"tileTime": tile_time, "viewer": opened}
        checks.check(
            "open-from-tile-autoplay",
            opened.get("paused") is False and "which=proxy" in (opened.get("src") or ""),
            json.dumps(record["openFromTile"]),
        )
        checks.check(
            "open-from-tile-keeps-time",
            abs((opened.get("currentTime") or 0) - tile_time) <= 0.35,
            json.dumps(record["openFromTile"]),
        )
        page.locator("#viewer-back").click()
        wait_viewer_closed(page)

    size_before_dates = page.evaluate("() => document.getElementById('grid').dataset.size")
    page.locator("#date-group").select_option("off")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'off'",
        timeout=5000,
    )
    size_after_dates = page.evaluate("() => document.getElementById('grid').dataset.size")
    record["datesKeepSize"] = {"before": size_before_dates, "after": size_after_dates}
    checks.check("dates-off-keeps-size", size_before_dates == size_after_dates, json.dumps(record["datesKeepSize"]))
    checks.check(
        "dates-off-is-wall",
        page.locator("#grid").get_attribute("data-group-dates") == "off",
        page.locator("#grid").get_attribute("data-group-dates") or "",
    )
    set_settings(url, {"zoomLevel": "years"})
    wait_level(page, "years")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'off'",
        timeout=5000,
    )
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
    page.locator("#date-group").select_option("days")
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
    page.wait_for_function(
        """() => {
          const video = document.getElementById('viewer-video');
          if (!video) return false;
          const src = video.currentSrc || video.getAttribute('src') || '';
          return (src.indexOf('which=proxy') !== -1 || src.indexOf('which=original') !== -1)
            && video.paused === false;
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
    play_src = proxy_state.get("src") or ""
    source_chrome = page.evaluate(
        """() => {
          const el = document.getElementById('viewer-source');
          const video = document.getElementById('viewer-video');
          return {
            text: el ? (el.textContent || '').trim() : '',
            hidden: !el || el.hidden,
            state: el ? (el.dataset.state || '') : '',
            usingProxy: video ? video.getAttribute('data-using-proxy') === '1' : null,
            src: video ? (video.currentSrc || video.getAttribute('src') || '') : '',
          };
        }"""
    )
    record["sourceChrome"] = source_chrome
    source_text = source_chrome.get("text") or ""
    checks.check(
        "viewer-source-visible",
        source_chrome.get("hidden") is False and source_text != "",
        json.dumps(source_chrome),
    )
    if source_chrome.get("usingProxy") is True or "which=proxy" in (source_chrome.get("src") or ""):
        checks.check(
            "viewer-source-preview-or-loading",
            source_text in ("Preview", "Loading full…", "Preview — full unavailable"),
            json.dumps(source_chrome),
        )
    else:
        checks.check(
            "viewer-source-original",
            source_text == "Original",
            json.dumps(source_chrome),
        )
    checks.check(
        "play-starts-proxy",
        "which=proxy" in play_src or proxy_state.get("usingProxy") is True or "which=original" in play_src,
        json.dumps(proxy_state),
    )
    checks.check("play-keeps-fit", play_jump <= 2, json.dumps({"before": before_play, "after": after_play, "delta": play_jump}))

    page.wait_for_timeout(400)
    later = video_state(page)
    record["afterSwap"] = later
    swap_box = {"left": later.get("left"), "top": later.get("top"), "width": later.get("width"), "height": later.get("height")}
    swap_jump = box_delta(before_play, swap_box)
    checks.check("swap-keeps-fit", swap_jump <= 2, json.dumps({"before": before_play, "after": swap_box, "delta": swap_jump}))
    later_source = page.evaluate(
        """() => {
          const el = document.getElementById('viewer-source');
          return el ? { text: (el.textContent || '').trim(), hidden: el.hidden, state: el.dataset.state || '' } : {};
        }"""
    )
    record["sourceAfterSwap"] = later_source
    later_src = later.get("src") or ""
    if "which=original" in later_src:
        checks.check("swap-keeps-time", (later.get("currentTime") or 0) > 0.05, json.dumps(later))
        checks.check(
            "viewer-source-says-original",
            later_source.get("text") == "Original" and later_source.get("hidden") is False,
            json.dumps(later_source),
        )
    else:
        checks.check("stayed-on-proxy-or-original", "which=proxy" in later_src, json.dumps(later))
        checks.check(
            "viewer-source-honest-proxy",
            later_source.get("text") in ("Preview", "Loading full…", "Preview — full unavailable"),
            json.dumps(later_source),
        )

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
    chrome_layout = page.evaluate(
        """() => {
          const stage = document.getElementById('viewer-stage');
          const bottom = document.getElementById('viewer-bottom');
          const wrap = document.getElementById('viewer-scrub-wrap');
          const slider = document.getElementById('viewer-zoom-slider');
          const pct = document.getElementById('viewer-zoom-pct');
          const sr = stage ? stage.getBoundingClientRect() : null;
          const br = bottom ? bottom.getBoundingClientRect() : null;
          const wr = wrap ? wrap.getBoundingClientRect() : null;
          const zr = slider ? slider.getBoundingClientRect() : null;
          return {
            scrubInBottom: !!(bottom && wrap && bottom.contains(wrap)),
            zoomInBottom: !!(bottom && slider && bottom.contains(slider)),
            zoomVertical: !!(zr && zr.height > zr.width + 20),
            pctText: pct ? (pct.textContent || '').trim() : '',
            scrubBelowStage: !!(sr && wr && wr.top >= sr.bottom - 1),
            bottomBelowStage: !!(sr && br && br.top >= sr.bottom - 1),
          };
        }"""
    )
    record["chromeLayout"] = chrome_layout
    checks.check("scrub-in-bottom-chrome", chrome_layout.get("scrubInBottom") is True, json.dumps(chrome_layout))
    checks.check("scrub-not-over-picture", chrome_layout.get("scrubBelowStage") is True, json.dumps(chrome_layout))
    checks.check("bottom-chrome-below-stage", chrome_layout.get("bottomBelowStage") is True, json.dumps(chrome_layout))
    checks.check("viewer-zoom-vertical", chrome_layout.get("zoomVertical") is True, json.dumps(chrome_layout))
    checks.check(
        "viewer-zoom-shows-percent",
        isinstance(chrome_layout.get("pctText"), str) and chrome_layout.get("pctText", "").endswith("%"),
        json.dumps(chrome_layout),
    )
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
        fresh_root(isolated)
        folder = artifacts / "scan-media"
        copy_rels(media_src, folder, MEDIA_RELS)
        scanned = run_library(isolated, ["scan", str(folder), "--serve-from-there"], timeout=180)
        commands.append("python -m library scan <folder> --serve-from-there")
        checks.check("scan-ok", scanned.returncode == 0, scanned.stderr[-200:])
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
