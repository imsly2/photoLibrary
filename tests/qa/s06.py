"""Slice S06 / Check F5 / Check F7 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import PHOTO_SUFFIXES, VIDEO_SUFFIXES, file_suffix, sha256_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    FORMAT_FILES,
    PRODUCT_ROOT,
    Checks,
    _env,
    assert_no_pillow_in_server,
    copy_committed_fixtures,
    find_free_port,
    run_library,
    start_server,
    stop_owned,
    wait_health,
    write_isolated_port,
)
from tests.qa.s01 import (
    hash_tree,
    id_matches_primary_file_bytes,
    load_items,
    load_sources,
    parse_summary,
    primary_byte_path,
)
from tests.qa.s03 import find_item, ffprobe_wh, png_size
from tests.qa.s05 import (
    PERSON_ID,
    THING_ID,
    item_has_ada_mug,
    pin_media_from_manifest,
    pin_mtime,
    seed_entities,
)

MATRIX_RELS = list(FORMAT_FILES) + ["a/clip.mp4", "b/oriented.jpg"]
LONG_NAME = "raw_relative_path_would_make_a_bad_pending_json_filename.jpg"
DUPLICATE_REL = "second/source/same.jpg"
FRAME = 1.0 / 30.0
HEIC_NOTE = "ffprobe cannot decode (moov atom not found); stays error + placeholder"


def write_result(
    ident: str,
    kind: str,
    checks: Checks,
    artifacts: Path,
    commands: list[str],
    extra_paths: dict[str, str] | None = None,
) -> int:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest_hash = (
        sha256_file(COMMITTED_FIXTURES / "manifest.json")
        if (COMMITTED_FIXTURES / "manifest.json").is_file()
        else ""
    )
    artifact_paths = {
        "result.json": str(artifacts / "result.json"),
        "stdout.log": str(artifacts / "stdout.log"),
    }
    if extra_paths:
        artifact_paths.update(extra_paths)
    result = {
        kind: ident,
        "pass": checks.ok(),
        "assertions": checks.assertions,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version,
        },
        "fixtureManifestHash": manifest_hash,
        "revision": revision,
        "commands": commands,
        "artifactPaths": artifact_paths,
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def copy_rels(src: Path, dest: Path, rels: list[str] | tuple[str, ...]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for rel in rels:
        target = dest / Path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / Path(rel), target)
    pin_media_from_manifest(dest)


def fresh_root(root: Path) -> Path:
    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    write_isolated_port(isolated, find_free_port())
    return isolated


def settings_port(root: Path) -> int:
    data = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    return int(data["port"])


def start_owned(root: Path) -> tuple[subprocess.Popen[str], str, list[int]]:
    port = settings_port(root)
    server = start_server(root)
    url = f"http://127.0.0.1:{port}/"
    health_status, health_body = wait_health(url, server)
    if health_status != 200 or health_body != {"ok": True}:
        stop_owned(server)
        raise RuntimeError(f"health {health_status} {health_body}")
    owned_pids: list[int] = []
    try:
        status, runtime = request_json(url.rstrip("/") + "/api/runtime", timeout=2)
        if status == 200 and isinstance(runtime, dict):
            pid = runtime.get("pid")
            if type(pid) is int:
                owned_pids.append(pid)
    except Exception:
        pass
    return server, url, owned_pids


def slot_file(root: Path, item_id: str, slot: str) -> Path:
    if slot == "proxy":
        return root / "renditions" / item_id / "proxy.mp4"
    return root / "renditions" / item_id / f"{slot}.webp"


def rendition_files(root: Path) -> list[Path]:
    folder = root / "renditions"
    if not folder.exists():
        return []
    return [path for path in folder.rglob("*") if path.is_file()]


def photo_queued(item: dict[str, Any]) -> bool:
    rend = item.get("renditions") or {}
    status = rend.get("status") or {}
    return (
        status.get("thumb") == "queued"
        and status.get("preview") == "queued"
        and status.get("poster") == "not-applicable"
        and status.get("proxy") == "not-applicable"
        and rend.get("thumb") is None
        and rend.get("preview") is None
        and rend.get("poster") is None
        and rend.get("proxy") is None
    )


def video_queued(item: dict[str, Any]) -> bool:
    rend = item.get("renditions") or {}
    status = rend.get("status") or {}
    return (
        status.get("thumb") == "not-applicable"
        and status.get("preview") == "not-applicable"
        and status.get("poster") == "queued"
        and status.get("proxy") == "queued"
        and rend.get("thumb") is None
        and rend.get("preview") is None
        and rend.get("poster") is None
        and rend.get("proxy") is None
    )


def broken_error(item: dict[str, Any]) -> bool:
    rend = item.get("renditions") or {}
    status = rend.get("status") or {}
    return (
        status.get("thumb") == "error"
        and status.get("preview") == "error"
        and rend.get("thumb") is None
        and rend.get("preview") is None
    )


def ffprobe_media(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None) or {}
    audio_count = sum(1 for s in streams if s.get("codec_type") == "audio")
    duration_raw = (payload.get("format") or {}).get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None
    return {
        "codec": video.get("codec_name"),
        "width": video.get("width") if type(video.get("width")) is int else None,
        "height": video.get("height") if type(video.get("height")) is int else None,
        "duration": duration,
        "audioStreamCount": audio_count,
        "bytes": path.stat().st_size if path.is_file() else 0,
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "").strip(),
    }


def wait_core_ready(root: Path, timeout: float = 180) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        items = load_items(root)
        oriented = find_item(items, "oriented.jpg")
        clip = find_item(items, "clip.mp4")
        last = {
            "oriented": None if oriented is None else (oriented.get("renditions") or {}).get("status"),
            "clip": None if clip is None else (clip.get("renditions") or {}).get("status"),
        }
        if oriented is None or clip is None:
            time.sleep(0.2)
            continue
        o_status = (oriented.get("renditions") or {}).get("status") or {}
        c_status = (clip.get("renditions") or {}).get("status") or {}
        thumb = slot_file(root, oriented["id"], "thumb")
        preview = slot_file(root, oriented["id"], "preview")
        poster = slot_file(root, clip["id"], "poster")
        proxy = slot_file(root, clip["id"], "proxy")
        if (
            o_status.get("thumb") == "ready"
            and o_status.get("preview") == "ready"
            and c_status.get("poster") == "ready"
            and c_status.get("proxy") == "ready"
            and thumb.is_file()
            and thumb.stat().st_size > 0
            and preview.is_file()
            and preview.stat().st_size > 0
            and poster.is_file()
            and poster.stat().st_size > 0
            and proxy.is_file()
            and proxy.stat().st_size > 0
        ):
            last["ready"] = True
            return last
        time.sleep(0.2)
    last["ready"] = False
    return last


def wait_matrix_settled(root: Path, rels: list[str], timeout: float = 180) -> None:
    names = {Path(rel).name for rel in rels}
    deadline = time.time() + timeout
    while time.time() < deadline:
        items = {item.get("filename"): item for item in load_items(root)}
        done = True
        for name in names:
            item = items.get(name)
            if item is None:
                done = False
                break
            status = (item.get("renditions") or {}).get("status") or {}
            kind = item.get("kind")
            if kind == "photo":
                slots = ("thumb", "preview")
            elif kind == "video":
                slots = ("poster", "proxy")
            else:
                continue
            for slot in slots:
                if status.get(slot) == "queued":
                    done = False
                    break
            if not done:
                break
        if done:
            return
        time.sleep(0.25)


def build_format_matrix(root: Path, media: Path, rels: list[str]) -> list[dict[str, Any]]:
    items = load_items(root)
    by_name = {item.get("filename"): item for item in items}
    rows: list[dict[str, Any]] = []
    for rel in rels:
        name = Path(rel).name
        path = media / Path(rel)
        item = by_name.get(name)
        digest = sha256_file(path) if path.is_file() else None
        if item is None:
            rows.append(
                {
                    "path": rel,
                    "hash": digest,
                    "kind": None,
                    "slots": {},
                    "note": "not indexed",
                }
            )
            continue
        rend = item.get("renditions") or {}
        status = rend.get("status") or {}
        slots: dict[str, Any] = {}
        for slot in ("thumb", "preview", "poster", "proxy"):
            dest = slot_file(root, item["id"], slot)
            ready_file = (
                status.get(slot) == "ready"
                and dest.is_file()
                and dest.stat().st_size > 0
            )
            slots[slot] = {
                "status": status.get(slot),
                "path": rend.get(slot),
                "readyNonEmpty": ready_file,
            }
        note = None
        if name in {"quad.heic", "quad.heif"}:
            note = HEIC_NOTE
        if name == "broken.heic":
            note = "invalid HEIF brand; decode-error; no WebP"
        rows.append(
            {
                "path": rel,
                "hash": item.get("id"),
                "kind": item.get("kind"),
                "slots": slots,
                "note": note,
            }
        )
    return rows


def set_settings(url: str, patch: dict[str, Any]) -> dict[str, Any]:
    status, body = request_json(
        url.rstrip("/") + "/api/settings",
        method="PUT",
        body=patch,
        timeout=5,
    )
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"settings {status} {body}")
    return body


def playing_cell_videos(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const videos = Array.from(document.querySelectorAll('.cell video'));
          const playing = videos.filter(function (video) {
            return !video.paused && !video.ended;
          });
          return {
            videoCount: videos.length,
            playingCount: playing.length,
            muted: playing.every(function (video) { return video.muted === true; }),
            volumeZero: playing.every(function (video) { return video.volume === 0; }),
            looped: playing.every(function (video) { return video.loop === true; }),
            ids: playing.map(function (video) {
              const cell = video.closest('.cell');
              return cell ? cell.getAttribute('data-id') : null;
            })
          };
        }"""
    )


