"""Batch favorite / remove on a multi-selection. Not an F-id grade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import collect_console, wait_catalog

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/no-exif.jpg",
    "a/clip.mp4",
)

I18N = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "i18n.js"


def filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") or "" for item in items]


def item_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("filename") or "": item for item in items}


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    i18n_text = I18N.read_text(encoding="utf-8")
    checks.check("i18n-selected-en", "selectedCount: \"{n} selected\"" in i18n_text)
    checks.check("i18n-selected-zh", "selectedCount: \"已选 {n} 项\"" in i18n_text)
    checks.check("i18n-clear-zh", "clearSelection: \"清除选择\"" in i18n_text)
    checks.check("i18n-remove-many-zh", "removeTitleMany: \"从图库中移除 {n} 项？\"" in i18n_text)

    root = fresh_root(artifacts / "api-root")
    folder = artifacts / "api-media"
    copy_rels(media_src, folder, MEDIA_RELS)
    before_media = hash_tree(folder)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    checks.check("scan-ok", scanned.returncode == 0, scanned.stderr[-200:])
    items = item_map(load_items(root))
    need = ("IMG_1042.jpg", "near.jpg", "no-exif.jpg", "clip.mp4")
    checks.check("has-four", all(items.get(name) for name in need), json.dumps(sorted(items)))
    photo_a = items["IMG_1042.jpg"]["id"]
    photo_b = items["near.jpg"]["id"]
    photo_c = items["no-exif.jpg"]["id"]
    video = items["clip.mp4"]["id"]
    record["ids"] = {
        "IMG_1042.jpg": photo_a,
        "near.jpg": photo_b,
        "no-exif.jpg": photo_c,
        "clip.mp4": video,
    }

    one = run_library(root, ["favorite", photo_a, "--on"])
    checks.check("single-favorite-cli", one.returncode == 0, one.stderr[-200:])
    one_body = json.loads(one.stdout)
    checks.check("single-favorite-true", one_body.get("favorite") is True, json.dumps(one_body.get("favorite")))

    batch = run_library(root, ["favorite", photo_a, photo_b, video, "--on"])
    checks.check("batch-favorite-cli", batch.returncode == 0, batch.stderr[-200:])
    batch_body = json.loads(batch.stdout)
    batch_items = batch_body.get("items") or []
    checks.check("batch-favorite-count", len(batch_items) == 3, json.dumps(batch_body))
    checks.check(
        "batch-favorite-all-true",
        all(row.get("favorite") is True for row in batch_items),
        json.dumps([row.get("favorite") for row in batch_items]),
    )
    listed = item_map(json.loads(run_library(root, ["items"]).stdout))
    checks.check(
        "cli-items-hearted",
        listed["IMG_1042.jpg"].get("favorite") is True
        and listed["near.jpg"].get("favorite") is True
        and listed["clip.mp4"].get("favorite") is True,
        json.dumps({name: listed[name].get("favorite") for name in need}),
    )

    server, url, pids = start_owned(root)
    try:
        base = url.rstrip("/")
        status, payload = request_json(
            base + "/api/items/favorite",
            method="POST",
            body={"itemIds": [photo_a, photo_b, video], "favorite": True},
            timeout=8,
        )
        checks.check("http-favorite-200", status == 200, json.dumps(payload))
        http_items = (payload or {}).get("items") or []
        checks.check(
            "http-favorite-all-true",
            status == 200 and len(http_items) == 3 and all(row.get("favorite") is True for row in http_items),
            json.dumps(payload),
        )
        status, listed = request_json(base + "/api/items", timeout=5)
        by_name = item_map(listed if isinstance(listed, list) else [])
        checks.check(
            "http-get-hearted",
            status == 200
            and by_name["IMG_1042.jpg"].get("favorite") is True
            and by_name["near.jpg"].get("favorite") is True
            and by_name["clip.mp4"].get("favorite") is True,
            json.dumps({name: by_name.get(name, {}).get("favorite") for name in need}),
        )

        status, payload = request_json(
            base + "/api/items/favorite",
            method="POST",
            body={"itemIds": [photo_a, photo_b, video], "favorite": False},
            timeout=8,
        )
        checks.check(
            "http-unfavorite-all-false",
            status == 200 and all(row.get("favorite") is False for row in (payload or {}).get("items") or []),
            json.dumps(payload),
        )

        status, payload = request_json(
            base + "/api/items/favorite",
            method="POST",
            body={"itemIds": [photo_a], "favorite": True},
            timeout=8,
        )
        checks.check(
            "http-one-via-batch",
            status == 200 and ((payload or {}).get("items") or [{}])[0].get("favorite") is True,
            json.dumps(payload),
        )
        status, payload = request_json(
            base + "/api/items/" + photo_a + "/favorite",
            method="PUT",
            body={"favorite": False},
            timeout=8,
        )
        checks.check("http-single-put-stays", status == 200 and payload.get("favorite") is False, json.dumps(payload))

        status, payload = request_json(base + "/api/items/favorite", method="POST", body={}, timeout=5)
        checks.check(
            "http-favorite-empty",
            status == 400 and isinstance(payload, dict) and payload.get("error") == "invalid-argument",
            json.dumps(payload),
        )
        status, payload = request_json(
            base + "/api/items/favorite",
            method="POST",
            body={"itemIds": ["missing-id"], "favorite": True},
            timeout=5,
        )
        checks.check(
            "http-favorite-unknown",
            status == 404 and isinstance(payload, dict) and payload.get("error") == "not-found",
            json.dumps(payload),
        )

        status, payload = request_json(base + "/api/items/remove", method="POST", body={"itemIds": []}, timeout=5)
        checks.check(
            "http-remove-empty",
            status == 400 and isinstance(payload, dict) and payload.get("error") == "invalid-argument",
            json.dumps(payload),
        )
        status, payload = request_json(
            base + "/api/items/remove",
            method="POST",
            body={"itemIds": ["missing-id"]},
            timeout=5,
        )
        checks.check(
            "http-remove-unknown",
            status == 404 and isinstance(payload, dict) and payload.get("error") == "not-found",
            json.dumps(payload),
        )
        status, still = request_json(base + "/api/items", timeout=5)
        still_names = set(filenames(still if isinstance(still, list) else []))
        checks.check(
            "unknown-remove-leaves-catalog",
            status == 200 and still_names >= set(need),
            json.dumps(sorted(still_names)),
        )

        status, payload = request_json(
            base + "/api/items/remove",
            method="POST",
            body={"itemIds": [photo_a, video]},
            timeout=8,
        )
        checks.check("http-remove-200", status == 200 and payload.get("ok") is True, json.dumps(payload))
        checks.check(
            "http-remove-ids",
            status == 200 and set(payload.get("ids") or []) == {photo_a, video},
            json.dumps(payload),
        )
        status, after = request_json(base + "/api/items", timeout=5)
        after_names = set(filenames(after if isinstance(after, list) else []))
        checks.check(
            "http-remove-gone",
            status == 200 and "IMG_1042.jpg" not in after_names and "clip.mp4" not in after_names,
            json.dumps(sorted(after_names)),
        )
        checks.check(
            "http-remove-keeps-others",
            "near.jpg" in after_names and "no-exif.jpg" in after_names,
            json.dumps(sorted(after_names)),
        )
    finally:
        stop_owned(server, extra_pids=pids)

    leftover = run_library(root, ["remove", photo_b, photo_c])
    checks.check("cli-remove-batch", leftover.returncode == 0, leftover.stderr[-200:])
    leftover_body = json.loads(leftover.stdout)
    checks.check("cli-remove-ok", leftover_body.get("ok") is True, json.dumps(leftover_body))
    remain = filenames(json.loads(run_library(root, ["items"]).stdout))
    checks.check("cli-remove-empty", remain == [], json.dumps(remain))
    checks.check("originals-stay", hash_tree(folder) == before_media)
    record["originalsUnchanged"] = True
    return record


def bar_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const bar = document.getElementById('selection-bar');
          const fav = document.getElementById('selection-favorite');
          const count = document.getElementById('selection-count');
          const selected = (document.getElementById('grid').dataset.selected || '').split(',').filter(Boolean);
          const hearts = {};
          document.querySelectorAll('#grid .cell[data-slot=\"grid\"]').forEach(function (cell) {
            const heart = cell.querySelector('.heart');
            hearts[cell.getAttribute('data-filename') || ''] = heart ? heart.getAttribute('aria-pressed') : null;
          });
          return {
            hidden: !bar || bar.hidden,
            count: (count || {}).textContent || '',
            favorite: (fav || {}).textContent || '',
            selected: selected,
            files: Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(function (el) {
              return el.getAttribute('data-filename');
            }),
            hearts: hearts,
            confirmOpen: !!(document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open),
            confirmTitle: (document.getElementById('confirm-remove-title') || {}).textContent || '',
            confirmHelp: (document.getElementById('confirm-remove-help') || {}).textContent || '',
            lang: document.documentElement.lang
          };
        }"""
    )


