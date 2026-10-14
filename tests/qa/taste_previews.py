"""Grid thumbs stay painted across person-filter cycles. Not an F-id grade."""

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
    "a/clip.mp4",
)

PHOTO_NAMES = ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg")
ALL_NAMES = PHOTO_NAMES + ("clip.mp4",)


def wait_stills(base: str, names: tuple[str, ...] | list[str], timeout: float = 90) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            by_name = {item.get("filename"): item for item in payload}
            ready = True
            for name in names:
                item = by_name.get(name)
                if not item:
                    ready = False
                    break
                slot = "poster" if item.get("kind") == "video" else "thumb"
                if ((item.get("renditions") or {}).get("status") or {}).get(slot) != "ready":
                    ready = False
                    break
            if ready:
                return last
        time.sleep(0.25)
    raise RuntimeError("stills timeout " + json.dumps([(item.get("filename"), (item.get("renditions") or {}).get("status")) for item in last]))


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


def thumb_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => window.libraryTest && window.libraryTest.gridThumbs
          ? window.libraryTest.gridThumbs()
          : { count: 0, painted: 0, missing: -1, files: [] }"""
    )


def hammer_stills(page: Any, times: int = 8) -> None:
    page.evaluate(
        """(n) => {
          const api = window.libraryTest || {};
          for (let i = 0; i < n; i += 1) {
            if (api.paintGridStills) {
              api.paintGridStills();
            }
            if (api.loadCatalog) {
              api.loadCatalog();
            }
          }
        }""",
        times,
    )


def wait_painted(page: Any, names: tuple[str, ...] | list[str], timeout: int = 20000) -> dict[str, Any]:
    wanted = list(names)
    page.wait_for_function(
        """(wanted) => {
          const stats = window.libraryTest && window.libraryTest.gridThumbs && window.libraryTest.gridThumbs();
          if (!stats || !stats.files) {
            return false;
          }
          const byName = {};
          stats.files.forEach(function (row) { byName[row.file] = row; });
          return wanted.every(function (name) {
            const row = byName[name];
            return row && row.painted && !row.placeholder;
          });
        }""",
        arg=wanted,
        timeout=timeout,
    )
    return thumb_state(page)


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    ids = seed(root, media_src, artifacts / "api")
    listed = json.loads(run_library(root, ["items"]).stdout)
    names = set(filenames(listed))
    checks.check("items-have-photos-and-video", names >= set(ALL_NAMES), json.dumps(sorted(names)))
    people = json.loads(run_library(root, ["people"]).stdout)
    rows = people.get("people") if isinstance(people, dict) else people
    ada = [row for row in (rows or []) if row.get("id") == ids["Ada"]]
    checks.check("people-have-ada", bool(ada), json.dumps(ada))
    record["people"] = ids
    record["itemCount"] = len(listed)
    return record


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    first = wait_painted(page, ALL_NAMES)
    record["first"] = first
    checks.check("first-all-painted", first.get("missing") == 0 and first.get("painted") >= 5, json.dumps(first))
    checks.check(
        "first-photos-painted",
        all(row.get("painted") for row in first.get("files") or [] if row.get("file") in PHOTO_NAMES),
        json.dumps(first.get("files")),
    )
    video = [row for row in (first.get("files") or []) if row.get("file") == "clip.mp4"]
    checks.check(
        "first-video-poster",
        bool(video) and video[0].get("painted") and "which=poster" in (video[0].get("which") or ""),
        json.dumps(video),
    )

    def click_person() -> None:
        page.locator(".person-row", has_text="Ada").click()
        page.wait_for_function(
            """() => {
              const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
              return (document.getElementById('grid').dataset.person || '').indexOf('person_') === 0
                && names.indexOf('IMG_1042.jpg') >= 0 && names.indexOf('far.jpg') < 0;
            }""",
            timeout=8000,
        )

    def click_person_chip_x() -> None:
        page.locator(".filter-chip", has_text="Person: Ada").click()
        page.wait_for_function(
            """() => !document.getElementById('grid').dataset.person
              && document.querySelectorAll('#grid .cell[data-slot=\"grid\"]').length >= 5""",
            timeout=8000,
        )

    click_person()
    filtered = wait_painted(page, ("IMG_1042.jpg", "near.jpg"))
    record["filtered"] = filtered
    checks.check(
        "person-filter-keeps-thumbs",
        all(row.get("painted") and not row.get("placeholder") for row in filtered.get("files") or [] if row.get("file") in {"IMG_1042.jpg", "near.jpg"}),
        json.dumps(filtered),
    )
    checks.check(
        "person-filter-hides-others",
        all(row.get("file") in {"IMG_1042.jpg", "near.jpg"} for row in filtered.get("files") or []),
        json.dumps(filtered.get("files")),
    )

    click_person_chip_x()
    cleared = wait_painted(page, ALL_NAMES)
    record["chipX"] = cleared
    checks.check(
        "chip-x-keeps-thumbs",
        cleared.get("missing") == 0 and cleared.get("painted") >= 5,
        json.dumps(cleared),
    )
    checks.check(
        "chip-x-no-placeholder",
        all(not row.get("placeholder") and row.get("painted") for row in cleared.get("files") or []),
        json.dumps(cleared.get("files")),
    )

    click_person()
    wait_painted(page, ("IMG_1042.jpg", "near.jpg"))
    click_person_chip_x()
    cycled = wait_painted(page, ALL_NAMES)
    record["cycled"] = cycled
    checks.check("person-filter-chip-x-cycle", cycled.get("missing") == 0 and cycled.get("painted") >= 5, json.dumps(cycled))
    video_after = [row for row in (cycled.get("files") or []) if row.get("file") == "clip.mp4"]
    checks.check(
        "video-poster-survives-cycles",
        bool(video_after) and video_after[0].get("painted") and "which=poster" in (video_after[0].get("which") or ""),
        json.dumps(video_after),
    )

    hammer_stills(page)
    after_hammer = wait_painted(page, ALL_NAMES)
    record["afterHammer"] = after_hammer
    checks.check(
        "repaint-does-not-stall",
        after_hammer.get("missing") == 0 and after_hammer.get("painted") >= 5,
        json.dumps(after_hammer),
    )

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    hammer_stills(page)
    reloaded = wait_painted(page, ALL_NAMES, timeout=30000)
    record["reloaded"] = reloaded
    checks.check(
        "reload-keeps-thumbs",
        reloaded.get("missing") == 0 and reloaded.get("painted") >= 5,
        json.dumps(reloaded),
    )
    page.wait_for_timeout(2500)
    hammer_stills(page, 4)
    stayed = wait_painted(page, ALL_NAMES, timeout=15000)
    record["reloadStayed"] = stayed
    checks.check(
        "reload-stays-painted",
        stayed.get("missing") == 0 and stayed.get("painted") >= 5,
        json.dumps(stayed),
    )

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    hammer_stills(page)
    second = wait_painted(page, ALL_NAMES, timeout=30000)
    record["secondReload"] = second
    checks.check(
        "second-reload-keeps-thumbs",
        second.get("missing") == 0 and second.get("painted") >= 5,
        json.dumps(second),
    )

    page.screenshot(path=str(artifacts / "grid-thumbs.png"))
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "previews-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["previews-api.json"] = str(artifacts / "previews-api.json")
        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed(isolated, media_src, artifacts / "browser")
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ALL_NAMES)
            wait_stills(url.rstrip("/"), ALL_NAMES)
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
            (artifacts / "previews-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["previews-browser.json"] = str(artifacts / "previews-browser.json")
            extra["grid-thumbs.png"] = str(artifacts / "grid-thumbs.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-previews-runner", False, str(exc))
    return write_result("TASTE-PREVIEWS", "slice", checks, artifacts, ["python -m tests.qa slice TASTE-PREVIEWS"], extra)