def wait_play_proxies(page: Any, value: str, timeout: float = 8000) -> None:
    page.wait_for_function(
        "value => document.getElementById('grid') && document.getElementById('grid').dataset.playProxies === value",
        arg=value,
        timeout=timeout,
    )


def wait_level(page: Any, level: str, timeout: float = 8000) -> None:
    page.wait_for_function(
        "level => document.getElementById('grid') && document.getElementById('grid').dataset.level === level",
        arg=level,
        timeout=timeout,
    )


def prove_hover(
    page: Any,
    url: str,
    checks: Checks,
    artifacts: Path,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "viewport": {"width": 1280, "height": 720},
        "policies": {},
        "leaveRestoresPoster": False,
        "hoverMuted": False,
        "viewerFallbackProxy": False,
    }
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('.cell[data-kind="video"]', timeout=20000)
    set_settings(url, {"playProxies": "days-and-all", "zoomLevel": "years"})
    wait_play_proxies(page, "days-and-all")
    wait_level(page, "years")
    years_cells = page.locator('.cell[data-kind="video"]')
    checks.check("hover-video-cells", years_cells.count() >= 1, str(years_cells.count()))
    if years_cells.count() >= 1:
        years_cells.nth(0).hover()
        time.sleep(0.6)
        years_hover = playing_cell_videos(page)
        record["policies"]["days-and-all"] = {"yearsHover": years_hover}
        checks.check(
            "days-and-all-years-silent",
            years_hover["playingCount"] == 0,
            json.dumps(years_hover),
        )

    set_settings(url, {"zoomLevel": "all"})
    wait_level(page, "all")
    all_cells = page.locator('.cell[data-kind="video"]')
    checks.check("hover-all-two-videos", all_cells.count() >= 2, str(all_cells.count()))
    first = all_cells.nth(0)
    second = all_cells.nth(1)
    first.hover()
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('.cell video')).some(function (v) {
          return !v.paused && !v.ended;
        })""",
        timeout=8000,
    )
    first_state = playing_cell_videos(page)
    second.hover()
    time.sleep(0.5)
    second_state = playing_cell_videos(page)
    record["policies"]["days-and-all"]["allFirst"] = first_state
    record["policies"]["days-and-all"]["allSecond"] = second_state
    checks.check("days-and-all-one-plays", first_state["playingCount"] == 1, json.dumps(first_state))
    checks.check(
        "only-one-hovered-plays",
        second_state["playingCount"] == 1,
        json.dumps(second_state),
    )
    checks.check(
        "hover-muted",
        first_state["muted"] and first_state["volumeZero"] and second_state["muted"] and second_state["volumeZero"],
        json.dumps({"first": first_state, "second": second_state}),
    )
    record["hoverMuted"] = bool(first_state["muted"] and first_state["volumeZero"])
    second_id = second.get_attribute("data-id") or ""
    page.mouse.move(2, 2)
    page.wait_for_function(
        "() => document.querySelectorAll('.cell video').length === 0",
        timeout=5000,
    )
    restored = page.evaluate(
        """(id) => {
          const cell = document.querySelector('.cell[data-id="' + id + '"]');
          if (!cell) return false;
          const img = cell.querySelector('img');
          const src = img ? (img.getAttribute('src') || '') : '';
          return !!(img && !img.hidden && src.indexOf('which=poster') !== -1);
        }""",
        second_id,
    )
    record["leaveRestoresPoster"] = bool(restored)
    checks.check("leave-restores-poster", bool(restored), f"id={second_id}")

    set_settings(url, {"playProxies": "off", "zoomLevel": "all"})
    wait_play_proxies(page, "off")
    wait_level(page, "all")
    off_cell = page.locator('.cell[data-kind="video"]').nth(0)
    off_cell.hover()
    time.sleep(0.6)
    off_state = playing_cell_videos(page)
    record["policies"]["off"] = off_state
    checks.check("off-plays-none", off_state["playingCount"] == 0 and off_state["videoCount"] == 0, json.dumps(off_state))

    set_settings(url, {"playProxies": "always", "zoomLevel": "years"})
    wait_play_proxies(page, "always")
    wait_level(page, "years")
    always_cell = page.locator('.cell[data-kind="video"]').nth(0)
    always_cell.hover()
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('.cell video')).some(function (v) {
          return !v.paused && !v.ended;
        })""",
        timeout=8000,
    )
    always_state = playing_cell_videos(page)
    record["policies"]["always"] = always_state
    checks.check("always-plays-at-years", always_state["playingCount"] == 1, json.dumps(always_state))
    page.mouse.move(2, 2)
    page.wait_for_function("() => document.querySelectorAll('.cell video').length === 0", timeout=5000)

    fallback_name = None
    for name in ("clip.avi", "clip.mkv"):
        loc = page.locator('.cell[data-filename="' + name + '"]')
        if loc.count() > 0:
            fallback_name = name
            loc.first.click()
            break
    if fallback_name is None:
        checks.check("viewer-fallback-cell", False, "no clip.avi or clip.mkv cell")
    else:
        page.wait_for_function(
            """() => {
              const viewer = document.getElementById('viewer');
              const video = document.getElementById('viewer-video');
              return viewer && !viewer.hidden && video && !video.hidden;
            }""",
            timeout=8000,
        )
        poster = page.locator("#viewer-video").get_attribute("poster") or ""
        checks.check("viewer-poster-first", "which=poster" in poster, poster)
        src_before = page.locator("#viewer-video").get_attribute("src") or ""
        checks.check("viewer-no-autoplay-src", src_before == "", src_before)
        page.keyboard.press("Space")
        page.wait_for_function(
            """() => {
              const video = document.getElementById('viewer-video');
              if (!video) return false;
              const src = video.currentSrc || video.getAttribute('src') || '';
              return src.indexOf('which=proxy') !== -1 && video.paused === false;
            }""",
            timeout=12000,
        )
        fallback = page.evaluate(
            """() => {
              const video = document.getElementById('viewer-video');
              const src = video ? (video.currentSrc || video.getAttribute('src') || '') : '';
              return {
                src: src,
                usingProxy: video && video.getAttribute('data-using-proxy') === '1',
                paused: video ? video.paused : true
              };
            }"""
        )
        record["viewerFallbackProxy"] = bool(fallback.get("usingProxy") or "which=proxy" in (fallback.get("src") or ""))
        checks.check(
            "viewer-fallback-proxy",
            record["viewerFallbackProxy"] and fallback.get("paused") is False,
            json.dumps(fallback),
        )
        page.keyboard.press("Escape")
        page.wait_for_function(
            "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
            timeout=5000,
        )
    shot = artifacts / "hover-playback.png"
    page.screenshot(path=str(shot), full_page=False)
    record["screenshot"] = str(shot)
    return record


