"""Merge wizard, Live/burst stacks, Print. Not an F-id grade."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.stacks import annotate_stacks
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import collect_console, wait_catalog

I18N = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "i18n.js"
HTML = Path(__file__).resolve().parents[2] / "library" / "web" / "index.html"
JS = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "library.js"
CSS = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "style.css"

PEOPLE_RELS = ("a/near.jpg", "b/far.jpg")
LIVE_RELS = ("live/LIVE_0001.jpg", "live/LIVE_0001.mov")


def filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") or "" for item in items]


def item_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("filename") or "": item for item in items}


def person_id_for(item: dict[str, Any]) -> str:
    for face in item.get("faces") or []:
        pid = face.get("personId")
        if type(pid) is str and pid:
            return pid
    for person in ((item.get("entities") or {}).get("people") or []):
        pid = person.get("id")
        if type(pid) is str and pid:
            return pid
    return ""


def plant_index(root: Path, vectors: dict[str, list[float]]) -> None:
    path = root / "models" / "faces" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "backend": "fixture",
        "matchThreshold": 0.85,
        "people": {pid: {"centroid": vec, "faces": []} for pid, vec in vectors.items()},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_burst_jpegs(folder: Path, src_jpeg: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    data = src_jpeg.read_bytes()
    names = ("IMG_2001.jpg", "IMG_2002.jpg", "IMG_2003.jpg")
    paths: list[Path] = []
    base = time.time()
    for index, name in enumerate(names):
        path = folder / name
        path.write_bytes(data + bytes([0, index, 255]))
        stamp = base + index * 0.4
        os.utime(path, (stamp, stamp))
        paths.append(path)
    return paths


def prove_static(checks: Checks) -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    checks.check("html-review", 'id="people-review"' in html)
    checks.check("html-wizard", 'id="merge-wizard"' in html)
    checks.check("html-wizard-merge", 'id="merge-wizard-merge"' in html)
    checks.check("html-wizard-not-same", 'id="merge-wizard-not-same"' in html)
    checks.check("html-wizard-skip", 'id="merge-wizard-skip"' in html)
    checks.check("html-stack", 'id="viewer-stack"' in html)
    checks.check("html-print", 'id="viewer-print"' in html and 'id="print-sheet"' in html)
    checks.check("html-help-print", "Ctrl+P" in html)
    checks.check("js-suggestions", "/api/people/suggestions" in js)
    checks.check("js-not-same", "/api/people/not-same" in js)
    checks.check("js-no-auto-merge", "wizardMerge" in js and "runPendingMerge" in js)
    checks.check("js-stack-hidden", "isStackHidden" in js)
    checks.check("js-print", "printViewer" in js)
    checks.check("css-print", "@media print" in css and "#print-sheet" in css)
    checks.check("i18n-review-zh", 'reviewMatches: "核对可能是同一人"' in i18n)
    checks.check("i18n-not-same-zh", 'notSame: "不是同一人"' in i18n)
    checks.check("i18n-skip-zh", 'skip: "跳过"' in i18n)
    checks.check("i18n-print-zh", 'print: "打印"' in i18n)
    checks.check("i18n-burst-zh", 'burstBadge: "连拍 {n}"' in i18n)
    checks.check("no-auto-delete-js", "auto-delete" not in js.lower())
    checks.check("no-auto-merge-js", "auto-merge" not in js.lower())


def prove_stacks_unit(checks: Checks) -> None:
    loc = {
        "sourceId": "src_a",
        "role": "primary",
        "component": "still",
        "current": True,
        "libraryRelativePath": "roll/IMG_2001.jpg",
    }

    def photo(item_id: str, name: str, captured: str) -> dict[str, Any]:
        item_loc = dict(loc)
        item_loc["libraryRelativePath"] = "roll/" + name
        return {
            "id": item_id,
            "kind": "photo",
            "filename": name,
            "capturedAt": captured,
            "locations": [item_loc],
        }

    burst = annotate_stacks(
        [
            photo("b1", "IMG_2001.jpg", "2024-06-12T15:04:00"),
            photo("b2", "IMG_2002.jpg", "2024-06-12T15:04:01"),
            photo("b3", "IMG_2003.jpg", "2024-06-12T15:04:02"),
            {"id": "live1", "kind": "live", "filename": "LIVE_0001.jpg", "locations": [dict(loc)]},
            photo("other", "near.jpg", "2023-01-01T00:00:00"),
            {
                "id": "stem-still",
                "kind": "photo",
                "filename": "IMG_3001.jpg",
                "capturedAt": "2024-07-01T10:00:00",
                "locations": [{**loc, "libraryRelativePath": "roll/IMG_3001.jpg"}],
            },
            {
                "id": "stem-motion",
                "kind": "video",
                "filename": "IMG_3001.MOV",
                "capturedAt": "2024-07-01T10:00:00",
                "metadata": {"durationSec": 2.0},
                "locations": [
                    {
                        **loc,
                        "component": "motion",
                        "libraryRelativePath": "roll/IMG_3001.MOV",
                    }
                ],
            },
        ]
    )
    by_id = {item["id"]: item for item in burst}
    stack = by_id["b1"].get("stack") or {}
    checks.check("unit-burst-kind", stack.get("kind") == "burst", json.dumps(stack))
    checks.check("unit-burst-count", stack.get("count") == 3, json.dumps(stack.get("itemIds")))
    checks.check("unit-burst-rep", stack.get("representative") is True)
    checks.check("unit-burst-hidden", (by_id["b2"].get("stack") or {}).get("representative") is False)
    checks.check("unit-live-self", (by_id["live1"].get("stack") or {}).get("kind") == "live")
    checks.check("unit-other-none", "stack" not in by_id["other"])
    stem = by_id["stem-still"].get("stack") or {}
    checks.check("unit-stem-live", stem.get("kind") == "live" and stem.get("count") == 2, json.dumps(stem))
    checks.check("unit-stem-motion-hidden", (by_id["stem-motion"].get("stack") or {}).get("representative") is False)


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    folder = artifacts / "api-media"
    copy_rels(media_src, folder, PEOPLE_RELS + LIVE_RELS)
    burst_paths = write_burst_jpegs(folder / "burst", media_src / "b" / "no-exif.jpg")
    before = {path.name: path.read_bytes() for path in burst_paths}
    live_still = folder / "live" / "LIVE_0001.jpg"
    live_motion = folder / "live" / "LIVE_0001.mov"
    live_hashes = {
        "still": live_still.read_bytes() if live_still.is_file() else b"",
        "motion": live_motion.read_bytes() if live_motion.is_file() else b"",
    }

    scan = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    checks.check("scan-ok", scan.returncode == 0, scan.stderr[-200:])
    listed = item_map(json.loads(run_library(root, ["items"]).stdout))
    checks.check("has-near-far", "near.jpg" in listed and "far.jpg" in listed, json.dumps(sorted(listed)))
    live_item = listed.get("LIVE_0001.jpg") or {}
    checks.check("live-kind", live_item.get("kind") == "live", json.dumps(live_item.get("kind")))
    live_stack = live_item.get("stack") or {}
    checks.check("live-stack", live_stack.get("kind") == "live", json.dumps(live_stack))
    burst_items = [listed.get(name) for name in ("IMG_2001.jpg", "IMG_2002.jpg", "IMG_2003.jpg")]
    checks.check("burst-scanned", all(item is not None for item in burst_items), json.dumps(filenames(list(listed.values()))))
    burst_stack = (burst_items[0] or {}).get("stack") or {}
    checks.check("burst-kind", burst_stack.get("kind") == "burst", json.dumps(burst_stack))
    checks.check("burst-count", burst_stack.get("count") == 3, json.dumps(burst_stack.get("itemIds")))
    reps = [item for item in burst_items if item and (item.get("stack") or {}).get("representative")]
    checks.check("burst-one-rep", len(reps) == 1, json.dumps([(item or {}).get("filename") for item in burst_items]))
    disk_item = next((item for item in load_items(root) if item.get("filename") == "IMG_2001.jpg"), {})
    checks.check("disk-no-stack", "stack" not in disk_item, json.dumps(sorted(disk_item.keys())))
    after_burst = {path.name: path.read_bytes() for path in burst_paths}
    checks.check("burst-bytes-same", after_burst == before)
    checks.check("live-bytes-same", live_still.read_bytes() == live_hashes["still"] and live_motion.read_bytes() == live_hashes["motion"])

    near = listed["near.jpg"]
    far = listed["far.jpg"]
    ann_a = run_library(root, ["annotate", near["id"], "--person", "Ada"])
    ann_b = run_library(root, ["annotate", far["id"], "--person", "Bob"])
    checks.check("annotate-ok", ann_a.returncode == 0 and ann_b.returncode == 0, ann_a.stderr[-120:] + ann_b.stderr[-120:])
    named = item_map(json.loads(run_library(root, ["items"]).stdout))
    ada = person_id_for(named["near.jpg"])
    bob = person_id_for(named["far.jpg"])
    record["ada"] = ada
    record["bob"] = bob
    checks.check("person-ids", bool(ada and bob and ada != bob), json.dumps({"ada": ada, "bob": bob}))

    empty = json.loads(run_library(root, ["people", "suggestions"]).stdout)
    checks.check("suggest-empty-no-index", empty.get("suggestions") == [], json.dumps(empty))

    plant_index(root, {ada: [1.0, 0.0, 0.0], bob: [0.98, 0.199, 0.0]})
    suggested = json.loads(run_library(root, ["people", "suggestions"]).stdout)
    pairs = suggested.get("suggestions") or []
    record["suggestions"] = pairs
    checks.check("suggest-one", len(pairs) == 1, json.dumps(pairs))
    if pairs:
        ids = {pairs[0].get("keepId"), pairs[0].get("dropId")}
        checks.check("suggest-ada-bob", ids == {ada, bob}, json.dumps(pairs[0]))
        checks.check("suggest-score", float(pairs[0].get("score") or 0) > 0.55, json.dumps(pairs[0]))
    people_after = json.loads(run_library(root, ["people", "list"]).stdout)
    names = {row.get("name") for row in people_after.get("people") or []}
    checks.check("suggest-no-merge", names >= {"Ada", "Bob"}, json.dumps(sorted(names)))

    bad = run_library(root, ["people", "not-same", ada, ada])
    checks.check("not-same-self", bad.returncode != 0, bad.stderr[-160:])

    server, url, pids = start_owned(root)
    try:
        base = url.rstrip("/")
        status, payload = request_json(base + "/api/people/suggestions", timeout=8)
        checks.check("http-suggest-200", status == 200, json.dumps(payload))
        http_pairs = (payload or {}).get("suggestions") if isinstance(payload, dict) else []
        checks.check("http-suggest-one", isinstance(http_pairs, list) and len(http_pairs) == 1, json.dumps(payload))
        status, payload = request_json(base + "/api/items", timeout=8)
        checks.check("http-items-200", status == 200)
        http_map = item_map(payload if isinstance(payload, list) else [])
        checks.check("http-burst", ((http_map.get("IMG_2001.jpg") or {}).get("stack") or {}).get("kind") == "burst")
        checks.check("http-live", ((http_map.get("LIVE_0001.jpg") or {}).get("stack") or {}).get("kind") == "live")
        status, payload = request_json(
            base + "/api/people/not-same",
            method="POST",
            body={"a": ada, "b": bob},
            timeout=8,
        )
        checks.check("http-not-same-200", status == 200, json.dumps(payload))
        status, payload = request_json(base + "/api/people/suggestions", timeout=8)
        after_block = (payload or {}).get("suggestions") if isinstance(payload, dict) else []
        checks.check("not-same-hides", after_block == [], json.dumps(payload))
        still = json.loads(run_library(root, ["people", "list"]).stdout)
        still_names = {row.get("name") for row in still.get("people") or []}
        checks.check("not-same-no-merge", still_names >= {"Ada", "Bob"}, json.dumps(sorted(still_names)))
        status, payload = request_json(
            base + "/api/people/merge",
            method="POST",
            body={"keepId": ada, "dropId": bob},
            timeout=8,
        )
        checks.check("merge-still-explicit", status == 200 and isinstance(payload, dict) and payload.get("id") == ada, json.dumps(payload))
    finally:
        stop_owned(server, extra_pids=pids)
    merged = json.loads(run_library(root, ["people", "list"]).stdout)
    merged_names = {row.get("name") for row in merged.get("people") or []}
    checks.check("merge-kept-ada", "Ada" in merged_names and "Bob" not in merged_names, json.dumps(sorted(merged_names)))
    return record


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    wait_catalog(url.rstrip("/"), ("near.jpg", "far.jpg", "IMG_2001.jpg", "LIVE_0001.jpg"))
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return names.indexOf('near.jpg') >= 0 && names.indexOf('IMG_2001.jpg') >= 0;
        }""",
        timeout=20000,
    )
    grid = page.evaluate(
        """() => {
          const cells = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]'));
          return {
            names: cells.map(el => el.getAttribute('data-filename')),
            burst: cells.filter(el => el.dataset.stackKind === 'burst').map(el => ({
              name: el.getAttribute('data-filename'),
              count: el.dataset.stackCount,
              badge: (el.querySelector('.burst-badge') || {}).textContent || '',
              rep: el.dataset.stackRep
            })),
            live: cells.filter(el => (el.querySelector('.live-badge') || {}).textContent === 'LIVE').map(el => el.getAttribute('data-filename')),
            hiddenBurst: cells.filter(el => el.dataset.stackKind === 'burst' && el.dataset.stackRep === '0').length
          };
        }"""
    )
    record["grid"] = grid
    names = grid.get("names") or []
    checks.check("grid-hides-burst-members", "IMG_2002.jpg" not in names and "IMG_2003.jpg" not in names, json.dumps(names))
    checks.check("grid-shows-burst-rep", "IMG_2001.jpg" in names, json.dumps(names))
    checks.check("grid-one-burst", len(grid.get("burst") or []) == 1, json.dumps(grid.get("burst")))
    checks.check("grid-burst-badge", "3" in ((grid.get("burst") or [{}])[0].get("badge") or ""), json.dumps(grid.get("burst")))
    checks.check("grid-live-badge", "LIVE_0001.jpg" in (grid.get("live") or []), json.dumps(grid.get("live")))
    page.screenshot(path=str(artifacts / "burst-tile.png"))

    page.locator('[data-filename="IMG_2001.jpg"]').click()
    page.wait_for_function("() => !document.getElementById('viewer').hidden", timeout=8000)
    stack = page.evaluate(
        """() => {
          const nav = document.getElementById('viewer-stack');
          const buttons = nav ? Array.from(nav.querySelectorAll('button')).map(el => el.textContent.trim()) : [];
          return { hidden: nav ? nav.hidden : true, count: buttons.length, labels: buttons };
        }"""
    )
    record["viewerStack"] = stack
    checks.check("viewer-stack-open", stack.get("hidden") is False and int(stack.get("count") or 0) >= 3, json.dumps(stack))
    page.screenshot(path=str(artifacts / "burst-viewer.png"))

    page.evaluate(
        """() => {
          window.__printed = false;
          window.print = () => { window.__printed = true; };
        }"""
    )
    page.keyboard.press("Control+p")
    printed = page.evaluate(
        """() => ({
          printed: !!window.__printed,
          src: (document.getElementById('print-image') || {}).getAttribute('src') || ''
        })"""
    )
    record["print"] = printed
    checks.check("print-ctrl-p", printed.get("printed") is True, json.dumps(printed))
    checks.check("print-src", "/api/media/" in (printed.get("src") or ""), json.dumps(printed))
    page.keyboard.press("Escape")
    page.wait_for_function("() => document.getElementById('viewer').hidden", timeout=5000)

    page.evaluate(
        """() => {
          const select = document.getElementById('language');
          if (!select) { return; }
          select.value = 'zh-Hans';
          select.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )
    page.wait_for_function(
        """() => {
          const lang = window.LibraryI18n && window.LibraryI18n.getLanguage ? window.LibraryI18n.getLanguage() : '';
          const print = ((document.getElementById('viewer-print') || {}).textContent || '').trim();
          return lang === 'zh-Hans' && print === '打印';
        }""",
        timeout=8000,
    )
    zh = page.evaluate(
        """() => ({
          print: ((document.getElementById('viewer-print') || {}).textContent || '').trim(),
          review: ((document.getElementById('people-review') || {}).textContent || '').trim(),
          skip: ((document.getElementById('merge-wizard-skip') || {}).textContent || '').trim(),
          notSame: ((document.getElementById('merge-wizard-not-same') || {}).textContent || '').trim(),
          burst: ((document.querySelector('.burst-badge') || {}).textContent || '').trim(),
          burstT: window.LibraryI18n ? window.LibraryI18n.t('burstBadge', { n: 3 }) : ''
        })"""
    )
    record["zh"] = zh
    checks.check("zh-print", zh.get("print") == "打印", json.dumps(zh))
    checks.check("zh-review", zh.get("review") == "核对可能是同一人", json.dumps(zh))
    checks.check("zh-skip", zh.get("skip") == "跳过", json.dumps(zh))
    checks.check("zh-not-same", zh.get("notSame") == "不是同一人", json.dumps(zh))
    checks.check("zh-burst", "连拍" in ((zh.get("burst") or "") + (zh.get("burstT") or "")), json.dumps(zh))
    page.screenshot(path=str(artifacts / "chinese-burn.png"))
    page.locator("#language").select_option("en")
    page.wait_for_function(
        "() => (document.getElementById('viewer-print') || {}).textContent === 'Print'",
        timeout=8000,
    )

    page.wait_for_function(
        "() => { const b = document.getElementById('people-review'); return b && !b.hidden; }",
        timeout=8000,
    )
    people_before = page.evaluate(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent)"
    )
    record["peopleBefore"] = people_before
    checks.check("people-ada-bob", "Ada" in people_before and "Bob" in people_before, json.dumps(people_before))
    page.locator("#people-review").click()
    page.wait_for_function(
        "() => { const d = document.getElementById('merge-wizard'); return d && d.open; }",
        timeout=5000,
    )
    page.screenshot(path=str(artifacts / "merge-wizard.png"))
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => { const d = document.getElementById('merge-wizard'); return d && !d.open; }",
        timeout=5000,
    )
    people_esc = page.evaluate(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent)"
    )
    checks.check("esc-no-merge", "Ada" in people_esc and "Bob" in people_esc, json.dumps(people_esc))

    page.locator("#people-review").click()
    page.wait_for_function(
        "() => { const d = document.getElementById('merge-wizard'); return d && d.open; }",
        timeout=5000,
    )
    page.locator("#merge-wizard-skip").click()
    page.wait_for_function(
        "() => { const d = document.getElementById('merge-wizard'); return d && !d.open; }",
        timeout=5000,
    )
    people_skip = page.evaluate(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent)"
    )
    checks.check("skip-no-merge", "Ada" in people_skip and "Bob" in people_skip, json.dumps(people_skip))

    page.locator("#people-review").click()
    page.wait_for_function(
        "() => { const d = document.getElementById('merge-wizard'); return d && d.open; }",
        timeout=5000,
    )
    page.locator("#merge-wizard-merge").click()
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent);
          return names.indexOf('Ada') >= 0 && names.indexOf('Bob') < 0;
        }""",
        timeout=8000,
    )
    people_merged = page.evaluate(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent)"
    )
    record["peopleMerged"] = people_merged
    checks.check("wizard-merge-ada", "Ada" in people_merged and "Bob" not in people_merged, json.dumps(people_merged))
    return record


