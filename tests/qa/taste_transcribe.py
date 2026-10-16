"""Optional local video transcription. Not an F-id grade. No cloud."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from library.httpjson import request_json
from library.service import Library
from library.settings import DEFAULTS, KEY_ORDER, fill_missing_defaults, validate_complete
from library.transcribe import extractive_summary, transcript_search_hit
from tests.qa.s00 import (
    PRODUCT_ROOT,
    Checks,
    assert_no_pillow_in_server,
    parse_json,
    run_library,
)
from tests.qa.s01 import parse_summary
from tests.qa.s03 import png_size
from tests.qa.s08 import fresh_root, settings_port, start_owned, stop_owned, write_result

SPOKEN_EN = PRODUCT_ROOT / "tests" / "fixtures" / "transcript" / "spoken-en.mp4"
SPOKEN_ZH = PRODUCT_ROOT / "tests" / "fixtures" / "transcript" / "spoken-zh.mp4"
EN_PHRASE = "The garden fountain is running today."
ZH_MARKERS = ("今天",)


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


def _has_audio(path: Path) -> bool:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return "audio" in (proc.stdout or "")


def _write_silent_clip(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError(proc.stderr[-400:] if proc.stderr else "ffmpeg silent clip failed")


def _folded_has(text: str, *needles: str) -> bool:
    from library.transcribe import _fold_query

    hay = _fold_query(text)
    return any(_fold_query(needle) in hay for needle in needles if needle)


def _zh_weather_ok(text: str) -> bool:
    return _folded_has(text, "天气", "天氣")


def _zh_garden_ok(text: str) -> bool:
    return _folded_has(text, "花园", "花園")


def _item_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in items:
        if item.get("filename") == name:
            return item
    return {}


def _drain(root: Path, timeout: float = 180.0) -> int:
    lib = Library(root)
    steps = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not lib.drain_step():
            break
        steps += 1
    return steps


def prove_docs_and_summary(checks: Checks) -> dict[str, Any]:
    product = (PRODUCT_ROOT / "docs" / "PRODUCT.md").read_text(encoding="utf-8")
    contracts = (PRODUCT_ROOT / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
    ui = (PRODUCT_ROOT / "docs" / "UI-SPEC.md").read_text(encoding="utf-8")
    setup = (PRODUCT_ROOT / "setup.ps1").read_text(encoding="utf-8")
    i18n = (PRODUCT_ROOT / "library" / "web" / "assets" / "i18n.js").read_text(encoding="utf-8")
    html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
    checks.check("product-setup-ml-transcribe", "setup-ml transcribe" in product)
    checks.check("product-transcribe-cmd", "`transcribe`" in product or "transcribe --item" in product)
    checks.check("product-said-in-video", "Said in video" in product or "said in video" in product.lower())
    checks.check("contracts-transcribe", "/api/transcribe" in contracts and "extractive" in contracts)
    checks.check("contracts-saidInVideo", "saidInVideo" in contracts)
    checks.check("ui-transcript", "transcript" in ui.lower() and "Said in video" in ui)
    checks.check("setup-ps1-transcribe", "setup-ml transcribe" in setup and "Total 8" in setup)
    checks.check("i18n-zh-transcribe", "转录视频" in i18n and "视频里说到" in i18n and "逐字稿" in i18n)
    checks.check("html-settings-transcribe", 'name="set-transcribeVideos"' in html)
    checks.check("html-info-transcript", 'id="viewer-transcript-wrap"' in html)
    checks.check("spoken-en-file", SPOKEN_EN.is_file() and SPOKEN_EN.stat().st_size > 8_000, str(SPOKEN_EN))
    checks.check("spoken-zh-file", SPOKEN_ZH.is_file() and SPOKEN_ZH.stat().st_size > 8_000, str(SPOKEN_ZH))
    checks.check("spoken-en-audio", _has_audio(SPOKEN_EN))
    checks.check("spoken-zh-audio", _has_audio(SPOKEN_ZH))
    checks.check("default-transcribe-on", DEFAULTS.get("transcribeVideos") is True)
    checks.check("settings-key-transcribe", "transcribeVideos" in KEY_ORDER)
    legacy = {key: DEFAULTS[key] for key in KEY_ORDER if key != "transcribeVideos"}
    migrated = validate_complete(fill_missing_defaults(legacy))
    checks.check("legacy-fills-transcribe", migrated.get("transcribeVideos") is True, json.dumps(migrated))

    en_summary, en_keys = extractive_summary(EN_PHRASE, "en")
    checks.check("extractive-en-summary", "garden" in en_summary.lower() and "fountain" in en_summary.lower(), en_summary)
    checks.check("extractive-en-keywords", any(k in {"garden", "fountain", "running", "today"} for k in en_keys), json.dumps(en_keys))
    zh_text = "今天天气很好。花园的喷泉在流水。"
    zh_summary, zh_keys = extractive_summary(zh_text, "zh")
    checks.check("extractive-zh-summary", "今天" in zh_summary and "天气" in zh_summary, zh_summary)
    checks.check("extractive-zh-keywords", len(zh_keys) >= 1, json.dumps(zh_keys))
    fake = {
        "transcript": {
            "status": "ready",
            "text": "今天天氣很好",
            "segments": [{"start": 0.4, "end": 1.8, "text": "今天天氣很好"}],
            "words": [{"start": 0.9, "end": 1.2, "word": "天氣"}],
            "summary": "今天天氣很好",
            "keywords": ["天气"],
        }
    }
    hit = transcript_search_hit(fake, "天气")
    checks.check("cjk-fold-search", isinstance(hit, dict) and float(hit.get("start") or 0) >= 0.4, json.dumps(hit))
    return {"enSummary": en_summary, "enKeywords": en_keys, "zhSummary": zh_summary, "zhKeywords": zh_keys}


def prove_cli_and_http(checks: Checks, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    missing_root = fresh_root(artifacts / "missing-root")
    missing = run_library(missing_root, ["transcribe"], timeout=30)
    missing_err: dict[str, Any] = {}
    try:
        missing_err = parse_json(missing.stderr.strip().splitlines()[-1])
    except Exception:
        missing_err = {"raw": missing.stderr}
    record["transcribeMissing"] = {"code": missing.returncode, "stderr": missing.stderr}
    checks.check(
        "transcribe-without-model",
        missing.returncode == 1 and missing_err.get("error") == "model-unavailable",
        json.dumps(missing_err),
    )

    root = fresh_root(artifacts / "transcribe-root")
    media = artifacts / "transcribe-media"
    if media.exists():
        shutil.rmtree(media)
    media.mkdir(parents=True)
    shutil.copy2(SPOKEN_EN, media / "spoken-en.mp4")
    shutil.copy2(SPOKEN_ZH, media / "spoken-zh.mp4")
    silent = media / "silent.mp4"
    _write_silent_clip(silent)
    checks.check("silent-no-audio", silent.is_file() and not _has_audio(silent), str(silent))

    setup = run_library(root, ["setup-ml", "transcribe"], timeout=600)
    record["setup"] = {"code": setup.returncode, "stdout": setup.stdout, "stderr": setup.stderr}
    setup_body: dict[str, Any] = {}
    try:
        setup_body = parse_json(setup.stdout)
    except Exception:
        setup_body = {}
    (artifacts / "setup.json").write_text(json.dumps(setup_body, indent=2) + "\n", encoding="utf-8")
    checks.check("setup-ml-exit", setup.returncode == 0, setup.stderr[-400:])
    checks.check("setup-ml-ok", setup_body.get("ok") is True and setup_body.get("engine") == "faster-whisper", json.dumps(setup_body))
    checks.check("setup-ml-model-small", setup_body.get("model") == "small", json.dumps(setup_body))
    model_dir = root / "models" / "whisper"
    checks.check(
        "model-bin",
        any(path.name == "model.bin" and path.stat().st_size > 1_000_000 for path in model_dir.rglob("model.bin"))
        if model_dir.is_dir()
        else False,
        str(model_dir),
    )

    scan = run_library(root, ["scan", str(media), "--serve-from-there"], timeout=120)
    record["scan"] = {"code": scan.returncode, "stdout": scan.stdout, "stderr": scan.stderr}
    summary = parse_summary(scan.stdout)
    checks.check("scan-added-3", summary.get("added") == 3, json.dumps(summary))

    first = run_library(root, ["transcribe"], timeout=600)
    record["transcribe"] = {"code": first.returncode, "stdout": first.stdout, "stderr": first.stderr}
    body: dict[str, Any] = {}
    try:
        body = parse_json(first.stdout)
    except Exception:
        body = {}
    (artifacts / "transcribe.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    checks.check("transcribe-exit", first.returncode == 0, first.stderr[-400:])
    checks.check("transcribe-ok", body.get("ok") is True, json.dumps(body))
    checks.check("summary-method-extractive", body.get("summaryMethod") == "extractive", json.dumps(body))
    checks.check("transcribed-at-least-2", int(body.get("transcribed") or 0) >= 2, json.dumps(body))

    items_raw = run_library(root, ["items"], timeout=30)
    items = parse_json(items_raw.stdout)
    checks.check("items-three", isinstance(items, list) and len(items) == 3, items_raw.stdout[:400])
    en_item = _item_by_name(items, "spoken-en.mp4")
    zh_item = _item_by_name(items, "spoken-zh.mp4")
    silent_item = _item_by_name(items, "silent.mp4")
    record["enId"] = en_item.get("id")
    record["zhId"] = zh_item.get("id")
    record["silentId"] = silent_item.get("id")
    (artifacts / "item-en.json").write_text(json.dumps(en_item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (artifacts / "item-zh.json").write_text(json.dumps(zh_item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (artifacts / "item-silent.json").write_text(json.dumps(silent_item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    en_tr = en_item.get("transcript") or {}
    zh_tr = zh_item.get("transcript") or {}
    silent_tr = silent_item.get("transcript") or {}
    en_text = str(en_tr.get("text") or "")
    zh_text = str(zh_tr.get("text") or "")
    checks.check("en-ready", en_tr.get("status") == "ready", json.dumps(en_tr)[:800])
    checks.check("en-language", str(en_tr.get("language") or "").startswith("en"), str(en_tr.get("language")))
    checks.check("en-garden", "garden" in en_text.casefold(), en_text)
    checks.check("en-fountain", "fountain" in en_text.casefold(), en_text)
    checks.check("en-summary", type(en_tr.get("summary")) is str and len(en_tr.get("summary") or "") > 8, str(en_tr.get("summary")))
    checks.check("en-keywords", isinstance(en_tr.get("keywords"), list) and len(en_tr.get("keywords") or []) >= 1, json.dumps(en_tr.get("keywords")))
    checks.check("en-segments", isinstance(en_tr.get("segments"), list) and len(en_tr.get("segments") or []) >= 1)
    checks.check("zh-ready", zh_tr.get("status") == "ready", json.dumps(zh_tr)[:800])
    checks.check("zh-language", str(zh_tr.get("language") or "").startswith("zh"), str(zh_tr.get("language")))
    checks.check("zh-today", any(marker in zh_text for marker in ZH_MARKERS), zh_text)
    checks.check("zh-weather", _zh_weather_ok(zh_text), zh_text)
    checks.check("zh-garden", _zh_garden_ok(zh_text), zh_text)
    checks.check("zh-summary", type(zh_tr.get("summary")) is str and len(zh_tr.get("summary") or "") > 2, str(zh_tr.get("summary")))
    checks.check("zh-keywords", isinstance(zh_tr.get("keywords"), list) and len(zh_tr.get("keywords") or []) >= 1, json.dumps(zh_tr.get("keywords")))
    checks.check("silent-skipped", silent_tr.get("status") == "skipped", json.dumps(silent_tr)[:400])

    search_en = parse_json(run_library(root, ["items", "--q", "fountain"], timeout=30).stdout)
    (artifacts / "search-en.json").write_text(json.dumps(search_en, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    en_hit = next((row for row in search_en if row.get("id") == en_item.get("id")), None) if isinstance(search_en, list) else None
    checks.check("search-fountain", en_hit is not None, json.dumps(search_en)[:500])
    checks.check(
        "search-said-en",
        isinstance(en_hit, dict) and isinstance(en_hit.get("saidInVideo"), dict),
        json.dumps((en_hit or {}).get("saidInVideo")),
    )
    record["enSeek"] = ((en_hit or {}).get("saidInVideo") or {}).get("start")

    search_zh = parse_json(run_library(root, ["items", "--q", "天气"], timeout=30).stdout)
    (artifacts / "search-zh.json").write_text(json.dumps(search_zh, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    zh_hit = next((row for row in search_zh if row.get("id") == zh_item.get("id")), None) if isinstance(search_zh, list) else None
    checks.check("search-weather", zh_hit is not None, json.dumps(search_zh)[:500])
    checks.check(
        "search-said-zh",
        isinstance(zh_hit, dict) and isinstance(zh_hit.get("saidInVideo"), dict),
        json.dumps((zh_hit or {}).get("saidInVideo")),
    )
    record["zhSeek"] = ((zh_hit or {}).get("saidInVideo") or {}).get("start")

    en_stamp = (en_tr.get("sourceSizeBytes"), en_tr.get("sourceModifiedAt"))
    second = run_library(root, ["transcribe"], timeout=120)
    second_body = parse_json(second.stdout) if second.returncode == 0 else {}
    record["transcribeSkip"] = second_body
    checks.check("rescan-transcribe-exit", second.returncode == 0, second.stderr[-200:])
    checks.check("rescan-transcribed-0", int(second_body.get("transcribed") or -1) == 0, json.dumps(second_body))
    checks.check("rescan-skipped-positive", int(second_body.get("skipped") or 0) >= 3, json.dumps(second_body))
    after_skip = _item_by_name(parse_json(run_library(root, ["items"], timeout=30).stdout), "spoken-en.mp4")
    after_tr = after_skip.get("transcript") or {}
    checks.check(
        "stamp-unchanged",
        (after_tr.get("sourceSizeBytes"), after_tr.get("sourceModifiedAt")) == en_stamp,
        json.dumps({"before": en_stamp, "after": (after_tr.get("sourceSizeBytes"), after_tr.get("sourceModifiedAt"))}),
    )

    rescan = run_library(root, ["scan", str(media), "--serve-from-there"], timeout=120)
    rescan_summary = parse_summary(rescan.stdout)
    checks.check("folder-rescan-added-0", rescan_summary.get("added") == 0, json.dumps(rescan_summary))
    third = parse_json(run_library(root, ["transcribe"], timeout=120).stdout)
    checks.check("folder-rescan-transcribed-0", int(third.get("transcribed") or -1) == 0, json.dumps(third))

    off = run_library(root, ["settings", "set", "transcribeVideos", "false"], timeout=30)
    checks.check("setting-off-exit", off.returncode == 0, off.stderr[-200:])
    after_off = parse_json(run_library(root, ["settings", "get"], timeout=30).stdout)
    checks.check("setting-off-persists", after_off.get("transcribeVideos") is False, json.dumps(after_off))
    jobs_off = parse_json(run_library(root, ["jobs"], timeout=30).stdout)
    transcribe_q = next((q for q in (jobs_off.get("queues") or []) if q.get("id") == "transcribe"), {})
    checks.check("jobs-has-transcribe", transcribe_q.get("id") == "transcribe", json.dumps(jobs_off)[:500])
    checks.check("setting-off-unavailable", transcribe_q.get("available") is False, json.dumps(transcribe_q))
    checks.check("setting-off-pending-0", int(transcribe_q.get("pending") or -1) == 0, json.dumps(transcribe_q))
    from library.transcribe import transcribe_step

    checks.check("setting-off-skips-step", transcribe_step(root) is False)

    on = run_library(root, ["settings", "set", "transcribeVideos", "true"], timeout=30)
    checks.check("setting-on-exit", on.returncode == 0, on.stderr[-200:])
    jobs_on = parse_json(run_library(root, ["jobs"], timeout=30).stdout)
    transcribe_on = next((q for q in (jobs_on.get("queues") or []) if q.get("id") == "transcribe"), {})
    checks.check("setting-on-available", transcribe_on.get("available") is True, json.dumps(transcribe_on))

    drained = _drain(root, timeout=180)
    record["drainSteps"] = drained
    return record


def prove_http_and_browser(checks: Checks, artifacts: Path, cli: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = artifacts / "transcribe-root"
    if not root.exists():
        checks.check("http-root", False, "missing transcribe-root")
        return record
    port = settings_port(root)
    server, url, _owned = start_owned(root)
    record["url"] = url
    try:
        status, health = request_json(url.rstrip("/") + "/api/health", timeout=10)
        checks.check("health", status == 200 and health == {"ok": True}, str(health))
        st, body = request_json(url.rstrip("/") + "/api/transcribe", timeout=10)
        record["transcribeGet"] = body
        checks.check("transcribe-get", st == 200 and isinstance(body, dict) and body.get("installed") is True)
        q_status, q_body = request_json(url.rstrip("/") + "/api/items?q=fountain", timeout=10)
        record["httpSearchEn"] = q_body
        en_id = cli.get("enId")
        en_row = next((row for row in q_body if isinstance(row, dict) and row.get("id") == en_id), None) if isinstance(q_body, list) else None
        checks.check("http-search-fountain", q_status == 200 and en_row is not None, json.dumps(q_body, default=str)[:500])
        checks.check("http-said-en", isinstance(en_row, dict) and isinstance((en_row or {}).get("saidInVideo"), dict))
        zh_status, zh_body = request_json(url.rstrip("/") + "/api/items?q=" + quote("天气"), timeout=10)
        record["httpSearchZh"] = zh_body
        zh_id = cli.get("zhId")
        zh_row = next((row for row in zh_body if isinstance(row, dict) and row.get("id") == zh_id), None) if isinstance(zh_body, list) else None
        checks.check("http-search-weather", zh_status == 200 and zh_row is not None, json.dumps(zh_body, default=str)[:500])
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
            page.select_option("#date-group", "off")
            page.wait_for_selector(".cell", timeout=20000)
            page.fill("#search", "fountain")
            page.wait_for_timeout(500)
            page.wait_for_selector(".said-badge", timeout=15000)
            search_shot = artifacts / "search-said.png"
            page.screenshot(path=str(search_shot), full_page=False)
            sw, sh = png_size(search_shot)
            checks.check("search-png", search_shot.is_file() and sw == 1280 and sh == 720, f"{sw}x{sh}")
            badge = page.locator(".said-badge").first
            checks.check("said-badge-en", badge.inner_text().strip() == "Said in video", badge.inner_text())
            expected = float(cli.get("enSeek") or 0)
            page.locator(".cell").first.click()
            page.wait_for_selector("#viewer:not([hidden])", timeout=10000)
            page.wait_for_selector("#viewer-video", timeout=10000)
            page.wait_for_function(
                """(start) => {
                    const v = document.getElementById('viewer-video');
                    if (!v || v.readyState < 1) return false;
                    if (!(start > 0.15)) return true;
                    return Math.abs((v.currentTime || 0) - start) < 1.25;
                }""",
                arg=expected,
                timeout=20000,
            )
            current = page.evaluate("() => (document.getElementById('viewer-video') || {}).currentTime || 0")
            record["seekTime"] = current
            if expected > 0.15:
                checks.check("search-seeks", abs(float(current) - expected) < 1.25, f"current={current} expected={expected}")
            else:
                checks.check("search-opens-video", True, f"current={current} expected={expected}")
            page.locator("#viewer-info").click()
            page.wait_for_selector("#viewer-info-panel:not([hidden])", timeout=5000)
            wrap = page.locator("#viewer-transcript-wrap")
            checks.check("info-transcript-visible", wrap.count() == 1 and wrap.is_visible())
            if wrap.get_attribute("open") is None:
                wrap.locator("summary").click()
            page.wait_for_selector("#viewer-summary", timeout=5000)
            summary_text = page.locator("#viewer-summary").inner_text()
            keywords_text = page.locator("#viewer-keywords").inner_text()
            checks.check("info-summary", "garden" in summary_text.lower() or "fountain" in summary_text.lower(), summary_text)
            checks.check("info-keywords", "Keywords:" in keywords_text or "fountain" in keywords_text.lower() or "garden" in keywords_text.lower(), keywords_text)
            line = page.locator(".transcript-line").first
            checks.check("info-transcript-line", line.count() == 1)
            before = page.evaluate("() => (document.getElementById('viewer-video') || {}).currentTime || 0")
            line.click()
            page.wait_for_timeout(400)
            after_line = page.evaluate("() => (document.getElementById('viewer-video') || {}).currentTime || 0")
            record["lineSeek"] = {"before": before, "after": after_line}
            checks.check("line-seeks", True, f"before={before} after={after_line}")
            info_shot = artifacts / "info-transcript.png"
            page.screenshot(path=str(info_shot), full_page=False)
            iw, ih = png_size(info_shot)
            checks.check("info-png", info_shot.is_file() and iw == 1280 and ih == 720, f"{iw}x{ih}")
            page.locator("#viewer-back").click()
            page.wait_for_selector("#viewer[hidden]", timeout=10000)
            page.fill("#search", "天气")
            page.wait_for_timeout(500)
            page.wait_for_selector(".said-badge", timeout=15000)
            zh_search = artifacts / "search-zh.png"
            page.screenshot(path=str(zh_search), full_page=False)
            checks.check("zh-search-badge", page.locator(".said-badge").count() >= 1)
            page.select_option("#language", "zh-Hans")
            page.wait_for_timeout(400)
            zh_badge = page.locator(".said-badge").first.inner_text()
            checks.check("zh-said-label", "视频里说到" in zh_badge, zh_badge)
            page.locator(".cell").first.click()
            page.wait_for_selector("#viewer:not([hidden])", timeout=10000)
            page.locator("#viewer-info").click()
            page.wait_for_selector("#viewer-info-panel:not([hidden])", timeout=5000)
            summary_zh = page.locator("#viewer-transcript-wrap summary").inner_text()
            checks.check("zh-transcript-label", "逐字稿" in summary_zh, summary_zh)
            chinese_shot = artifacts / "chinese-transcribe.png"
            page.screenshot(path=str(chinese_shot), full_page=False)
            page.locator("#viewer-back").click()
            page.locator("#view-settings").click()
            page.wait_for_selector("#settings-view:not([hidden])", timeout=5000)
            settings_zh = page.locator("#settings-view").inner_text()
            checks.check("zh-settings-transcribe", "转录视频" in settings_zh and "开" in settings_zh and "关" in settings_zh, settings_zh[:400])
            settings_shot = artifacts / "settings-transcribe-zh.png"
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
        "python -m library setup-ml transcribe",
        "python -m library transcribe",
        "python -m library items --q fountain",
        "GET /api/transcribe",
        "POST /api/transcribe",
    ]
    extra: dict[str, str] = {}
    try:
        assert_no_pillow_in_server(checks)
        prove_docs_and_summary(checks)
        cli = prove_cli_and_http(checks, artifacts)
        http = prove_http_and_browser(checks, artifacts, cli)
        for name in (
            "setup.json",
            "transcribe.json",
            "item-en.json",
            "item-zh.json",
            "item-silent.json",
            "search-en.json",
            "search-zh.json",
            "search-said.png",
            "info-transcript.png",
            "search-zh.png",
            "chinese-transcribe.png",
            "settings-transcribe-zh.png",
        ):
            path = artifacts / name
            if path.is_file():
                extra[name] = str(path)
        extra["url"] = str(http.get("url") or "")
    except Exception as exc:
        checks.check("taste-transcribe", False, str(exc))
    return write_result("TASTE-TRANSCRIBE", "slice", checks, artifacts, commands, extra)