def prove_queued_scan(checks: Checks, root: Path, media: Path, commands: list[str]) -> dict[str, Any]:
    first = run_library(root, ["scan", str(media), "--serve-from-there"], timeout=300)
    commands.append("python -m library scan <media> --serve-from-there")
    summary = parse_summary(first.stdout) if first.stdout.strip() else {}
    errors = summary.get("errors") or []
    checks.check(
        "scan-exit",
        first.returncode == 1 if errors else first.returncode == 0,
        f"exit={first.returncode} stderr={first.stderr!r}",
    )
    items = load_items(root)
    by_name = {item.get("filename"): item for item in items}
    for rel in MATRIX_RELS:
        name = Path(rel).name
        item = by_name.get(name)
        checks.check(f"indexed:{name}", item is not None)
        if item is None:
            continue
        suffix = file_suffix(Path(rel))
        if name == "broken.heic":
            checks.check("broken-error", broken_error(item), json.dumps(item.get("renditions")))
            checks.check(
                "broken-no-webp",
                not slot_file(root, item["id"], "thumb").exists()
                and not slot_file(root, item["id"], "preview").exists(),
            )
            continue
        if suffix in PHOTO_SUFFIXES:
            checks.check(f"photo-queued:{name}", photo_queued(item), json.dumps(item.get("renditions")))
        elif suffix in VIDEO_SUFFIXES:
            checks.check(f"video-queued:{name}", video_queued(item), json.dumps(item.get("renditions")))
    checks.check("scan-no-rendition-files", rendition_files(root) == [], str(rendition_files(root)))
    error_paths = [err.get("path") for err in errors]
    checks.check("broken-decode-error", "formats/broken.heic" in error_paths, str(errors))
    return summary


