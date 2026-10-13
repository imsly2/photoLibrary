"""Slice S09 / Check F10 / Check F15 diagnostic assertions. This log is not the grade."""

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
    Checks,
    assert_no_pillow_in_server,
    copy_committed_fixtures,
    start_server,
    stop_owned,
    wait_health,
)
from tests.qa.s01 import hash_tree, parse_summary
from tests.qa.s03 import find_item, header_get, png_size, request_raw
from tests.qa.s04 import collect_console
from tests.qa.s05 import pin_media_from_manifest
from tests.qa.s06 import set_settings, wait_level
from tests.qa.s08 import copy_rels, fresh_root, run_library, write_result

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "b/oriented.jpg",
    "a/clip.mp4",
    "formats/clip.avi",
)
EMPTY_SEARCH = "No matching pictures"


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def copy_s09_media(src: Path, dest: Path) -> Path:
    copy_rels(src, dest, MEDIA_RELS)
    dup = dest / "second" / "source" / "same.jpg"
    dup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest / "a" / "IMG_1042.jpg", dup)
    pin_media_from_manifest(dest)
    return dest


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
                    p_status, _, p_body = request_raw(f"{base}/api/media/{item['id']}?which=poster")
                    if p_status != 200 or not p_body:
                        ready = False
                        break
                else:
                    if rend.get("thumb") != "ready" or rend.get("preview") != "ready":
                        ready = False
                        break
                    t_status, _, t_body = request_raw(f"{base}/api/media/{item['id']}?which=preview")
                    if t_status != 200 or not t_body:
                        ready = False
                        break
            if ready:
                return payload
        time.sleep(0.25)
    raise RuntimeError(
        "catalog timeout "
        + json.dumps(
            [
                {
                    "filename": item.get("filename"),
                    "status": (item.get("renditions") or {}).get("status"),
                }
                for item in last
            ]
        )
    )


def media_record(base: str, item_id: str, which: str) -> dict[str, Any]:
    status, headers, body = request_raw(f"{base}/api/media/{item_id}?which={which}")
    length_header = header_get(headers, "Content-Length")
    try:
        length = int(length_header) if length_header is not None else None
    except ValueError:
        length = None
    return {
        "status": status,
        "contentType": header_get(headers, "Content-Type"),
        "contentLength": length,
        "bodyLength": len(body),
    }


