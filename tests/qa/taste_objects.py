"""Optional local YOLO Things. Not an F-id grade. No faces."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.objects import detections_to_things
from tests.qa.s00 import (
    PRODUCT_ROOT,
    Checks,
    assert_no_pillow_in_server,
    parse_json,
    run_library,
    start_server,
    stop_owned,
    wait_health,
)
from tests.qa.s01 import parse_summary
from tests.qa.s03 import png_size
from tests.qa.s08 import fresh_root, settings_port, write_result


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

OBJECTS_STILL = PRODUCT_ROOT / "tests" / "fixtures" / "objects" / "still.jpg"


def _thing_names(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for rec in ((item.get("entities") or {}).get("things") or []):
        name = rec.get("name")
        if type(name) is str and name:
            names.append(name)
    return names


def prove_docs_and_filter(checks: Checks, artifacts: Path) -> dict[str, Any]:
    product = (PRODUCT_ROOT / "docs" / "PRODUCT.md").read_text(encoding="utf-8")
    contracts = (PRODUCT_ROOT / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
    launch = (PRODUCT_ROOT / "launch.ps1").read_text(encoding="utf-8")
    setup_bat = (PRODUCT_ROOT / "Setup.bat").read_text(encoding="utf-8")
    checks.check("product-setup-ml", "setup-ml objects" in product)
    checks.check("product-analyze", "`analyze`" in product or "analyze --item" in product)
    checks.check(
        "product-coco-person-ignored",
        "coco" in product.lower() and "person" in product.lower() and "ignored" in product.lower(),
    )
    checks.check("contracts-model-unavailable", "model-unavailable" in contracts)
    checks.check("launch-setupml", "[switch]$SetupMl" in launch and "setup-ml" in launch)
    checks.check("setup-bat", "launch.ps1" in setup_bat and "SetupMl" in setup_bat)
    checks.check("objects-still", OBJECTS_STILL.is_file() and OBJECTS_STILL.stat().st_size > 10_000)

    out = detections_to_things(
        [
            {"name": "person", "box": [0.1, 0.1, 0.2, 0.3], "score": 0.9},
            {"name": "bus", "box": [0.2, 0.3, 0.6, 0.4], "score": 0.8},
        ],
        {"things": []},
        artifacts,
    )
    labels = [row.get("name") for row in out]
    checks.check("filter-skips-person", "person" not in labels, str(labels))
    checks.check("filter-keeps-bus", "bus" in labels, str(labels))
    checks.check("filter-name-only", all("id" not in row for row in out), str(out))
    return {"detections": out}


def prove_cli_and_http(checks: Checks, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "objects-root")
    media = artifacts / "objects-media"
    if media.exists():
        shutil.rmtree(media)
    media.mkdir(parents=True)
    shutil.copy2(OBJECTS_STILL, media / "still.jpg")

    missing = run_library(root, ["analyze"], timeout=30)
    record["analyzeMissing"] = {"code": missing.returncode, "stderr": missing.stderr}
    missing_err = {}
    try:
        missing_err = parse_json(missing.stderr.strip().splitlines()[-1])
    except Exception:
        missing_err = {"raw": missing.stderr}
    checks.check(
        "analyze-without-model",
        missing.returncode == 1 and missing_err.get("error") == "model-unavailable",
        json.dumps(missing_err),
    )

    setup = run_library(root, ["setup-ml", "objects"], timeout=300)
    record["setup"] = {"code": setup.returncode, "stdout": setup.stdout, "stderr": setup.stderr}
    setup_body = {}
    try:
        setup_body = parse_json(setup.stdout)
    except Exception:
        setup_body = {}
    checks.check("setup-ml-exit", setup.returncode == 0, setup.stderr)
    checks.check("setup-ml-ok", setup_body.get("ok") is True, json.dumps(setup_body))
    model = root / "models" / "yolov8n.onnx"
    checks.check("model-bytes", model.is_file() and model.stat().st_size > 1_000_000, str(model))
    manifest = root / "models" / "objects.json"
    checks.check("objects-manifest", manifest.is_file(), str(manifest))

    scan = run_library(
        root,
        ["scan", str(media), "--serve-from-there"],
        timeout=120,
    )
    record["scan"] = {"code": scan.returncode, "stdout": scan.stdout, "stderr": scan.stderr}
    summary = parse_summary(scan.stdout)
    checks.check("scan-added-1", summary.get("added") == 1, json.dumps(summary))

    items = run_library(root, ["items"], timeout=30)
    catalog = parse_json(items.stdout)
    checks.check("items-one", isinstance(catalog, list) and len(catalog) == 1, items.stdout[:500])
    item = catalog[0] if isinstance(catalog, list) and catalog else {}
    item_id = item.get("id")
    record["itemId"] = item_id
    checks.check("item-id", type(item_id) is str and bool(item_id), str(item_id))

    tagged = run_library(root, ["annotate", str(item_id), "--thing", "mug"], timeout=30)
    after_human = parse_json(tagged.stdout)
    human_things = after_human.get("entities", {}).get("things") or []
    mug = next((row for row in human_things if row.get("name") == "mug"), None)
    mug_id = mug.get("id") if mug else None
    record["mugId"] = mug_id
    checks.check("human-mug", type(mug_id) is str and mug_id.startswith("thing_"), str(mug))

    analyzed = run_library(root, ["analyze", "--item", str(item_id)], timeout=180)
    record["analyze"] = {
        "code": analyzed.returncode,
        "stdout": analyzed.stdout,
        "stderr": analyzed.stderr,
    }
    analyze_body = {}
    try:
        analyze_body = parse_json(analyzed.stdout)
    except Exception:
        analyze_body = {}
    (artifacts / "analyze.json").write_text(
        json.dumps(analyze_body, indent=2) + "\n", encoding="utf-8"
    )
    checks.check("analyze-exit", analyzed.returncode == 0, analyzed.stderr)
    checks.check("analyze-tagged", analyze_body.get("tagged", 0) >= 1, json.dumps(analyze_body))

    items2 = run_library(root, ["items"], timeout=30)
    after = parse_json(items2.stdout)[0]
    (artifacts / "item.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
    names = _thing_names(after)
    record["thingNames"] = names
    mug_after = next(
        (row for row in (after.get("entities") or {}).get("things") or [] if row.get("name") == "mug"),
        None,
    )
    checks.check("human-mug-kept", mug_after is not None and mug_after.get("id") == mug_id, str(mug_after))
    auto_names = [name for name in names if name.casefold() != "mug"]
    checks.check("auto-thing-present", len(auto_names) >= 1, json.dumps(names))
    checks.check("no-person-thing", all(name.casefold() != "person" for name in names), json.dumps(names))
    checks.check("no-faces", after.get("faces") == [], json.dumps(after.get("faces")))
    people_dir = root / "catalog" / "people"
    people_files = list(people_dir.glob("*.json")) if people_dir.exists() else []
    checks.check("no-people-files", people_files == [], str(people_files))

    label = auto_names[0] if auto_names else ""
    record["autoLabel"] = label
    search = run_library(root, ["items", "--q", label], timeout=30)
    found = parse_json(search.stdout)
    (artifacts / "search.json").write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
    checks.check(
        "search-auto-thing",
        isinstance(found, list) and any(row.get("id") == item_id for row in found),
        search.stdout[:500],
    )
    return record


def prove_http_and_browser(checks: Checks, artifacts: Path, cli: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = artifacts / "objects-root"
    if not root.exists():
        checks.check("http-root", False, "missing objects-root")
        return record
    port = settings_port(root)
    server = start_server(root)
    url = f"http://127.0.0.1:{port}/"
    record["url"] = url
    try:
        health_status, health = wait_health(url, server)
        checks.check("health", health_status == 200 and health == {"ok": True}, str(health))
        status, body = request_json(url.rstrip("/") + "/api/analyze", timeout=10)
        record["analyzeGet"] = body
        checks.check("analyze-get", status == 200 and isinstance(body, dict) and body.get("installed") is True)
        items_status, items = request_json(url.rstrip("/") + "/api/items", timeout=10)
        checks.check("http-items", items_status == 200 and isinstance(items, list) and items)
        item = items[0] if isinstance(items, list) and items else {}
        names = _thing_names(item)
        label = cli.get("autoLabel") or next((name for name in names if name.casefold() != "mug"), "")
        q_status, q_body = request_json(
            url.rstrip("/") + "/api/items?q=" + label + "&scope=things",
            timeout=10,
        )
        record["search"] = q_body
        checks.check(
            "http-search-things",
            q_status == 200 and isinstance(q_body, list) and any(row.get("id") == item.get("id") for row in q_body),
            json.dumps(q_body, default=str)[:500],
        )
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
            page.locator(".cell").first.click()
            page.wait_for_selector("#viewer:not([hidden])", timeout=10000)
            page.locator("#viewer-info").click()
            page.wait_for_selector("#viewer-info-panel:not([hidden])", timeout=5000)
            page.wait_for_selector("#viewer-things .entity-label", timeout=10000)
            thing_text = page.locator("#viewer-things").inner_text()
            record["infoText"] = thing_text
            checks.check("info-shows-mug", "mug" in thing_text.lower(), thing_text)
            checks.check(
                "info-shows-auto",
                label.lower() in thing_text.lower(),
                thing_text,
            )
            info_shot = artifacts / "info-things.png"
            page.screenshot(path=str(info_shot), full_page=False)
            iw, ih = png_size(info_shot)
            checks.check("info-png", info_shot.is_file() and iw == 1280 and ih == 720, f"{iw}x{ih}")
            page.locator("#viewer-back").click()
            page.fill("#search", label)
            page.wait_for_timeout(400)
            page.wait_for_selector(".cell", timeout=10000)
            search_shot = artifacts / "search-thing.png"
            page.screenshot(path=str(search_shot), full_page=False)
            sw, sh = png_size(search_shot)
            checks.check("search-png", search_shot.is_file() and sw == 1280 and sh == 720, f"{sw}x{sh}")
            checks.check("search-has-cell", page.locator(".cell").count() >= 1)
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
        "python -m library setup-ml objects",
        "python -m library analyze --item <id>",
        "POST /api/analyze",
    ]
    extra: dict[str, str] = {}
    try:
        assert_no_pillow_in_server(checks)
        prove_docs_and_filter(checks, artifacts)
        cli = prove_cli_and_http(checks, artifacts)
        http = prove_http_and_browser(checks, artifacts, cli)
        extra["analyze.json"] = str(artifacts / "analyze.json")
        extra["item.json"] = str(artifacts / "item.json")
        extra["search.json"] = str(artifacts / "search.json")
        if (artifacts / "info-things.png").is_file():
            extra["info-things.png"] = str(artifacts / "info-things.png")
        if (artifacts / "search-thing.png").is_file():
            extra["search-thing.png"] = str(artifacts / "search-thing.png")
        extra["url"] = str(http.get("url") or "")
    except Exception as exc:
        checks.check("taste-objects", False, str(exc))
    return write_result("TASTE-OBJECTS", "slice", checks, artifacts, commands, extra)