def prove_ffprobe(checks: Checks, root: Path, artifacts: Path) -> dict[str, Any]:
    items = load_items(root)
    oriented = find_item(items, "oriented.jpg")
    clip = find_item(items, "clip.mp4")
    payload: dict[str, Any] = {}
    if oriented is None or clip is None:
        checks.check("ffprobe-items", False, "missing oriented.jpg or clip.mp4")
        return payload
    thumb = slot_file(root, oriented["id"], "thumb")
    preview = slot_file(root, oriented["id"], "preview")
    poster = slot_file(root, clip["id"], "poster")
    proxy = slot_file(root, clip["id"], "proxy")
    payload = {
        "thumb": ffprobe_media(thumb),
        "preview": ffprobe_media(preview),
        "poster": ffprobe_media(poster),
        "proxy": ffprobe_media(proxy),
    }
    tw, th = payload["thumb"]["width"], payload["thumb"]["height"]
    pw, ph = payload["preview"]["width"], payload["preview"]["height"]
    checks.check("thumb-size", tw == 240 and th == 320, json.dumps(payload["thumb"]))
    checks.check("preview-size", pw == 480 and ph == 640, json.dumps(payload["preview"]))
    proxy_w = payload["proxy"]["width"]
    checks.check(
        "proxy-width",
        type(proxy_w) is int and proxy_w <= 480,
        json.dumps(payload["proxy"]),
    )
    checks.check("proxy-codec", payload["proxy"]["codec"] == "h264", json.dumps(payload["proxy"]))
    checks.check("proxy-audio-0", payload["proxy"]["audioStreamCount"] == 0, json.dumps(payload["proxy"]))
    duration = payload["proxy"]["duration"]
    checks.check(
        "proxy-duration",
        type(duration) is float and abs(duration - 2.0) <= FRAME,
        json.dumps(payload["proxy"]),
    )
    meta = (oriented.get("metadata") or {})
    checks.check(
        "oriented-raw-size",
        meta.get("width") == 640 and meta.get("height") == 480,
        json.dumps(meta),
    )
    (artifacts / "ffprobe.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def prove_matrix(checks: Checks, root: Path, media: Path, artifacts: Path) -> list[dict[str, Any]]:
    wait_matrix_settled(root, MATRIX_RELS)
    rows = build_format_matrix(root, media, MATRIX_RELS)
    (artifacts / "format-matrix.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    by_path = {row["path"]: row for row in rows}
    for rel in MATRIX_RELS:
        row = by_path.get(rel)
        checks.check(f"matrix-row:{rel}", row is not None)
        if row is None:
            continue
        name = Path(rel).name
        if name == "broken.heic":
            checks.check(
                "matrix-broken-error",
                row["slots"].get("thumb", {}).get("status") == "error"
                and row["slots"].get("preview", {}).get("status") == "error"
                and row["slots"].get("thumb", {}).get("readyNonEmpty") is False,
                json.dumps(row),
            )
            continue
        if name in {"quad.heic", "quad.heif"}:
            checks.check(
                f"matrix-heic-not-ready:{name}",
                row["slots"].get("thumb", {}).get("status") == "error"
                and row["slots"].get("thumb", {}).get("readyNonEmpty") is False,
                json.dumps(row),
            )
            continue
        suffix = file_suffix(Path(rel))
        if suffix in PHOTO_SUFFIXES:
            checks.check(
                f"matrix-photo-ready:{name}",
                row["slots"]["thumb"]["status"] == "ready"
                and row["slots"]["preview"]["status"] == "ready"
                and row["slots"]["thumb"]["readyNonEmpty"] is True
                and row["slots"]["preview"]["readyNonEmpty"] is True,
                json.dumps(row),
            )
        elif suffix in VIDEO_SUFFIXES:
            checks.check(
                f"matrix-video-ready:{name}",
                row["slots"]["poster"]["status"] == "ready"
                and row["slots"]["proxy"]["status"] == "ready"
                and row["slots"]["poster"]["readyNonEmpty"] is True
                and row["slots"]["proxy"]["readyNonEmpty"] is True,
                json.dumps(row),
            )
    return rows


def prove_browser(checks: Checks, url: str, artifacts: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        checks.check("playwright-import", False, str(exc))
        (artifacts / "hover-playback.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record
    checks.check("playwright-import", True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            record = prove_hover(page, url, checks, artifacts)
            shot = artifacts / "hover-playback.png"
            if shot.is_file():
                width, height = png_size(shot)
                checks.check("hover-shot-1280x720", width == 1280 and height == 720, f"{width}x{height}")
            browser.close()
    except Exception as exc:
        checks.check("hover-browser", False, str(exc))
    (artifacts / "hover-playback.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def prove_originals(checks: Checks, media: Path, before: dict[str, str]) -> None:
    after = hash_tree(media)
    checks.check("original-hashes-unchanged", before == after, json.dumps({"before": len(before), "after": len(after)}))
    assert_no_pillow_in_server(checks)


def run_rendition_gate(root: Path, artifacts: Path, ident: str, kind: str) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    extra = {
        "ffprobe.json": str(artifacts / "ffprobe.json"),
        "format-matrix.json": str(artifacts / "format-matrix.json"),
        "hover-playback.json": str(artifacts / "hover-playback.json"),
    }
    try:
        src = prepare_media(artifacts)
        media = artifacts / "s06-media"
        copy_rels(src, media, MATRIX_RELS)
        before = hash_tree(media)
        isolated = fresh_root(root)
        prove_queued_scan(checks, isolated, media, commands)
        server, url, pids = start_owned(isolated)
        owned.append(server)
        owned_pids.extend(pids)
        ready = wait_core_ready(isolated)
        checks.check("core-ready", ready.get("ready") is True, json.dumps(ready))
        if ready.get("ready") is not True:
            return write_result(ident, kind, checks, artifacts, commands, extra)
        prove_ffprobe(checks, isolated, artifacts)
        prove_matrix(checks, isolated, media, artifacts)
        prove_browser(checks, url, artifacts)
        prove_originals(checks, media, before)
    finally:
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)
        if not (artifacts / "ffprobe.json").exists():
            (artifacts / "ffprobe.json").write_text("{}\n", encoding="utf-8")
        if not (artifacts / "format-matrix.json").exists():
            (artifacts / "format-matrix.json").write_text("[]\n", encoding="utf-8")
        if not (artifacts / "hover-playback.json").exists():
            (artifacts / "hover-playback.json").write_text("{}\n", encoding="utf-8")
    return write_result(ident, kind, checks, artifacts, commands, extra)


def run_slice(root: Path, artifacts: Path) -> int:
    return run_rendition_gate(root, artifacts, "S06", "slice")


def run_check_f7(root: Path, artifacts: Path) -> int:
    return run_rendition_gate(root, artifacts, "F7", "check")


def run_check_f5(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    resume: dict[str, Any] = {}
    extra = {"scan-resume.json": str(artifacts / "scan-resume.json")}
    try:
        src = prepare_media(artifacts)
        media = artifacts / "f5-media"
        if media.exists():
            shutil.rmtree(media)
        shutil.copytree(src, media)
        pin_media_from_manifest(media)
        dup = media / Path(*DUPLICATE_REL.split("/"))
        dup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media / "a" / "IMG_1042.jpg", dup)
        pin_media_from_manifest(media)
        (media / "notes.txt").write_text("not media\n", encoding="utf-8")
        before = hash_tree(media)

        isolated = fresh_root(root)
        first = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=300)
        commands.append("python -m library scan <media> --serve-from-there")
        summary1 = parse_summary(first.stdout) if first.stdout.strip() else {}
        errors = summary1.get("errors") or []
        checks.check(
            "scan-first-exit",
            first.returncode == 1 if errors else first.returncode == 0,
            f"exit={first.returncode} stderr={first.stderr!r}",
        )
        checks.check("scan-first-added", isinstance(summary1.get("added"), int) and summary1.get("added", 0) > 0)
        resume["first"] = summary1

        after = hash_tree(media)
        checks.check("originals-byte-identical", before == after)
        sources = load_sources(isolated)
        source = sources[0] if sources else {}
        items = load_items(isolated)
        by_name = {item.get("filename"): item for item in items}

        for rel in FORMAT_FILES:
            name = Path(rel).name
            item = by_name.get(name)
            checks.check(f"format-indexed:{name}", item is not None)
            if item is not None:
                path = primary_byte_path(media, source, item)
                expected = sha256_file(path) if path is not None else None
                checks.check(
                    f"format-id-hash:{name}",
                    id_matches_primary_file_bytes(media, source, item),
                    f"id={item.get('id')!r} expected={expected!r}",
                )
        checks.check("unicode-indexed", "旅行 photo.jpg" in by_name)
        checks.check("long-path-indexed", LONG_NAME in by_name)
        if "旅行 photo.jpg" in by_name:
            pending_would = isolated / "catalog" / "items"
            checks.check(
                "unicode-hash-id",
                not str(by_name["旅行 photo.jpg"]["id"]).startswith("pending-"),
            )
        img_hash = sha256_file(media / "a" / "IMG_1042.jpg")
        dup_items = [item for item in items if item.get("id") == img_hash]
        checks.check("duplicate-one-item", len(dup_items) == 1)
        if dup_items:
            locs = dup_items[0].get("locations") or []
            checks.check("duplicate-two-locations", len(locs) == 2, str(len(locs)))
        resume["duplicate"] = {"locations": len((dup_items[0].get("locations") or []) if dup_items else [])}

        second = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=300)
        commands.append("python -m library scan <media> --serve-from-there #2")
        summary2 = parse_summary(second.stdout) if second.stdout.strip() else {}
        resume["second"] = {"summary": summary2, "stdout": second.stdout}
        checks.check("scan-second-added-0", summary2.get("added") == 0, str(summary2.get("added")))
        checks.check(
            "scan-second-skipped",
            isinstance(summary2.get("skipped"), int) and summary2.get("skipped", 0) > 0,
            str(summary2.get("skipped")),
        )
        checks.check("scan-second-stdout-skipped", "skipped" in second.stdout)
        checks.check("rescan-same-item-count", len(load_items(isolated)) == len(items))

        skip_root = artifacts / "f5-skip-root"
        skip_media = artifacts / "f5-skip-media"
        if skip_root.exists():
            shutil.rmtree(skip_root)
        if skip_media.exists():
            shutil.rmtree(skip_media)
        prepare_root(skip_root)
        write_isolated_port(skip_root, find_free_port())
        skip_media.mkdir()
        shutil.copy2(src / "a" / "IMG_1042.jpg", skip_media / "keep.jpg")
        (skip_media / "notes.txt").write_text("nope", encoding="utf-8")
        hidden = skip_media / ".library" / "hidden.jpg"
        hidden.parent.mkdir()
        shutil.copy2(src / "a" / "near.jpg", hidden)
        skip_scan = run_library(skip_root, ["scan", str(skip_media), "--serve-from-there"], timeout=120)
        skip_summary = parse_summary(skip_scan.stdout) if skip_scan.stdout.strip() else {}
        skip_names = {item.get("filename") for item in load_items(skip_root)}
        checks.check("skip-keep-indexed", "keep.jpg" in skip_names, str(skip_names))
        checks.check("skip-hidden-library", "hidden.jpg" not in skip_names)
        checks.check("skip-notes", "notes.txt" not in skip_names)
        checks.check("skip-added-one", skip_summary.get("added") == 1, str(skip_summary))
        self_scan = run_library(skip_root, ["scan", str(skip_root), "--serve-from-there"])
        checks.check("scan-library-data-rejected-exit", self_scan.returncode == 2, self_scan.stderr)
        resume["skip"] = {"summary": skip_summary, "names": sorted(skip_names)}

        iroot = artifacts / "f5-interrupt-root"
        imedia = artifacts / "f5-interrupt-media"
        if iroot.exists():
            shutil.rmtree(iroot)
        if imedia.exists():
            shutil.rmtree(imedia)
        prepare_root(iroot)
        write_isolated_port(iroot, find_free_port())
        imedia.mkdir()
        shutil.copy2(src / "b" / "no-exif.jpg", imedia / "one.jpg")
        env = _env()
        env["LIBRARY_TEST"] = "1"
        env["LIBRARY_TEST_BARRIER"] = "hash-publication"
        crashed = run_library(iroot, ["scan", str(imedia), "--serve-from-there"], env=env, timeout=60)
        pending_files = list((iroot / "catalog" / "items").glob("pending-*.json")) if (iroot / "catalog" / "items").exists() else []
        hash_files = [
            path
            for path in ((iroot / "catalog" / "items").glob("*.json") if (iroot / "catalog" / "items").exists() else [])
            if not path.name.startswith("pending-")
        ]
        checks.check("barrier-hash-exit-86", crashed.returncode == 86, crashed.stderr)
        checks.check("barrier-pending-present", len(pending_files) == 1, str(len(pending_files)))
        checks.check("barrier-hash-not-published", len(hash_files) == 0, str(len(hash_files)))
        checks.check(
            "pending-name-flat",
            pending_files and "/" not in pending_files[0].name and "\\" not in pending_files[0].name,
            pending_files[0].name if pending_files else "",
        )
        if pending_files:
            seed_entities(iroot, pending_files[0])
        recovered = run_library(iroot, ["settings", "get"])
        checks.check("barrier-recover-exit", recovered.returncode == 0, recovered.stderr)
        after_pending = list((iroot / "catalog" / "items").glob("pending-*.json")) if (iroot / "catalog" / "items").exists() else []
        after_items = load_items(iroot)
        checks.check("barrier-pending-cleared", after_pending == [])
        checks.check("barrier-one-item", len(after_items) == 1, str([item.get("id") for item in after_items]))
        if after_items:
            checks.check("seeded-annotations-moved", item_has_ada_mug(after_items[0]), json.dumps(after_items[0].get("faces")))
            checks.check("barrier-item-is-hash", after_items[0]["id"] == sha256_file(imedia / "one.jpg"))
        resume["barrier"] = {
            "itemIds": [item.get("id") for item in after_items],
            "annotationsMoved": bool(after_items and item_has_ada_mug(after_items[0])),
        }

        mroot = artifacts / "f5-modified-root"
        mmedia = artifacts / "f5-modified-media"
        if mroot.exists():
            shutil.rmtree(mroot)
        if mmedia.exists():
            shutil.rmtree(mmedia)
        prepare_root(mroot)
        write_isolated_port(mroot, find_free_port())
        mmedia.mkdir()
        first_file = mmedia / "photo.jpg"
        shutil.copy2(src / "a" / "IMG_1042.jpg", first_file)
        pin_mtime(first_file, "2022-01-01T00:00:00Z")
        old_hash = sha256_file(first_file)
        run_library(mroot, ["scan", str(mmedia), "--serve-from-there"], timeout=120)
        shutil.copy2(src / "b" / "far.jpg", first_file)
        later = (datetime(2022, 1, 1, tzinfo=timezone.utc) + timedelta(days=30)).isoformat().replace("+00:00", "Z")
        pin_mtime(first_file, later)
        new_hash = sha256_file(first_file)
        checks.check("modified-bytes-differ", old_hash != new_hash)
        run_library(mroot, ["scan", str(mmedia), "--serve-from-there"], timeout=120)
        modified_items = {item["id"]: item for item in load_items(mroot)}
        checks.check("modified-two-items", old_hash in modified_items and new_hash in modified_items)
        old_item = modified_items.get(old_hash) or {}
        new_item = modified_items.get(new_hash) or {}
        old_current = [loc.get("current") for loc in (old_item.get("locations") or [])]
        new_current = [loc.get("current") for loc in (new_item.get("locations") or [])]
        checks.check("modified-old-current-false", old_current == [False], str(old_current))
        checks.check("modified-new-current-true", True in new_current, str(new_current))
        resume["modified"] = {"oldHash": old_hash, "newHash": new_hash, "oldCurrent": old_current}

        hroot = artifacts / "f5-heic-root"
        hmedia = artifacts / "f5-heic-media"
        if hroot.exists():
            shutil.rmtree(hroot)
        if hmedia.exists():
            shutil.rmtree(hmedia)
        prepare_root(hroot)
        write_isolated_port(hroot, find_free_port())
        copy_rels(src, hmedia, ["formats/broken.heic", "b/oriented.jpg"])
        heic = run_library(hroot, ["scan", str(hmedia), "--serve-from-there"], timeout=120)
        heic_summary = parse_summary(heic.stdout) if heic.stdout.strip() else {}
        checks.check("heic-cli-exit-1", heic.returncode == 1, heic.stderr)
        heic_items = load_items(hroot)
        jpeg = find_item(heic_items, "oriented.jpg")
        broken = find_item(heic_items, "broken.heic")
        checks.check("heic-jpeg-present", jpeg is not None)
        checks.check("heic-broken-present", broken is not None)
        if jpeg is not None:
            checks.check("heic-jpeg-queued-or-ready", photo_queued(jpeg) or (jpeg.get("renditions") or {}).get("status", {}).get("thumb") in {"queued", "ready"})
        if broken is not None:
            checks.check("heic-broken-error", broken_error(broken), json.dumps(broken.get("renditions")))
            checks.check(
                "heic-broken-no-webp",
                not slot_file(hroot, broken["id"], "thumb").exists()
                and not slot_file(hroot, broken["id"], "preview").exists(),
            )
        error_paths = [err.get("path") for err in (heic_summary.get("errors") or [])]
        checks.check("heic-decode-error", "formats/broken.heic" in error_paths or "broken.heic" in error_paths, str(heic_summary))
        resume["heic"] = heic_summary
        prove_originals(checks, media, before)
    finally:
        (artifacts / "scan-resume.json").write_text(json.dumps(resume, indent=2) + "\n", encoding="utf-8")
    return write_result("F5", "check", checks, artifacts, commands, extra)