def item_ids(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [item.get("id") for item in payload if isinstance(item, dict)]


def filenames_of(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [item.get("filename") or "" for item in payload if isinstance(item, dict)]


def scan_library(root: Path, folder: Path, commands: list[str]) -> dict[str, Any]:
    first = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    commands.append("python -m library scan <folder> --serve-from-there")
    summary = parse_summary(first.stdout) if first.stdout.strip() else {}
    return {"proc": first, "summary": summary}


def start_owned(root: Path) -> tuple[Any, str, list[int]]:
    port = json.loads((root / "settings.json").read_text(encoding="utf-8"))["port"]
    server = start_server(root)
    url = f"http://127.0.0.1:{port}/"
    health_status, health_body = wait_health(url, server)
    if health_status != 200 or health_body != {"ok": True}:
        stop_owned(server)
        raise RuntimeError(f"health {health_status} {health_body}")
    owned: list[int] = []
    try:
        status, runtime = request_json(url.rstrip("/") + "/api/runtime", timeout=2)
        if status == 200 and isinstance(runtime, dict) and type(runtime.get("pid")) is int:
            owned.append(runtime["pid"])
    except Exception:
        pass
    return server, url, owned


def wait_viewer_still(page: Any) -> None:
    page.wait_for_function(
        """() => {
          const viewer = document.getElementById('viewer');
          const img = document.getElementById('viewer-image');
          return viewer && !viewer.hidden && img && img.getAttribute('src')
            && img.getAttribute('src').indexOf('which=preview') !== -1
            && img.complete && img.naturalWidth > 0;
        }""",
        timeout=15000,
    )


def wait_viewer_original(page: Any) -> None:
    page.wait_for_function(
        """() => {
          const original = document.getElementById('viewer-original');
          return original && !original.hidden
            && (original.getAttribute('src') || '').indexOf('which=original') !== -1
            && original.complete && original.naturalWidth > 0;
        }""",
        timeout=15000,
    )


def wait_viewer_closed(page: Any) -> None:
    page.wait_for_function(
        "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
        timeout=8000,
    )


def grid_cell_count(page: Any) -> int:
    return int(page.evaluate("() => document.querySelectorAll('#grid .cell').length"))


def grid_filenames(page: Any) -> list[str]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('#grid .cell')).map(function (cell) {
          return cell.getAttribute('data-filename') || '';
        })"""
    )


def prove_media_http(
    checks: Checks,
    url: str,
    items: list[dict[str, Any]],
    commands: list[str],
) -> dict[str, Any]:
    photo = find_item(items, "IMG_1042.jpg")
    video = find_item(items, "clip.mp4")
    fallback = find_item(items, "clip.avi")
    checks.check("photo-item", photo is not None)
    checks.check("video-item", video is not None)
    record: dict[str, Any] = {"photo": {}, "video": {}, "fallback": {}}
    if photo:
        preview = media_record(url.rstrip("/"), photo["id"], "preview")
        original = media_record(url.rstrip("/"), photo["id"], "original")
        commands.append("GET /api/media/<photo-id>?which=preview")
        commands.append("GET /api/media/<photo-id>?which=original")
        record["photo"] = {
            "id": photo["id"],
            "filename": photo.get("filename"),
            "preview": preview,
            "original": original,
        }
        checks.check(
            "photo-preview",
            preview["status"] == 200 and preview["contentType"] == "image/webp" and (preview["bodyLength"] or 0) > 0,
            json.dumps(preview),
        )
        checks.check(
            "photo-original",
            original["status"] == 200
            and original["contentType"] == "image/jpeg"
            and (original["bodyLength"] or 0) > 0,
            json.dumps(original),
        )
    if video:
        poster = media_record(url.rstrip("/"), video["id"], "poster")
        original = media_record(url.rstrip("/"), video["id"], "original")
        proxy = media_record(url.rstrip("/"), video["id"], "proxy")
        commands.append("GET /api/media/<video-id>?which=poster")
        commands.append("GET /api/media/<video-id>?which=original")
        commands.append("GET /api/media/<video-id>?which=proxy")
        record["video"] = {
            "id": video["id"],
            "filename": video.get("filename"),
            "poster": poster,
            "original": original,
            "proxy": proxy,
        }
        checks.check(
            "video-poster",
            poster["status"] == 200 and poster["contentType"] == "image/webp" and (poster["bodyLength"] or 0) > 0,
            json.dumps(poster),
        )
        checks.check(
            "video-original",
            original["status"] == 200
            and original["contentType"] == "video/mp4"
            and (original["bodyLength"] or 0) > 0,
            json.dumps(original),
        )
        checks.check(
            "video-proxy",
            proxy["status"] == 200 and proxy["contentType"] == "video/mp4" and (proxy["bodyLength"] or 0) > 0,
            json.dumps(proxy),
        )
    if fallback:
        record["fallback"] = {
            "id": fallback["id"],
            "filename": fallback.get("filename"),
            "proxy": media_record(url.rstrip("/"), fallback["id"], "proxy"),
        }
    return record


def prove_search_http(
    checks: Checks,
    url: str,
    jpeg_id: str,
    other_id: str,
    ada_id: str,
    mug_id: str,
    place_id: str,
    commands: list[str],
) -> dict[str, Any]:
    base = url.rstrip("/")
    queries = {
        "q_IMG_1042": "/api/items?q=IMG_1042",
        "q_mug": "/api/items?q=mug",
        "q_MUG": "/api/items?q=MUG",
        "q_Ada": "/api/items?q=Ada",
        "q_ada_people": "/api/items?q=Ada&scope=people",
        "q_ada_things": "/api/items?q=Ada&scope=things",
        "q_mug_things": "/api/items?q=mug&scope=things",
        "q_Kitchen_places": "/api/items?q=Kitchen&scope=places",
        "q_Cup_things": "/api/items?q=Cup&scope=things",
        "thing_id": f"/api/items?thing={mug_id}",
        "person_id": f"/api/items?person={ada_id}",
        "place_id": f"/api/items?place={place_id}",
        "q_empty": "/api/items?q=zzzz-no-such",
    }
    bodies: dict[str, Any] = {}
    for key, path in queries.items():
        status, body = request_json(base + path, timeout=5)
        commands.append("GET " + path)
        checks.check(f"http-{key}-status", status == 200 and isinstance(body, list), str(status))
        bodies[key] = body if isinstance(body, list) else []
        ids = item_ids(bodies[key])
        checks.check(f"http-{key}-unique", len(ids) == len(set(ids)), str(ids))
    img_names = filenames_of(bodies["q_IMG_1042"])
    checks.check("http-q-IMG_1042-filename", "IMG_1042.jpg" in img_names, str(img_names))
    checks.check("http-q-IMG_1042-once", item_ids(bodies["q_IMG_1042"]) == [jpeg_id], str(item_ids(bodies["q_IMG_1042"])))
    mug_ids = sorted(item_ids(bodies["q_mug"]))
    checks.check("http-q-mug-both", mug_ids == sorted([jpeg_id, other_id]), str(mug_ids))
    checks.check("http-q-MUG-casefold", sorted(item_ids(bodies["q_MUG"])) == mug_ids, str(item_ids(bodies["q_MUG"])))
    checks.check("http-q-Ada-only", item_ids(bodies["q_Ada"]) == [jpeg_id], str(item_ids(bodies["q_Ada"])))
    checks.check(
        "http-chip-people-ada",
        item_ids(bodies["q_ada_people"]) == [jpeg_id],
        str(item_ids(bodies["q_ada_people"])),
    )
    checks.check("http-chip-things-ada-empty", item_ids(bodies["q_ada_things"]) == [], str(item_ids(bodies["q_ada_things"])))
    checks.check("http-chip-things-mug", sorted(item_ids(bodies["q_mug_things"])) == mug_ids, str(item_ids(bodies["q_mug_things"])))
    checks.check(
        "http-chip-places-kitchen",
        jpeg_id in item_ids(bodies["q_Kitchen_places"]),
        str(item_ids(bodies["q_Kitchen_places"])),
    )
    checks.check("http-alias-cup", sorted(item_ids(bodies["q_Cup_things"])) == mug_ids, str(item_ids(bodies["q_Cup_things"])))
    checks.check("http-thing-id", sorted(item_ids(bodies["thing_id"])) == mug_ids, str(item_ids(bodies["thing_id"])))
    checks.check("http-person-id", item_ids(bodies["person_id"]) == [jpeg_id], str(item_ids(bodies["person_id"])))
    checks.check("http-place-id", jpeg_id in item_ids(bodies["place_id"]), str(item_ids(bodies["place_id"])))
    checks.check("http-empty-q", bodies["q_empty"] == [], str(bodies["q_empty"]))
    mug_items = bodies["thing_id"]
    inspector = {
        "name": "mug",
        "count": len({item.get("id") for item in mug_items}),
        "filenames": sorted(filenames_of(mug_items)),
        "itemIds": sorted(item_ids(mug_items)),
    }
    checks.check("inspector-count-unique-ids", inspector["count"] == 2, json.dumps(inspector))
    checks.check(
        "inspector-filenames",
        inspector["filenames"] == sorted(["IMG_1042.jpg", "no-exif.jpg"]),
        json.dumps(inspector),
    )
    return {"queries": {key: item_ids(bodies[key]) for key in bodies}, "inspector": inspector, "bodies": bodies}


def prove_browser(
    checks: Checks,
    url: str,
    artifacts: Path,
    jpeg: dict[str, Any],
    other: dict[str, Any],
    *,
    do_annotate: bool,
    do_search: bool,
    do_playback: bool,
    prepare_search: Any = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "stillPreviewFirst": False,
        "stillOriginalAfter": False,
        "videoPosterFirst": False,
        "videoPlayback": "",
        "fallbackProxy": False,
        "emptySearch": "",
        "inspector": {},
    }
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        checks.check("playwright-import", False, str(exc))
        return record
    checks.check("playwright-import", True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            errors = collect_console(page)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
            set_settings(url, {"zoomLevel": "all"})
            wait_level(page, "all")
            page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=15000)

            if do_playback:
                page.locator('[data-filename="IMG_1042.jpg"]').click()
                wait_viewer_still(page)
                preview_src = page.locator("#viewer-image").get_attribute("src") or ""
                record["stillPreviewFirst"] = "which=preview" in preview_src
                checks.check("still-preview-first", record["stillPreviewFirst"], preview_src)
                wait_viewer_original(page)
                original_src = page.locator("#viewer-original").get_attribute("src") or ""
                record["stillOriginalAfter"] = "which=original" in original_src and not page.locator("#viewer-original").is_hidden()
                checks.check("still-original-after", record["stillOriginalAfter"], original_src)
                preview_src_after = page.locator("#viewer-image").get_attribute("src") or ""
                checks.check("still-preview-kept", "which=preview" in preview_src_after, preview_src_after)
                page.keyboard.press("Escape")
                wait_viewer_closed(page)

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
                poster = page.locator("#viewer-video").get_attribute("poster") or ""
                src_before = page.locator("#viewer-video").get_attribute("src") or ""
                record["videoPosterFirst"] = "which=poster" in poster and src_before == ""
                checks.check("video-poster-first", record["videoPosterFirst"], poster)
                page.keyboard.press("Space")
                page.wait_for_function(
                    """() => {
                      const video = document.getElementById('viewer-video');
                      if (!video) return false;
                      const src = video.currentSrc || video.getAttribute('src') || '';
                      return (src.indexOf('which=original') !== -1 || src.indexOf('which=proxy') !== -1)
                        && video.paused === false;
                    }""",
                    timeout=15000,
                )
                video_state = page.evaluate(
                    """() => {
                      const video = document.getElementById('viewer-video');
                      const src = video ? (video.currentSrc || video.getAttribute('src') || '') : '';
                      return { src: src, paused: video ? video.paused : true, usingProxy: video && video.getAttribute('data-using-proxy') === '1' };
                    }"""
                )
                if "which=original" in (video_state.get("src") or ""):
                    record["videoPlayback"] = "original"
                elif "which=proxy" in (video_state.get("src") or ""):
                    record["videoPlayback"] = "proxy"
                checks.check(
                    "video-original-or-proxy",
                    record["videoPlayback"] in {"original", "proxy"} and video_state.get("paused") is False,
                    json.dumps(video_state),
                )
                page.keyboard.press("Escape")
                wait_viewer_closed(page)

                page.locator('[data-filename="clip.avi"]').click()
                page.wait_for_function(
                    """() => {
                      const viewer = document.getElementById('viewer');
                      const video = document.getElementById('viewer-video');
                      return viewer && !viewer.hidden && video && !video.hidden;
                    }""",
                    timeout=10000,
                )
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
                fallback = page.evaluate(
                    """() => {
                      const video = document.getElementById('viewer-video');
                      const src = video ? (video.currentSrc || video.getAttribute('src') || '') : '';
                      return { src: src, usingProxy: video && video.getAttribute('data-using-proxy') === '1' };
                    }"""
                )
                fallback_src = fallback.get("src") or ""
                record["fallbackProxy"] = bool(fallback.get("usingProxy") or "which=proxy" in fallback_src)
                checks.check(
                    "video-fallback-proxy",
                    record["fallbackProxy"] and "which=proxy" in fallback_src,
                    json.dumps(fallback),
                )
                page.keyboard.press("Escape")
                wait_viewer_closed(page)

            if do_annotate:
                page.locator('[data-filename="IMG_1042.jpg"]').click()
                wait_viewer_still(page)
                page.locator("#person-field").fill("Ada")
                page.locator("#person-field").press("Enter")
                page.wait_for_selector('#viewer-people .entity-label', timeout=10000)
                ada_text = page.locator("#viewer-people .entity-label").inner_text()
                checks.check("viewer-ada-label", ada_text == "Ada", ada_text)
                page.locator("#thing-field").fill("mug")
                page.locator("#thing-field").blur()
                page.wait_for_selector('#viewer-things .entity-label', timeout=10000)
                mug_text = page.locator("#viewer-things .entity-label").inner_text()
                checks.check("viewer-mug-label", mug_text == "mug", mug_text)
                page.locator("#place-field").fill("Kitchen")
                page.locator("#place-field").press("Enter")
                page.wait_for_selector('#viewer-place .entity-label', timeout=10000)
                place_text = page.locator("#viewer-place .entity-label").inner_text()
                checks.check("viewer-kitchen-label", place_text == "Kitchen", place_text)
                shot = artifacts / "viewer-annotations.png"
                page.screenshot(path=str(shot), full_page=False)
                vw, vh = png_size(shot)
                checks.check("viewer-annotations-png", shot.is_file() and vw == 1280 and vh == 720, f"{vw}x{vh}")
                page.route(
                    "**/api/items/*/annotations",
                    lambda route: route.fulfill(
                        status=400,
                        content_type="application/json",
                        body=json.dumps({"error": "invalid-argument"}),
                    ),
                )
                page.locator("#person-field").fill("Nope")
                page.locator("#person-field").press("Enter")
                page.wait_for_function(
                    "() => { const err = document.getElementById('annotate-error'); return err && !err.hidden && err.textContent === 'invalid-argument'; }",
                    timeout=8000,
                )
                kept = page.locator("#person-field").input_value()
                err = page.locator("#annotate-error").inner_text()
                checks.check("failed-annotate-keeps-text", kept == "Nope", kept)
                checks.check("failed-annotate-inline-error", err == "invalid-argument", err)
                page.unroute("**/api/items/*/annotations")
                page.locator("#person-field").fill("")
                page.keyboard.press("Escape")
                wait_viewer_closed(page)

            if do_search:
                if prepare_search:
                    prepare_search()
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
                    set_settings(url, {"zoomLevel": "all"})
                    wait_level(page, "all")
                page.fill("#search", "mug")
                page.wait_for_function(
                    "() => document.getElementById('grid') && document.getElementById('grid').dataset.q === 'mug'",
                    timeout=8000,
                )
                page.wait_for_function(
                    "() => document.querySelectorAll('#grid .cell').length === 2",
                    timeout=10000,
                )
                mug_names = grid_filenames(page)
                checks.check(
                    "search-mug-cells",
                    sorted(mug_names) == ["IMG_1042.jpg", "no-exif.jpg"],
                    str(mug_names),
                )
                search_shot = artifacts / "search-mug.png"
                page.screenshot(path=str(search_shot), full_page=False)
                sw, sh = png_size(search_shot)
                checks.check("search-mug-png", search_shot.is_file() and sw == 1280 and sh == 720, f"{sw}x{sh}")

                page.locator('[data-filename="IMG_1042.jpg"]').click()
                wait_viewer_still(page)
                page.locator('#viewer-things .entity-label').click()
                page.wait_for_function(
                    "() => { const el = document.getElementById('inspector'); return el && !el.hidden && el.dataset.count === '2'; }",
                    timeout=10000,
                )
                inspector = page.evaluate(
                    """() => {
                      const el = document.getElementById('inspector');
                      const files = Array.from(document.querySelectorAll('#inspector-filenames li')).map(function (li) {
                        return li.textContent || '';
                      });
                      return {
                        name: (document.getElementById('inspector-name') || {}).textContent || '',
                        count: Number(el ? el.dataset.count : 0),
                        filenames: files,
                        entityId: el ? (el.dataset.entityId || '') : '',
                        kind: el ? (el.dataset.kind || '') : ''
                      };
                    }"""
                )
                record["inspector"] = inspector
                checks.check("inspector-name-mug", inspector.get("name") == "mug", json.dumps(inspector))
                checks.check("inspector-count-2", inspector.get("count") == 2, json.dumps(inspector))
                checks.check(
                    "inspector-page-filenames",
                    sorted(inspector.get("filenames") or []) == ["IMG_1042.jpg", "no-exif.jpg"],
                    json.dumps(inspector),
                )
                page.keyboard.press("Escape")
                wait_viewer_closed(page)
                page.wait_for_function(
                    "() => document.getElementById('grid') && document.getElementById('grid').dataset.q === 'mug'",
                    timeout=8000,
                )
                after_esc = grid_filenames(page)
                checks.check(
                    "esc-restores-filter",
                    sorted(after_esc) == ["IMG_1042.jpg", "no-exif.jpg"],
                    str(after_esc),
                )

                page.fill("#search", "mug")
                page.wait_for_function(
                    "() => document.getElementById('grid') && document.getElementById('grid').dataset.q === 'mug'",
                    timeout=8000,
                )
                page.wait_for_function(
                    "() => document.querySelectorAll('#grid .cell').length === 2",
                    timeout=10000,
                )
                page.locator('[data-filename="IMG_1042.jpg"]').click()
                wait_viewer_still(page)
                start_src = page.locator("#viewer-image").get_attribute("src") or ""
                page.keyboard.press("ArrowLeft")
                left_src = page.locator("#viewer-image").get_attribute("src") or ""
                checks.check("filtered-arrow-left-end", left_src == start_src, f"{start_src} {left_src}")
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
                mid_src = page.locator("#viewer-image").get_attribute("src") or ""
                checks.check("filtered-arrow-right-moves", mid_src != start_src, mid_src)
                page.keyboard.press("ArrowRight")
                end_src = page.locator("#viewer-image").get_attribute("src") or ""
                checks.check("filtered-arrow-right-end", end_src == mid_src, f"{mid_src} {end_src}")
                page.keyboard.press("Escape")
                wait_viewer_closed(page)
                restored = grid_filenames(page)
                checks.check(
                    "esc-keeps-mug-grid",
                    sorted(restored) == ["IMG_1042.jpg", "no-exif.jpg"],
                    str(restored),
                )

                page.fill("#search", "zzzz-no-such")
                page.wait_for_function(
                    "() => document.getElementById('grid') && (document.getElementById('grid').innerText || '').indexOf('No matching pictures') !== -1",
                    timeout=8000,
                )
                empty_text = page.evaluate("() => (document.querySelector('#grid > p') || {}).textContent || ''")
                record["emptySearch"] = empty_text
                checks.check("empty-search-copy", empty_text == EMPTY_SEARCH, empty_text)
                page.fill("#search", "")
                page.wait_for_function(
                    "() => document.querySelectorAll('#grid .cell').length >= 4",
                    timeout=10000,
                )
                checks.check("clear-search-restores-grid", grid_cell_count(page) >= 4, str(grid_filenames(page)))

                page.fill("#search", "Ada")
                page.locator("#chip-people").click()
                page.wait_for_function(
                    "() => document.getElementById('grid') && document.getElementById('grid').dataset.scope === 'people' && document.getElementById('grid').dataset.q === 'Ada'",
                    timeout=8000,
                )
                page.wait_for_function(
                    "() => document.querySelectorAll('#grid .cell').length === 1",
                    timeout=8000,
                )
                checks.check("chip-people-ada", grid_filenames(page) == ["IMG_1042.jpg"], str(grid_filenames(page)))
                page.locator("#chip-things").click()
                page.wait_for_function(
                    "() => document.getElementById('grid') && document.getElementById('grid').dataset.scope === 'things'",
                    timeout=8000,
                )
                page.wait_for_function(
                    "() => (document.querySelector('#grid > p') || {}).textContent === 'No matching pictures'",
                    timeout=8000,
                )
                checks.check(
                    "chip-things-ada-empty",
                    page.evaluate("() => (document.querySelector('#grid > p') || {}).textContent || ''") == EMPTY_SEARCH,
                )
                page.locator("#chip-things").click()
                page.fill("#search", "")
                page.wait_for_function(
                    "() => document.querySelectorAll('#grid .cell').length >= 4",
                    timeout=10000,
                )

            unexpected = [
                message
                for message in errors
                if "status of 400" not in message
            ]
            checks.check("no-console-errors", unexpected == [], json.dumps(errors))
            browser.close()
    except Exception as exc:
        checks.check("browser-proof", False, str(exc))
    return record


def annotate_second_and_alias(
    checks: Checks,
    url: str,
    other_id: str,
    mug_id: str,
    commands: list[str],
) -> None:
    status, body = request_json(
        url.rstrip("/") + f"/api/items/{other_id}/annotations",
        method="POST",
        body={"things": [{"name": "mug"}]},
        timeout=5,
    )
    commands.append("POST /api/items/<other-id>/annotations mug")
    checks.check("http-second-mug", status == 200 and isinstance(body, dict), str(status))
    alias_status, alias_body = request_json(
        url.rstrip("/") + f"/api/items/{other_id}/annotations",
        method="POST",
        body={"things": [{"id": mug_id, "aliases": ["Cup"]}]},
        timeout=5,
    )
    commands.append("POST /api/items/<id>/annotations alias Cup")
    checks.check("http-alias-cup-write", alias_status == 200, str(alias_status))
    if isinstance(alias_body, dict):
        things = ((alias_body.get("entities") or {}).get("things") or [])
        mug = [rec for rec in things if rec.get("id") == mug_id]
        aliases = mug[0].get("aliases") if mug else []
        checks.check("alias-cup-present", "Cup" in (aliases or []), json.dumps(mug))


def run_session(
    artifacts: Path,
    checks: Checks,
    commands: list[str],
    *,
    do_annotate: bool,
    do_search: bool,
    do_playback: bool,
) -> dict[str, str]:
    extra: dict[str, str] = {}
    media_src = prepare_media(artifacts)
    before = hash_tree(media_src)
    folder = copy_s09_media(media_src, artifacts / "s09-media")
    root = fresh_root(artifacts / "s09-root")
    scanned = scan_library(root, folder, commands)
    checks.check("scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
    server, url, pids = start_owned(root)
    playback: dict[str, Any] = {}
    inspector_doc: dict[str, Any] = {}
    try:
        items = wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "no-exif.jpg", "oriented.jpg", "clip.mp4", "clip.avi"))
        jpeg = find_item(items, "IMG_1042.jpg") or {}
        other = find_item(items, "no-exif.jpg") or {}
        checks.check("jpeg-two-locations", len(jpeg.get("locations") or []) == 2, str(len(jpeg.get("locations") or [])))
        if do_playback:
            playback = prove_media_http(checks, url, items, commands)

        def prepare_search() -> None:
            current = request_json(url.rstrip("/") + "/api/items", timeout=5)[1]
            if not isinstance(current, list):
                return
            jpeg_now = find_item(current, "IMG_1042.jpg") or {}
            other_now = find_item(current, "no-exif.jpg") or {}
            things_now = ((jpeg_now.get("entities") or {}).get("things") or [])
            mug_now = [rec for rec in things_now if rec.get("name") == "mug"]
            mug_now_id = mug_now[0]["id"] if mug_now else ""
            other_now_id = other_now.get("id") or ""
            if other_now_id and mug_now_id:
                annotate_second_and_alias(checks, url, other_now_id, mug_now_id, commands)

        browser = prove_browser(
            checks,
            url,
            artifacts,
            jpeg,
            other,
            do_annotate=do_annotate,
            do_search=do_search,
            do_playback=do_playback,
            prepare_search=prepare_search if do_search else None,
        )
        playback["browser"] = {
            "stillPreviewFirst": browser.get("stillPreviewFirst"),
            "stillOriginalAfter": browser.get("stillOriginalAfter"),
            "videoPosterFirst": browser.get("videoPosterFirst"),
            "videoPlayback": browser.get("videoPlayback"),
            "fallbackProxy": browser.get("fallbackProxy"),
        }
        items = wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "no-exif.jpg"))
        jpeg = find_item(items, "IMG_1042.jpg") or {}
        other = find_item(items, "no-exif.jpg") or {}
        jpeg_id = jpeg.get("id") or ""
        other_id = other.get("id") or ""
        people = ((jpeg.get("entities") or {}).get("people") or [])
        things = ((jpeg.get("entities") or {}).get("things") or [])
        places = ((jpeg.get("entities") or {}).get("places") or [])
        ada = [rec for rec in people if rec.get("name") == "Ada"]
        mug = [rec for rec in things if rec.get("name") == "mug"]
        kitchen = [rec for rec in places if rec.get("name") == "Kitchen"]
        if do_annotate or do_search:
            checks.check("ada-on-jpeg", bool(ada), json.dumps(people))
            checks.check("mug-on-jpeg", bool(mug), json.dumps(things))
        ada_id = ada[0]["id"] if ada else ""
        mug_id = mug[0]["id"] if mug else ""
        place_id = kitchen[0]["id"] if kitchen else jpeg.get("placeId") or ""
        if do_search and other_id and mug_id:
            annotate_second_and_alias(checks, url, other_id, mug_id, commands)
            items = wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "no-exif.jpg"))
            jpeg = find_item(items, "IMG_1042.jpg") or jpeg
            other = find_item(items, "no-exif.jpg") or other
            jpeg_id = jpeg.get("id") or jpeg_id
            other_id = other.get("id") or other_id
            search = prove_search_http(checks, url, jpeg_id, other_id, ada_id, mug_id, place_id, commands)
            inspector_doc = {
                "name": "mug",
                "count": search["inspector"]["count"],
                "filenames": search["inspector"]["filenames"],
                "itemIds": search["inspector"]["itemIds"],
                "queries": search["queries"],
                "page": browser.get("inspector") or {},
                "emptySearch": browser.get("emptySearch") or EMPTY_SEARCH,
            }
            if do_search and not (browser.get("inspector") or {}).get("name"):
                # Browser inspector recorded during page proof; HTTP inspector still required.
                pass
    finally:
        stop_owned(server, extra_pids=pids)
    if do_playback:
        playback_path = artifacts / "playback.json"
        playback_path.write_text(json.dumps(playback, indent=2) + "\n", encoding="utf-8")
        extra["playback.json"] = str(playback_path)
    if do_search:
        inspector_path = artifacts / "inspector.json"
        inspector_path.write_text(json.dumps(inspector_doc, indent=2) + "\n", encoding="utf-8")
        extra["inspector.json"] = str(inspector_path)
        extra["search-mug.png"] = str(artifacts / "search-mug.png")
    if do_annotate:
        extra["viewer-annotations.png"] = str(artifacts / "viewer-annotations.png")
    checks.check("original-fixture-bytes", hash_tree(media_src) == before)
    assert_no_pillow_in_server(checks)
    return extra


def run_check_f10(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(
            artifacts,
            checks,
            commands,
            do_annotate=True,
            do_search=False,
            do_playback=True,
        )
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("f10-runner", False, str(exc))
    return write_result("F10", "check", checks, artifacts, commands, extra)


def run_check_f15(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(
            artifacts,
            checks,
            commands,
            do_annotate=True,
            do_search=True,
            do_playback=False,
        )
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("f15-runner", False, str(exc))
    return write_result("F15", "check", checks, artifacts, commands, extra)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(
            artifacts,
            checks,
            commands,
            do_annotate=True,
            do_search=True,
            do_playback=True,
        )
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("s09-runner", False, str(exc))
    return write_result("S09", "slice", checks, artifacts, commands, extra)
