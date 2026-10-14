"""Grid thumbs stay painted across person-filter cycles. Not an F-id grade."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s03 import header_get, request_raw
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


def _faces_queue(status: dict[str, Any]) -> dict[str, Any]:
    for queue in status.get("queues") or []:
        if queue.get("id") == "infer-faces":
            return queue
    return {}


def prove_faces_rescan_progress(checks: Checks, artifacts: Path) -> dict[str, Any]:
    from library.faces import (
        faces_force_rescan,
        infer_faces_step,
        request_faces_rescan,
        scanned_item_ids,
    )
    from library.jobs import jobs_status
    from library.service import Library
    from tests.qa.faces import make_face_media, test_env

    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "faces-progress-root")
    media = make_face_media(artifacts / "faces-progress-media")
    setup = run_library(root, ["setup-ml", "faces", "--backend", "fixture"], env=test_env())
    checks.check("faces-progress-setup", setup.returncode == 0, setup.stderr[-200:])
    scan = run_library(root, ["scan", str(media), "--serve-from-there"], env=test_env(), timeout=120)
    checks.check("faces-progress-scan", scan.returncode == 0, scan.stderr[-200:])
    infer = run_library(root, ["infer-faces"], env=test_env(), timeout=120)
    checks.check("faces-progress-infer", infer.returncode == 0, infer.stderr[-200:])
    request_faces_rescan(root)
    queued = _faces_queue(jobs_status(root, False))
    photo_pending = int(queued.get("pending") or 0)
    record["pending"] = photo_pending
    checks.check("faces-rescan-pending", photo_pending >= 5, json.dumps(queued))

    pending_seen: list[int] = []
    scanned_seen: list[int] = []
    steps = 0
    while infer_faces_step(root) and steps < 20:
        steps += 1
        scanned_seen.append(len(scanned_item_ids(root)))
        pending_seen.append(int(_faces_queue(jobs_status(root, False)).get("pending") or 0))
    record["steps"] = steps
    record["pendingSeen"] = pending_seen
    record["scannedSeen"] = scanned_seen
    checks.check(
        "faces-rescan-steps",
        steps == photo_pending,
        json.dumps({"steps": steps, "pending": photo_pending, "seen": pending_seen}),
    )
    checks.check(
        "faces-rescan-pending-drops",
        pending_seen == list(range(photo_pending - 1, -1, -1)),
        json.dumps(pending_seen),
    )
    checks.check(
        "faces-rescan-scanned-grows",
        scanned_seen == list(range(1, photo_pending + 1)),
        json.dumps(scanned_seen),
    )
    checks.check("faces-rescan-force-cleared", faces_force_rescan(root) is False, "forceRescan")
    idle = _faces_queue(jobs_status(root, False))
    checks.check(
        "faces-rescan-pending-zero",
        idle.get("pending") == 0 and idle.get("state") == "idle",
        json.dumps(idle),
    )

    request_faces_rescan(root)
    import library.faces as faces_mod

    real_infer = faces_mod.infer_faces
    calls = {"n": 0}

    def boom(root_arg: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("planted-face-fail")
        return real_infer(root_arg, payload)

    faces_mod.infer_faces = boom
    try:
        fail_steps = 0
        fail_pending: list[int] = []
        while infer_faces_step(root) and fail_steps < 20:
            fail_steps += 1
            fail_pending.append(int(_faces_queue(jobs_status(root, False)).get("pending") or 0))
    finally:
        faces_mod.infer_faces = real_infer
    record["failSteps"] = fail_steps
    record["failPending"] = fail_pending
    checks.check(
        "faces-rescan-survives-error",
        fail_steps == photo_pending,
        json.dumps({"steps": fail_steps, "pending": fail_pending, "calls": calls["n"]}),
    )
    checks.check(
        "faces-rescan-error-drains",
        bool(fail_pending) and fail_pending[-1] == 0,
        json.dumps(fail_pending),
    )

    request_faces_rescan(root)
    library = Library(root)
    drain_steps = 0
    while library.drain_step() and drain_steps < 40:
        drain_steps += 1
    drained = _faces_queue(jobs_status(root, False))
    record["drainSteps"] = drain_steps
    checks.check(
        "faces-drain-runs-queue",
        drain_steps >= photo_pending and drained.get("pending") == 0,
        json.dumps({"drainSteps": drain_steps, "queue": drained}),
    )
    return record


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


def prove_cached_http(base: str, items: list[dict[str, Any]], checks: Checks) -> dict[str, Any]:
    urls: list[str] = []
    for item in items:
        if item.get("filename") not in ALL_NAMES:
            continue
        slot = "poster" if item.get("kind") == "video" else "thumb"
        urls.append(base + "/api/media/" + item["id"] + "?which=" + slot)
    for url in urls:
        request_raw(url)
    t0 = time.perf_counter()
    headers_ok = True
    etag_ok = True
    details: list[dict[str, Any]] = []
    for url in urls:
        status, headers, _body = request_raw(url)
        cache = header_get(headers, "Cache-Control") or ""
        etag = header_get(headers, "ETag") or ""
        if status != 200 or "max-age" not in cache.lower() or "no-store" in cache.lower():
            headers_ok = False
        if not etag:
            etag_ok = False
        else:
            again, _again_headers, _ = request_raw(url, {"If-None-Match": etag})
            if again != 304:
                etag_ok = False
        details.append({"url": url, "status": status, "cache": cache, "etag": etag})
    elapsed = time.perf_counter() - t0
    checks.check("thumb-cache-control", headers_ok, json.dumps(details))
    checks.check("thumb-etag-304", etag_ok, json.dumps(details))
    checks.check("cached-thumbs-fast", elapsed < 0.4, json.dumps({"elapsed": elapsed, "n": len(urls)}))
    return {"elapsed": elapsed, "n": len(urls), "details": details}


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
    page.wait_for_selector(".person-face-choice", timeout=8000)
    choice_count = page.locator(".person-face-choice").count()
    checks.check("face-picker-has-choices", choice_count >= 2, str(choice_count))
    page.locator(".person-face-choice").nth(choice_count - 1).click()
    immediate_last = page.evaluate(
        """() => Array.from(document.querySelectorAll('.person-face-choice')).map(el => el.getAttribute('aria-pressed'))"""
    )
    checks.check(
        "face-picker-immediate-last",
        immediate_last.count("true") == 1 and immediate_last[-1] == "true",
        json.dumps(immediate_last),
    )
    page.wait_for_function(
        """() => {
          const all = Array.from(document.querySelectorAll('.person-face-choice'));
          const pressed = all.filter(el => el.getAttribute('aria-pressed') === 'true');
          return all.length >= 2 && pressed.length === 1 && pressed[0] === all[all.length - 1];
        }""",
        timeout=3000,
    )
    last_pressed = page.evaluate(
        """() => Array.from(document.querySelectorAll('.person-face-choice')).map(el => el.getAttribute('aria-pressed'))"""
    )
    record["pickerLast"] = last_pressed
    checks.check("face-picker-single-last", last_pressed.count("true") == 1 and last_pressed[-1] == "true", json.dumps(last_pressed))
    page.locator(".person-face-choice").first.click()
    page.wait_for_function(
        """() => {
          const all = Array.from(document.querySelectorAll('.person-face-choice'));
          const pressed = all.filter(el => el.getAttribute('aria-pressed') === 'true');
          return pressed.length === 1 && pressed[0] === all[0];
        }""",
        timeout=3000,
    )
    first_pressed = page.evaluate(
        """() => Array.from(document.querySelectorAll('.person-face-choice')).map(el => el.getAttribute('aria-pressed'))"""
    )
    record["pickerFirst"] = first_pressed
    checks.check("face-picker-single-first", first_pressed.count("true") == 1 and first_pressed[0] == "true", json.dumps(first_pressed))
    page.locator(".person-face-choice").nth(choice_count - 1).click()
    page.locator(".person-face-choice").first.click()
    page.locator(".person-face-choice").nth(choice_count - 1).click()
    rapid = page.evaluate(
        """() => Array.from(document.querySelectorAll('.person-face-choice')).map(el => el.getAttribute('aria-pressed'))"""
    )
    record["pickerRapid"] = rapid
    checks.check(
        "face-picker-rapid-single",
        rapid.count("true") == 1 and rapid[-1] == "true",
        json.dumps(rapid),
    )

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
    t0 = time.perf_counter()
    second = wait_painted(page, ALL_NAMES, timeout=2500)
    cached_elapsed = time.perf_counter() - t0
    record["secondReload"] = second
    record["cachedReloadSec"] = cached_elapsed
    checks.check(
        "second-reload-keeps-thumbs",
        second.get("missing") == 0 and second.get("painted") >= 5,
        json.dumps(second),
    )
    checks.check(
        "reload-cached-fast",
        cached_elapsed < 2.0 and second.get("missing") == 0,
        json.dumps({"elapsed": cached_elapsed, "thumbs": second}),
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
        progress = prove_faces_rescan_progress(checks, artifacts)
        (artifacts / "faces-progress.json").write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
        extra["faces-progress.json"] = str(artifacts / "faces-progress.json")
        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed(isolated, media_src, artifacts / "browser")
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ALL_NAMES)
            stills = wait_stills(url.rstrip("/"), ALL_NAMES)
            cache = prove_cached_http(url.rstrip("/"), stills, checks)
            (artifacts / "previews-cache.json").write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
            extra["previews-cache.json"] = str(artifacts / "previews-cache.json")
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
