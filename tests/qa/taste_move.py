"""Multi-select Move to folder. Not an F-id grade."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.s00 import Checks, _env, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import load_items, load_sources, parse_summary
from tests.qa.s03 import request_raw
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s07 import wait_ready
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import collect_console, wait_catalog

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/no-exif.jpg",
    "a/clip.mp4",
)

I18N = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "i18n.js"


def item_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("filename") or "": item for item in items}


def resolved(path: Path) -> str:
    return str(path.resolve())


def current_paths(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for loc in item.get("locations") or []:
        if loc.get("current") is True:
            path = loc.get("lastKnownPath")
            if type(path) is str and path:
                out.append(path)
    return out


def primary_path(item: dict[str, Any]) -> str:
    for loc in item.get("locations") or []:
        if loc.get("current") is True and loc.get("role") == "primary":
            path = loc.get("lastKnownPath")
            if type(path) is str:
                return path
    paths = current_paths(item)
    return paths[0] if paths else ""


def source_by_path(sources: list[dict[str, Any]], folder: Path) -> dict[str, Any] | None:
    want = str(folder.resolve())
    for source in sources:
        last = ((source.get("origin") or {}).get("lastKnownPath") or "")
        if last == want or last.rstrip("/\\") == want.rstrip("/\\"):
            return source
    return None


def seed_two_folders(media_src: Path, artifacts: Path, prefix: str) -> tuple[Path, Path]:
    src = artifacts / f"{prefix}-src"
    dest = artifacts / f"{prefix}-dest"
    copy_rels(media_src, src, MEDIA_RELS)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    return src, dest


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    i18n_text = I18N.read_text(encoding="utf-8")
    checks.check("i18n-move-en", "move: \"Move\"" in i18n_text)
    checks.check("i18n-move-zh", "move: \"移动\"" in i18n_text)
    checks.check("i18n-move-title-zh", "moveTitle: \"移动到文件夹\"" in i18n_text)
    checks.check("i18n-move-confirm-zh", "将 {n} 项移动到 {path}？" in i18n_text)

    root = fresh_root(artifacts / "api-root")
    src_folder, dest_folder = seed_two_folders(media_src, artifacts, "api")
    scanned_src = run_library(root, ["scan", str(src_folder), "--serve-from-there"], timeout=180)
    checks.check("scan-src-ok", scanned_src.returncode == 0, scanned_src.stderr[-200:])
    scanned_dest = run_library(root, ["scan", str(dest_folder), "--serve-from-there"], timeout=180)
    checks.check("scan-dest-ok", scanned_dest.returncode == 0, scanned_dest.stderr[-200:])

    items = item_map(load_items(root))
    need = ("IMG_1042.jpg", "near.jpg", "no-exif.jpg", "clip.mp4")
    checks.check("has-four", all(items.get(name) for name in need), json.dumps(sorted(items)))
    photo_a = items["IMG_1042.jpg"]["id"]
    photo_b = items["near.jpg"]["id"]
    photo_c = items["no-exif.jpg"]["id"]
    video = items["clip.mp4"]["id"]
    record["ids"] = {name: items[name]["id"] for name in need}

    fav = run_library(root, ["favorite", photo_a, "--on"])
    checks.check("favorite-on", fav.returncode == 0, fav.stderr[-200:])
    annotated = run_library(root, ["annotate", photo_a, "--person", "Ada", "--thing", "Hiking"])
    checks.check("annotate-ok", annotated.returncode == 0, annotated.stderr[-200:])
    before_item = item_map(load_items(root))["IMG_1042.jpg"]
    before_faces = before_item.get("faces") or []
    before_things = before_item.get("things") or []
    checks.check("faces-before", len(before_faces) >= 1, json.dumps(before_faces))
    checks.check("things-before", len(before_things) >= 1, json.dumps(before_things))

    empty = run_library(root, ["move", "--to", str(dest_folder)])
    checks.check("cli-move-no-ids", empty.returncode == 2, empty.stderr[-200:])

    server, url, pids = start_owned(root)
    try:
        base = url.rstrip("/")
        wait_ready(url, need, slots=("thumb",), timeout=120)
        status, thumb_before, thumb_bytes = request_raw(f"{base}/api/media/{photo_a}?which=thumb")
        checks.check("thumb-before-200", status == 200 and bool(thumb_bytes), str(status))
        thumb_hash = sha256_file(root / "renditions" / photo_a / "thumb.webp") if (
            root / "renditions" / photo_a / "thumb.webp"
        ).is_file() else ""
        checks.check("thumb-file-before", bool(thumb_hash), thumb_hash)

        status, payload = request_json(base + "/api/items/move", method="POST", body={}, timeout=5)
        checks.check(
            "http-move-empty",
            status == 400 and isinstance(payload, dict) and payload.get("error") == "invalid-argument",
            json.dumps(payload),
        )
        status, payload = request_json(
            base + "/api/items/move",
            method="POST",
            body={"itemIds": ["missing-id"], "destination": str(dest_folder)},
            timeout=5,
        )
        checks.check(
            "http-move-unknown",
            status == 404 and isinstance(payload, dict) and payload.get("error") == "not-found",
            json.dumps(payload),
        )
        status, payload = request_json(
            base + "/api/items/move",
            method="POST",
            body={"itemIds": [photo_c], "destination": str(artifacts / "not-a-source")},
            timeout=5,
        )
        checks.check(
            "http-move-outside",
            status == 400 and isinstance(payload, dict) and payload.get("error") == "invalid-argument",
            json.dumps(payload),
        )
        still_src = src_folder / "b" / "no-exif.jpg"
        checks.check("outside-leaves-file", still_src.is_file(), str(still_src))

        moved = run_library(root, ["move", photo_a, video, "--to", str(dest_folder)], timeout=60)
        checks.check("cli-move-ok", moved.returncode == 0, moved.stderr[-200:])
        body = json.loads(moved.stdout)
        checks.check("cli-move-count", len(body.get("moved") or []) == 2, json.dumps(body))
        record["cliMove"] = body

        checks.check("old-a-gone", not (src_folder / "a" / "IMG_1042.jpg").exists())
        checks.check("old-video-gone", not (src_folder / "a" / "clip.mp4").exists())
        checks.check("new-a-exists", (dest_folder / "IMG_1042.jpg").is_file())
        checks.check("new-video-exists", (dest_folder / "clip.mp4").is_file())
        checks.check("unmoved-stays", (src_folder / "a" / "near.jpg").is_file())

        after_items = item_map(load_items(root))
        after_a = after_items["IMG_1042.jpg"]
        after_video = after_items["clip.mp4"]
        checks.check(
            "catalog-a-new",
            resolved(dest_folder / "IMG_1042.jpg") in current_paths(after_a),
            json.dumps(current_paths(after_a)),
        )
        checks.check(
            "catalog-a-old-gone",
            resolved(src_folder / "a" / "IMG_1042.jpg") not in current_paths(after_a),
            json.dumps(current_paths(after_a)),
        )
        checks.check(
            "catalog-video-new",
            resolved(dest_folder / "clip.mp4") in current_paths(after_video),
            json.dumps(current_paths(after_video)),
        )
        checks.check(
            "faces-kept",
            (after_a.get("faces") or []) == before_faces,
            json.dumps(after_a.get("faces")),
        )
        checks.check(
            "things-kept",
            (after_a.get("things") or []) == before_things,
            json.dumps(after_a.get("things")),
        )
        listed = item_map(json.loads(run_library(root, ["items"]).stdout))
        checks.check("favorite-kept", listed["IMG_1042.jpg"].get("favorite") is True, json.dumps(listed["IMG_1042.jpg"].get("favorite")))
        rend = after_a.get("renditions") or {}
        checks.check(
            "thumb-status-ready",
            (rend.get("status") or {}).get("thumb") == "ready",
            json.dumps(rend.get("status")),
        )
        thumb_after_path = root / "renditions" / photo_a / "thumb.webp"
        checks.check("thumb-file-stays", thumb_after_path.is_file() and sha256_file(thumb_after_path) == thumb_hash)
        status, _, thumb_after = request_raw(f"{base}/api/media/{photo_a}?which=thumb")
        checks.check("thumb-served", status == 200 and thumb_after == thumb_bytes, str(status))
        status, reveal = request_json(base + "/api/items/" + photo_a + "/reveal", method="POST", body={}, timeout=5)
        checks.check(
            "reveal-new-path",
            status == 200 and resolved(dest_folder / "IMG_1042.jpg") == (reveal or {}).get("path"),
            json.dumps(reveal),
        )

        planted = dest_folder / "near.jpg"
        shutil.copy2(src_folder / "b" / "no-exif.jpg", planted)
        planted_hash = sha256_file(planted)
        collide = run_library(root, ["move", photo_b, "--to", str(dest_folder)], timeout=60)
        checks.check("collision-cli", collide.returncode == 0, collide.stderr[-200:])
        collide_body = json.loads(collide.stdout)
        record["collision"] = collide_body
        renamed = dest_folder / "near_2.jpg"
        checks.check("collision-renamed", renamed.is_file(), str(renamed))
        checks.check("collision-no-overwrite", planted.is_file() and sha256_file(planted) == planted_hash)
        checks.check("collision-old-gone", not (src_folder / "a" / "near.jpg").exists())
        after_b = item_map(load_items(root))["near.jpg"]
        checks.check(
            "collision-catalog",
            resolved(renamed) in current_paths(after_b),
            json.dumps(current_paths(after_b)),
        )

        sources = load_sources(root)
        src_source = source_by_path(sources, src_folder)
        dest_source = source_by_path(sources, dest_folder)
        checks.check("has-src-source", src_source is not None)
        checks.check("has-dest-source", dest_source is not None)
        before_count = len(load_items(root))
        if src_source:
            rescan_src = run_library(root, ["rescan", src_source["id"]], timeout=180)
            checks.check("rescan-src-ok", rescan_src.returncode == 0, rescan_src.stderr[-200:])
            src_summary = parse_summary(rescan_src.stdout)
            checks.check("rescan-src-added-0", src_summary.get("added") == 0, json.dumps(src_summary))
        if dest_source:
            rescan_dest = run_library(root, ["rescan", dest_source["id"]], timeout=180)
            checks.check("rescan-dest-ok", rescan_dest.returncode == 0, rescan_dest.stderr[-200:])
            dest_summary = parse_summary(rescan_dest.stdout)
            checks.check("rescan-dest-added-0", dest_summary.get("added") == 0, json.dumps(dest_summary))
        checks.check("rescan-no-dupes", len(load_items(root)) == before_count, str(len(load_items(root))))
    finally:
        stop_owned(server, extra_pids=pids)

    fail_root = fresh_root(artifacts / "fail-root")
    fail_src, fail_dest = seed_two_folders(media_src, artifacts, "fail")
    run_library(fail_root, ["scan", str(fail_src), "--serve-from-there"], timeout=180)
    run_library(fail_root, ["scan", str(fail_dest), "--serve-from-there"], timeout=180)
    fail_items = item_map(load_items(fail_root))
    fail_a = fail_items["IMG_1042.jpg"]["id"]
    fail_b = fail_items["near.jpg"]["id"]
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_BARRIER"] = "move-after-item"
    crashed = run_library(fail_root, ["move", fail_a, fail_b, "--to", str(fail_dest)], env=env, timeout=60)
    checks.check("barrier-exit", crashed.returncode == 86, str(crashed.returncode) + crashed.stderr[-200:])
    checks.check("barrier-first-moved", (fail_dest / "IMG_1042.jpg").is_file())
    checks.check("barrier-first-old-gone", not (fail_src / "a" / "IMG_1042.jpg").exists())
    checks.check("barrier-second-stays", (fail_src / "a" / "near.jpg").is_file())
    checks.check("barrier-second-not-dest", not (fail_dest / "near.jpg").exists())
    fail_after = item_map(load_items(fail_root))
    checks.check(
        "barrier-catalog-first",
        resolved(fail_dest / "IMG_1042.jpg") in current_paths(fail_after["IMG_1042.jpg"]),
        json.dumps(current_paths(fail_after["IMG_1042.jpg"])),
    )
    checks.check(
        "barrier-catalog-second",
        resolved(fail_src / "a" / "near.jpg") in current_paths(fail_after["near.jpg"]),
        json.dumps(current_paths(fail_after["near.jpg"])),
    )
    record["barrier"] = {
        "destHasA": (fail_dest / "IMG_1042.jpg").is_file(),
        "srcHasB": (fail_src / "a" / "near.jpg").is_file(),
    }

    roll_root = fresh_root(artifacts / "rollback-root")
    roll_src, roll_dest = seed_two_folders(media_src, artifacts, "rollback")
    run_library(roll_root, ["scan", str(roll_src), "--serve-from-there"], timeout=180)
    run_library(roll_root, ["scan", str(roll_dest), "--serve-from-there"], timeout=180)
    roll_items = item_map(load_items(roll_root))
    roll_id = roll_items["no-exif.jpg"]["id"]
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_BARRIER"] = "move-after-bytes"
    rolled = run_library(roll_root, ["move", roll_id, "--to", str(roll_dest)], env=env, timeout=60)
    checks.check("bytes-barrier-exit", rolled.returncode == 86, str(rolled.returncode))
    checks.check("bytes-rollback-src", (roll_src / "b" / "no-exif.jpg").is_file())
    checks.check("bytes-rollback-dest", not (roll_dest / "no-exif.jpg").exists())
    roll_after = item_map(load_items(roll_root))["no-exif.jpg"]
    checks.check(
        "bytes-rollback-catalog",
        resolved(roll_src / "b" / "no-exif.jpg") in current_paths(roll_after),
        json.dumps(current_paths(roll_after)),
    )

    cross_root = fresh_root(artifacts / "cross-root")
    cross_src, cross_dest = seed_two_folders(media_src, artifacts, "cross")
    run_library(cross_root, ["scan", str(cross_src), "--serve-from-there"], timeout=180)
    run_library(cross_root, ["scan", str(cross_dest), "--serve-from-there"], timeout=180)
    cross_items = item_map(load_items(cross_root))
    cross_id = cross_items["no-exif.jpg"]["id"]
    before_hash = sha256_file(cross_src / "b" / "no-exif.jpg")
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_CROSS_DRIVE"] = "1"
    crossed = run_library(cross_root, ["move", cross_id, "--to", str(cross_dest)], env=env, timeout=60)
    checks.check("cross-ok", crossed.returncode == 0, crossed.stderr[-200:])
    checks.check("cross-dest", (cross_dest / "no-exif.jpg").is_file() and sha256_file(cross_dest / "no-exif.jpg") == before_hash)
    checks.check("cross-src-gone", not (cross_src / "b" / "no-exif.jpg").exists())
    return record


def bar_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const bar = document.getElementById('selection-bar');
          const move = document.getElementById('selection-move');
          const dialog = document.getElementById('move-folder');
          const confirm = document.getElementById('move-folder-confirm');
          const path = document.getElementById('move-folder-path');
          const sources = Array.from(document.querySelectorAll('#move-folder-sources button')).map(function (el) {
            return {id: el.getAttribute('data-source-id'), text: el.textContent, pressed: el.getAttribute('aria-pressed')};
          });
          return {
            hidden: !bar || bar.hidden,
            moveLabel: (move || {}).textContent || '',
            dialogOpen: !!(dialog && dialog.open),
            confirm: (confirm || {}).textContent || '',
            path: (path || {}).value || '',
            sources: sources,
            files: Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(function (el) {
              return el.getAttribute('data-filename');
            }),
            lang: document.documentElement.lang
          };
        }"""
    )


