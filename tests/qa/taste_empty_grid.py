"""Catalog has photos and people: the grid must show photos. Not an F-id grade."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import annotate_json, collect_console, filenames, wait_catalog

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "a/near.jpg",
    "b/far.jpg",
)


def seed(root: Path, media_src: Path, artifacts: Path) -> dict[str, str]:
    folder = artifacts / "media"
    copy_rels(media_src, folder, MEDIA_RELS)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    if scanned.returncode != 0:
        raise RuntimeError(scanned.stderr[-200:])
    items = {item.get("filename"): item for item in load_items(root)}
    jpeg = items["IMG_1042.jpg"]
    near = items["near.jpg"]
    ada = json.loads(run_library(root, ["annotate", jpeg["id"], "--person", "Ada"]).stdout)
    ada_id = ((ada.get("entities") or {}).get("people") or [{}])[0].get("id") or ""
    annotate_json(root, near["id"], {"people": [{"id": ada_id}]}, artifacts, "near-ada.json")
    return {"Ada": ada_id}


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    ids = seed(root, media_src, artifacts / "api")
    listed = run_library(root, ["items"])
    checks.check("items-cli", listed.returncode == 0, listed.stderr[-200:])
    body = json.loads(listed.stdout)
    names = set(filenames(body))
    checks.check(
        "items-have-photos",
        names >= {"IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg"},
        json.dumps(sorted(names)),
    )
    people = json.loads(run_library(root, ["people"]).stdout)
    rows = people.get("people") if isinstance(people, dict) else people
    ada = [row for row in (rows or []) if row.get("id") == ids["Ada"]]
    checks.check("people-have-ada", bool(ada) and int(ada[0].get("itemCount") or 0) >= 2, json.dumps(ada))
    record["people"] = ids
    record["itemCount"] = len(body)
    return record


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    first = page.evaluate(
        """() => ({
          empty: !!(document.getElementById('empty-library')),
          emptyText: (document.querySelector('#empty-library p') || {}).textContent || '',
          files: Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename')),
          people: Array.from(document.querySelectorAll('.person-row')).map(n => n.textContent.trim()),
          person: document.getElementById('grid').dataset.person || '',
          kind: document.getElementById('grid').dataset.kind || '',
          favorite: document.getElementById('grid').dataset.favorite || '',
          arrange: document.getElementById('grid').dataset.arrange || ''
        })"""
    )
    record["first"] = first
    checks.check("grid-not-empty-copy", first.get("empty") is False, json.dumps(first))
    checks.check("grid-not-no-pictures", first.get("emptyText") != "No pictures yet", json.dumps(first))
    checks.check(
        "grid-shows-photos",
        set(first.get("files") or []) >= {"IMG_1042.jpg", "near.jpg", "far.jpg"},
        json.dumps(first.get("files")),
    )
    checks.check(
        "people-panel-has-ada",
        any("Ada" in row for row in (first.get("people") or [])),
        json.dumps(first.get("people")),
    )
    checks.check("default-filter-clear", not first.get("person") and not first.get("kind") and not first.get("favorite"), json.dumps(first))
    checks.check("default-group-date", first.get("arrange") == "dates", json.dumps(first))

    page.locator(".person-row", has_text="Ada").click()
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return (document.getElementById('grid').dataset.person || '').indexOf('person_') === 0
            && names.indexOf('IMG_1042.jpg') >= 0 && names.indexOf('far.jpg') < 0;
        }""",
        timeout=8000,
    )
    page.locator("#clear-filters").click()
    page.wait_for_function(
        """() => !document.getElementById('grid').dataset.person
          && document.querySelectorAll('#grid .cell[data-slot=\"grid\"]').length >= 4
          && !document.getElementById('empty-library')""",
        timeout=8000,
    )
    after_clear = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["afterClear"] = after_clear
    checks.check(
        "clear-all-restores-photos",
        set(after_clear) >= {"IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg"},
        json.dumps(after_clear),
    )

    page.locator("#arrange").select_option("people")
    page.wait_for_function(
        """() => document.getElementById('grid').dataset.arrange === 'people'
          && Array.from(document.querySelectorAll('#grid .group-key')).some(n => n.textContent.indexOf('Ada') >= 0)
          && document.querySelectorAll('#grid .cell[data-slot=\"grid\"]').length >= 4
          && !document.getElementById('empty-library')""",
        timeout=8000,
    )
    grouped = page.evaluate(
        """() => ({
          files: Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename')),
          headers: Array.from(document.querySelectorAll('#grid .group-key')).map(n => n.textContent.trim())
        })"""
    )
    record["groupPeople"] = grouped
    checks.check(
        "group-people-still-shows-photos",
        set(grouped.get("files") or []) >= {"IMG_1042.jpg", "near.jpg"},
        json.dumps(grouped),
    )

    page.locator("#filter-favorites").click()
    page.wait_for_function(
        "() => document.getElementById('grid').dataset.favorite === '1'",
        timeout=5000,
    )
    page.locator("#filter-all").click()
    page.wait_for_function(
        """() => !document.getElementById('grid').dataset.favorite
          && document.querySelectorAll('#grid .cell[data-slot=\"grid\"]').length >= 4
          && !document.getElementById('empty-library')""",
        timeout=8000,
    )
    checks.check("all-restores-after-favorites", True)

    page.route("**/api/groups*", lambda route: route.fulfill(status=400, content_type="application/json", body='{"error":"invalid-argument"}'))
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    after_groups_fail = page.evaluate(
        """() => ({
          empty: !!document.getElementById('empty-library'),
          files: Array.from(document.querySelectorAll('#grid .cell')).map(el => el.getAttribute('data-filename'))
        })"""
    )
    record["groupsFail"] = after_groups_fail
    checks.check(
        "groups-fail-still-shows-photos",
        after_groups_fail.get("empty") is False and "IMG_1042.jpg" in (after_groups_fail.get("files") or []),
        json.dumps(after_groups_fail),
    )
    page.unroute("**/api/groups*")

    delayed = {"n": 0}

    def slow_items(route: Any) -> None:
        delayed["n"] += 1
        time.sleep(1.2)
        route.continue_()

    page.route("**/api/items*", slow_items)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=45000)
    after_slow = page.evaluate(
        """() => ({
          empty: !!document.getElementById('empty-library'),
          files: Array.from(document.querySelectorAll('#grid .cell')).map(el => el.getAttribute('data-filename')),
          count: window.libraryTest ? window.libraryTest.itemCount() : -1
        })"""
    )
    record["slowItems"] = after_slow
    checks.check(
        "slow-items-still-shows-photos",
        after_slow.get("empty") is False and "IMG_1042.jpg" in (after_slow.get("files") or []),
        json.dumps(after_slow),
    )
    page.unroute("**/api/items*")
    page.screenshot(path=str(artifacts / "grid-with-people.png"))
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "empty-grid-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["empty-grid-api.json"] = str(artifacts / "empty-grid-api.json")
        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed(isolated, media_src, artifacts / "browser")
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg"))
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
            (artifacts / "empty-grid-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["empty-grid-browser.json"] = str(artifacts / "empty-grid-browser.json")
            extra["grid-with-people.png"] = str(artifacts / "grid-with-people.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-empty-grid-runner", False, str(exc))
    return write_result("TASTE-EMPTY-GRID", "slice", checks, artifacts, ["python -m tests.qa slice TASTE-EMPTY-GRID"], extra)
