"""English / Simplified Chinese chrome and search. Not an F-id grade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import annotate_json, collect_console, wait_catalog

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "a/near.jpg",
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
    json.loads(
        annotate_json(
            root,
            near["id"],
            {"people": [{"name": "小明"}], "places": [{"name": "北京"}], "things": [{"name": "徒步"}]},
            artifacts,
            "chinese.json",
        ).stdout
    )
    return {"Ada": ada_id}


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    seed(root, media_src, artifacts / "api")
    listed = json.loads(run_library(root, ["items", "--q", "小明"]).stdout)
    names = [item.get("filename") for item in listed]
    checks.check("search-chinese-person", "near.jpg" in names, json.dumps(names))
    listed = json.loads(run_library(root, ["items", "--q", "北京"]).stdout)
    names = [item.get("filename") for item in listed]
    checks.check("search-chinese-place", "near.jpg" in names, json.dumps(names))
    listed = json.loads(run_library(root, ["items", "--q", "徒步"]).stdout)
    names = [item.get("filename") for item in listed]
    checks.check("search-chinese-tag", "near.jpg" in names, json.dumps(names))
    settings = json.loads(run_library(root, ["settings", "get"]).stdout)
    checks.check("language-default-en", settings.get("language") == "en", json.dumps(settings.get("language")))
    set_lang = run_library(root, ["settings", "set", "language", "zh-Hans"])
    checks.check("language-set-ok", set_lang.returncode == 0, set_lang.stderr[-200:])
    after = json.loads(run_library(root, ["settings", "get"]).stdout)
    checks.check("language-persists", after.get("language") == "zh-Hans", json.dumps(after.get("language")))
    record["language"] = after.get("language")
    return record


def chrome_copy(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => ({
          lang: document.documentElement.lang,
          library: (document.getElementById('view-library') || {}).textContent,
          search: (document.getElementById('search') || {}).placeholder,
          all: (document.getElementById('filter-all') || {}).textContent,
          people: (document.getElementById('people-heading') || {}).textContent,
          group: (document.querySelector('#filter-bar .toolbar-field span') || {}).textContent,
          clear: (document.getElementById('clear-filters') || {}).textContent,
          processing: (document.getElementById('jobs-heading') || {}).textContent,
          empty: (document.querySelector('#empty-library p') || {}).textContent || '',
          setting: window.libraryTest ? window.libraryTest.language() : '',
          select: (document.getElementById('language') || {}).value
        })"""
    )


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    english = chrome_copy(page)
    record["english"] = english
    checks.check("html-lang-en", english.get("lang") == "en", json.dumps(english))
    checks.check("library-en", english.get("library") == "Library", json.dumps(english))
    checks.check("search-en", english.get("search") == "Search", json.dumps(english))
    checks.check("people-en", english.get("people") == "People", json.dumps(english))

    page.locator("#language").select_option("zh-Hans")
    page.wait_for_function(
        "() => document.documentElement.lang === 'zh-Hans' && (document.getElementById('view-library') || {}).textContent === '图库'",
        timeout=8000,
    )
    chinese = chrome_copy(page)
    record["chinese"] = chinese
    checks.check("html-lang-zh", chinese.get("lang") == "zh-Hans", json.dumps(chinese))
    checks.check("library-zh", chinese.get("library") == "图库", json.dumps(chinese))
    checks.check("search-zh", chinese.get("search") == "搜索", json.dumps(chinese))
    checks.check("all-zh", chinese.get("all") == "全部", json.dumps(chinese))
    checks.check("people-zh", chinese.get("people") == "人物", json.dumps(chinese))
    checks.check("processing-zh", chinese.get("processing") == "处理中", json.dumps(chinese))
    checks.check("language-select-zh", chinese.get("select") == "zh-Hans", json.dumps(chinese))

    page.fill("#search", "小明")
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return names.indexOf('near.jpg') >= 0 && names.indexOf('IMG_1042.jpg') < 0;
        }""",
        timeout=8000,
    )
    page.fill("#search", "没有这个词")
    page.wait_for_function(
        "() => (document.querySelector('#grid > p') || {}).textContent.indexOf('没有与') === 0",
        timeout=8000,
    )
    empty_zh = page.evaluate("() => (document.querySelector('#grid > p') || {}).textContent || ''")
    record["emptyZh"] = empty_zh
    checks.check("empty-search-zh", "没有这个词" in empty_zh, empty_zh)
    page.fill("#search", "")
    page.wait_for_function(
        "() => document.querySelectorAll('#grid .cell[data-slot=\"grid\"]').length >= 3",
        timeout=8000,
    )

    status, settings = request_json(url.rstrip("/") + "/api/settings", timeout=5)
    checks.check("settings-language-zh", status == 200 and settings.get("language") == "zh-Hans", json.dumps(settings))

    page.reload(wait_until="domcontentloaded")
    page.wait_for_function(
        "() => document.documentElement.lang === 'zh-Hans' && (document.getElementById('people-heading') || {}).textContent === '人物'",
        timeout=15000,
    )
    persisted = chrome_copy(page)
    record["persisted"] = persisted
    checks.check("language-stays-after-reload", persisted.get("lang") == "zh-Hans" and persisted.get("people") == "人物", json.dumps(persisted))
    page.screenshot(path=str(artifacts / "chinese-chrome.png"))
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "i18n-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["i18n-api.json"] = str(artifacts / "i18n-api.json")
        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed(isolated, media_src, artifacts / "browser")
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg"))
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
            (artifacts / "i18n-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["i18n-browser.json"] = str(artifacts / "i18n-browser.json")
            extra["chinese-chrome.png"] = str(artifacts / "chinese-chrome.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-i18n-runner", False, str(exc))
    return write_result("TASTE-I18N", "slice", checks, artifacts, ["python -m tests.qa slice TASTE-I18N"], extra)