def cell(page: Any, name: str) -> Any:
    return page.locator('#grid .cell[data-slot="grid"][data-filename="' + name + '"]').first


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    page.locator("#date-group").select_option("off")
    page.wait_for_function(
        """() => document.querySelectorAll('#grid .cell[data-slot=\"grid\"][data-filename]').length >= 4""",
        timeout=8000,
    )
    start = bar_state(page)
    record["start"] = start
    checks.check("bar-hidden-idle", start.get("hidden") is True, json.dumps(start))

    cell(page, "IMG_1042.jpg").click(modifiers=["ControlOrMeta"])
    cell(page, "near.jpg").click(modifiers=["ControlOrMeta"])
    page.wait_for_function(
        """() => {
          const bar = document.getElementById('selection-bar');
          const selected = (document.getElementById('grid').dataset.selected || '').split(',').filter(Boolean);
          return bar && !bar.hidden && selected.length === 2;
        }""",
        timeout=5000,
    )
    two = bar_state(page)
    record["two"] = two
    checks.check("bar-visible", two.get("hidden") is False, json.dumps(two))
    checks.check("count-en", two.get("count") == "2 selected", json.dumps(two.get("count")))
    checks.check("favorite-label", two.get("favorite") == "Favorite", json.dumps(two.get("favorite")))
    checks.check("selected-two", len(two.get("selected") or []) == 2, json.dumps(two.get("selected")))

    cell(page, "clip.mp4").click(modifiers=["Shift"])
    page.wait_for_function(
        """() => (document.getElementById('grid').dataset.selected || '').split(',').filter(Boolean).length >= 2""",
        timeout=5000,
    )
    ranged = bar_state(page)
    record["shift"] = ranged
    checks.check(
        "shift-keeps-bar",
        ranged.get("hidden") is False and len(ranged.get("selected") or []) >= 2,
        json.dumps(ranged),
    )

    page.locator("#selection-clear").click()
    page.wait_for_function(
        """() => {
          const bar = document.getElementById('selection-bar');
          const selected = (document.getElementById('grid').dataset.selected || '').split(',').filter(Boolean);
          return bar && bar.hidden && selected.length === 0;
        }""",
        timeout=5000,
    )
    checks.check("clear-hides-bar", True)

    page.locator("#language").select_option("zh-Hans")
    page.wait_for_function(
        "() => document.documentElement.lang === 'zh-Hans'",
        timeout=8000,
    )
    cell(page, "IMG_1042.jpg").click(modifiers=["ControlOrMeta"])
    cell(page, "near.jpg").click(modifiers=["ControlOrMeta"])
    page.wait_for_function(
        """() => {
          const bar = document.getElementById('selection-bar');
          const count = (document.getElementById('selection-count') || {}).textContent || '';
          const fav = (document.getElementById('selection-favorite') || {}).textContent || '';
          const clear = (document.getElementById('selection-clear') || {}).textContent || '';
          const remove = (document.getElementById('selection-remove') || {}).textContent || '';
          return bar && !bar.hidden && count.indexOf('已选') === 0 && fav === '收藏'
            && clear === '清除选择' && remove === '移出图库';
        }""",
        timeout=8000,
    )
    zh = bar_state(page)
    record["chinese"] = zh
    checks.check("count-zh", zh.get("count") == "已选 2 项", json.dumps(zh.get("count")))
    checks.check("favorite-zh", zh.get("favorite") == "收藏", json.dumps(zh.get("favorite")))
    page.screenshot(path=str(artifacts / "selection-bar-zh.png"))

    page.locator("#language").select_option("en")
    page.wait_for_function(
        """() => document.documentElement.lang === 'en'
          && ((document.getElementById('selection-count') || {}).textContent || '') === '2 selected'""",
        timeout=8000,
    )

    page.locator("#selection-favorite").click()
    page.wait_for_function(
        """() => {
          const hearts = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).filter(function (cell) {
            const name = cell.getAttribute('data-filename');
            return name === 'IMG_1042.jpg' || name === 'near.jpg';
          }).map(function (cell) {
            const heart = cell.querySelector('.heart');
            return heart ? heart.getAttribute('aria-pressed') : '';
          });
          const fav = (document.getElementById('selection-favorite') || {}).textContent || '';
          return hearts.length === 2 && hearts.every(function (v) { return v === 'true'; }) && fav === 'Unfavorite';
        }""",
        timeout=8000,
    )
    hearted = bar_state(page)
    record["hearted"] = hearted
    checks.check(
        "batch-favorite-hearts",
        hearted.get("hearts", {}).get("IMG_1042.jpg") == "true"
        and hearted.get("hearts", {}).get("near.jpg") == "true",
        json.dumps(hearted.get("hearts")),
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    by_name = item_map(listed if isinstance(listed, list) else [])
    checks.check(
        "batch-favorite-api-true",
        status == 200
        and by_name["IMG_1042.jpg"].get("favorite") is True
        and by_name["near.jpg"].get("favorite") is True,
        json.dumps({name: by_name.get(name, {}).get("favorite") for name in ("IMG_1042.jpg", "near.jpg")}),
    )
    page.screenshot(path=str(artifacts / "selection-bar.png"))

    page.locator("#selection-favorite").click()
    page.wait_for_function(
        """() => {
          const names = ['IMG_1042.jpg', 'near.jpg'];
          return names.every(function (name) {
            const cell = document.querySelector('#grid .cell[data-slot=\"grid\"][data-filename=\"' + name + '\"]');
            const heart = cell && cell.querySelector('.heart');
            return heart && heart.getAttribute('aria-pressed') === 'false';
          }) && ((document.getElementById('selection-favorite') || {}).textContent || '') === 'Favorite';
        }""",
        timeout=8000,
    )
    checks.check("batch-unfavorite-toggle", True)
    page.locator("#selection-favorite").click()
    page.wait_for_function(
        """() => {
          const names = ['IMG_1042.jpg', 'near.jpg'];
          return names.every(function (name) {
            const cell = document.querySelector('#grid .cell[data-slot=\"grid\"][data-filename=\"' + name + '\"]');
            const heart = cell && cell.querySelector('.heart');
            return heart && heart.getAttribute('aria-pressed') === 'true';
          });
        }""",
        timeout=8000,
    )
    checks.check("batch-favorite-again", True)

    page.locator("#selection-remove").click()
    page.wait_for_function(
        "() => document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open",
        timeout=5000,
    )
    confirm = bar_state(page)
    record["confirm"] = confirm
    checks.check("confirm-open", confirm.get("confirmOpen") is True, json.dumps(confirm.get("confirmTitle")))
    checks.check(
        "confirm-many-title",
        "2" in (confirm.get("confirmTitle") or "") and "Library" in (confirm.get("confirmTitle") or ""),
        json.dumps(confirm.get("confirmTitle")),
    )
    checks.check("confirm-files-stay", "files stay on disk" in (confirm.get("confirmHelp") or ""), json.dumps(confirm.get("confirmHelp")))
    page.screenshot(path=str(artifacts / "batch-remove-confirm.png"))
    page.locator("#confirm-remove-cancel").click()
    page.wait_for_function(
        "() => !document.getElementById('confirm-remove').open",
        timeout=5000,
    )
    after_cancel = bar_state(page)
    record["afterCancel"] = after_cancel
    checks.check(
        "cancel-leaves-items",
        "IMG_1042.jpg" in (after_cancel.get("files") or []) and "near.jpg" in (after_cancel.get("files") or []),
        json.dumps(after_cancel.get("files")),
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    cancel_names = set(filenames(listed if isinstance(listed, list) else []))
    checks.check(
        "cancel-leaves-catalog",
        status == 200 and "IMG_1042.jpg" in cancel_names and "near.jpg" in cancel_names,
        json.dumps(sorted(cancel_names)),
    )

    page.locator("#selection-remove").click()
    page.wait_for_function(
        "() => document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open",
        timeout=5000,
    )
    page.locator("#confirm-remove-ok").click()
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(function (el) {
            return el.getAttribute('data-filename');
          });
          return names.indexOf('IMG_1042.jpg') < 0 && names.indexOf('near.jpg') < 0
            && names.indexOf('no-exif.jpg') >= 0;
        }""",
        timeout=10000,
    )
    gone = bar_state(page)
    record["afterRemove"] = gone
    checks.check(
        "remove-drops-grid",
        "IMG_1042.jpg" not in (gone.get("files") or []) and "near.jpg" not in (gone.get("files") or []),
        json.dumps(gone.get("files")),
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    remain = set(filenames(listed if isinstance(listed, list) else []))
    checks.check(
        "remove-drops-catalog",
        status == 200 and "IMG_1042.jpg" not in remain and "near.jpg" not in remain,
        json.dumps(sorted(remain)),
    )
    checks.check(
        "remove-keeps-others",
        "no-exif.jpg" in remain and "clip.mp4" in remain,
        json.dumps(sorted(remain)),
    )
    page.screenshot(path=str(artifacts / "after-batch-remove.png"))

    cell(page, "no-exif.jpg").click(modifiers=["ControlOrMeta"])
    cell(page, "clip.mp4").click(modifiers=["ControlOrMeta"])
    page.wait_for_function(
        "() => document.getElementById('selection-bar') && !document.getElementById('selection-bar').hidden",
        timeout=5000,
    )
    page.keyboard.press("Escape")
    page.wait_for_function(
        """() => {
          const bar = document.getElementById('selection-bar');
          const selected = (document.getElementById('grid').dataset.selected || '').split(',').filter(Boolean);
          return bar && bar.hidden && selected.length === 0;
        }""",
        timeout=5000,
    )
    checks.check("esc-clears-selection", True)
    return record


def seed_browser_root(root: Path, media_src: Path, artifacts: Path) -> Path:
    folder = artifacts / "browser-media"
    copy_rels(media_src, folder, MEDIA_RELS)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    if scanned.returncode != 0:
        raise RuntimeError(scanned.stderr[-200:])
    return folder


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library favorite <id> <id> --on",
        "python -m library remove <id> <id>",
        "POST /api/items/favorite",
        "POST /api/items/remove",
    ]
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "select-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["select-api.json"] = str(artifacts / "select-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        media_folder = seed_browser_root(isolated, media_src, artifacts)
        before_browser_media = hash_tree(media_folder)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg", "no-exif.jpg", "clip.mp4"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks)
                unexpected = [
                    message
                    for message in errors
                    if "status of 400" not in message and "status of 404" not in message
                ]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "select-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["select-browser.json"] = str(artifacts / "select-browser.json")
            extra["selection-bar.png"] = str(artifacts / "selection-bar.png")
            extra["selection-bar-zh.png"] = str(artifacts / "selection-bar-zh.png")
            extra["batch-remove-confirm.png"] = str(artifacts / "batch-remove-confirm.png")
            extra["after-batch-remove.png"] = str(artifacts / "after-batch-remove.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("browser-originals-stay", hash_tree(media_folder) == before_browser_media)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-select-runner", False, str(exc))
    return write_result("TASTE-SELECT", "slice", checks, artifacts, commands, extra)
