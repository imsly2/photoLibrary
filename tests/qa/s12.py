"""Slice S12 / Check F19 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    Checks,
    assert_no_pillow_in_server,
    copy_committed_fixtures,
)
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s03 import find_item, png_size
from tests.qa.s05 import pin_media_from_manifest, pin_mtime
from tests.qa.s06 import playing_cell_videos, set_settings, wait_level, wait_play_proxies
from tests.qa.s08 import copy_rels, fresh_root, run_library, write_result
from tests.qa.s09 import start_owned
from tests.qa.s10 import write_json

LIVE_STILL = "live/LIVE_0001.jpg"
LIVE_MOTION = "live/LIVE_0001.mov"
LIVE_CID = "11111111-2222-4333-8444-555555555555"
PIN_MTIME = "2022-01-01T00:00:00Z"


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    pin_mtime(dest, PIN_MTIME)


def scan_folder(root: Path, folder: Path, commands: list[str]) -> dict[str, Any]:
    proc = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    commands.append("python -m library scan <folder> --serve-from-there")
    return {"proc": proc, "stdout": proc.stdout, "stderr": proc.stderr, "code": proc.returncode}


def components(item: dict[str, Any]) -> list[str]:
    return sorted(loc.get("component") for loc in (item.get("locations") or []))


def live_items_of(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("kind") == "live"]


def history_item_paths(root: Path, operation: str | None = None) -> list[str]:
    state_path = root / "undo" / "state.json"
    if not state_path.is_file():
        return []
    state = json.loads(state_path.read_text(encoding="utf-8"))
    paths: list[str] = []
    for entry_id in (state.get("entries") or [])[: state.get("cursor") or 0]:
        entry_path = root / "undo" / "entries" / f"{entry_id}.json"
        if not entry_path.is_file():
            continue
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
        if operation is not None and entry.get("operation") != operation:
            continue
        for change in entry.get("changes") or []:
            path = change.get("path")
            if type(path) is str and path.startswith("catalog/items/"):
                paths.append(path)
    return paths


def prove_pair(
    checks: Checks,
    root: Path,
    folder: Path,
    still_src: Path,
    commands: list[str],
) -> dict[str, Any] | None:
    scanned = scan_folder(root, folder, commands)
    checks.check("pair-scan-exit", scanned["code"] == 0, scanned["stderr"])
    items = load_items(root)
    still_hash = sha256_file(still_src)
    lives = live_items_of(items)
    checks.check("one-live-item", len(lives) == 1, str([item.get("id") for item in lives]))
    if not lives:
        return None
    live = lives[0]
    checks.check("live-kind", live.get("kind") == "live", str(live.get("kind")))
    checks.check("live-id-is-still-hash", live.get("id") == still_hash, str(live.get("id")))
    checks.check("live-cid", live.get("contentIdentifier") == LIVE_CID, str(live.get("contentIdentifier")))
    locs = live.get("locations") or []
    checks.check("live-two-locations", len(locs) == 2, str(len(locs)))
    checks.check("live-components", components(live) == ["motion", "still"], str(components(live)))
    still_primary = sum(
        1 for loc in locs if loc.get("component") == "still" and loc.get("role") == "primary"
    )
    motion_primary = sum(
        1 for loc in locs if loc.get("component") == "motion" and loc.get("role") == "primary"
    )
    checks.check("live-still-primary", still_primary == 1, str(still_primary))
    checks.check("live-motion-primary", motion_primary == 1, str(motion_primary))
    checks.check("no-stolen-second-live", len(lives) == 1)
    return live


def prove_honesty(checks: Checks, artifacts: Path, src: Path, commands: list[str]) -> dict[str, Any]:
    still_src = src / Path(LIVE_STILL)
    motion_src = src / Path(LIVE_MOTION)
    clip_src = src / "a" / "clip.mp4"
    still_hash = sha256_file(still_src)
    motion_hash = sha256_file(motion_src)
    record: dict[str, Any] = {}

    orphan_still_root = fresh_root(artifacts / "honesty-orphan-still-root")
    orphan_still = artifacts / "honesty-orphan-still"
    if orphan_still.exists():
        shutil.rmtree(orphan_still)
    copy_file(still_src, orphan_still / "LIVE_0001.jpg")
    scan_folder(orphan_still_root, orphan_still, commands)
    orphan_still_items = load_items(orphan_still_root)
    record["orphanStill"] = {
        "count": len(orphan_still_items),
        "kinds": [item.get("kind") for item in orphan_still_items],
        "ids": [item.get("id") for item in orphan_still_items],
    }
    checks.check("orphan-still-one", len(orphan_still_items) == 1, json.dumps(record["orphanStill"]))
    if orphan_still_items:
        item = orphan_still_items[0]
        checks.check("orphan-still-photo", item.get("kind") == "photo", str(item.get("kind")))
        checks.check("orphan-still-id", item.get("id") == still_hash, str(item.get("id")))
        checks.check("orphan-still-one-location", len(item.get("locations") or []) == 1)

    orphan_motion_root = fresh_root(artifacts / "honesty-orphan-motion-root")
    orphan_motion = artifacts / "honesty-orphan-motion"
    if orphan_motion.exists():
        shutil.rmtree(orphan_motion)
    copy_file(motion_src, orphan_motion / "LIVE_0001.mov")
    scan_folder(orphan_motion_root, orphan_motion, commands)
    orphan_motion_items = load_items(orphan_motion_root)
    record["orphanMotion"] = {
        "count": len(orphan_motion_items),
        "kinds": [item.get("kind") for item in orphan_motion_items],
        "ids": [item.get("id") for item in orphan_motion_items],
    }
    checks.check("orphan-motion-one", len(orphan_motion_items) == 1, json.dumps(record["orphanMotion"]))
    if orphan_motion_items:
        item = orphan_motion_items[0]
        checks.check("orphan-motion-video", item.get("kind") == "video", str(item.get("kind")))
        checks.check("orphan-motion-id", item.get("id") == motion_hash, str(item.get("id")))
        checks.check("orphan-motion-not-still-hash", item.get("id") != still_hash)

    reverse_root = fresh_root(artifacts / "honesty-reverse-root")
    reverse_folder = artifacts / "honesty-reverse"
    if reverse_folder.exists():
        shutil.rmtree(reverse_folder)
    copy_file(motion_src, reverse_folder / "LIVE_0001.mov")
    scan_folder(reverse_root, reverse_folder, commands)
    before_still = load_items(reverse_root)
    checks.check("reverse-motion-only-video", len(before_still) == 1 and before_still[0].get("kind") == "video")
    motion_only_id = before_still[0]["id"] if before_still else ""
    copy_file(still_src, reverse_folder / "LIVE_0001.jpg")
    scan_folder(reverse_root, reverse_folder, commands)
    reverse_items = load_items(reverse_root)
    reverse_lives = live_items_of(reverse_items)
    record["reversed"] = {
        "count": len(reverse_items),
        "liveIds": [item.get("id") for item in reverse_lives],
        "kinds": [item.get("kind") for item in reverse_items],
    }
    checks.check("reverse-one-item", len(reverse_items) == 1, json.dumps(record["reversed"]))
    checks.check("reverse-one-live", len(reverse_lives) == 1, json.dumps(record["reversed"]))
    if reverse_lives:
        checks.check("reverse-id-still-hash", reverse_lives[0]["id"] == still_hash, reverse_lives[0]["id"])
        checks.check("reverse-did-not-keep-motion-id", reverse_lives[0]["id"] != motion_only_id)
        checks.check("reverse-two-locations", len(reverse_lives[0].get("locations") or []) == 2)

    scan_folder(reverse_root, reverse_folder, commands)
    restarted = load_items(reverse_root)
    record["restart"] = {
        "count": len(restarted),
        "liveIds": [item.get("id") for item in live_items_of(restarted)],
    }
    checks.check("restart-still-one-item", len(restarted) == 1, json.dumps(record["restart"]))
    checks.check("restart-same-live-id", record["restart"]["liveIds"] == [still_hash], json.dumps(record["restart"]))

    mismatch_root = fresh_root(artifacts / "honesty-mismatch-root")
    mismatch = artifacts / "honesty-mismatch"
    if mismatch.exists():
        shutil.rmtree(mismatch)
    copy_file(still_src, mismatch / "LIVE_0001.jpg")
    copy_file(clip_src, mismatch / "LIVE_0001.mov")
    scan_folder(mismatch_root, mismatch, commands)
    mismatch_items = load_items(mismatch_root)
    mismatch_lives = live_items_of(mismatch_items)
    record["mismatch"] = {
        "count": len(mismatch_items),
        "kinds": [item.get("kind") for item in mismatch_items],
        "ids": [item.get("id") for item in mismatch_items],
        "cids": [item.get("contentIdentifier") for item in mismatch_items],
    }
    checks.check("mismatch-two-items", len(mismatch_items) == 2, json.dumps(record["mismatch"]))
    checks.check("mismatch-no-live", mismatch_lives == [], json.dumps(record["mismatch"]))
    mismatch_ids = {item.get("id") for item in mismatch_items}
    checks.check("mismatch-kept-still-id", still_hash in mismatch_ids, json.dumps(record["mismatch"]))
    checks.check("mismatch-kept-clip-id", sha256_file(clip_src) in mismatch_ids, json.dumps(record["mismatch"]))

    alt_root = fresh_root(artifacts / "honesty-altname-root")
    alt = artifacts / "honesty-altname"
    if alt.exists():
        shutil.rmtree(alt)
    copy_file(still_src, alt / "still.jpg")
    copy_file(motion_src, alt / "motion.mov")
    scan_folder(alt_root, alt, commands)
    alt_items = load_items(alt_root)
    alt_lives = live_items_of(alt_items)
    record["altNames"] = {
        "count": len(alt_items),
        "kinds": [item.get("kind") for item in alt_items],
        "ids": [item.get("id") for item in alt_items],
    }
    checks.check("identifier-not-filename-one", len(alt_items) == 1 and len(alt_lives) == 1, json.dumps(record["altNames"]))
    if alt_lives:
        checks.check("identifier-not-filename-id", alt_lives[0]["id"] == still_hash, alt_lives[0]["id"])

    absorb_root = fresh_root(artifacts / "honesty-absorb-root")
    absorb = artifacts / "honesty-absorb"
    if absorb.exists():
        shutil.rmtree(absorb)
    copy_file(motion_src, absorb / "LIVE_0001.mov")
    scan_folder(absorb_root, absorb, commands)
    motion_only = load_items(absorb_root)
    checks.check("absorb-motion-present", len(motion_only) == 1, str(len(motion_only)))
    motion_id = motion_only[0]["id"] if motion_only else ""
    annotated = run_library(absorb_root, ["annotate", motion_id, "--person", "Ada", "--thing", "mug"])
    commands.append("python -m library annotate <motion-id> --person Ada --thing mug")
    checks.check("absorb-annotate-exit", annotated.returncode == 0, annotated.stderr)
    before_paths = history_item_paths(absorb_root, "annotate")
    checks.check(
        "absorb-history-had-motion",
        any(path.endswith(f"{motion_id}.json") for path in before_paths),
        json.dumps(before_paths),
    )
    copy_file(still_src, absorb / "LIVE_0001.jpg")
    scan_folder(absorb_root, absorb, commands)
    absorb_items = load_items(absorb_root)
    absorb_lives = live_items_of(absorb_items)
    record["absorb"] = {
        "count": len(absorb_items),
        "liveIds": [item.get("id") for item in absorb_lives],
        "faces": (absorb_lives[0].get("faces") if absorb_lives else None),
        "things": (absorb_lives[0].get("things") if absorb_lives else None),
    }
    checks.check("absorb-one-live", len(absorb_items) == 1 and len(absorb_lives) == 1, json.dumps(record["absorb"]))
    if absorb_lives:
        live = absorb_lives[0]
        checks.check("absorb-id-still-hash", live["id"] == still_hash, live["id"])
        checks.check("absorb-kept-faces", len(live.get("faces") or []) >= 1, json.dumps(live.get("faces")))
        checks.check("absorb-kept-things", len(live.get("things") or []) >= 1, json.dumps(live.get("things")))
        after_paths = history_item_paths(absorb_root, "annotate")
        checks.check(
            "absorb-history-now-live",
            any(path.endswith(f"{still_hash}.json") for path in after_paths),
            json.dumps(after_paths),
        )
        checks.check(
            "absorb-history-dropped-motion",
            not any(path.endswith(f"{motion_id}.json") for path in after_paths),
            json.dumps(after_paths),
        )
        checks.check(
            "absorb-motion-file-gone",
            not (absorb_root / "catalog" / "items" / f"{motion_id}.json").is_file(),
        )
        stay = run_library(absorb_root, ["annotate", live["id"], "--place", "Kitchen"])
        commands.append("python -m library annotate <live-id> --place Kitchen")
        checks.check("live-annotate-exit", stay.returncode == 0, stay.stderr)
        after = load_items(absorb_root)
        after_live = live_items_of(after)
        checks.check("live-annotate-stays", len(after_live) == 1 and after_live[0]["id"] == still_hash)
        if after_live:
            checks.check("live-annotate-place", after_live[0].get("placeId") not in {None, ""}, str(after_live[0].get("placeId")))
    return record


def wait_live_ready(base: str, timeout: float = 90) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            lives = live_items_of(payload)
            if len(lives) == 1:
                rend = ((lives[0].get("renditions") or {}).get("status") or {})
                if (
                    rend.get("thumb") == "ready"
                    and rend.get("preview") == "ready"
                    and rend.get("poster") == "ready"
                    and rend.get("proxy") == "ready"
                    and lives[0].get("motionAvailable") is True
                ):
                    return payload
        time.sleep(0.25)
    raise RuntimeError("live renditions timeout " + json.dumps([
        {
            "id": item.get("id"),
            "kind": item.get("kind"),
            "status": (item.get("renditions") or {}).get("status"),
            "motionAvailable": item.get("motionAvailable"),
        }
        for item in last
    ]))


def wait_live_stills(base: str, timeout: float = 90) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            lives = live_items_of(payload)
            if len(lives) == 1:
                rend = ((lives[0].get("renditions") or {}).get("status") or {})
                if rend.get("thumb") == "ready" and rend.get("preview") == "ready":
                    return payload
        time.sleep(0.25)
    raise RuntimeError("live still timeout " + json.dumps([
        {
            "id": item.get("id"),
            "status": (item.get("renditions") or {}).get("status"),
        }
        for item in last
    ]))


def prove_browser(
    checks: Checks,
    url: str,
    artifacts: Path,
    live_id: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "viewport": {"width": 1280, "height": 720},
        "badge": None,
        "hover": {},
        "viewer": {},
    }
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        checks.check("playwright-import", False, str(exc))
        return record
    checks.check("playwright-import", True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            set_settings(url.rstrip("/"), {"playProxies": "days-and-all", "zoomLevel": "all"})
            wait_play_proxies(page, "days-and-all")
            wait_level(page, "all")
            cell = page.locator('.cell[data-kind="live"]')
            page.wait_for_selector('.cell[data-kind="live"]', timeout=20000)
            checks.check("live-cell-present", cell.count() >= 1, str(cell.count()))
            badge = page.locator('.cell[data-kind="live"] .live-badge')
            badge_text = badge.first.inner_text() if badge.count() else ""
            record["badge"] = badge_text
            checks.check("live-badge-text", badge_text == "LIVE", badge_text)
            cell.first.hover()
            page.wait_for_function(
                """() => Array.from(document.querySelectorAll('.cell video')).some(function (v) {
                  return !v.paused && !v.ended;
                })""",
                timeout=8000,
            )
            hover = playing_cell_videos(page)
            src = page.evaluate(
                """() => {
                  const video = document.querySelector('.cell video');
                  return video ? (video.currentSrc || video.getAttribute('src') || '') : '';
                }"""
            )
            record["hover"] = {"state": hover, "src": src}
            checks.check("hover-plays-one", hover["playingCount"] == 1, json.dumps(hover))
            checks.check("hover-muted", hover["muted"] is True and hover["volumeZero"] is True, json.dumps(hover))
            checks.check("hover-uses-proxy", "which=proxy" in (src or ""), src or "")
            page.mouse.move(2, 2)
            page.wait_for_function("() => document.querySelectorAll('.cell video').length === 0", timeout=5000)
            restored = page.evaluate(
                """(id) => {
                  const cell = document.querySelector('.cell[data-id="' + id + '"]');
                  if (!cell) return false;
                  const img = cell.querySelector('img');
                  const src = img ? (img.getAttribute('src') || '') : '';
                  return !!(img && !img.hidden && src.indexOf('which=thumb') !== -1);
                }""",
                live_id,
            )
            record["hover"]["leaveRestoresStill"] = bool(restored)
            checks.check("hover-leave-restores-still", bool(restored), live_id)
            shot = artifacts / "live.png"
            page.screenshot(path=str(shot), full_page=False)
            width, height = png_size(shot)
            checks.check("live-shot-1280x720", width == 1280 and height == 720, f"{width}x{height}")
            record["screenshot"] = str(shot)
            cell.first.click()
            page.wait_for_function(
                """() => {
                  const viewer = document.getElementById('viewer');
                  const img = document.getElementById('viewer-image');
                  return viewer && !viewer.hidden && img && !img.hidden;
                }""",
                timeout=8000,
            )
            video_hidden = page.evaluate(
                "() => { const v = document.getElementById('viewer-video'); return !v || v.hidden; }"
            )
            img_src = page.evaluate(
                "() => { const img = document.getElementById('viewer-image'); return img ? (img.currentSrc || img.src || '') : ''; }"
            )
            record["viewer"]["stillFirst"] = bool(video_hidden) and "which=preview" in (img_src or "")
            checks.check("viewer-still-first", record["viewer"]["stillFirst"], json.dumps({"img": img_src, "videoHidden": video_hidden}))
            page.keyboard.press("Space")
            page.wait_for_function(
                """() => {
                  const video = document.getElementById('viewer-video');
                  if (!video || video.hidden) return false;
                  return video.paused === false;
                }""",
                timeout=12000,
            )
            playback = page.evaluate(
                """() => {
                  const video = document.getElementById('viewer-video');
                  const src = video ? (video.currentSrc || video.getAttribute('src') || '') : '';
                  return {
                    hidden: video ? video.hidden : true,
                    paused: video ? video.paused : true,
                    src: src,
                    usingProxy: video && video.getAttribute('data-using-proxy') === '1',
                  };
                }"""
            )
            record["viewer"]["space"] = playback
            checks.check(
                "viewer-space-plays",
                playback.get("paused") is False and playback.get("hidden") is False,
                json.dumps(playback),
            )
            page.keyboard.press("Escape")
            page.wait_for_function(
                "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
                timeout=5000,
            )
            browser.close()
    except Exception as exc:
        checks.check("live-browser", False, str(exc))
    return record


def prove_missing_motion(
    checks: Checks,
    artifacts: Path,
    src: Path,
    commands: list[str],
    record: dict[str, Any],
) -> None:
    still_src = src / Path(LIVE_STILL)
    motion_src = src / Path(LIVE_MOTION)
    folder = artifacts / "missing-motion-media"
    if folder.exists():
        shutil.rmtree(folder)
    copy_file(still_src, folder / "LIVE_0001.jpg")
    copy_file(motion_src, folder / "LIVE_0001.mov")
    root = fresh_root(artifacts / "missing-motion-root")
    scan_folder(root, folder, commands)
    (folder / "LIVE_0001.mov").unlink()
    server, url, pids = start_owned(root)
    try:
        items = wait_live_stills(url.rstrip("/"))
        live = live_items_of(items)[0]
        checks.check("missing-motion-live", live.get("kind") == "live")
        checks.check("missing-motion-flag", live.get("motionAvailable") is False, json.dumps(live.get("motionAvailable")))
        rend = ((live.get("renditions") or {}).get("status") or {})
        checks.check(
            "missing-motion-stills-ready",
            rend.get("thumb") == "ready" and rend.get("preview") == "ready",
            json.dumps(rend),
        )
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            set_settings(url.rstrip("/"), {"playProxies": "always", "zoomLevel": "all"})
            wait_play_proxies(page, "always")
            wait_level(page, "all")
            page.wait_for_selector('.cell[data-kind="live"]', timeout=20000)
            page.locator('.cell[data-kind="live"]').first.hover()
            time.sleep(0.7)
            hover = playing_cell_videos(page)
            record["missingMotion"] = {"hover": hover}
            checks.check(
                "missing-motion-hover-still",
                hover["playingCount"] == 0 and hover["videoCount"] == 0,
                json.dumps(hover),
            )
            still_shown = page.evaluate(
                """() => {
                  const cell = document.querySelector('.cell[data-kind="live"]');
                  const img = cell && cell.querySelector('img');
                  return !!(img && !img.hidden);
                }"""
            )
            checks.check("missing-motion-cell-still", still_shown is True)
            page.locator('.cell[data-kind="live"]').first.click()
            page.wait_for_function(
                """() => {
                  const viewer = document.getElementById('viewer');
                  const img = document.getElementById('viewer-image');
                  return viewer && !viewer.hidden && img && !img.hidden;
                }""",
                timeout=8000,
            )
            page.keyboard.press("Space")
            time.sleep(0.5)
            viewer = page.evaluate(
                """() => {
                  const video = document.getElementById('viewer-video');
                  const img = document.getElementById('viewer-image');
                  return {
                    videoHidden: !video || video.hidden,
                    videoPaused: !video || video.paused,
                    imgHidden: !img || img.hidden,
                  };
                }"""
            )
            record["missingMotion"]["viewer"] = viewer
            checks.check(
                "missing-motion-viewer-still",
                viewer.get("videoHidden") is True and viewer.get("imgHidden") is False,
                json.dumps(viewer),
            )
            browser.close()
    finally:
        from tests.qa.s00 import stop_owned

        stop_owned(server, extra_pids=pids)


def run_regression(artifacts: Path) -> dict[str, Any]:
    from tests.qa.s06 import run_check_f5, run_check_f7
    from tests.qa.s07 import run_check_f16
    from tests.qa.s08 import run_check_f14
    from tests.qa.s09 import run_check_f10

    runners = {
        "F5": run_check_f5,
        "F7": run_check_f7,
        "F10": run_check_f10,
        "F14": run_check_f14,
        "F16": run_check_f16,
    }
    record: dict[str, Any] = {}
    for feature_id, runner in runners.items():
        sub_art = artifacts / "regression" / feature_id.lower()
        sub_root = artifacts / "regression-roots" / feature_id.lower()
        if sub_art.exists():
            shutil.rmtree(sub_art)
        if sub_root.exists():
            shutil.rmtree(sub_root)
        sub_art.mkdir(parents=True, exist_ok=True)
        code = runner(sub_root, sub_art)
        result_path = sub_art / "result.json"
        passed = False
        if result_path.is_file():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            passed = payload.get("pass") is True
        record[feature_id] = {
            "pass": passed,
            "exit": code,
            "artifacts": str(sub_art),
        }
    return record


def run_session(root: Path, artifacts: Path, checks: Checks, commands: list[str]) -> dict[str, str]:
    extra = {
        "live-item.json": str(artifacts / "live-item.json"),
        "live.png": str(artifacts / "live.png"),
        "live-playback.json": str(artifacts / "live-playback.json"),
        "regression.json": str(artifacts / "regression.json"),
    }
    src = prepare_media(artifacts)
    before = hash_tree(src)
    pair_folder = artifacts / "s12-pair"
    copy_rels(src, pair_folder, [LIVE_STILL, LIVE_MOTION])
    isolated = fresh_root(root)
    live = prove_pair(checks, isolated, pair_folder, src / Path(LIVE_STILL), commands)
    if live is not None:
        write_json(artifacts / "live-item.json", live)
    prove_honesty(checks, artifacts, src, commands)

    playback: dict[str, Any] = {}
    server = None
    pids: list[int] = []
    try:
        server, url, pids = start_owned(isolated)
        api_items = wait_live_ready(url.rstrip("/"))
        api_live = live_items_of(api_items)[0]
        write_json(artifacts / "live-item.json", api_live)
        rend = (api_live.get("renditions") or {}).get("status") or {}
        checks.check(
            "live-all-four-ready",
            rend.get("thumb") == "ready"
            and rend.get("preview") == "ready"
            and rend.get("poster") == "ready"
            and rend.get("proxy") == "ready",
            json.dumps(rend),
        )
        checks.check("live-motion-available", api_live.get("motionAvailable") is True)
        playback = prove_browser(checks, url, artifacts, api_live["id"])
        prove_missing_motion(checks, artifacts, src, commands, playback)
    finally:
        if server is not None:
            from tests.qa.s00 import stop_owned

            stop_owned(server, extra_pids=pids)
    write_json(artifacts / "live-playback.json", playback)

    regression = run_regression(artifacts)
    write_json(artifacts / "regression.json", regression)
    for feature_id, row in regression.items():
        checks.check(f"regression-{feature_id}", row.get("pass") is True and row.get("exit") == 0, json.dumps(row))

    checks.check("original-fixture-bytes", hash_tree(src) == before)
    assert_no_pillow_in_server(checks)
    return extra


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {
        "live-item.json": str(artifacts / "live-item.json"),
        "live.png": str(artifacts / "live.png"),
        "live-playback.json": str(artifacts / "live-playback.json"),
        "regression.json": str(artifacts / "regression.json"),
    }
    try:
        extra = run_session(root, artifacts, checks, commands)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("s12-runner", False, str(exc))
        for name in ("live-item.json", "live-playback.json", "regression.json"):
            path = artifacts / name
            if not path.exists():
                path.write_text("{}\n", encoding="utf-8")
    return write_result("S12", "slice", checks, artifacts, commands, extra)


def run_check_f19(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {
        "live-item.json": str(artifacts / "live-item.json"),
        "live.png": str(artifacts / "live.png"),
        "live-playback.json": str(artifacts / "live-playback.json"),
        "regression.json": str(artifacts / "regression.json"),
    }
    try:
        extra = run_session(root, artifacts, checks, commands)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("f19-runner", False, str(exc))
        for name in ("live-item.json", "live-playback.json", "regression.json"):
            path = artifacts / name
            if not path.exists():
                path.write_text("{}\n", encoding="utf-8")
    return write_result("F19", "check", checks, artifacts, commands, extra)
