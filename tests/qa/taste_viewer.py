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
            };
          }
          const fields = Array.from(document.querySelectorAll('#viewer-fields .annotate-field')).map(function (label) {
            return (label.textContent || '').replace(/\\s+/g, ' ').trim();
          });
          return {
            back: info('viewer-back'),
            prev: info('viewer-prev'),
            next: info('viewer-next'),
            zoomOut: info('viewer-zoom-out'),
            zoomIn: info('viewer-zoom-in'),
            rotate: info('viewer-rotate'),
            favorite: info('viewer-favorite'),
            reveal: info('reveal-original'),
            crumb: (document.getElementById('viewer-crumb') || {}).textContent || '',
            fields: fields,
            personPlaceholder: (document.getElementById('person-field') || {}).placeholder || '',
            placePlaceholder: (document.getElementById('place-field') || {}).placeholder || '',
            thingPlaceholder: (document.getElementById('thing-field') || {}).placeholder || '',
            href: location.href,
          };
        }"""
    )
    record["chrome"] = chrome
    for name in ("back", "prev", "next", "zoomOut", "zoomIn", "rotate", "favorite", "reveal"):
        node = chrome.get(name) or {}
        min_w = 24 if name == "favorite" else 8
        checks.check(
            f"{name}-visible",
            bool(node.get("present")) and not node.get("hidden") and (node.get("width") or 0) > min_w,
            json.dumps(node),
        )
    checks.check("back-label", chrome.get("back", {}).get("text") == "Back", json.dumps(chrome.get("back")))
    checks.check("prev-label", chrome.get("prev", {}).get("text") == "Previous", json.dumps(chrome.get("prev")))
    checks.check("next-label", chrome.get("next", {}).get("text") == "Next", json.dumps(chrome.get("next")))
    checks.check(
        "prev-or-next-enabled",
        (not chrome.get("prev", {}).get("disabled")) or (not chrome.get("next", {}).get("disabled")),
        json.dumps({"prev": chrome.get("prev"), "next": chrome.get("next")}),
    )
    checks.check("reveal-label", chrome.get("reveal", {}).get("text") == "Reveal in Explorer", json.dumps(chrome.get("reveal")))
    checks.check("heart-unfilled", chrome.get("favorite", {}).get("text") == "♡", json.dumps(chrome.get("favorite")))
    checks.check("crumb-filename", "IMG_1042.jpg" in (chrome.get("crumb") or ""), chrome.get("crumb"))
    field_blob = " ".join(chrome.get("fields") or [])
    checks.check("person-field-labeled", "Person" in field_blob and chrome.get("personPlaceholder") == "Person", field_blob)
    checks.check("place-field-labeled", "Place" in field_blob and chrome.get("placePlaceholder") == "Place", field_blob)
    checks.check("thing-field-labeled", "Thing" in field_blob and chrome.get("thingPlaceholder") == "Thing", field_blob)
    blank_inputs = page.evaluate(
        """() => Array.from(document.querySelectorAll('#viewer-fields input')).filter(function (input) {
          const label = input.closest('label');
          const named = (input.getAttribute('aria-label') || input.placeholder || (label && label.textContent) || '').trim();
          return !named;
        }).length"""
    )
    checks.check("no-mystery-inputs", blank_inputs == 0, str(blank_inputs))

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

    wait_viewer_original(page)
    page.wait_for_function(
        """() => {
          const btn = document.getElementById('open-original');
          return btn && btn.getAttribute('aria-pressed') === 'true'
            && (btn.textContent || '').trim() === 'Showing original';
        }""",
        timeout=8000,
    )
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
        "open-original-shows-state",
        original_state.get("text") == "Showing original"
        and original_state.get("pressed") == "true"
        and "which=original" in (original_state.get("originalSrc") or ""),
        json.dumps(original_state),
    )
    page.locator("#open-original").click()
    page.wait_for_function(
        """() => {
          const btn = document.getElementById('open-original');
          const original = document.getElementById('viewer-original');
          return btn && btn.getAttribute('aria-pressed') === 'false'
            && (btn.textContent || '').trim() === 'Open original'
            && original && original.hidden;
        }""",
        timeout=8000,
    )
    preview_kept = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("open-original-toggles-off", "which=preview" in preview_kept, preview_kept)
    page.locator("#open-original").click()
    page.wait_for_function(
        """() => {
          const original = document.getElementById('viewer-original');
          const btn = document.getElementById('open-original');
          return original && !original.hidden
            && (original.getAttribute('src') || '').indexOf('which=original') !== -1
            && btn && btn.getAttribute('aria-pressed') === 'true';
        }""",
        timeout=8000,
    )
    checks.check("open-original-toggles-on", True)

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
    page.locator("#viewer-zoom-in").click()
    after_in = image_rect(page)
    checks.check(
        "zoom-in-enlarges",
        after_in["width"] > before["width"] + 1 and after_in["height"] > before["height"] + 1,
        json.dumps({"before": before, "after": after_in}),
    )
    page.locator("#viewer-zoom-out").click()
    page.locator("#viewer-zoom-out").click()
    after_out = image_rect(page)
    checks.check(
        "zoom-out-below-fit",
        after_out["width"] < before["width"] - 1 and after_out["height"] < before["height"] - 1,
        json.dumps({"fit": before, "out": after_out}),
    )

    page.locator("#viewer-rotate").click()
    rotation = page.evaluate("() => document.getElementById('viewer').dataset.rotation || ''")
    checks.check("rotate-90", rotation == "90", rotation)

    page.locator("#viewer-back").click()
    wait_viewer_closed(page)
    after_back = page.url
    record["backUrl"] = {"before": start_url, "after": after_back}
    checks.check("back-same-url", after_back == start_url, f"{start_url} -> {after_back}")
    checks.check("back-same-port", page.evaluate("() => location.port") == start_url.split(":")[-1].rstrip("/"), page.url)
    checks.check("back-shows-grid", page.locator('[data-filename="IMG_1042.jpg"]').count() == 1)

    page.locator('[data-filename="clip.mp4"]').click()
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
    page.locator("#viewer-zoom-out").click()
    video_out = media_box(page, "#viewer-video")
    checks.check(
        "video-zoom-out",
        video_out["width"] < video_fit["width"] - 1 and video_out["height"] < video_fit["height"] - 1,
        json.dumps({"fit": video_fit, "out": video_out}),
    )
    page.locator("#viewer-zoom-in").click()
    page.locator("#viewer-zoom-in").click()
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

    page.locator("#play-preview").click()
    page.wait_for_function(
        """() => {
          const video = document.getElementById('viewer-video');
          if (!video) return false;
          const src = video.currentSrc || video.getAttribute('src') || '';
          return src.indexOf('which=proxy') !== -1 && video.paused === false;
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


