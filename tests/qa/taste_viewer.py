"""Taste-Windows viewer chrome. Diagnostic log, not the F10 grade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.s00 import Checks, assert_no_pillow_in_server
from tests.qa.s03 import find_item, png_size
from tests.qa.s06 import set_settings, wait_level
from tests.qa.s08 import fresh_root, write_result
from tests.qa.s09 import (
    copy_s09_media,
    hash_tree,
    prepare_media,
    scan_library,
    start_owned,
    stop_owned,
    wait_catalog,
    wait_viewer_closed,
    wait_viewer_original,
    wait_viewer_still,
)


def collect_console(page: Any) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


def image_rect(page: Any) -> dict[str, float]:
    return page.evaluate(
        """() => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return {
            left: r.left,
            top: r.top,
            width: r.width,
            height: r.height,
            complete: img.complete,
            naturalWidth: img.naturalWidth
          };
        }"""
    )


def set_zoom_slider(page: Any, percent: int) -> None:
    page.locator("#viewer-zoom-slider").evaluate(
        """(el, value) => {
          el.value = String(value);
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        percent,
    )


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


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    set_settings(url, {"zoomLevel": "all"})
    wait_level(page, "all")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=15000)
    start_url = page.url

    update_chrome = page.evaluate(
        """() => {
          const el = document.getElementById('update-library');
          if (!el) {
            return { present: false };
          }
          const r = el.getBoundingClientRect();
          return {
            present: true,
            text: (el.textContent || '').trim(),
            hidden: el.hidden,
            width: r.width,
            height: r.height,
          };
        }"""
    )
    record["update"] = update_chrome
    checks.check(
        "update-library-visible",
        bool(update_chrome.get("present"))
        and not update_chrome.get("hidden")
        and (update_chrome.get("width") or 0) > 8
        and update_chrome.get("text") == "Update Library",
        json.dumps(update_chrome),
    )
    with page.expect_response(lambda res: res.url.endswith("/api/update") and res.request.method == "POST") as update_info:
        page.locator("#update-library").click()
    update_res = update_info.value
    update_body = update_res.json()
    record["updateHttp"] = {"status": update_res.status, "body": update_body}
    checks.check(
        "update-http-shape",
        update_res.status == 200
        and isinstance(update_body, dict)
        and "ok" in update_body
        and "updated" in update_body
        and "revision" in update_body
        and "message" in update_body,
        json.dumps(record["updateHttp"]),
    )

    page.locator('[data-filename="IMG_1042.jpg"]').click()
    wait_viewer_still(page)
    chrome = page.evaluate(
        """() => {
          function info(id) {
            const el = document.getElementById(id);
            if (!el) {
              return { present: false };
            }
            const r = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return {
              present: true,
              text: (el.textContent || '').trim(),
              disabled: !!el.disabled,
              hidden: el.hidden || style.display === 'none',
              width: r.width,
              height: r.height,
              top: r.top,
              left: r.left,
              bottom: r.bottom,
            };
          }
          const fields = Array.from(document.querySelectorAll('#viewer-fields .annotate-field')).map(function (label) {
            return (label.textContent || '').replace(/\\s+/g, ' ').trim();
          });
          const slider = document.getElementById('viewer-zoom-slider');
          const sliderRect = slider ? slider.getBoundingClientRect() : null;
          return {
            back: info('viewer-back'),
            prev: info('viewer-prev'),
            next: info('viewer-next'),
            zoomOut: info('viewer-zoom-out'),
            zoomIn: info('viewer-zoom-in'),
            zoomSlider: {
              present: !!slider,
              type: slider ? slider.type : '',
              min: slider ? slider.min : '',
              max: slider ? slider.max : '',
              hidden: slider ? slider.hidden : true,
              width: sliderRect ? sliderRect.width : 0,
              height: sliderRect ? sliderRect.height : 0,
              top: sliderRect ? sliderRect.top : 0,
              inBottom: !!(slider && document.getElementById('viewer-bottom') && document.getElementById('viewer-bottom').contains(slider)),
            },
            rotate: info('viewer-rotate'),
            favorite: info('viewer-favorite'),
            reveal: info('reveal-original'),
            info: info('viewer-info'),
            open: info('open-original'),
            slideshow: info('viewer-slideshow'),
            fullscreen: info('viewer-fullscreen'),
            titles: {
              prev: (document.getElementById('viewer-prev') || {}).title || '',
              next: (document.getElementById('viewer-next') || {}).title || '',
              rotate: (document.getElementById('viewer-rotate') || {}).title || '',
              slideshow: (document.getElementById('viewer-slideshow') || {}).title || '',
              fullscreen: (document.getElementById('viewer-fullscreen') || {}).title || '',
            },
            crumb: (document.getElementById('viewer-crumb') || {}).textContent || '',
            fields: fields,
            personPlaceholder: (document.getElementById('person-field') || {}).placeholder || '',
            placePlaceholder: (document.getElementById('place-field') || {}).placeholder || '',
            thingPlaceholder: (document.getElementById('thing-field') || {}).placeholder || '',
            overlayLabels: !!document.getElementById('viewer-labels'),
            stagePills: document.querySelectorAll('#viewer-stage .entity-label').length,
            showingOriginalText: Array.from(document.querySelectorAll('#viewer button')).some(function (btn) {
              return (btn.textContent || '').trim() === 'Showing original';
            }),
            href: location.href,
          };
        }"""
    )
    record["chrome"] = chrome
    for name in ("back", "prev", "next", "rotate", "favorite", "reveal", "info", "open", "slideshow", "fullscreen"):
        node = chrome.get(name) or {}
        min_w = 24 if name == "favorite" else 8
        checks.check(
            f"{name}-visible",
            bool(node.get("present")) and not node.get("hidden") and (node.get("width") or 0) > min_w,
            json.dumps(node),
        )
    checks.check("no-zoom-minus", not (chrome.get("zoomOut") or {}).get("present"), json.dumps(chrome.get("zoomOut")))
    checks.check("no-zoom-plus", not (chrome.get("zoomIn") or {}).get("present"), json.dumps(chrome.get("zoomIn")))
    slider = chrome.get("zoomSlider") or {}
    checks.check(
        "zoom-is-slider",
        bool(slider.get("present"))
        and slider.get("type") == "range"
        and slider.get("min") == "25"
        and slider.get("max") == "1600"
        and ((slider.get("height") or 0) > 80 or (slider.get("width") or 0) > 80),
        json.dumps(slider),
    )
    checks.check("zoom-slider-not-in-bottom", slider.get("inBottom") is False, json.dumps(slider))
    checks.check("back-label", chrome.get("back", {}).get("text") == "Back", json.dumps(chrome.get("back")))
    checks.check("prev-label", chrome.get("prev", {}).get("text") == "Previous", json.dumps(chrome.get("prev")))
    checks.check("next-label", chrome.get("next", {}).get("text") == "Next", json.dumps(chrome.get("next")))
    checks.check("info-label", chrome.get("info", {}).get("text") == "Info", json.dumps(chrome.get("info")))
    checks.check("open-label", chrome.get("open", {}).get("text") == "Open", json.dumps(chrome.get("open")))
    checks.check("no-showing-original-button", chrome.get("showingOriginalText") is False, json.dumps(chrome.get("showingOriginalText")))
    checks.check(
        "prev-or-next-enabled",
        (not chrome.get("prev", {}).get("disabled")) or (not chrome.get("next", {}).get("disabled")),
        json.dumps({"prev": chrome.get("prev"), "next": chrome.get("next")}),
    )
    checks.check("reveal-label", chrome.get("reveal", {}).get("text") == "Reveal in Explorer", json.dumps(chrome.get("reveal")))
    titles = chrome.get("titles") or {}
    checks.check("tooltip-prev", titles.get("prev") == "Previous ←", json.dumps(titles))
    checks.check("tooltip-next", titles.get("next") == "Next →", json.dumps(titles))
    checks.check("tooltip-rotate", titles.get("rotate") == "Rotate Ctrl+R", json.dumps(titles))
    checks.check("tooltip-slideshow", titles.get("slideshow") == "Slideshow F5", json.dumps(titles))
    checks.check("tooltip-fullscreen", titles.get("fullscreen") == "Fullscreen F11", json.dumps(titles))
    checks.check("heart-unfilled", chrome.get("favorite", {}).get("text") == "♡", json.dumps(chrome.get("favorite")))
    checks.check("crumb-filename", "IMG_1042.jpg" in (chrome.get("crumb") or ""), chrome.get("crumb"))
    checks.check(
        "nav-at-bottom",
        (chrome.get("prev", {}).get("top") or 0) > 500
        and (chrome.get("next", {}).get("top") or 0) > 500
        and (chrome.get("rotate", {}).get("top") or 0) > 500,
        json.dumps({"prev": chrome.get("prev"), "next": chrome.get("next"), "rotate": chrome.get("rotate")}),
    )
    checks.check(
        "info-top-right",
        (chrome.get("info", {}).get("top") or 999) < 80
        and (chrome.get("info", {}).get("left") or 0) > 900,
        json.dumps(chrome.get("info")),
    )
    checks.check("no-overlay-label-row", chrome.get("overlayLabels") is False, json.dumps(chrome.get("overlayLabels")))
    checks.check("no-stage-pills", chrome.get("stagePills") == 0, str(chrome.get("stagePills")))

    page.locator("#viewer-info").click()
    page.wait_for_function(
        """() => {
          const btn = document.getElementById('viewer-info');
          const panel = document.getElementById('viewer-info-panel');
          return btn && btn.getAttribute('aria-expanded') === 'true' && panel && !panel.hidden;
        }""",
        timeout=5000,
    )
    info_open = page.evaluate(
        """() => {
          const panel = document.getElementById('viewer-info-panel');
          const fields = Array.from(document.querySelectorAll('#viewer-fields .annotate-field')).map(function (label) {
            return (label.textContent || '').replace(/\\s+/g, ' ').trim();
          });
          function facts() {
            return Array.from(document.querySelectorAll('#viewer-fact-list .info-fact')).map(function (row) {
              const dt = row.querySelector('dt');
              const dd = row.querySelector('dd');
              return {
                label: dt ? (dt.textContent || '').trim() : '',
                value: dd ? (dd.textContent || '').trim() : '',
              };
            });
          }
          return {
            headings: Array.from(panel.querySelectorAll('.info-heading')).map(function (el) {
              return (el.textContent || '').trim();
            }),
            facts: facts(),
            fields: fields,
            personPlaceholder: (document.getElementById('person-field') || {}).placeholder || '',
            placePlaceholder: (document.getElementById('place-field') || {}).placeholder || '',
            thingPlaceholder: (document.getElementById('thing-field') || {}).placeholder || '',
            personInPanel: !!(document.getElementById('person-field') && panel.contains(document.getElementById('person-field'))),
          };
        }"""
    )
    record["infoOpen"] = info_open
    field_blob = " ".join(info_open.get("fields") or [])
    headings = info_open.get("headings") or []
    checks.check(
        "info-lists-kinds",
        headings == ["File", "People", "Places", "Things"],
        json.dumps(headings),
    )
    facts = {row.get("label"): row.get("value") for row in (info_open.get("facts") or []) if isinstance(row, dict)}
    record["infoFacts"] = facts
    checks.check("info-facts-first", headings[:1] == ["File"] and headings[1:4] == ["People", "Places", "Things"], json.dumps(headings))
    checks.check("info-date-taken", "2024-06-12" in (facts.get("Date taken") or ""), json.dumps(facts.get("Date taken")))
    checks.check(
        "info-no-camera",
        facts.get("Camera") == "No camera info for this file.",
        json.dumps(facts.get("Camera")),
    )
    checks.check("info-dimensions", facts.get("Dimensions") == "640 × 480", json.dumps(facts.get("Dimensions")))
    checks.check("info-size", bool(facts.get("Size")), json.dumps(facts.get("Size")))
    checks.check("info-path", "IMG_1042.jpg" in (facts.get("Path") or ""), json.dumps(facts.get("Path")))
    checks.check("info-gps", "41.88000" in (facts.get("GPS") or "") and "87.63000" in (facts.get("GPS") or ""), json.dumps(facts.get("GPS")))
    checks.check("person-field-labeled", "Person" in field_blob and info_open.get("personPlaceholder") == "Person", field_blob)
    checks.check("place-field-labeled", "Place" in field_blob and info_open.get("placePlaceholder") == "Place", field_blob)
    checks.check("thing-field-labeled", "Thing" in field_blob and info_open.get("thingPlaceholder") == "Thing", field_blob)
    checks.check("fields-in-info", info_open.get("personInPanel") is True, json.dumps(info_open))
    blank_inputs = page.evaluate(
        """() => Array.from(document.querySelectorAll('#viewer-fields input')).filter(function (input) {
          const label = input.closest('label');
          const named = (input.getAttribute('aria-label') || input.placeholder || (label && label.textContent) || '').trim();
          return !named;
        }).length"""
    )
    checks.check("no-mystery-inputs", blank_inputs == 0, str(blank_inputs))
    page.locator("#viewer-info").click()
    page.wait_for_function(
        """() => {
          const btn = document.getElementById('viewer-info');
          const panel = document.getElementById('viewer-info-panel');
          return btn && btn.getAttribute('aria-expanded') === 'false' && panel && panel.hidden;
        }""",
        timeout=5000,
    )
    checks.check("info-closes", True)

    shot = artifacts / "viewer-chrome.png"
    page.screenshot(path=str(shot), full_page=False)
    vw, vh = png_size(shot)
    checks.check("viewer-chrome-png", shot.is_file() and vw == 1280 and vh == 720, f"{vw}x{vh}")

    start_src = page.locator("#viewer-image").get_attribute("src") or ""
    page.locator("#viewer-next").click()
    page.wait_for_function(
        """(prev) => {
          const img = document.getElementById('viewer-image');
          return img && img.getAttribute('src') && img.getAttribute('src') !== prev
            && img.complete && img.naturalWidth > 0;
        }""",
        arg=start_src,
        timeout=10000,
    )
    mid_src = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("next-moves", mid_src != start_src, mid_src)
    page.locator("#viewer-prev").click()
    page.wait_for_function(
        """(want) => {
          const img = document.getElementById('viewer-image');
          return img && img.getAttribute('src') === want && img.complete && img.naturalWidth > 0;
        }""",
        arg=start_src,
        timeout=10000,
    )
    back_src = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("prev-returns", back_src == start_src, back_src)

    page.keyboard.press("ArrowRight")
    page.wait_for_function(
        """(prev) => {
          const img = document.getElementById('viewer-image');
          return img && img.getAttribute('src') && img.getAttribute('src') !== prev
            && img.complete && img.naturalWidth > 0;
        }""",
        arg=start_src,
        timeout=10000,
    )
    arrow_src = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("arrow-right-moves", arrow_src != start_src, arrow_src)
    page.keyboard.press("ArrowLeft")
    page.wait_for_function(
        """(want) => {
          const img = document.getElementById('viewer-image');
          return img && img.getAttribute('src') === want && img.complete && img.naturalWidth > 0;
        }""",
        arg=start_src,
        timeout=10000,
    )
    checks.check("arrow-left-returns", (page.locator("#viewer-image").get_attribute("src") or "") == start_src)

    wait_viewer_original(page)
    original_state = page.evaluate(
        """() => {
          const btn = document.getElementById('open-original');
          const original = document.getElementById('viewer-original');
          return {
            text: (btn && btn.textContent || '').trim(),
            pressed: btn ? btn.getAttribute('aria-pressed') : '',
            showing: document.getElementById('viewer').dataset.showingOriginal || '',
            originalSrc: original ? (original.getAttribute('src') || '') : '',
            originalHidden: original ? original.hidden : true,
          };
        }"""
    )
    record["originalAuto"] = original_state
    checks.check(
        "original-autoload-no-toggle",
        original_state.get("text") == "Open"
        and not original_state.get("pressed")
        and "which=original" in (original_state.get("originalSrc") or "")
        and original_state.get("originalHidden") is False,
        json.dumps(original_state),
    )
    with page.expect_response(lambda res: "/open" in res.url and res.request.method == "POST") as open_info:
        page.locator("#open-original").click()
    open_res = open_info.value
    open_body = open_res.json()
    record["open"] = open_body
    checks.check("open-http", open_res.status == 200, str(open_res.status))
    checks.check(
        "open-path",
        bool(open_body.get("path")) and Path(open_body.get("path") or "").is_file(),
        json.dumps(open_body),
    )
    preview_kept = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("open-keeps-preview", "which=preview" in preview_kept, preview_kept)

    page.locator("#viewer-favorite").click()
    page.wait_for_function(
        """() => {
          const btn = document.getElementById('viewer-favorite');
          return btn && btn.getAttribute('aria-pressed') === 'true' && (btn.textContent || '').trim() === '♥';
        }""",
        timeout=8000,
    )
    checks.check("heart-favorites", True)
    with page.expect_response(lambda res: "/reveal" in res.url and res.request.method == "POST") as reveal_info:
        page.locator("#reveal-original").click()
    reveal_res = reveal_info.value
    reveal_body = reveal_res.json()
    record["reveal"] = reveal_body
    checks.check("reveal-http", reveal_res.status == 200, str(reveal_res.status))
    checks.check(
        "reveal-folder",
        bool(reveal_body.get("folder")) and Path(reveal_body.get("folder") or "").is_dir(),
        json.dumps(reveal_body),
    )
    checks.check(
        "reveal-file",
        bool(reveal_body.get("path")) and Path(reveal_body.get("path") or "").is_file(),
        json.dumps(reveal_body),
    )

    before = image_rect(page)
    set_zoom_slider(page, 200)
    page.wait_for_function(
        """(fit) => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return r.width > fit.width + 1 && r.height > fit.height + 1;
        }""",
        arg=before,
        timeout=5000,
    )
    after_in = image_rect(page)
    checks.check(
        "zoom-slider-in",
        after_in["width"] > before["width"] + 1 and after_in["height"] > before["height"] + 1,
        json.dumps({"before": before, "after": after_in}),
    )
    pre_pan = image_rect(page)
    pan_x = pre_pan["left"] + pre_pan["width"] / 2
    pan_y = pre_pan["top"] + pre_pan["height"] / 2
    page.mouse.move(pan_x, pan_y)
    page.mouse.down()
    page.mouse.move(pan_x + 40, pan_y + 25)
    page.mouse.up()
    post_pan = image_rect(page)
    moved_x = post_pan["left"] - pre_pan["left"]
    moved_y = post_pan["top"] - pre_pan["top"]
    pan_err = max(abs(moved_x - 40), abs(moved_y - 25))
    record["stillPan"] = {"errorPx": pan_err, "before": pre_pan, "after": post_pan}
    checks.check("click-hold-pan-zoomed", pan_err <= 2, json.dumps(record["stillPan"]))
    set_zoom_slider(page, 50)
    page.wait_for_function(
        """(fit) => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return r.width < fit.width - 1 && r.height < fit.height - 1;
        }""",
        arg=before,
        timeout=5000,
    )
    after_out = image_rect(page)
    checks.check(
        "zoom-slider-out-below-fit",
        after_out["width"] < before["width"] - 1 and after_out["height"] < before["height"] - 1,
        json.dumps({"fit": before, "out": after_out}),
    )

    page.keyboard.press("Control+0")
    page.wait_for_function(
        """(fit) => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return Math.abs(r.width - fit.width) < 3 && Math.abs(r.height - fit.height) < 3;
        }""",
        arg=before,
        timeout=5000,
    )
    after_fit = image_rect(page)
    record["ctrl0"] = after_fit
    checks.check(
        "ctrl-0-fit",
        abs(after_fit["width"] - before["width"]) < 3 and abs(after_fit["height"] - before["height"]) < 3,
        json.dumps({"fit": before, "after": after_fit}),
    )
    page.keyboard.press("Control+1")
    page.wait_for_function(
        """() => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return img && img.naturalWidth > 0 && Math.abs(r.width - img.naturalWidth) < 3;
        }""",
        timeout=5000,
    )
    after_100 = image_rect(page)
    record["ctrl1"] = after_100
    checks.check(
        "ctrl-1-100",
        abs(after_100["width"] - after_100["naturalWidth"]) < 3,
        json.dumps(after_100),
    )
    page.keyboard.press("Control+Equal")
    page.wait_for_function(
        """(prev) => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return r.width > prev.width + 1;
        }""",
        arg=after_100,
        timeout=5000,
    )
    after_plus = image_rect(page)
    checks.check(
        "ctrl-plus-zoom-in",
        after_plus["width"] > after_100["width"] + 1,
        json.dumps({"before": after_100, "after": after_plus}),
    )
    page.keyboard.press("Control+Minus")
    page.wait_for_function(
        """(prev) => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return r.width < prev.width - 1;
        }""",
        arg=after_plus,
        timeout=5000,
    )
    after_minus = image_rect(page)
    checks.check(
        "ctrl-minus-zoom-out",
        after_minus["width"] < after_plus["width"] - 1,
        json.dumps({"before": after_plus, "after": after_minus}),
    )
    page.keyboard.press("Control+0")

    page.locator("#viewer-rotate").click()
    rotation = page.evaluate("() => document.getElementById('viewer').dataset.rotation || ''")
    checks.check("rotate-90", rotation == "90", rotation)
    page.keyboard.press("Control+r")
    rotation_key = page.evaluate("() => document.getElementById('viewer').dataset.rotation || ''")
    checks.check("ctrl-r-rotate", rotation_key == "180", rotation_key)

    page.locator("#viewer-back").click()
    wait_viewer_closed(page)
    after_back = page.url
    record["backUrl"] = {"before": start_url, "after": after_back}
    checks.check("back-same-url", after_back == start_url, f"{start_url} -> {after_back}")
    checks.check("back-same-port", page.evaluate("() => location.port") == start_url.split(":")[-1].rstrip("/"), page.url)
    grid_photo = page.locator('#grid .cell[data-slot="grid"][data-filename="IMG_1042.jpg"]')
    checks.check("back-shows-grid", grid_photo.count() == 1, f"grid={grid_photo.count()}")

    page.keyboard.press("F5")
    page.wait_for_function(
        """() => {
          const viewer = document.getElementById('viewer');
          return viewer && !viewer.hidden && (viewer.dataset.slideshow || '') === '1';
        }""",
        timeout=10000,
    )
    show_state = page.evaluate(
        """() => {
          const viewer = document.getElementById('viewer');
          const app = window.libraryApp && window.libraryApp.slideshowState ? window.libraryApp.slideshowState() : {};
          return {
            hidden: viewer ? viewer.hidden : true,
            slideshow: viewer ? viewer.dataset.slideshow || '' : '',
            paused: viewer ? viewer.dataset.slideshowPaused || '' : '',
            intervalMs: app.intervalMs || 0,
            active: !!app.active,
          };
        }"""
    )
    record["slideshowStart"] = show_state
    checks.check(
        "f5-starts-slideshow",
        show_state.get("hidden") is False
        and show_state.get("slideshow") == "1"
        and show_state.get("active") is True
        and show_state.get("intervalMs") == 5000,
        json.dumps(show_state),
    )
    def media_key() -> str:
        return page.evaluate(
            """() => {
              const crumb = (document.getElementById('viewer-crumb') || {}).textContent || '';
              const img = document.getElementById('viewer-image');
              const video = document.getElementById('viewer-video');
              const imgSrc = img ? (img.getAttribute('src') || '') : '';
              const poster = video ? (video.getAttribute('poster') || '') : '';
              const videoSrc = video ? (video.getAttribute('src') || '') : '';
              return crumb + '|' + imgSrc + '|' + poster + '|' + videoSrc;
            }"""
        )

    start_slide = media_key()
    page.keyboard.press("Space")
    paused = page.evaluate("() => document.getElementById('viewer').dataset.slideshowPaused || ''")
    checks.check("space-pauses-slideshow", paused == "1", paused)
    page.evaluate("() => window.libraryApp && window.libraryApp.advanceSlideshow && window.libraryApp.advanceSlideshow()")
    paused_src = media_key()
    checks.check("paused-slideshow-holds", paused_src == start_slide, paused_src)
    page.keyboard.press("Space")
    resumed = page.evaluate("() => document.getElementById('viewer').dataset.slideshowPaused || ''")
    checks.check("space-resumes-slideshow", resumed == "0", resumed)
    page.evaluate("() => window.libraryApp && window.libraryApp.advanceSlideshow && window.libraryApp.advanceSlideshow()")
    page.wait_for_function(
        """(prev) => {
          const crumb = (document.getElementById('viewer-crumb') || {}).textContent || '';
          const img = document.getElementById('viewer-image');
          const video = document.getElementById('viewer-video');
          const imgSrc = img ? (img.getAttribute('src') || '') : '';
          const poster = video ? (video.getAttribute('poster') || '') : '';
          const videoSrc = video ? (video.getAttribute('src') || '') : '';
          return (crumb + '|' + imgSrc + '|' + poster + '|' + videoSrc) !== prev;
        }""",
        arg=start_slide,
        timeout=8000,
    )
    advanced = media_key()
    checks.check("slideshow-advances", advanced != start_slide, advanced)
    page.keyboard.press("Escape")
    after_esc_show = page.evaluate(
        """() => {
          const viewer = document.getElementById('viewer');
          return {
            hidden: viewer ? viewer.hidden : true,
            slideshow: viewer ? viewer.dataset.slideshow || '' : '',
          };
        }"""
    )
    checks.check(
        "esc-stops-slideshow",
        after_esc_show.get("hidden") is False and after_esc_show.get("slideshow") == "0",
        json.dumps(after_esc_show),
    )

    page.keyboard.press("f")
    full_on = page.evaluate("() => document.getElementById('viewer').dataset.fullscreen || ''")
    checks.check("f-enters-fullscreen", full_on == "1", full_on)
    page.keyboard.press("Escape")
    after_esc_full = page.evaluate(
        """() => {
          const viewer = document.getElementById('viewer');
          return {
            hidden: viewer ? viewer.hidden : true,
            fullscreen: viewer ? viewer.dataset.fullscreen || '' : '',
          };
        }"""
    )
    checks.check(
        "esc-exits-fullscreen",
        after_esc_full.get("hidden") is False and after_esc_full.get("fullscreen") == "0",
        json.dumps(after_esc_full),
    )
    page.wait_for_function("() => !document.fullscreenElement", timeout=5000)
    page.keyboard.press("Escape")
    wait_viewer_closed(page)
    checks.check("esc-then-closes-viewer", True)

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
          return r.width > 20 && r.height > 20;
        }""",
        timeout=8000,
    )
    video_fit = media_box(page, "#viewer-video")
    set_zoom_slider(page, 50)
    page.wait_for_function(
        """(fit) => {
          const video = document.getElementById('viewer-video');
          const r = video.getBoundingClientRect();
          return r.width < fit.width - 1 && r.height < fit.height - 1;
        }""",
        arg=video_fit,
        timeout=5000,
    )
    video_out = media_box(page, "#viewer-video")
    checks.check(
        "video-zoom-out",
        video_out["width"] < video_fit["width"] - 1 and video_out["height"] < video_fit["height"] - 1,
        json.dumps({"fit": video_fit, "out": video_out}),
    )
    set_zoom_slider(page, 200)
    page.wait_for_function(
        """(fit) => {
          const video = document.getElementById('viewer-video');
          const r = video.getBoundingClientRect();
          return r.width > fit.width + 1 && r.height > fit.height + 1;
        }""",
        arg=video_fit,
        timeout=5000,
    )
    pre_pan = media_box(page, "#viewer-video")
    pan_x = pre_pan["left"] + pre_pan["width"] / 2
    pan_y = pre_pan["top"] + pre_pan["height"] / 2
    page.evaluate(
        """([x1, y1, x2, y2]) => {
          const viewer = document.getElementById('viewer');
          const opts = (x, y, buttons) => ({
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
            button: 1,
            buttons: buttons,
          });
          viewer.dispatchEvent(new MouseEvent('mousedown', opts(x1, y1, 4)));
          window.dispatchEvent(new MouseEvent('mousemove', opts(x2, y2, 4)));
          window.dispatchEvent(new MouseEvent('mouseup', opts(x2, y2, 0)));
        }""",
        [pan_x, pan_y, pan_x + 40, pan_y + 25],
    )
    post_pan = media_box(page, "#viewer-video")
    moved_x = post_pan["left"] - pre_pan["left"]
    moved_y = post_pan["top"] - pre_pan["top"]
    pan_err = max(abs(moved_x - 40), abs(moved_y - 25))
    record["videoPan"] = {"errorPx": pan_err, "before": pre_pan, "after": post_pan}
    checks.check("video-pan-zoomed", pan_err <= 2, json.dumps(record["videoPan"]))
    hold_before = media_box(page, "#viewer-video")
    hold_x = hold_before["left"] + hold_before["width"] / 2
    hold_y = hold_before["top"] + hold_before["height"] / 2
    page.mouse.move(hold_x, hold_y)
    page.mouse.down()
    page.mouse.move(hold_x + 30, hold_y + 20)
    page.mouse.up()
    hold_after = media_box(page, "#viewer-video")
    hold_err = max(abs((hold_after["left"] - hold_before["left"]) - 30), abs((hold_after["top"] - hold_before["top"]) - 20))
    record["videoHoldPan"] = {"errorPx": hold_err, "before": hold_before, "after": hold_after}
    checks.check("video-click-hold-pan-zoomed", hold_err <= 2, json.dumps(record["videoHoldPan"]))

    page.locator("#play-preview").click()
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
    page.locator("#viewer-video").click()
    page.wait_for_function(
        "() => { const v = document.getElementById('viewer-video'); return v && v.paused === true; }",
        timeout=8000,
    )
    checks.check("play-preview-click-pauses", True)
    page.locator("#viewer-video").click()
    page.wait_for_function(
        "() => { const v = document.getElementById('viewer-video'); return v && v.paused === false; }",
        timeout=8000,
    )
    checks.check("play-preview-click-plays", True)

    page.locator("#viewer-back").click()
    wait_viewer_closed(page)
    checks.check("video-back-same-url", page.url == start_url, page.url)
    return record


def prove_empty_slideshow(page: Any, url: str, checks: Checks) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("#add-folder-btn", timeout=15000)
    page.keyboard.press("F5")
    page.wait_for_function(
        """() => {
          const el = document.getElementById('slideshow-empty');
          return el && !el.hidden && (el.textContent || '').trim() === 'Add photos first';
        }""",
        timeout=8000,
    )
    state = page.evaluate(
        """() => {
          const el = document.getElementById('slideshow-empty');
          const viewer = document.getElementById('viewer');
          return {
            text: el ? (el.textContent || '').trim() : '',
            hidden: el ? el.hidden : true,
            viewerHidden: viewer ? viewer.hidden : true,
          };
        }"""
    )
    checks.check("empty-slideshow-copy", state.get("text") == "Add photos first", json.dumps(state))
    checks.check("empty-slideshow-no-viewer", state.get("viewerHidden") is True, json.dumps(state))
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => { const el = document.getElementById('slideshow-empty'); return el && el.hidden; }",
        timeout=5000,
    )
    checks.check("empty-slideshow-esc", True)
    return state


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        folder = copy_s09_media(media_src, artifacts / "taste-viewer-media")
        isolated = fresh_root(artifacts / "taste-viewer-root")
        scanned = scan_library(isolated, folder, commands)
        checks.check("scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
        photo_path = folder / "a" / "IMG_1042.jpg"
        photo_hash_before = sha256_file(photo_path)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "no-exif.jpg", "clip.mp4"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks)
                unexpected = [message for message in errors if "status of 400" not in message]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                empty_root = fresh_root(artifacts / "empty-slideshow-root")
                empty_server, empty_url, empty_pids = start_owned(empty_root)
                try:
                    empty_page = browser.new_page(viewport={"width": 1280, "height": 720})
                    record["emptySlideshow"] = prove_empty_slideshow(empty_page, empty_url, checks)
                    empty_page.close()
                finally:
                    stop_owned(empty_server, extra_pids=empty_pids)
                browser.close()
            extra["viewer-chrome.json"] = str(artifacts / "viewer-chrome.json")
            (artifacts / "viewer-chrome.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            items = wait_catalog(url.rstrip("/"), ("IMG_1042.jpg",))
            photo = find_item(items, "IMG_1042.jpg") or {}
            checks.check("api-favorite-after-heart", photo.get("favorite") is True, json.dumps(photo.get("favorite")))
            fav_path = isolated / "catalog" / "favorites.json"
            checks.check("favorites-json", fav_path.is_file(), str(fav_path))
            if fav_path.is_file():
                fav = json.loads(fav_path.read_text(encoding="utf-8"))
                checks.check("favorites-has-photo", photo.get("id") in (fav.get("itemIds") or []), json.dumps(fav))
            off_status, off_body = request_json(
                url.rstrip("/") + f"/api/items/{photo.get('id')}/favorite",
                method="POST",
                body={"favorite": False},
                timeout=5,
            )
            checks.check("http-unfavorite", off_status == 200 and isinstance(off_body, dict) and off_body.get("favorite") is False, str(off_status))
        finally:
            stop_owned(server, extra_pids=pids)
        photo_hash_after = sha256_file(photo_path)
        checks.check("rotate-original-unchanged", photo_hash_before == photo_hash_after, photo_hash_after)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
        extra["viewer-chrome.png"] = str(artifacts / "viewer-chrome.png")
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("taste-viewer-runner", False, str(exc))
    return write_result("TASTE-VIEWER", "slice", checks, artifacts, commands, extra)


