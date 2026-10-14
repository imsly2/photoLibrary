"""Windows video + zoom taste. Diagnostic log, not an F-id grade."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.records import read_renditions, renditions_for
from library.renditions import (
    PLAYBACK_MAX_WIDTH,
    browser_safe_mp4,
    cleanup_tmp_siblings,
    should_remux_playback,
    sweep_orphan_tmps,
    write_playback,
    write_proxy,
)
from tests.qa.launch_ps1_args import run_assertions as launch_arglist_assertions
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree
from tests.qa.s03 import find_item, request_raw
from tests.qa.s06 import (
    copy_rels,
    ffprobe_media,
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
    "formats/clip.mov",
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
                    name_l = str(name).lower()
                    if name_l.endswith((".mov", ".avi", ".mkv")) and rend.get("playback") not in {
                        "ready",
                        "not-applicable",
                        "error",
                    }:
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


def wait_tile_hover_playing(page: Any, timeout: float = 8000) -> dict[str, Any]:
    page.locator('.cell[data-slot="grid"][data-kind="video"]').first.hover()
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('.cell video')).some(function (v) {
          return !v.paused && !v.ended;
        })""",
        timeout=timeout,
    )
    return playing_cell_videos(page)


def seek_tile_scrub(page: Any) -> dict[str, Any]:
    before = page.evaluate(
        "() => { const v = document.querySelector('.cell video'); return v ? v.currentTime : 0; }"
    )
    target = "200" if (before or 0) > 0.8 else "600"
    expected = 0.4 if target == "200" else 1.2
    page.locator(".tile-scrub").evaluate(
        """(el, value) => {
          el.value = value;
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        target,
    )
    after = page.evaluate(
        "() => { const v = document.querySelector('.cell video'); return v ? v.currentTime : 0; }"
    )
    return {"before": before, "after": after, "target": target, "expected": expected}


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
    years_dated = wait_tile_hover_playing(page)
    record["datedYearsHover"] = years_dated
    checks.check(
        "dated-years-hover-plays",
        years_dated.get("playingCount") == 1,
        json.dumps(years_dated),
    )
    years_scrub = seek_tile_scrub(page)
    record["datedYearsScrub"] = years_scrub
    checks.check(
        "dated-years-tile-scrub",
        abs((years_scrub.get("after") or 0) - (years_scrub.get("expected") or 0)) <= 0.2,
        json.dumps(years_scrub),
    )
    page.locator("#date-group").select_option("months")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'months'",
        timeout=5000,
    )
    months_dated = wait_tile_hover_playing(page)
    record["datedMonthsHover"] = months_dated
    checks.check(
        "dated-months-hover-plays",
        months_dated.get("playingCount") == 1,
        json.dumps(months_dated),
    )
    months_scrub = seek_tile_scrub(page)
    record["datedMonthsScrub"] = months_scrub
    checks.check(
        "dated-months-tile-scrub",
        abs((months_scrub.get("after") or 0) - (months_scrub.get("expected") or 0)) <= 0.2,
        json.dumps(months_scrub),
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
        record["tileScrub"] = seek_tile_scrub(page)
        after_t = record["tileScrub"].get("after") or 0
        expected = record["tileScrub"].get("expected") or 0
        checks.check(
            "tile-scrub-seeks",
            abs(after_t - expected) <= 0.2,
            json.dumps(record["tileScrub"]),
        )
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
    elif "which=playback" in later_src:
        checks.check("swap-keeps-time", (later.get("currentTime") or 0) > 0.05, json.dumps(later))
        checks.check(
            "viewer-source-says-full",
            later_source.get("text") == "Full" and later_source.get("hidden") is False,
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

    page.locator('#grid .cell[data-slot="grid"][data-filename="clip.mov"]').click()
    page.wait_for_function(
        """() => {
          const viewer = document.getElementById('viewer');
          const video = document.getElementById('viewer-video');
          if (!viewer || viewer.hidden || !video || video.hidden) return false;
          const src = video.currentSrc || video.getAttribute('src') || '';
          return src.indexOf('which=proxy') !== -1 || src.indexOf('which=playback') !== -1;
        }""",
        timeout=15000,
    )
    page.wait_for_function(
        """() => {
          const video = document.getElementById('viewer-video');
          const el = document.getElementById('viewer-source');
          if (!video || !el || el.hidden) return false;
          const src = video.currentSrc || video.getAttribute('src') || '';
          return src.indexOf('which=playback') !== -1
            && (el.textContent || '').trim() === 'Full'
            && video.paused === false;
        }""",
        timeout=25000,
    )
    mov = page.evaluate(
        """() => {
          const el = document.getElementById('viewer-source');
          const video = document.getElementById('viewer-video');
          return {
            text: el ? (el.textContent || '').trim() : '',
            hidden: !el || el.hidden,
            state: el ? (el.dataset.state || '') : '',
            usingProxy: video ? video.getAttribute('data-using-proxy') === '1' : null,
            usingPlayback: video ? video.getAttribute('data-using-playback') === '1' : null,
            src: video ? (video.currentSrc || video.getAttribute('src') || '') : '',
            muted: video ? video.muted : null,
            paused: video ? video.paused : null,
          };
        }"""
    )
    record["movSource"] = mov
    checks.check(
        "mov-plays-playback",
        "which=playback" in (mov.get("src") or "") and mov.get("usingPlayback") is True,
        json.dumps(mov),
    )
    checks.check(
        "mov-source-says-full",
        mov.get("text") == "Full" and mov.get("hidden") is False and mov.get("state") == "full",
        json.dumps(mov),
    )
    checks.check("mov-not-silent-proxy", mov.get("usingProxy") is not True, json.dumps(mov))
    page.screenshot(path=str(artifacts / "video-mov.png"), full_page=False)
    page.locator("#viewer-back").click()
    wait_viewer_closed(page)
    page.screenshot(path=str(artifacts / "video-grid.png"), full_page=False)
    return record


def prove_playback_http(checks: Checks, url: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    base = url.rstrip("/")
    record: dict[str, Any] = {}
    mp4 = find_item(items, "clip.mp4")
    mov = find_item(items, "clip.mov")
    checks.check("http-has-mp4", mp4 is not None)
    checks.check("http-has-mov", mov is not None)
    if mp4 is None or mov is None:
        return record
    mp4_status = ((mp4.get("renditions") or {}).get("status") or {}).get("playback")
    mov_status = ((mov.get("renditions") or {}).get("status") or {}).get("playback")
    record["mp4PlaybackStatus"] = mp4_status
    record["movPlaybackStatus"] = mov_status
    checks.check("mp4-playback-not-applicable", mp4_status == "not-applicable", str(mp4_status))
    checks.check("mov-playback-ready", mov_status == "ready", str(mov_status))
    mp4_code, _, mp4_body = request_raw(f"{base}/api/media/{mp4['id']}?which=playback")
    mov_code, mov_headers, mov_body = request_raw(f"{base}/api/media/{mov['id']}?which=playback")
    record["mp4PlaybackHttp"] = mp4_code
    record["movPlaybackHttp"] = mov_code
    checks.check("mp4-playback-404", mp4_code == 404, str(mp4_code))
    checks.check("mov-playback-200", mov_code == 200 and len(mov_body) > 0, str(mov_code))
    ctype = ""
    for key, value in mov_headers.items():
        if key.lower() == "content-type":
            ctype = value
            break
    checks.check("mov-playback-type", ctype.startswith("video/mp4"), ctype)
    dest = Path("/tmp/library-playback-clip.mov.mp4")
    dest.write_bytes(mov_body)
    probe = ffprobe_media(dest)
    record["movPlaybackProbe"] = probe
    checks.check("mov-playback-h264", probe.get("codec") == "h264", json.dumps(probe))
    checks.check("mov-playback-has-audio", (probe.get("audioStreamCount") or 0) >= 1, json.dumps(probe))
    checks.check(
        "mov-playback-full-size",
        probe.get("width") == 640 and probe.get("height") == 480,
        json.dumps(probe),
    )
    orig_code, _, orig_body = request_raw(f"{base}/api/media/{mov['id']}?which=original")
    record["movOriginalHttp"] = orig_code
    checks.check("mov-original-still-there", orig_code == 200 and len(orig_body) > 0, str(orig_code))
    record["mp4PlaybackBytes"] = len(mp4_body)
    record["movPlaybackBytes"] = len(mov_body)
    checks.check("mp4-playback-no-body", len(mp4_body) == 0, str(len(mp4_body)))
    checks.check(
        "mov-playback-width-capped",
        type(probe.get("width")) is int and probe["width"] <= PLAYBACK_MAX_WIDTH,
        json.dumps(probe),
    )
    return record


def _make_synthetic_clip(dest: Path, *, width: int, height: int, container: str, seconds: float = 2.0) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={width}x{height}:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-f",
            container,
            str(dest),
        ],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def _legacy_crf18_full(source: Path, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(dest),
        ],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def prove_rendition_size(checks: Checks, media_src: Path, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "policy": {
            "proxy": "width <= proxyWidth (480), CRF 28, no audio, scrub-friendly",
            "playback": "only when not browser-safe MP4; longest side <= 1280; CRF 23; remux only if already <=1280 and <=80MiB",
        }
    }
    mp4 = media_src / "a" / "clip.mp4"
    mov = media_src / "formats" / "clip.mov"
    proxy_dest = artifacts / "size-proxy.mp4"
    checks.check("size-write-proxy", write_proxy(mp4, proxy_dest, 480) is True)
    proxy_probe = ffprobe_media(proxy_dest)
    record["fixtureProxy"] = proxy_probe
    checks.check(
        "size-proxy-width",
        type(proxy_probe.get("width")) is int and proxy_probe["width"] <= 480,
        json.dumps(proxy_probe),
    )
    checks.check("size-proxy-silent", proxy_probe.get("audioStreamCount") == 0, json.dumps(proxy_probe))
    checks.check(
        "size-proxy-bytes",
        type(proxy_probe.get("bytes")) is int and 0 < proxy_probe["bytes"] <= 500_000,
        json.dumps(proxy_probe),
    )
    skip = artifacts / "size-mp4-playback.mp4"
    skip_out = write_playback(mp4, skip)
    record["browserSafeMp4"] = {"outcome": skip_out, "exists": skip.exists()}
    checks.check("size-mp4-not-applicable", skip_out == "not-applicable" and not skip.exists(), skip_out)
    checks.check("size-fixture-mov-may-remux", should_remux_playback(mov) is True)

    synth = artifacts / "synth"
    wide_mov = synth / "wide.mov"
    wide_mp4 = synth / "wide.mp4"
    made_mov = _make_synthetic_clip(wide_mov, width=3840, height=2160, container="mov")
    made_mp4 = _make_synthetic_clip(wide_mp4, width=3840, height=2160, container="mp4")
    checks.check("size-synth-mov", made_mov, str(wide_mov))
    checks.check("size-synth-mp4", made_mp4, str(wide_mp4))
    record["synthSource"] = {
        "movBytes": wide_mov.stat().st_size if wide_mov.is_file() else 0,
        "mp4Bytes": wide_mp4.stat().st_size if wide_mp4.is_file() else 0,
    }
    if made_mov:
        checks.check("size-4k-no-remux", should_remux_playback(wide_mov) is False)
        new_dest = synth / "policy-playback.mp4"
        outcome = write_playback(wide_mov, new_dest)
        new_probe = ffprobe_media(new_dest) if new_dest.is_file() else {}
        record["policyPlayback"] = {"outcome": outcome, "probe": new_probe}
        checks.check("size-4k-playback-ready", outcome == "ready" and new_dest.is_file(), outcome)
        checks.check(
            "size-4k-playback-width",
            type(new_probe.get("width")) is int and new_probe["width"] <= PLAYBACK_MAX_WIDTH,
            json.dumps(new_probe),
        )
        checks.check("size-4k-playback-audio", (new_probe.get("audioStreamCount") or 0) >= 1, json.dumps(new_probe))
        checks.check(
            "size-4k-playback-bytes",
            type(new_probe.get("bytes")) is int and 0 < new_probe["bytes"] <= 3_000_000,
            json.dumps(new_probe),
        )
        legacy_dest = synth / "legacy-crf18.mp4"
        legacy_ok = _legacy_crf18_full(wide_mov, legacy_dest)
        legacy_probe = ffprobe_media(legacy_dest) if legacy_ok else {}
        record["legacyCrf18"] = {"ok": legacy_ok, "probe": legacy_probe}
        if legacy_ok:
            checks.check(
                "size-policy-smaller-than-crf18",
                new_probe.get("bytes", 0) < legacy_probe.get("bytes", 0),
                json.dumps({"new": new_probe.get("bytes"), "legacy": legacy_probe.get("bytes")}),
            )
            record["beforeAfter"] = {
                "legacyCrf18Full4kBytes": legacy_probe.get("bytes"),
                "policy1280Crf23Bytes": new_probe.get("bytes"),
                "note": "Same 2s 3840x2160 MOV. Old write_playback used CRF 18 at original pixels (or remuxed the whole file). New policy transcodes to <=1280 / CRF 23.",
            }
        wide_proxy = synth / "wide-proxy.mp4"
        checks.check("size-4k-proxy", write_proxy(wide_mov, wide_proxy, 480) is True)
        wide_proxy_probe = ffprobe_media(wide_proxy)
        record["wideProxy"] = wide_proxy_probe
        checks.check(
            "size-4k-proxy-width",
            type(wide_proxy_probe.get("width")) is int and wide_proxy_probe["width"] <= 480,
            json.dumps(wide_proxy_probe),
        )
        checks.check(
            "size-4k-proxy-bytes",
            type(wide_proxy_probe.get("bytes")) is int and 0 < wide_proxy_probe["bytes"] <= 500_000,
            json.dumps(wide_proxy_probe),
        )
    if made_mp4:
        huge_skip = synth / "wide-mp4-playback.mp4"
        huge_out = write_playback(wide_mp4, huge_skip)
        record["wideMp4"] = {"outcome": huge_out, "exists": huge_skip.exists(), "sourceBytes": record["synthSource"]["mp4Bytes"]}
        checks.check("size-4k-mp4-not-applicable", huge_out == "not-applicable" and not huge_skip.exists(), huge_out)

    planted = artifacts / "renditions" / "orphan" / "playback.mp4.deadbeef.tmp"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(b"orphan-tmp")
    sibling = artifacts / "cleanup-target.mp4.deadbeef.tmp"
    sibling.write_bytes(b"sibling-tmp")
    target = artifacts / "cleanup-target.mp4"
    removed_sib = cleanup_tmp_siblings(target)
    removed_sweep = sweep_orphan_tmps(artifacts)
    record["tmpCleanup"] = {"siblings": removed_sib, "sweep": removed_sweep}
    checks.check("size-tmp-sibling-gone", removed_sib >= 1 and not sibling.exists())
    checks.check("size-tmp-sweep-gone", removed_sweep >= 1 and not planted.exists())
    return record


def prove_playback_units(checks: Checks, media_src: Path, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    mp4 = media_src / "a" / "clip.mp4"
    mov = media_src / "formats" / "clip.mov"
    checks.check("unit-mp4-browser-safe", browser_safe_mp4(mp4) is True)
    checks.check("unit-mov-needs-derivative", browser_safe_mp4(mov) is False)
    dest = artifacts / "unit-playback.mp4"
    outcome = write_playback(mov, dest)
    record["writePlayback"] = outcome
    checks.check("unit-write-playback", outcome == "ready" and dest.is_file() and dest.stat().st_size > 0, outcome)
    probe = ffprobe_media(dest)
    record["unitProbe"] = probe
    checks.check("unit-playback-audio", (probe.get("audioStreamCount") or 0) >= 1, json.dumps(probe))
    skip = artifacts / "unit-mp4-skip.mp4"
    skip_out = write_playback(mp4, skip)
    record["writeMp4"] = skip_out
    checks.check("unit-mp4-not-applicable", skip_out == "not-applicable" and not skip.exists(), skip_out)
    photo = renditions_for("photo", "src_test")
    video = renditions_for("video", "src_test")
    checks.check("unit-photo-playback-na", photo["status"]["playback"] == "not-applicable")
    checks.check("unit-video-playback-queued", video["status"]["playback"] == "queued")
    legacy = {
        "store": "with-server",
        "sourceId": "src_test",
        "thumb": None,
        "preview": None,
        "poster": None,
        "proxy": None,
        "status": {
            "thumb": "not-applicable",
            "preview": "not-applicable",
            "poster": "ready",
            "proxy": "ready",
        },
    }
    loaded = read_renditions(legacy)
    record["legacyPlayback"] = loaded["status"]["playback"]
    checks.check("unit-legacy-video-queued", loaded["status"]["playback"] == "queued", json.dumps(loaded["status"]))
    photo_legacy = {
        "store": "with-server",
        "sourceId": "src_test",
        "thumb": None,
        "preview": None,
        "poster": None,
        "proxy": None,
        "status": {
            "thumb": "ready",
            "preview": "ready",
            "poster": "not-applicable",
            "proxy": "not-applicable",
        },
    }
    loaded_photo = read_renditions(photo_legacy)
    checks.check(
        "unit-legacy-photo-na",
        loaded_photo["status"]["playback"] == "not-applicable",
        json.dumps(loaded_photo["status"]),
    )
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
        units = prove_playback_units(checks, media_src, artifacts)
        (artifacts / "playback-units.json").write_text(json.dumps(units, indent=2) + "\n", encoding="utf-8")
        extra["playback-units.json"] = str(artifacts / "playback-units.json")
        sizes = prove_rendition_size(checks, media_src, artifacts)
        (artifacts / "rendition-size.json").write_text(json.dumps(sizes, indent=2) + "\n", encoding="utf-8")
        extra["rendition-size.json"] = str(artifacts / "rendition-size.json")
        arglist = launch_arglist_assertions()
        (artifacts / "launch-arglist.json").write_text(json.dumps(arglist, indent=2) + "\n", encoding="utf-8")
        extra["launch-arglist.json"] = str(artifacts / "launch-arglist.json")
        for item in arglist["assertions"]:
            checks.check("launch-" + str(item["name"]), bool(item["pass"]), str(item.get("detail") or ""))
        server, url, pids = start_owned(isolated)
        try:
            items = wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "clip.mp4", "clip.mov"))
            checks.check("has-clip", find_item(items, "clip.mp4") is not None)
            checks.check("has-mov", find_item(items, "clip.mov") is not None)
            http_record = prove_playback_http(checks, url, items)
            (artifacts / "playback-http.json").write_text(json.dumps(http_record, indent=2) + "\n", encoding="utf-8")
            extra["playback-http.json"] = str(artifacts / "playback-http.json")
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
            extra["video-mov.png"] = str(artifacts / "video-mov.png")
            extra["video-grid.png"] = str(artifacts / "video-grid.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-video-runner", False, str(exc))
    return write_result("TASTE-VIDEO", "slice", checks, artifacts, commands, extra)
