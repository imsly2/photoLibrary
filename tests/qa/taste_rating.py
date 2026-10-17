"""Photo rating system. Not an F-id grade. Never deletes. No cloud."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import item_rel, load_item
from library.httpjson import request_json
from library.records import clone, ordered_item
from library.service import Library
from library.settings import DEFAULTS, KEY_ORDER, fill_missing_defaults, validate_complete
from tests.qa.s00 import (
    PRODUCT_ROOT,
    Checks,
    _env,
    assert_no_pillow_in_server,
    parse_json,
    run_library,
)
from tests.qa.s03 import png_size
from tests.qa.s08 import fresh_root, settings_port, start_owned, stop_owned, write_result


def collect_console(page: Any) -> list[str]:
    errors: list[str] = []

    def on_console(msg: Any) -> None:
        if msg.type == "error":
            errors.append(msg.text)

    def on_pageerror(exc: Any) -> None:
        errors.append(str(exc))

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    return errors


def test_env() -> dict[str, str]:
    env = _env()
    env["LIBRARY_TEST"] = "1"
    return env


def _ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-y", *args], capture_output=True, text=True, check=False)
    dest = Path(args[-1])
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 200:
        raise RuntimeError(proc.stderr[-400:] if proc.stderr else f"ffmpeg failed: {args}")


def write_rating_media(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    sharp = folder / "sharp.jpg"
    _ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1280x720:rate=1:duration=1",
            "-f",
            "lavfi",
            "-i",
            "color=c=0xE0AC7A:s=220x260:d=1",
            "-filter_complex",
            "[1:v]format=rgb24[face];[0:v][face]overlay=530:230",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(sharp),
        ]
    )
    blur = folder / "blur.jpg"
    _ffmpeg(["-i", str(sharp), "-vf", "gblur=sigma=14", "-frames:v", "1", "-q:v", "4", str(blur)])
    dark = folder / "dark.jpg"
    _ffmpeg(
        ["-i", str(sharp), "-vf", "eq=brightness=-0.55:gamma=0.45", "-frames:v", "1", "-q:v", "3", str(dark)]
    )
    bright = folder / "bright.jpg"
    _ffmpeg(
        ["-i", str(sharp), "-vf", "eq=brightness=0.55:saturation=0.2", "-frames:v", "1", "-q:v", "3", str(bright)]
    )
    colorful = folder / "colorful.jpg"
    _ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=960x640:rate=1:duration=1",
            "-vf",
            "hue=s=2.4,eq=saturation=1.8,gblur=sigma=1.8",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(colorful),
        ]
    )
    gray = folder / "graysharp.jpg"
    _ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=960x640:rate=1:duration=1",
            "-vf",
            "format=gray,format=yuvj420p",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(gray),
        ]
    )
    burst1 = folder / "burst_001.jpg"
    burst2 = folder / "burst_002.jpg"
    burst3 = folder / "burst_003.jpg"
    _ffmpeg(["-i", str(sharp), "-vf", "gblur=sigma=3", "-frames:v", "1", "-q:v", "3", str(burst1)])
    _ffmpeg(["-i", str(sharp), "-vf", "gblur=sigma=10", "-frames:v", "1", "-q:v", "4", str(burst2)])
    shutil.copy2(sharp, burst3)
    now = time.time()
    for offset, path in enumerate((burst1, burst2, burst3)):
        os.utime(path, (now + offset, now + offset))
    return {
        "sharp": sharp,
        "blur": blur,
        "dark": dark,
        "bright": bright,
        "colorful": colorful,
        "gray": gray,
        "burst1": burst1,
        "burst2": burst2,
        "burst3": burst3,
    }


def _item_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in items:
        if item.get("filename") == name:
            return item
    return {}


def _quality_of(root: Path, item_id: str) -> dict[str, Any]:
    item = load_item(root, item_id)
    rec = item.get("quality")
    return rec if isinstance(rec, dict) else {}


def _plant_face(root: Path, item_id: str) -> None:
    before = load_item(root, item_id)
    after = clone(before)
    after["faces"] = [{"personId": "person_rating_face", "box": [0.41, 0.32, 0.17, 0.36]}]
    transact(root, [{"path": item_rel(item_id), "before": before, "after": ordered_item(after)}])


def _original_path(item: dict[str, Any], root: Path) -> Path | None:
    from library.volumes import location_file

    for loc in item.get("locations") or []:
        if not isinstance(loc, dict) or loc.get("current") is not True:
            continue
        path = location_file(loc, root)
        if path is not None:
            return path
    return None


def prove_docs(checks: Checks) -> None:
    product = (PRODUCT_ROOT / "docs" / "PRODUCT.md").read_text(encoding="utf-8")
    contracts = (PRODUCT_ROOT / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
    ui = (PRODUCT_ROOT / "docs" / "UI-SPEC.md").read_text(encoding="utf-8")
    setup = (PRODUCT_ROOT / "setup.ps1").read_text(encoding="utf-8")
    i18n = (PRODUCT_ROOT / "library" / "web" / "assets" / "i18n.js").read_text(encoding="utf-8")
    html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
    checks.check("product-setup-ml-aesthetic", "setup-ml aesthetic" in product)
    checks.check("product-rate-photos", "rate-photos" in product)
    checks.check("product-rate-cmd", "`rate <id>`" in product or "rate <id>" in product)
    checks.check("product-rating-mode", "ratingMode" in product and "basic" in product)
    checks.check("contracts-rate", "/api/rate" in contracts and "/api/items/<id>/rating" in contracts)
    checks.check("contracts-hide-rejects", "hideRejects" in contracts and "never deletes" in contracts.lower() or "never delete" in contracts)
    checks.check("ui-rating-chips", "4 stars" in ui.lower() or "fourStarsUp" in html)
    checks.check("html-settings-rating", 'name="set-ratingMode"' in html and 'id="filter-stars"' in html)
    checks.check("setup-ps1-aesthetic", "setup-ml aesthetic" in setup and "Total 9" in setup)
    checks.check("i18n-zh-rating", "评分" in i18n and "四星及以上" in i18n and "精选" in i18n and "隐藏排除" in i18n and "模糊" in i18n)
    checks.check("default-rating-basic", DEFAULTS.get("ratingMode") == "basic")
    checks.check("default-rating-learn-off", DEFAULTS.get("ratingLearn") is False)
    checks.check("settings-key-rating", "ratingMode" in KEY_ORDER and "ratingLearn" in KEY_ORDER)
    legacy = {key: DEFAULTS[key] for key in KEY_ORDER if key not in {"ratingMode", "ratingLearn"}}
    migrated = validate_complete(fill_missing_defaults(legacy))
    checks.check("legacy-fills-rating", migrated.get("ratingMode") == "basic" and migrated.get("ratingLearn") is False)


def prove_cli_and_http(checks: Checks, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "rating-root")
    media = artifacts / "rating-media"
    if media.exists():
        shutil.rmtree(media)
    files = write_rating_media(media)
    record["media"] = {name: str(path) for name, path in files.items()}
    for name, path in files.items():
        checks.check(f"media-{name}", path.is_file() and path.stat().st_size > 400, str(path))

    scan = run_library(root, ["scan", str(media), "--serve-from-there"], timeout=120)
    checks.check("scan-exit", scan.returncode == 0, scan.stderr[-300:])
    items = parse_json(run_library(root, ["items"]).stdout)
    checks.check("scanned-9", isinstance(items, list) and len(items) >= 9, str(len(items) if isinstance(items, list) else items))
    by_name = {item.get("filename"): item for item in items} if isinstance(items, list) else {}
    sharp = by_name.get("sharp.jpg") or {}
    if sharp.get("id"):
        _plant_face(root, sharp["id"])

    setup = run_library(root, ["setup-ml", "aesthetic", "--backend", "fixture"], env=test_env(), timeout=180)
    setup_body = parse_json(setup.stdout) if setup.returncode == 0 else {}
    record["setup"] = setup_body
    checks.check("setup-ml-exit", setup.returncode == 0, setup.stderr[-300:])
    checks.check("setup-ml-ok", setup_body.get("ok") is True, json.dumps(setup_body))
    model = root / "models" / "aesthetic" / "nima-mobilenet.onnx"
    checks.check("fixture-model-file", model.is_file() and model.stat().st_size > 400, str(model))

    first = run_library(root, ["rate-photos"], timeout=180)
    first_body = parse_json(first.stdout) if first.returncode == 0 else {}
    record["rate"] = first_body
    checks.check("rate-exit", first.returncode == 0, first.stderr[-300:])
    checks.check("rate-ok", first_body.get("ok") is True, json.dumps(first_body))
    checks.check("rated-at-least-8", int(first_body.get("rated") or 0) >= 8, json.dumps(first_body))

    items = parse_json(run_library(root, ["items"]).stdout)
    by_name = {item.get("filename"): item for item in items} if isinstance(items, list) else {}
    sharp = by_name.get("sharp.jpg") or {}
    blur = by_name.get("blur.jpg") or {}
    dark = by_name.get("dark.jpg") or {}
    bright = by_name.get("bright.jpg") or {}
    colorful = by_name.get("colorful.jpg") or {}
    gray = by_name.get("graysharp.jpg") or {}
    burst1 = by_name.get("burst_001.jpg") or {}
    burst2 = by_name.get("burst_002.jpg") or {}
    burst3 = by_name.get("burst_003.jpg") or {}
    record["basicScores"] = {
        name: (row.get("rating") or {})
        for name, row in (
            ("sharp", sharp),
            ("blur", blur),
            ("dark", dark),
            ("bright", bright),
            ("colorful", colorful),
            ("gray", gray),
            ("burst1", burst1),
            ("burst2", burst2),
            ("burst3", burst3),
        )
    }
    sharp_s = (sharp.get("rating") or {}).get("suggested")
    blur_s = (blur.get("rating") or {}).get("suggested")
    checks.check("blur-below-sharp", type(blur_s) is int and type(sharp_s) is int and blur_s < sharp_s, f"blur={blur_s} sharp={sharp_s}")
    dark_flags = (dark.get("rating") or {}).get("flags") or []
    bright_flags = (bright.get("rating") or {}).get("flags") or []
    blur_flags = (blur.get("rating") or {}).get("flags") or []
    checks.check("dark-flagged", "too-dark" in dark_flags, json.dumps(dark_flags))
    checks.check("bright-flagged", "too-bright" in bright_flags, json.dumps(bright_flags))
    checks.check("blur-flagged", "blurry" in blur_flags, json.dumps(blur_flags))
    checks.check("burst3-best", (burst3.get("rating") or {}).get("bestOfGroup") is True, json.dumps(burst3.get("rating")))
    checks.check("burst-not-all-best", (burst1.get("rating") or {}).get("bestOfGroup") is not True or (burst2.get("rating") or {}).get("bestOfGroup") is not True)
    stack = burst3.get("stack") or {}
    checks.check("burst-stack", stack.get("kind") == "burst" and int(stack.get("count") or 0) >= 3, json.dumps(stack))
    checks.check("burst-rep-sharpest", stack.get("representative") is True, json.dumps(stack))
    face_q = ((_quality_of(root, sharp.get("id") or "") or {}).get("metrics") or {}).get("faceQuality")
    checks.check("face-quality-used", isinstance(face_q, (int, float)) and float(face_q) > 0, str(face_q))

    second = parse_json(run_library(root, ["rate-photos"], timeout=60).stdout)
    record["rescan"] = second
    checks.check("rescan-rated-0", int(second.get("rated", -1)) == 0, json.dumps(second))
    checks.check("rescan-skipped", int(second.get("skipped") or 0) >= 8, json.dumps(second))

    sharp_id = sharp.get("id")
    user = parse_json(run_library(root, ["rate", sharp_id, "--stars", "5"], timeout=30).stdout)
    checks.check("user-stars-5", (user.get("rating") or {}).get("yours") == 5, json.dumps(user.get("rating")))
    pick = parse_json(run_library(root, ["rate", sharp_id, "--pick"], timeout=30).stdout)
    checks.check("user-pick", (pick.get("rating") or {}).get("pick") is True, json.dumps(pick.get("rating")))
    blur_id = blur.get("id")
    reject = parse_json(run_library(root, ["rate", blur_id, "--reject"], timeout=30).stdout)
    checks.check("user-reject", (reject.get("rating") or {}).get("reject") is True, json.dumps(reject.get("rating")))
    blur_path = _original_path(blur, root)
    checks.check("reject-file-stays", blur_path is not None and blur_path.is_file(), str(blur_path))

    restarted = Library(root).items_list({})
    again = _item_by_name(restarted, "sharp.jpg")
    checks.check("stars-persist-restart", (again.get("rating") or {}).get("yours") == 5, json.dumps(again.get("rating")))
    checks.check("user-overrides-suggested", (again.get("rating") or {}).get("stars") == 5, json.dumps(again.get("rating")))

    hidden = parse_json(run_library(root, ["items", "--hide-rejects", "1"]).stdout)
    hidden_names = [row.get("filename") for row in hidden] if isinstance(hidden, list) else []
    checks.check("hide-rejects-hides-blur", "blur.jpg" not in hidden_names, json.dumps(hidden_names))
    shown = parse_json(run_library(root, ["items", "--hide-rejects", "0"]).stdout)
    shown_names = [row.get("filename") for row in shown] if isinstance(shown, list) else []
    checks.check("show-rejects-keeps-blur", "blur.jpg" in shown_names, json.dumps(shown_names))
    four = parse_json(run_library(root, ["items", "--min-stars", "4"]).stdout)
    four_names = [row.get("filename") for row in four] if isinstance(four, list) else []
    checks.check("min-stars-has-sharp", "sharp.jpg" in four_names, json.dumps(four_names))
    checks.check("min-stars-skips-blur", "blur.jpg" not in four_names, json.dumps(four_names))
    picks = parse_json(run_library(root, ["items", "--pick", "1"]).stdout)
    pick_names = [row.get("filename") for row in picks] if isinstance(picks, list) else []
    checks.check("picks-filter", pick_names == ["sharp.jpg"] or "sharp.jpg" in pick_names, json.dumps(pick_names))
    blurry = parse_json(run_library(root, ["items", "--flag", "blurry"]).stdout)
    blurry_names = [row.get("filename") for row in blurry] if isinstance(blurry, list) else []
    checks.check("blurry-filter", "blur.jpg" in blurry_names, json.dumps(blurry_names))
    ranked = parse_json(run_library(root, ["items", "--sort", "rating", "--dir", "desc"]).stdout)
    ranked_names = [row.get("filename") for row in ranked] if isinstance(ranked, list) else []
    checks.check("sort-rating-first-high", ranked_names[:1] == ["sharp.jpg"] or (ranked_names and ranked_names[0] == "sharp.jpg"), json.dumps(ranked_names[:5]))

    off = run_library(root, ["settings", "set", "ratingMode", "off"], timeout=30)
    checks.check("setting-off-exit", off.returncode == 0, off.stderr[-200:])
    after_off = parse_json(run_library(root, ["settings", "get"]).stdout)
    checks.check("setting-off-persists", after_off.get("ratingMode") == "off", json.dumps(after_off))
    jobs_off = parse_json(run_library(root, ["jobs"]).stdout)
    rate_q = next((q for q in (jobs_off.get("queues") or []) if q.get("id") == "rate"), {})
    checks.check("jobs-has-rate", rate_q.get("id") == "rate", json.dumps(jobs_off)[:400])
    checks.check("setting-off-unavailable", rate_q.get("available") is False, json.dumps(rate_q))
    from library.rating import rate_step

    checks.check("setting-off-skips-step", rate_step(root) is False)
    off_run = parse_json(run_library(root, ["rate-photos"], timeout=30).stdout)
    checks.check("setting-off-rated-0", int(off_run.get("rated", -1)) == 0 and off_run.get("mode") == "off", json.dumps(off_run))

    on = run_library(root, ["settings", "set", "ratingMode", "smart"], timeout=30)
    checks.check("setting-smart-exit", on.returncode == 0, on.stderr[-200:])
    jobs_on = parse_json(run_library(root, ["jobs"]).stdout)
    rate_on = next((q for q in (jobs_on.get("queues") or []) if q.get("id") == "rate"), {})
    checks.check("setting-smart-available", rate_on.get("available") is True, json.dumps(rate_on))
    smart = parse_json(run_library(root, ["rate-photos", "--force"], timeout=180).stdout)
    record["smart"] = smart
    checks.check("smart-rated", int(smart.get("rated") or 0) >= 8, json.dumps(smart))
    smart_items = parse_json(run_library(root, ["items"]).stdout)
    smart_by = {item.get("filename"): item for item in smart_items} if isinstance(smart_items, list) else {}
    color_r = smart_by.get("colorful.jpg") or {}
    gray_r = smart_by.get("graysharp.jpg") or {}
    basic_color = float((((colorful.get("rating") or {}).get("suggested")) or 0))
    basic_gray = float((((gray.get("rating") or {}).get("suggested")) or 0))
    smart_color = float((((color_r.get("rating") or {}).get("suggested")) or 0))
    smart_gray = float((((gray_r.get("rating") or {}).get("suggested")) or 0))
    color_aes = ((_quality_of(root, color_r.get("id") or "") or {}).get("metrics") or {}).get("aesthetic")
    gray_aes = ((_quality_of(root, gray_r.get("id") or "") or {}).get("metrics") or {}).get("aesthetic")
    record["smartOrder"] = {
        "basicColor": basic_color,
        "basicGray": basic_gray,
        "smartColor": smart_color,
        "smartGray": smart_gray,
        "colorAesthetic": color_aes,
        "grayAesthetic": gray_aes,
    }
    checks.check("smart-loads-aesthetic", isinstance(color_aes, (int, float)) and isinstance(gray_aes, (int, float)), json.dumps(record["smartOrder"]))
    checks.check(
        "smart-changes-order",
        (smart_color - smart_gray) > (basic_color - basic_gray) or (isinstance(color_aes, (int, float)) and isinstance(gray_aes, (int, float)) and float(color_aes) > float(gray_aes)),
        json.dumps(record["smartOrder"]),
    )
    learn = run_library(root, ["settings", "set", "ratingLearn", "true"], timeout=30)
    checks.check("learn-on", learn.returncode == 0)
    learned = parse_json(run_library(root, ["rate", sharp_id, "--pick"], timeout=30).stdout)
    checks.check("learn-pick-ok", (learned.get("rating") or {}).get("pick") is True)
    weights = root / "catalog" / "rating-weights.json"
    checks.check("learn-writes-weights", weights.is_file(), str(weights))
    cleared = parse_json(run_library(root, ["rate", sharp_id, "--clear"], timeout=30).stdout)
    checks.check("clear-stars", (cleared.get("rating") or {}).get("yours") is None, json.dumps(cleared.get("rating")))
    record["ids"] = {
        "sharp": sharp.get("id"),
        "blur": blur.get("id"),
        "dark": dark.get("id"),
        "bright": bright.get("id"),
        "colorful": color_r.get("id"),
        "gray": gray_r.get("id"),
        "burst3": burst3.get("id"),
    }
    return record


def prove_http_and_browser(checks: Checks, artifacts: Path, cli: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = artifacts / "rating-root"
    if not root.exists():
        checks.check("http-root", False, "missing rating-root")
        return record
    port = settings_port(root)
    del port
    server, url, _owned = start_owned(root)
    record["url"] = url
    try:
        status, health = request_json(url.rstrip("/") + "/api/health", timeout=10)
        checks.check("health", status == 200 and health == {"ok": True}, str(health))
        st, body = request_json(url.rstrip("/") + "/api/rate", timeout=10)
        record["rateGet"] = body
        checks.check("rate-get", st == 200 and isinstance(body, dict) and body.get("ok") is True)
        sharp_id = (cli.get("ids") or {}).get("sharp")
        if sharp_id:
            st, rated = request_json(
                url.rstrip("/") + "/api/items/" + sharp_id + "/rating",
                method="POST",
                body={"stars": 4},
                timeout=10,
            )
            checks.check("http-rate-stars", st == 200 and (rated.get("rating") or {}).get("yours") == 4, json.dumps(rated.get("rating")))
        st, four = request_json(url.rstrip("/") + "/api/items?minStars=4&hideRejects=1", timeout=10)
        names = [row.get("filename") for row in four] if isinstance(four, list) else []
        checks.check("http-min-stars", st == 200 and "sharp.jpg" in names, json.dumps(names))
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return record
        checks.check("playwright-import", True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            console = collect_console(page)
            page.goto(url, wait_until="load", timeout=60000)
            request_json(url.rstrip("/") + "/api/jobs", method="POST", body={"action": "pause"}, timeout=5)
            page.select_option("#date-group", "off")
            page.locator("#size-slider").evaluate(
                """(el) => {
                  el.value = '4';
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
            )
            page.wait_for_selector(".cell", timeout=20000)
            page.wait_for_selector(".tile-stars", timeout=15000)
            grid_shot = artifacts / "rating-grid.png"
            page.screenshot(path=str(grid_shot), full_page=False)
            gw, gh = png_size(grid_shot)
            checks.check("grid-png", grid_shot.is_file() and gw == 1280 and gh == 720, f"{gw}x{gh}")
            checks.check("tile-stars-visible", page.locator(".tile-stars").count() >= 1)
            page.locator(".cell").first.click()
            page.wait_for_selector("#viewer:not([hidden])", timeout=10000)
            page.keyboard.press("5")
            page.wait_for_timeout(300)
            page.locator("#viewer-info").click()
            page.wait_for_selector("#viewer-info-panel:not([hidden])", timeout=5000)
            info_text = page.locator("#viewer-facts").inner_text()
            checks.check("info-has-stars", "★" in info_text or "Suggested" in info_text or "Yours" in info_text, info_text[:400])
            info_shot = artifacts / "rating-info.png"
            page.screenshot(path=str(info_shot), full_page=False)
            page.keyboard.press("x")
            page.wait_for_timeout(250)
            page.locator("#viewer-back").click()
            page.wait_for_function("() => document.getElementById('viewer').hidden", timeout=10000)
            page.select_option("#language", "zh-Hans")
            page.wait_for_timeout(400)
            chips = page.locator("#filter-bar").inner_text()
            checks.check("zh-filter-chips", "四星及以上" in chips and "精选" in chips and "隐藏排除" in chips and "模糊" in chips, chips[:400])
            chinese_shot = artifacts / "chinese-rating.png"
            page.screenshot(path=str(chinese_shot), full_page=False)
            page.locator("#view-settings").click()
            page.wait_for_selector("#settings-view:not([hidden])", timeout=5000)
            settings_zh = page.locator("#settings-view").inner_text()
            checks.check("zh-settings-rating", "评分" in settings_zh and "基础" in settings_zh and "智能" in settings_zh, settings_zh[:500])
            page.locator("#settings-view h2[data-i18n='rating']").scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            settings_shot = artifacts / "settings-rating-zh.png"
            page.screenshot(path=str(settings_shot), full_page=False)
            record["console"] = console
            browser.close()
    finally:
        stop_owned(server)
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    del root
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library setup-ml aesthetic --backend fixture",
        "python -m library rate-photos",
        "python -m library rate <id> --stars 5",
        "python -m library items --min-stars 4 --hide-rejects 1",
        "GET /api/rate",
        "POST /api/items/<id>/rating",
    ]
    extra: dict[str, str] = {}
    try:
        assert_no_pillow_in_server(checks)
        prove_docs(checks)
        cli = prove_cli_and_http(checks, artifacts)
        http = prove_http_and_browser(checks, artifacts, cli)
        extra = {
            "rate.json": str(artifacts / "rate.json"),
            "rating-grid.png": str(artifacts / "rating-grid.png"),
            "rating-info.png": str(artifacts / "rating-info.png"),
            "chinese-rating.png": str(artifacts / "chinese-rating.png"),
            "settings-rating-zh.png": str(artifacts / "settings-rating-zh.png"),
        }
        (artifacts / "rate.json").write_text(json.dumps({"cli": cli, "http": http}, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        checks.check("taste-rating", False, str(exc))
    return write_result("TASTE-RATING", "slice", checks, artifacts, commands, extra)