def cell(page: Any, name: str) -> Any:
    return page.locator('#grid .cell[data-slot="grid"][data-filename="' + name + '"]').first


def prove_browser(page: Any, url: str, dest_folder: Path, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    page.locator("#date-group").select_option("off")
    page.wait_for_function(
        """() => document.querySelectorAll('#grid .cell[data-slot=\"grid\"][data-filename]').length >= 4""",
        timeout=8000,
    )
    cell(page, "IMG_1042.jpg").click(modifiers=["ControlOrMeta"])
    cell(page, "near.jpg").click(modifiers=["ControlOrMeta"])
    page.wait_for_function(
        """() => {
          const bar = document.getElementById('selection-bar');
          return bar && !bar.hidden && document.getElementById('selection-move');
        }""",
        timeout=5000,
    )
    start = bar_state(page)
    record["selected"] = start
    checks.check("move-btn-en", start.get("moveLabel") == "Move", json.dumps(start.get("moveLabel")))

    page.locator("#language").select_option("zh-Hans")
    page.wait_for_function(
        """() => document.documentElement.lang === 'zh-Hans'
          && ((document.getElementById('selection-move') || {}).textContent || '') === '移动'""",
        timeout=8000,
    )
    page.screenshot(path=str(artifacts / "selection-move-zh.png"))
    checks.check("move-btn-zh", True)

    page.locator("#selection-move").click()
    page.wait_for_function(
        "() => document.getElementById('move-folder') && document.getElementById('move-folder').open",
        timeout=5000,
    )
    page.wait_for_function(
        """() => ((document.getElementById('move-folder-title') || {}).textContent || '') === '移动到文件夹'""",
        timeout=5000,
    )
    zh = bar_state(page)
    record["zhDialog"] = zh
    checks.check("dialog-zh-title", True)
    page.screenshot(path=str(artifacts / "move-zh.png"))

    page.locator("#language").select_option("en")
    page.wait_for_function(
        """() => document.documentElement.lang === 'en'
          && ((document.getElementById('move-folder-title') || {}).textContent || '') === 'Move to folder'""",
        timeout=8000,
    )

    dest_text = str(dest_folder.resolve())
    page.evaluate(
        """(dest) => {
          const buttons = Array.from(document.querySelectorAll('#move-folder-sources button'));
          const match = buttons.find(function (el) { return (el.textContent || '').indexOf(dest) !== -1 || dest.indexOf(el.textContent || '') !== -1; });
          if (match) { match.click(); return true; }
          const path = document.getElementById('move-folder-path');
          if (path) { path.value = dest; path.dispatchEvent(new Event('input', {bubbles: true})); return true; }
          return false;
        }""",
        dest_text,
    )
    page.wait_for_function(
        """(dest) => {
          const confirm = (document.getElementById('move-folder-confirm') || {}).textContent || '';
          const path = (document.getElementById('move-folder-path') || {}).value || '';
          return path && confirm.indexOf('2') !== -1 && (confirm.indexOf(dest) !== -1 || path.indexOf(dest) !== -1);
        }""",
        dest_text,
        timeout=5000,
    )
    picked = bar_state(page)
    record["picked"] = picked
    checks.check(
        "confirm-count-dest",
        "2" in (picked.get("confirm") or "") and dest_text in (picked.get("path") or picked.get("confirm") or ""),
        json.dumps(picked),
    )
    page.screenshot(path=str(artifacts / "move-confirm.png"))

    page.locator("#move-folder-cancel").click()
    page.wait_for_function(
        "() => !document.getElementById('move-folder').open",
        timeout=5000,
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    cancel_names = {item.get("filename") for item in (listed if isinstance(listed, list) else [])}
    checks.check(
        "cancel-leaves-catalog",
        status == 200 and "IMG_1042.jpg" in cancel_names and "near.jpg" in cancel_names,
        json.dumps(sorted(cancel_names)),
    )
    checks.check("cancel-leaves-files", (dest_folder / "IMG_1042.jpg").exists() is False)

    page.locator("#selection-move").click()
    page.wait_for_function(
        "() => document.getElementById('move-folder') && document.getElementById('move-folder').open",
        timeout=5000,
    )
    page.evaluate(
        """(dest) => {
          const buttons = Array.from(document.querySelectorAll('#move-folder-sources button'));
          const match = buttons.find(function (el) { return (el.textContent || '').indexOf(dest) !== -1 || dest.indexOf(el.textContent || '') !== -1; });
          if (match) { match.click(); return; }
          const path = document.getElementById('move-folder-path');
          if (path) { path.value = dest; path.dispatchEvent(new Event('input', {bubbles: true})); }
        }""",
        dest_text,
    )
    page.wait_for_function(
        """() => {
          const confirm = (document.getElementById('move-folder-confirm') || {}).textContent || '';
          const ok = document.getElementById('move-folder-ok');
          return confirm && ok && !ok.disabled;
        }""",
        timeout=5000,
    )
    page.screenshot(path=str(artifacts / "selection-move.png"))
    page.locator("#move-folder-ok").click()
    page.wait_for_function(
        "() => !document.getElementById('move-folder').open",
        timeout=15000,
    )
    page.wait_for_timeout(400)
    checks.check("after-move-a", (dest_folder / "IMG_1042.jpg").is_file())
    checks.check("after-move-b", (dest_folder / "near.jpg").is_file())
    page.screenshot(path=str(artifacts / "after-move.png"))
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    by_name = item_map(listed if isinstance(listed, list) else [])
    checks.check(
        "browser-catalog-a",
        status == 200 and dest_text in (primary_path(by_name.get("IMG_1042.jpg") or {}) or ""),
        json.dumps(current_paths(by_name.get("IMG_1042.jpg") or {})),
    )
    return record


def seed_browser_root(root: Path, media_src: Path, artifacts: Path) -> tuple[Path, Path]:
    src, dest = seed_two_folders(media_src, artifacts, "browser")
    scanned = run_library(root, ["scan", str(src), "--serve-from-there"], timeout=180)
    if scanned.returncode != 0:
        raise RuntimeError(scanned.stderr[-200:])
    scanned_dest = run_library(root, ["scan", str(dest), "--serve-from-there"], timeout=180)
    if scanned_dest.returncode != 0:
        raise RuntimeError(scanned_dest.stderr[-200:])
    return src, dest


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library move <id> <id> --to <folder>",
        "POST /api/items/move",
    ]
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "move-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["move-api.json"] = str(artifacts / "move-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        _src_folder, dest_folder = seed_browser_root(isolated, media_src, artifacts)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg", "no-exif.jpg", "clip.mp4"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, dest_folder, artifacts, checks)
                unexpected = [
                    message
                    for message in errors
                    if "status of 400" not in message and "status of 404" not in message
                ]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "move-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["move-browser.json"] = str(artifacts / "move-browser.json")
            extra["selection-move.png"] = str(artifacts / "selection-move.png")
            extra["selection-move-zh.png"] = str(artifacts / "selection-move-zh.png")
            extra["move-confirm.png"] = str(artifacts / "move-confirm.png")
            extra["move-zh.png"] = str(artifacts / "move-zh.png")
            extra["after-move.png"] = str(artifacts / "after-move.png")
        finally:
            stop_owned(server, extra_pids=pids)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-move-runner", False, str(exc))
    return write_result("TASTE-MOVE", "slice", checks, artifacts, commands, extra)