def seed_browser_root(root: Path, media_src: Path, artifacts: Path) -> None:
    folder = artifacts / "browser-media"
    copy_rels(media_src, folder, PEOPLE_RELS + LIVE_RELS)
    write_burst_jpegs(folder / "burst", media_src / "b" / "no-exif.jpg")
    scan = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    if scan.returncode != 0:
        raise RuntimeError(scan.stderr[-200:])
    listed = item_map(json.loads(run_library(root, ["items"]).stdout))
    near = listed["near.jpg"]
    far = listed["far.jpg"]
    run_library(root, ["annotate", near["id"], "--person", "Ada"])
    run_library(root, ["annotate", far["id"], "--person", "Bob"])
    named = item_map(json.loads(run_library(root, ["items"]).stdout))
    ada = person_id_for(named["near.jpg"])
    bob = person_id_for(named["far.jpg"])
    plant_index(root, {ada: [1.0, 0.0, 0.0], bob: [0.98, 0.199, 0.0]})


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library people suggestions",
        "python -m library people not-same <a> <b>",
        "python -m library items",
    ]
    extra: dict[str, str] = {}
    try:
        prove_static(checks)
        prove_stacks_unit(checks)
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "burn-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["burn-api.json"] = str(artifacts / "burn-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed_browser_root(isolated, media_src, artifacts)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("near.jpg", "far.jpg", "IMG_2001.jpg", "LIVE_0001.jpg"))
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
            (artifacts / "burn-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["burn-browser.json"] = str(artifacts / "burn-browser.json")
            extra["burst-tile.png"] = str(artifacts / "burst-tile.png")
            extra["burst-viewer.png"] = str(artifacts / "burst-viewer.png")
            extra["merge-wizard.png"] = str(artifacts / "merge-wizard.png")
            extra["chinese-burn.png"] = str(artifacts / "chinese-burn.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-burn-runner", False, str(exc))
    return write_result("TASTE-BURN", "slice", checks, artifacts, commands, extra)
