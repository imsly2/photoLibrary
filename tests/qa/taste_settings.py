"""Taste proof: Settings folders, rescan, face slider, face crop URL."""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

from library.httpjson import request_json
from library.service import Library
from library.settings import DEFAULTS
from tests.qa.s00 import PRODUCT_ROOT, Checks, assert_no_pillow_in_server, run_library
from tests.qa.s03 import find_item
from tests.qa.s05 import pin_media_from_manifest
from tests.qa.s08 import fresh_root, start_owned, stop_owned, write_result


def _get_bytes(url: str) -> tuple[int, int, str]:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = resp.read()
            return resp.status, len(data), resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as exc:
        return exc.code, 0, ""


def _wait_source_idle(url: str, source_id: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, sources = request_json(url + "api/sources", timeout=5)
        if status == 200 and isinstance(sources, list):
            for src in sources:
                if isinstance(src, dict) and src.get("id") == source_id:
                    state = ((src.get("scan") or {}).get("state")) or "idle"
                    if state != "running":
                        return True
        time.sleep(0.25)
    return False


def prove_static(checks: Checks) -> None:
    html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
    js = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
    css = (PRODUCT_ROOT / "library" / "web" / "assets" / "style.css").read_text(encoding="utf-8")
    i18n = (PRODUCT_ROOT / "library" / "web" / "assets" / "i18n.js").read_text(encoding="utf-8")
    main = (PRODUCT_ROOT / "library" / "__main__.py").read_text(encoding="utf-8")
    server = (PRODUCT_ROOT / "library" / "server.py").read_text(encoding="utf-8")
    product = (PRODUCT_ROOT / "docs" / "PRODUCT.md").read_text(encoding="utf-8")
    contracts = (PRODUCT_ROOT / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
    checks.check("html-settings-view", 'id="settings-view"' in html and 'id="view-settings"' in html)
    checks.check("html-folders-first", 'id="settings-sources"' in html and 'data-i18n="folders"' in html)
    checks.check(
        "html-face-slider",
        'id="set-faceMatchThreshold"' in html
        and 'type="range"' in html
        and 'min="0.35"' in html
        and 'max="0.95"' in html
        and 'step="0.01"' in html
        and 'id="settings-faces-rerun"' in html,
    )
    checks.check("js-open-settings", "function openSettings" in js and 'showView("settings")' in js)
    checks.check("js-rescan", "/api/sources/" in js and "/rescan" in js and "function rescanSource" in js)
    checks.check("js-remove-source", "/remove" in js and "function performRemoveSource" in js)
    checks.check("js-slider-live", "syncFaceThresholdOutput" in js and "facesRerunNeeded" in js)
    checks.check("js-face-crop", "which=face&box=" in js)
    checks.check("css-picker-cover", "object-fit: cover" in css)
    checks.check("i18n-face-help", "faceMatchHelp" in i18n and "faceRerunNote" in i18n)
    checks.check("cli-rescan", 'add_parser("rescan")' in main)
    checks.check("cli-remove-source", 'add_parser("remove-source")' in main)
    checks.check("http-rescan-route", '/rescan"' in server or "/rescan" in server)
    checks.check("product-folders", "Folders / sources come first" in product)
    checks.check("contracts-rescan", "/api/sources/<id>/rescan" in contracts)
    checks.check("contracts-face-which", "which=face" in contracts or "face&box" in contracts)
    checks.check("default-threshold-045", abs(float(DEFAULTS["faceMatchThreshold"]) - 0.45) < 1e-9)


def prove_http(checks: Checks, root: Path, artifacts: Path, commands: list[str]) -> None:
    from tests.qa.s00 import copy_committed_fixtures

    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media" / "a"
    pin_media_from_manifest(media.parent)
    lib_root = fresh_root(root)
    scan = run_library(lib_root, ["scan", str(media), "--serve-from-there"], timeout=180)
    commands.append("python -m library scan <folder> --serve-from-there")
    checks.check("scan-exit", scan.returncode == 0, scan.stderr)
    server = None
    owned: list[int] = []
    source_id = ""
    try:
        server, url, owned = start_owned(lib_root)
        status, settings = request_json(url + "api/settings", timeout=5)
        checks.check("settings-http", status == 200, json.dumps(settings)[:400])
        checks.check(
            "settings-default-threshold",
            abs(float((settings or {}).get("faceMatchThreshold") or 0) - 0.45) < 1e-9,
            json.dumps(settings),
        )
        status, patched = request_json(
            url + "api/settings",
            method="PUT",
            body={"faceMatchThreshold": 0.85},
            timeout=5,
        )
        checks.check(
            "settings-slider-persist",
            status == 200 and abs(float((patched or {}).get("faceMatchThreshold") or 0) - 0.85) < 1e-9,
            json.dumps(patched),
        )
        status, sources = request_json(url + "api/sources", timeout=5)
        checks.check("sources-http", status == 200 and isinstance(sources, list) and sources, json.dumps(sources)[:400])
        source = sources[0] if isinstance(sources, list) and sources else {}
        stats = source.get("stats") or {}
        checks.check("source-has-path", type(source.get("path")) is str and source.get("path"), json.dumps(source)[:400])
        checks.check(
            "source-has-stats",
            isinstance(stats, dict)
            and "photos" in stats
            and "renditionsDone" in stats
            and "total" in stats,
            json.dumps(stats),
        )
        source_id = source.get("id")
        status, rescan = request_json(url + f"api/sources/{source_id}/rescan", method="POST", body={}, timeout=5)
        checks.check(
            "rescan-accepted",
            status == 202 and isinstance(rescan, dict),
            json.dumps({"status": status, "body": rescan}),
        )
        finished = _wait_source_idle(url, source_id)
        checks.check("rescan-finished", finished is True, source_id)
        items = Library(lib_root).items_list({})
        photo = find_item(items, "IMG_1042.jpg")
        checks.check("crop-item", photo is not None)
        if photo:
            crop_status, crop_len, crop_type = _get_bytes(
                url + f"api/media/{photo['id']}?which=face&box=0.20,0.20,0.30,0.40"
            )
            checks.check(
                "face-crop-bytes",
                crop_status == 200 and crop_len > 32 and "webp" in crop_type,
                json.dumps({"status": crop_status, "len": crop_len, "type": crop_type}),
            )
    finally:
        stop_owned(server, owned)

    if source_id:
        cli = run_library(lib_root, ["rescan", source_id], timeout=180)
        commands.append("python -m library rescan <source-id>")
        checks.check("cli-rescan-runs", cli.returncode == 0, cli.stderr)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    commands: list[str] = []
    artifacts.mkdir(parents=True, exist_ok=True)
    assert_no_pillow_in_server(checks)
    prove_static(checks)
    prove_http(checks, root, artifacts, commands)
    return write_result("TASTE-SETTINGS", "slice", checks, artifacts, commands)
