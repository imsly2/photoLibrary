"""Windows Presentable Shell Must 6–10 proof. This log is not an F-id grade."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.s00 import Checks, PRODUCT_ROOT, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import load_items
from tests.qa.s03 import find_item
from tests.qa.s05 import start_isolated
from tests.qa.s08 import copy_rels, fresh_root, prepare_media, run_library, start_owned, write_result


def wait_catalog(base: str, names: tuple[str, ...] | list[str], timeout: float = 90) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            have = {item.get("filename") for item in payload}
            if all(name in have for name in names):
                return last
        time.sleep(0.25)
    return last


MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "a/clip.mp4",
    "a/near.jpg",
)


def _filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") for item in items]


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = artifacts / "api-root"
    folder = copy_rels(media_src, artifacts / "api-media", MEDIA_RELS)
    fresh_root(root)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    checks.check("scan-ok", scanned.returncode == 0, scanned.stderr[-200:])
    items = load_items(root)
    photo = find_item(items, "IMG_1042.jpg") or {}
    video = find_item(items, "clip.mp4") or {}
    near = find_item(items, "near.jpg") or {}
    checks.check("has-photo-video", bool(photo.get("id") and video.get("id")))
    jpeg_path = folder / "a" / "IMG_1042.jpg"
    before_hash = sha256_file(jpeg_path)

    server, url, owned = start_owned(root)
    try:
        status, photos = request_json(url.rstrip("/") + "/api/items?kind=photo,live", timeout=5)
        checks.check("kind-photos-http", status == 200, str(status))
        photo_names = set(_filenames(photos if isinstance(photos, list) else []))
        checks.check("kind-photos-has-jpeg", "IMG_1042.jpg" in photo_names, str(sorted(photo_names)))
        checks.check("kind-photos-no-video", "clip.mp4" not in photo_names, str(sorted(photo_names)))

        status, videos = request_json(url.rstrip("/") + "/api/items?kind=video", timeout=5)
        video_names = set(_filenames(videos if isinstance(videos, list) else []))
        checks.check("kind-video-only", video_names == {"clip.mp4"}, str(sorted(video_names)))

        status, bad = request_json(url.rstrip("/") + "/api/items?kind=album", timeout=5)
        checks.check(
            "kind-invalid",
            status == 400 and isinstance(bad, dict) and bad.get("error") == "invalid-argument",
            str(bad),
        )

        captured = str(photo.get("capturedAt") or "")
        year = captured[:4]
        month = captured[:7]
        day = captured[:10]
        status, by_year = request_json(url.rstrip("/") + f"/api/items?q={year}", timeout=5)
        year_names = set(_filenames(by_year if isinstance(by_year, list) else []))
        checks.check("q-year", status == 200 and "IMG_1042.jpg" in year_names, str(sorted(year_names)))
        status, by_month = request_json(url.rstrip("/") + f"/api/items?q={month}", timeout=5)
        month_names = set(_filenames(by_month if isinstance(by_month, list) else []))
        checks.check("q-month", status == 200 and "IMG_1042.jpg" in month_names, str(sorted(month_names)))
        status, by_day = request_json(url.rstrip("/") + f"/api/items?q={day}", timeout=5)
        day_names = set(_filenames(by_day if isinstance(by_day, list) else []))
        checks.check("q-day", status == 200 and "IMG_1042.jpg" in day_names, str(sorted(day_names)))

        fav = run_library(root, ["favorite", photo["id"], "--on"])
        checks.check("favorite-on", fav.returncode == 0, fav.stderr[-200:])
        status, hearts = request_json(url.rstrip("/") + "/api/items?favorite=1", timeout=5)
        heart_names = set(_filenames(hearts if isinstance(hearts, list) else []))
        checks.check("favorite-filter", heart_names == {"IMG_1042.jpg"}, str(sorted(heart_names)))

        removed = run_library(root, ["remove", near["id"]])
        checks.check("remove-cli", removed.returncode == 0, removed.stderr[-200:])
        after_remove = load_items(root)
        checks.check("remove-dropped", find_item(after_remove, "near.jpg") is None)
        near_path = folder / "a" / "near.jpg"
        checks.check("remove-bytes-stay", near_path.is_file(), str(near_path))

        status, missing = request_json(
            url.rstrip("/") + f"/api/items/{near['id']}/remove",
            method="POST",
            body={},
            timeout=5,
        )
        checks.check(
            "remove-unknown",
            status == 404 and isinstance(missing, dict) and missing.get("error") == "not-found",
            str(missing),
        )

        undone = run_library(root, ["undo"])
        checks.check("undo-remove", undone.returncode == 0, undone.stderr[-200:])
        restored = load_items(root)
        checks.check("undo-restored-near", find_item(restored, "near.jpg") is not None)

        clip_path = folder / "a" / "clip.mp4"
        clip_existed = clip_path.is_file()
        deleted = run_library(root, ["delete-file", video["id"]])
        payload = {}
        try:
            payload = json.loads(deleted.stdout)
        except Exception:
            payload = {}
        checks.check("delete-file-cli", deleted.returncode == 0, deleted.stderr[-200:])
        checks.check("delete-file-ok", payload.get("ok") is True, str(payload))
        after_del = load_items(root)
        checks.check("delete-file-dropped", find_item(after_del, "clip.mp4") is None)
        if payload.get("trashed") is True:
            checks.check("delete-file-trashed", not clip_path.is_file(), str(clip_path))
        else:
            checks.check("delete-file-bytes-if-untrashed", clip_existed, str(clip_path))

        undone_del = run_library(root, ["undo"])
        checks.check("undo-delete-file", undone_del.returncode == 0, undone_del.stderr[-200:])
        after_undo_del = load_items(root)
        checks.check("undo-delete-catalog", find_item(after_undo_del, "clip.mp4") is not None)
        checks.check("jpeg-untouched", sha256_file(jpeg_path) == before_hash, before_hash)

        status, update_get = request_json(url.rstrip("/") + "/api/update", timeout=10)
        checks.check("update-get", status == 200 and isinstance(update_get, dict), str(update_get))
        if isinstance(update_get, dict):
            record["updateGet"] = update_get.get("message")
        cli_update = run_library(root, ["update"], timeout=90)
        try:
            update_body = json.loads(cli_update.stdout)
        except Exception:
            update_body = {}
        checks.check("update-cli-json", isinstance(update_body, dict) and "message" in update_body, str(update_body))
        record["updateCli"] = update_body.get("message")
        record["updateAlready"] = update_body.get("alreadyCurrent")
    finally:
        stop_owned(server, extra_pids=owned)
    record["photoId"] = photo.get("id")
    return record


def prove_browser(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        checks.check("playwright-import", False, str(exc))
        return record
    checks.check("playwright-import", True)
    empty_root = artifacts / "empty-root"
    server, url, port, owned = start_isolated(empty_root)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => (document.querySelector('#empty-library p') || {}).textContent === 'No pictures yet'",
                timeout=10000,
            )
            empty = page.evaluate(
                """() => ({
                  text: (document.querySelector('#empty-library p') || {}).textContent || '',
                  add: !!document.getElementById('empty-add-folder'),
                  samples: document.querySelectorAll('#grid .cell').length
                })"""
            )
            record["empty"] = empty
            checks.check("empty-copy", empty.get("text") == "No pictures yet", str(empty))
            checks.check("empty-add-cta", empty.get("add") is True, str(empty))
            checks.check("empty-no-samples", empty.get("samples") == 0, str(empty))
            page.locator("#empty-add-folder").click()
            page.wait_for_function("() => document.getElementById('add-folder') && document.getElementById('add-folder').open", timeout=5000)
            checks.check("empty-add-opens", True)
            page.locator("#add-cancel").click()

            page.locator("#update-library").click()
            page.wait_for_function(
                "() => { const el = document.getElementById('update-status'); return el && !el.hidden && (el.textContent || '').indexOf('Updating') !== -1; }",
                timeout=3000,
            )
            updating = page.locator("#update-status").inner_text()
            record["updating"] = updating
            checks.check("update-progress", "Updating" in updating, updating)
            page.wait_for_function(
                "() => { const el = document.getElementById('update-status'); return el && el.getAttribute('data-ok') != null; }",
                timeout=60000,
            )
            done = page.locator("#update-status").inner_text()
            record["updateDone"] = done
            checks.check("update-sentence", bool(done.strip()), done)
            browser.close()
    finally:
        stop_owned(server, extra_pids=owned)

    folder = copy_rels(media_src, artifacts / "ui-media", MEDIA_RELS)
    root = artifacts / "ui-root"
    fresh_root(root)
    run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    items = load_items(root)
    photo = find_item(items, "IMG_1042.jpg") or {}
    if photo.get("id"):
        run_library(root, ["favorite", photo["id"], "--on"])
    server, url, owned = start_owned(root)
    try:
        wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "clip.mp4", "near.jpg"))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
            labels = page.evaluate(
                """() => ({
                  sort: Array.from(document.querySelectorAll('#sort-presentable option')).map((n) => n.textContent.trim()),
                  filters: [
                    (document.getElementById('filter-all') || {}).textContent,
                    (document.getElementById('filter-photos') || {}).textContent,
                    (document.getElementById('filter-videos') || {}).textContent,
                    (document.getElementById('filter-favorites') || {}).textContent
                  ],
                  sortValue: (document.getElementById('sort-presentable') || {}).value
                })"""
            )
            record["toolbar"] = labels
            checks.check(
                "sort-labels",
                labels.get("sort") == ["Newest", "Oldest", "Name", "Location"],
                str(labels.get("sort")),
            )
            checks.check("sort-default-newest", labels.get("sortValue") == "newest", str(labels.get("sortValue")))
            checks.check(
                "filter-labels",
                labels.get("filters") == ["All", "Photos", "Videos", "Favorites"],
                str(labels.get("filters")),
            )

            page.locator("#filter-photos").click()
            page.wait_for_function(
                """() => document.getElementById('grid').dataset.kind === 'photo,live'
                  && document.querySelectorAll('#grid .cell[data-slot="grid"]').length > 0
                  && !Array.from(document.querySelectorAll('#grid .cell[data-slot="grid"]')).some((n) => n.dataset.kind === 'video')""",
                timeout=8000,
            )
            checks.check("filter-photos-hides-video", True)

            page.locator("#filter-videos").click()
            page.wait_for_function(
                """() => document.getElementById('grid').dataset.kind === 'video'
                  && document.querySelectorAll('#grid .cell[data-slot="grid"]').length > 0
                  && Array.from(document.querySelectorAll('#grid .cell[data-slot="grid"]')).every((n) => n.dataset.kind === 'video')""",
                timeout=8000,
            )
            kinds = page.evaluate(
                "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map((n) => n.dataset.kind)"
            )
            checks.check("filter-videos-only", set(kinds) == {"video"}, str(kinds))

            page.locator("#filter-favorites").click()
            page.wait_for_function(
                """() => document.getElementById('grid').dataset.favorite === '1'
                  && Array.from(document.querySelectorAll('#grid .cell[data-slot="grid"]')).map((n) => n.dataset.filename).includes('IMG_1042.jpg')""",
                timeout=8000,
            )
            fav_names = page.evaluate(
                "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map((n) => n.dataset.filename)"
            )
            checks.check("filter-favorites", "IMG_1042.jpg" in fav_names, str(fav_names))

            page.locator("#filter-all").click()
            page.wait_for_function(
                "() => document.getElementById('grid').dataset.kind === '' && document.getElementById('grid').dataset.favorite === ''",
                timeout=8000,
            )

            page.locator("#sort-presentable").select_option("oldest")
            page.wait_for_function(
                "() => document.getElementById('sort').value === 'date' && document.getElementById('dir').value === 'asc'",
                timeout=8000,
            )
            checks.check("sort-oldest-maps", True)
            page.locator("#sort-presentable").select_option("name")
            page.wait_for_function(
                "() => document.getElementById('sort').value === 'name'",
                timeout=8000,
            )
            checks.check("sort-name-maps", True)
            page.locator("#sort-presentable").select_option("newest")

            page.fill("#search", "zzzz-no-such")
            page.wait_for_function(
                "() => (document.querySelector('#grid > p') || {}).textContent === 'No matches for zzzz-no-such'",
                timeout=8000,
            )
            empty_q = page.evaluate("() => (document.querySelector('#grid > p') || {}).textContent || ''")
            record["emptySearch"] = empty_q
            checks.check("empty-search-for", empty_q == "No matches for zzzz-no-such", empty_q)
            page.fill("#search", "")
            page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=10000)

            page.locator('[data-filename="IMG_1042.jpg"][data-slot="grid"]').click()
            page.wait_for_function(
                "() => { const v = document.getElementById('viewer'); return v && !v.hidden; }",
                timeout=8000,
            )
            page.keyboard.press("Delete")
            page.wait_for_function(
                "() => document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open",
                timeout=5000,
            )
            title = page.locator("#confirm-remove-title").inner_text()
            body = page.evaluate("() => (document.querySelector('#confirm-remove p') || {}).textContent || ''")
            record["removeConfirm"] = {"title": title, "body": body}
            checks.check("remove-confirm-title", title == "Remove from Library?", title)
            checks.check("remove-confirm-bytes", "stays on disk" in body.lower(), body)
            page.locator("#confirm-remove-cancel").click()
            page.wait_for_function(
                "() => !document.getElementById('confirm-remove').open",
                timeout=5000,
            )
            page.keyboard.press("Escape")
            page.wait_for_function(
                "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
                timeout=5000,
            )
            page.locator("#delete-file").click()
            page.wait_for_function(
                "() => document.getElementById('confirm-delete-file') && document.getElementById('confirm-delete-file').open",
                timeout=5000,
            )
            del_title = page.locator("#confirm-delete-title").inner_text()
            checks.check("delete-file-extra-confirm", "Delete this file from disk?" in del_title, del_title)
            page.locator("#confirm-delete-cancel").click()
            page.wait_for_function(
                "() => !document.getElementById('confirm-delete-file').open",
                timeout=5000,
            )

            page.locator('[data-filename="IMG_1042.jpg"][data-slot="grid"]').click()
            page.wait_for_function(
                "() => { const v = document.getElementById('viewer'); return v && !v.hidden; }",
                timeout=8000,
            )
            page.keyboard.press("Delete")
            page.wait_for_function(
                "() => document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open",
                timeout=5000,
            )
            page.locator("#confirm-remove-ok").click()
            page.wait_for_function(
                "() => !document.querySelector('[data-filename=\"IMG_1042.jpg\"]')",
                timeout=10000,
            )
            checks.check("remove-from-grid", True)
            jpeg_path = folder / "a" / "IMG_1042.jpg"
            checks.check("remove-left-bytes", jpeg_path.is_file(), str(jpeg_path))

            page.screenshot(path=str(artifacts / "shell.png"), full_page=False)
            browser.close()
    finally:
        stop_owned(server, extra_pids=owned)
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    commands = [
        "python -m library items --kind photo,live",
        "python -m library remove <id>",
        "python -m library delete-file <id>",
        "python -m library update",
    ]
    media_src = prepare_media(artifacts)
    api = prove_api(checks, artifacts, media_src)
    try:
        ui = prove_browser(checks, artifacts, media_src)
    except Exception as exc:
        checks.check("browser-proof", False, str(exc))
        ui = {"error": str(exc)}
    extra = {
        "api": json.dumps(api, default=str),
        "ui": json.dumps(ui, default=str),
        "launcher": str(PRODUCT_ROOT / "Update.bat"),
    }
    try:
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("no-pillow-server", False, str(exc))
    return write_result("TASTE-SHELL", "slice", checks, artifacts, commands, extra)
