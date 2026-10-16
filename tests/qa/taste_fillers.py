"""Recently added, folder filter, keyboard help, missing-original badge."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items, load_sources
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import collect_console, wait_catalog

FOLDER_A = ("a/IMG_1042.jpg", "a/near.jpg")
FOLDER_B = ("b/no-exif.jpg", "b/far.jpg")
I18N = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "i18n.js"
HTML = Path(__file__).resolve().parents[2] / "library" / "web" / "index.html"
JS = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "library.js"


def filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") or "" for item in items]


def item_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("filename") or "": item for item in items}


def prove_static(checks: Checks) -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    checks.check("html-recent", 'id="filter-recent"' in html)
    checks.check("html-folder", 'id="filter-folder"' in html)
    checks.check("html-help", 'id="keyboard-help"' in html)
    checks.check("html-fit", 'id="viewer-fit"' in html and 'id="viewer-fill"' in html)
    checks.check("html-locate", 'id="locate-original"' in html)
    checks.check("js-recent-query", "merged.recent" in js)
    checks.check("js-source-query", "merged.source" in js)
    checks.check("js-missing-badge", "missing-badge" in js)
    checks.check("js-fit-fill", "toggleFitFill" in js)
    checks.check("js-help-key", "toggleKeyboardHelp" in js)
    checks.check("i18n-recent-en", 'recentlyAdded: "Recently added"' in i18n)
    checks.check("i18n-recent-zh", 'recentlyAdded: "最近添加"' in i18n)
    checks.check("i18n-locate-zh", 'locate: "定位"' in i18n)
    checks.check("i18n-missing-zh", 'missingBadge: "缺失"' in i18n)
    checks.check("i18n-help-zh", 'keyboardHelpTitle: "键盘快捷键"' in i18n)
    checks.check("i18n-fill-zh", 'fill: "铺满"' in i18n)
    checks.check("i18n-show-zh", 'showFolder: "显示照片"' in i18n)
    checks.check("no-auto-delete-js", "auto-delete" not in js.lower())


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    folder_a = artifacts / "api-a"
    folder_b = artifacts / "api-b"
    copy_rels(media_src, folder_a, FOLDER_A)
    copy_rels(media_src, folder_b, FOLDER_B)
    before_b = hash_tree(folder_b)

    scan_a = run_library(root, ["scan", str(folder_a), "--serve-from-there"], timeout=180)
    checks.check("scan-a-ok", scan_a.returncode == 0, scan_a.stderr[-200:])
    recent_a = json.loads(run_library(root, ["items", "--recent", "1"]).stdout)
    names_a = set(filenames(recent_a))
    checks.check("recent-after-a", names_a == {"IMG_1042.jpg", "near.jpg"}, json.dumps(sorted(names_a)))

    scan_b = run_library(root, ["scan", str(folder_b), "--serve-from-there"], timeout=180)
    checks.check("scan-b-ok", scan_b.returncode == 0, scan_b.stderr[-200:])
    recent_b = json.loads(run_library(root, ["items", "--recent", "1"]).stdout)
    names_b = set(filenames(recent_b))
    checks.check("recent-after-b", names_b == {"no-exif.jpg", "far.jpg"}, json.dumps(sorted(names_b)))

    sources = load_sources(root)
    checks.check("two-sources", len(sources) == 2, json.dumps([src.get("id") for src in sources]))
    src_a = next((src for src in sources if str(folder_a.resolve()) in str((src.get("origin") or {}).get("lastKnownPath") or "")), None)
    src_b = next((src for src in sources if str(folder_b.resolve()) in str((src.get("origin") or {}).get("lastKnownPath") or "")), None)
    if src_a is None or src_b is None:
        src_a = sources[0]
        src_b = sources[1]
        listed_all = item_map(json.loads(run_library(root, ["items"]).stdout))
        if "IMG_1042.jpg" in listed_all:
            for loc in listed_all["IMG_1042.jpg"].get("locations") or []:
                sid = loc.get("sourceId")
                if sid:
                    src_a = next((src for src in sources if src.get("id") == sid), src_a)
        if "far.jpg" in listed_all:
            for loc in listed_all["far.jpg"].get("locations") or []:
                sid = loc.get("sourceId")
                if sid:
                    src_b = next((src for src in sources if src.get("id") == sid), src_b)
    record["sourceA"] = src_a.get("id") if src_a else ""
    record["sourceB"] = src_b.get("id") if src_b else ""
    checks.check("source-ids", bool(record["sourceA"] and record["sourceB"] and record["sourceA"] != record["sourceB"]))

    only_a = json.loads(run_library(root, ["items", "--source", record["sourceA"]]).stdout)
    only_b = json.loads(run_library(root, ["items", "--source", record["sourceB"]]).stdout)
    checks.check("source-a-names", set(filenames(only_a)) == {"IMG_1042.jpg", "near.jpg"}, json.dumps(filenames(only_a)))
    checks.check("source-b-names", set(filenames(only_b)) == {"no-exif.jpg", "far.jpg"}, json.dumps(filenames(only_b)))

    bad_recent = run_library(root, ["items", "--recent", "2"])
    checks.check("recent-invalid", bad_recent.returncode != 0, bad_recent.stderr[-200:])

    extra = folder_a / "a" / "late.jpg"
    shutil.copy2(media_src / "b" / "created.jpg", extra)
    rescan = run_library(root, ["rescan", record["sourceA"]], timeout=180)
    checks.check("rescan-a-ok", rescan.returncode == 0, rescan.stderr[-200:])
    recent_late = json.loads(run_library(root, ["items", "--recent", "1"]).stdout)
    late_names = set(filenames(recent_late))
    checks.check("recent-rescan-late", "late.jpg" in late_names, json.dumps(sorted(late_names)))
    extra.unlink()

    listed = item_map(json.loads(run_library(root, ["items"]).stdout))
    missing_item = listed["IMG_1042.jpg"]
    missing_id = missing_item["id"]
    original = Path(missing_item.get("lastKnownPath") or "")
    if not original.is_file():
        for loc in missing_item.get("locations") or []:
            cand = Path(loc.get("lastKnownPath") or "")
            if cand.is_file():
                original = cand
                break
    checks.check("missing-target-exists", original.is_file(), str(original))
    original.unlink()
    checks.check("original-unlinked", not original.is_file())

    server, url, pids = start_owned(root)
    try:
        base = url.rstrip("/")
        status, payload = request_json(base + "/api/items?source=" + record["sourceA"], timeout=8)
        checks.check("http-source-200", status == 200, json.dumps(payload if not isinstance(payload, list) else filenames(payload)))
        http_a = filenames(payload if isinstance(payload, list) else [])
        checks.check("http-source-a", "IMG_1042.jpg" in http_a and "far.jpg" not in http_a, json.dumps(http_a))

        status, payload = request_json(base + "/api/items?recent=1", timeout=8)
        checks.check("http-recent-200", status == 200)
        http_recent = filenames(payload if isinstance(payload, list) else [])
        checks.check("http-recent-has-ids", status == 200 and isinstance(payload, list), json.dumps(http_recent))

        status, payload = request_json(base + "/api/items?recent=no", timeout=5)
        checks.check(
            "http-recent-invalid",
            status == 400 and isinstance(payload, dict) and payload.get("error") == "invalid-argument",
            json.dumps(payload),
        )

        status, payload = request_json(base + "/api/items", timeout=8)
        by_name = item_map(payload if isinstance(payload, list) else [])
        gone = by_name.get("IMG_1042.jpg") or {}
        checks.check("missing-still-listed", status == 200 and bool(gone.get("id")), json.dumps(gone.get("filename")))
        checks.check("missing-available-false", gone.get("available") is False, json.dumps(gone.get("available")))
        checks.check("missing-last-known", bool(gone.get("lastKnownPath")), json.dumps(gone.get("lastKnownPath")))
        checks.check("missing-folder-exists", bool(gone.get("lastKnownFolder")), json.dumps(gone.get("lastKnownFolder")))
        checks.check("no-auto-delete-catalog", (root / "catalog" / "items" / (missing_id + ".json")).is_file())

        status, loc = request_json(base + "/api/items/" + missing_id + "/locate", method="POST", body={}, timeout=8)
        checks.check("locate-200", status == 200, json.dumps(loc))
        checks.check("locate-mode", isinstance(loc, dict) and loc.get("mode") == "locate", json.dumps(loc))
        checks.check("locate-folder", isinstance(loc, dict) and bool(loc.get("folder")), json.dumps(loc))
        checks.check("locate-no-delete", (root / "catalog" / "items" / (missing_id + ".json")).is_file())
        record["locate"] = loc if isinstance(loc, dict) else {}
        record["missingId"] = missing_id
    finally:
        stop_owned(server, extra_pids=pids)

    checks.check("folder-b-bytes-stay", hash_tree(folder_b) == before_b)
    record["recentAfterB"] = sorted(names_b)
    return record


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks, source_a: str, source_b: str) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    chrome = page.evaluate(
        """() => ({
          recent: !!(document.getElementById('filter-recent')),
          folder: !!(document.getElementById('filter-folder')),
          help: !!(document.getElementById('keyboard-help')),
          fit: !!(document.getElementById('viewer-fit')),
          fill: !!(document.getElementById('viewer-fill')),
          locate: !!(document.getElementById('locate-original')),
          folderOptions: Array.from(document.querySelectorAll('#filter-folder option')).map(function (n) { return n.value; })
        })"""
    )
    record["chrome"] = chrome
    checks.check("ui-recent", chrome.get("recent") is True)
    checks.check("ui-folder", chrome.get("folder") is True)
    checks.check("ui-help", chrome.get("help") is True)
    checks.check("ui-fit-fill", chrome.get("fit") is True and chrome.get("fill") is True)
    checks.check("ui-locate", chrome.get("locate") is True)
    checks.check("ui-folder-options", len(chrome.get("folderOptions") or []) >= 3, json.dumps(chrome.get("folderOptions")))

    page.locator("#filter-recent").click()
    page.wait_for_function(
        """() => {
          const recent = document.getElementById('grid').dataset.recent;
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return recent === '1' && names.length > 0 && names.indexOf('IMG_1042.jpg') < 0 && names.indexOf('near.jpg') < 0;
        }""",
        timeout=8000,
    )
    recent_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["recentGrid"] = recent_names
    checks.check("click-recent", True)
    checks.check(
        "recent-grid-not-all",
        set(recent_names or []) <= {"far.jpg", "no-exif.jpg"} and bool(recent_names),
        json.dumps(recent_names),
    )
    page.screenshot(path=str(artifacts / "recently-added.png"))

    page.locator("#filter-all").click()
    page.wait_for_function(
        "() => !document.getElementById('grid').dataset.recent",
        timeout=8000,
    )
    page.locator("#filter-folder").select_option(source_a)
    page.wait_for_function(
        """() => {
          const source = document.getElementById('grid').dataset.source || '';
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return source.indexOf('src_') === 0 && names.length > 0 && names.indexOf('far.jpg') < 0 && names.indexOf('no-exif.jpg') < 0;
        }""",
        timeout=8000,
    )
    folder_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["folderGrid"] = folder_names
    checks.check("folder-filter-a", "far.jpg" not in (folder_names or []), json.dumps(folder_names))
    checks.check("folder-filter-has-a", "IMG_1042.jpg" in (folder_names or []) or "near.jpg" in (folder_names or []), json.dumps(folder_names))
    page.screenshot(path=str(artifacts / "folder-filter.png"))

    page.locator("#view-settings").click()
    page.wait_for_selector("#settings-view", timeout=5000)
    page.wait_for_function(
        "() => document.querySelectorAll('#settings-sources .source-show').length >= 1",
        timeout=8000,
    )
    page.locator("#settings-sources .source-show").nth(1 if source_b else 0).click()
    page.wait_for_function(
        "() => document.getElementById('view-library').getAttribute('aria-pressed') === 'true' && document.getElementById('grid').dataset.source",
        timeout=8000,
    )
    checks.check("settings-show-photos", True)
    page.locator("#clear-filters").click()
    page.wait_for_function(
        "() => !document.getElementById('grid').dataset.source",
        timeout=8000,
    )

    page.keyboard.press("Shift+Slash")
    page.wait_for_function(
        "() => document.getElementById('keyboard-help') && document.getElementById('keyboard-help').open",
        timeout=5000,
    )
    help_open = page.evaluate("() => ({ open: document.getElementById('keyboard-help').open, title: (document.getElementById('keyboard-help-title') || {}).textContent })")
    record["help"] = help_open
    checks.check("help-open", help_open.get("open") is True, json.dumps(help_open))
    checks.check("help-title", "Keyboard" in (help_open.get("title") or ""), json.dumps(help_open.get("title")))
    page.screenshot(path=str(artifacts / "keyboard-help.png"))
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.getElementById('keyboard-help').open",
        timeout=5000,
    )
    checks.check("help-esc", True)

    page.locator('[data-filename="near.jpg"]').click()
    page.wait_for_function("() => !document.getElementById('viewer').hidden", timeout=8000)
    page.keyboard.press("v")
    page.wait_for_function(
        "() => document.getElementById('viewer').dataset.fitMode === 'fill'",
        timeout=5000,
    )
    checks.check("fill-key", True)
    page.locator("#viewer-fit").click()
    page.wait_for_function(
        "() => document.getElementById('viewer').dataset.fitMode === 'fit'",
        timeout=5000,
    )
    checks.check("fit-button", True)
    page.keyboard.press("i")
    page.wait_for_function(
        "() => document.getElementById('viewer-info').getAttribute('aria-expanded') === 'true'",
        timeout=5000,
    )
    checks.check("info-key", True)
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.getElementById('viewer-info').getAttribute('aria-expanded') === 'false'",
        timeout=5000,
    )
    page.keyboard.press("Escape")
    page.wait_for_function("() => document.getElementById('viewer').hidden", timeout=5000)

    page.locator('[data-filename="IMG_1042.jpg"]').click()
    page.wait_for_function("() => !document.getElementById('viewer').hidden", timeout=8000)
    missing = page.evaluate(
        """() => {
          const cell = document.querySelector('#grid .cell[data-filename=\"IMG_1042.jpg\"]');
          const badge = cell && cell.querySelector('.missing-badge');
          const locate = document.getElementById('locate-original');
          const banner = document.getElementById('unavailable-banner');
          return {
            tileMissing: !!(cell && cell.dataset.missing === '1'),
            badge: badge ? badge.textContent : '',
            locateHidden: locate ? locate.hidden : true,
            locateDisabled: locate ? locate.disabled : true,
            bannerHidden: banner ? banner.hidden : true
          };
        }"""
    )
    record["missing"] = missing
    checks.check("tile-missing", missing.get("tileMissing") is True, json.dumps(missing))
    checks.check("tile-badge-text", "Missing" in (missing.get("badge") or ""), json.dumps(missing.get("badge")))
    checks.check("locate-offered", missing.get("locateHidden") is False, json.dumps(missing))
    page.locator("#viewer-info").click()
    page.wait_for_function(
        "() => document.getElementById('info-missing')",
        timeout=5000,
    )
    info_text = page.evaluate("() => (document.getElementById('info-missing') || {}).textContent || ''")
    checks.check("info-missing", "Missing" in info_text or "Original" in info_text, info_text)
    page.screenshot(path=str(artifacts / "missing-original.png"))
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    page.locator("#language").select_option("zh-Hans")
    page.wait_for_function(
        "() => (document.getElementById('filter-recent') || {}).textContent === '最近添加'",
        timeout=8000,
    )
    zh = page.evaluate(
        """() => ({
          recent: (document.getElementById('filter-recent') || {}).textContent,
          locate: (document.getElementById('locate-original') || {}).textContent,
          fit: (document.getElementById('viewer-fit') || {}).textContent,
          fill: (document.getElementById('viewer-fill') || {}).textContent,
          show: ((document.querySelector('.source-show') || {}).textContent) || ''
        })"""
    )
    record["zh"] = zh
    checks.check("zh-recent", zh.get("recent") == "最近添加", json.dumps(zh))
    checks.check("zh-fit", zh.get("fit") == "适合窗口", json.dumps(zh))
    checks.check("zh-fill", zh.get("fill") == "铺满", json.dumps(zh))
    page.screenshot(path=str(artifacts / "chinese-fillers.png"))
    return record


def seed_browser_root(root: Path, media_src: Path, artifacts: Path) -> dict[str, str]:
    folder_a = artifacts / "browser-a"
    folder_b = artifacts / "browser-b"
    copy_rels(media_src, folder_a, FOLDER_A)
    copy_rels(media_src, folder_b, FOLDER_B)
    scan_a = run_library(root, ["scan", str(folder_a), "--serve-from-there"], timeout=180)
    if scan_a.returncode != 0:
        raise RuntimeError(scan_a.stderr[-200:])
    scan_b = run_library(root, ["scan", str(folder_b), "--serve-from-there"], timeout=180)
    if scan_b.returncode != 0:
        raise RuntimeError(scan_b.stderr[-200:])
    items = item_map(json.loads(run_library(root, ["items"]).stdout))
    sources = load_sources(root)
    src_a = ""
    src_b = ""
    for loc in (items.get("IMG_1042.jpg") or {}).get("locations") or []:
        if loc.get("sourceId"):
            src_a = loc.get("sourceId") or ""
    for loc in (items.get("far.jpg") or {}).get("locations") or []:
        if loc.get("sourceId"):
            src_b = loc.get("sourceId") or ""
    if not src_a and sources:
        src_a = sources[0].get("id") or ""
    if not src_b and len(sources) > 1:
        src_b = sources[1].get("id") or ""
    original = Path((items.get("IMG_1042.jpg") or {}).get("lastKnownPath") or "")
    if not original.is_file():
        for loc in (items.get("IMG_1042.jpg") or {}).get("locations") or []:
            cand = Path(loc.get("lastKnownPath") or "")
            if cand.is_file():
                original = cand
                break
    if original.is_file():
        original.unlink()
    return {"sourceA": src_a, "sourceB": src_b}


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library items --source <id>",
        "python -m library items --recent 1",
        "python -m library locate <id>",
    ]
    extra: dict[str, str] = {}
    try:
        prove_static(checks)
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "fillers-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["fillers-api.json"] = str(artifacts / "fillers-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        ids = seed_browser_root(isolated, media_src, artifacts)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks, ids["sourceA"], ids["sourceB"])
                unexpected = [
                    message
                    for message in errors
                    if "status of 400" not in message and "status of 404" not in message
                ]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "fillers-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["fillers-browser.json"] = str(artifacts / "fillers-browser.json")
            extra["recently-added.png"] = str(artifacts / "recently-added.png")
            extra["folder-filter.png"] = str(artifacts / "folder-filter.png")
            extra["keyboard-help.png"] = str(artifacts / "keyboard-help.png")
            extra["missing-original.png"] = str(artifacts / "missing-original.png")
            extra["chinese-fillers.png"] = str(artifacts / "chinese-fillers.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-fillers-runner", False, str(exc))
    return write_result("TASTE-FILLERS", "slice", checks, artifacts, commands, extra)
