"""Slice S03 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    copy_committed_fixtures,
    find_free_port,
    run_library,
    start_server,
    stop_owned,
    wait_health,
    write_isolated_port,
)
from tests.qa.s01 import load_items, load_sources, parse_summary, scan_history_count
from tests.qa.s02 import item_for_rel, items_by_id


def history_len(root: Path) -> int:
    path = root / "undo" / "state.json"
    if not path.exists():
        return 0
    state = json.loads(path.read_text(encoding="utf-8"))
    entries = state.get("entries")
    return len(entries) if isinstance(entries, list) else 0


def webp_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.webp") if path.is_file())


def ffprobe_wh(path: Path) -> tuple[int | None, int | None]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None, None
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None, None
    streams = payload.get("streams") or []
    if not streams:
        return None, None
    width = streams[0].get("width")
    height = streams[0].get("height")
    if type(width) is not int or type(height) is not int:
        return None, None
    return width, height


def request_media(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            return _media_record(resp.status, resp.headers, body)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return _media_record(exc.code, exc.headers, body)


def _media_record(status: int, headers: Any, body: bytes) -> dict[str, Any]:
    error = None
    if body:
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict) and "error" in parsed:
                error = parsed.get("error")
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
    else:
        parsed = None
    return {
        "status": status,
        "contentType": headers.get("Content-Type") if headers is not None else None,
        "contentLength": headers.get("Content-Length") if headers is not None else None,
        "contentRange": headers.get("Content-Range") if headers is not None else None,
        "bodyLen": len(body),
        "bodySha256": hashlib.sha256(body).hexdigest(),
        "firstByte": body[0] if body else None,
        "error": error,
        "json": parsed if isinstance(parsed, dict) else None,
        "body": body,
    }


def public_media(rec: dict[str, Any]) -> dict[str, Any]:
    return {key: rec[key] for key in rec if key != "body"}


def original_hashes(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not folder.exists():
        return out
    for path in folder.rglob("*"):
        if path.is_file() and not path.is_symlink():
            out[path.relative_to(folder).as_posix()] = sha256_file(path)
    return out


def library_no_forbidden(checks: Checks) -> None:
    hits_pillow: list[str] = []
    hits_heif: list[str] = []
    hits_pw: list[str] = []
    hits_flag: list[str] = []
    for path in (PRODUCT_ROOT / "library").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        if "PIL" in text or "pillow" in lower:
            hits_pillow.append(str(path))
        if "pillow-heif" in lower or "pillow_heif" in lower:
            hits_heif.append(str(path))
        if "playwright" in lower:
            hits_pw.append(str(path))
        if "-noautorotate" in lower:
            hits_flag.append(str(path))
    checks.check("library-no-pillow", hits_pillow == [], ", ".join(hits_pillow))
    checks.check("library-no-pillow-heif", hits_heif == [], ", ".join(hits_heif))
    checks.check("library-no-playwright", hits_pw == [], ", ".join(hits_pw))
    checks.check("library-no-noautorotate", hits_flag == [], ", ".join(hits_flag))


def ensure_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.sync_api import sync_playwright

        return sync_playwright


def write_result(
    ident: str,
    kind: str,
    checks: Checks,
    artifacts: Path,
    commands: list[str],
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
        "artifactPaths": {
            "result.json": str(artifacts / "result.json"),
            "stdout.log": str(artifacts / "stdout.log"),
            "sizes.json": str(artifacts / "sizes.json"),
            "media-responses.json": str(artifacts / "media-responses.json"),
            "first-still.png": str(artifacts / "first-still.png"),
        },
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    owned: list[Any] = []
    server = None
    library_no_forbidden(checks)

    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    before_originals = original_hashes(media)

    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    port = find_free_port()
    write_isolated_port(isolated, port)

    first = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=300)
    commands.append("python -m library scan <media> --serve-from-there")
    summary = parse_summary(first.stdout) if first.stdout.strip() else {}
    checks.check(
        "scan-exit",
        first.returncode == 1 if summary.get("errors") else first.returncode == 0,
        f"exit={first.returncode} stderr={first.stderr!r}",
    )
    sources = load_sources(isolated)
    items = load_items(isolated)
    checks.check("one-source", len(sources) == 1, str(len(sources)))
    source = sources[0] if sources else {}
    by_id = items_by_id(items)
    oriented = item_for_rel(source, by_id, "b/oriented.jpg")
    broken = item_for_rel(source, by_id, "formats/broken.heic")
    png_item = item_for_rel(source, by_id, "formats/quad.png")
    clip = item_for_rel(source, by_id, "a/clip.mp4")
    img1042 = item_for_rel(source, by_id, "a/IMG_1042.jpg")
    checks.check("oriented-present", oriented is not None)
    checks.check("broken-present", broken is not None)
    if oriented:
        rend = oriented.get("renditions") or {}
        status = rend.get("status") or {}
        checks.check("oriented-thumb-queued", status.get("thumb") == "queued", str(status))
        checks.check("oriented-preview-queued", status.get("preview") == "queued", str(status))
        checks.check("oriented-thumb-path-null", rend.get("thumb") is None)
        checks.check("oriented-preview-path-null", rend.get("preview") is None)
        md = oriented.get("metadata") or {}
        checks.check("oriented-raw-width", md.get("width") == 640, str(md.get("width")))
        checks.check("oriented-raw-height", md.get("height") == 480, str(md.get("height")))
        checks.check("oriented-orientation", md.get("orientation") == 6, str(md.get("orientation")))
    if broken:
        rend = broken.get("renditions") or {}
        status = rend.get("status") or {}
        checks.check("broken-thumb-error", status.get("thumb") == "error", str(status))
        checks.check("broken-preview-error", status.get("preview") == "error", str(status))
        checks.check("broken-thumb-path-null", rend.get("thumb") is None)
        checks.check("broken-preview-path-null", rend.get("preview") is None)
    scan_webps = webp_files(isolated)
    checks.check("scan-no-webp", scan_webps == [], str(scan_webps))
    history_after_scan = history_len(isolated)
    scan_ops = scan_history_count(isolated)
    checks.check("scan-history-present", scan_ops >= 1, str(scan_ops))

    url = f"http://127.0.0.1:{port}/"
    try:
        server = start_server(isolated)
        owned.append(server)
        wait_health(url, server, timeout=20)
        commands.append("python -m library serve")

        oriented_id = oriented["id"] if oriented else ""
        deadline = time.time() + 90
        ready_item = None
        while time.time() < deadline:
            status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
            if status == 200 and isinstance(listed, list):
                ready_item = next((item for item in listed if item.get("id") == oriented_id), None)
                rend = (ready_item or {}).get("renditions") or {}
                st = rend.get("status") or {}
                if st.get("thumb") == "ready" and st.get("preview") == "ready":
                    break
            time.sleep(0.25)
            ready_item = None
        checks.check("oriented-ready-timeout-not-hit", ready_item is not None, "timeout")
        if ready_item:
            rend = ready_item.get("renditions") or {}
            st = rend.get("status") or {}
            checks.check("oriented-thumb-ready", st.get("thumb") == "ready", str(st))
            checks.check("oriented-preview-ready", st.get("preview") == "ready", str(st))
            checks.check(
                "oriented-thumb-rel",
                rend.get("thumb") == f"renditions/{oriented_id}/thumb.webp",
                str(rend.get("thumb")),
            )
            checks.check(
                "oriented-preview-rel",
                rend.get("preview") == f"renditions/{oriented_id}/preview.webp",
                str(rend.get("preview")),
            )
            md = ready_item.get("metadata") or {}
            checks.check("oriented-meta-width-unchanged", md.get("width") == 640, str(md.get("width")))
            checks.check("oriented-meta-height-unchanged", md.get("height") == 480, str(md.get("height")))
            checks.check("oriented-meta-orientation-unchanged", md.get("orientation") == 6)

        thumb_path = isolated / "renditions" / oriented_id / "thumb.webp"
        preview_path = isolated / "renditions" / oriented_id / "preview.webp"
        checks.check("thumb-file", thumb_path.is_file() and thumb_path.stat().st_size > 0)
        checks.check("preview-file", preview_path.is_file() and preview_path.stat().st_size > 0)
        tw, th = ffprobe_wh(thumb_path) if thumb_path.is_file() else (None, None)
        pw, ph = ffprobe_wh(preview_path) if preview_path.is_file() else (None, None)
        checks.check("thumb-size", tw == 240 and th == 320, f"{tw}x{th}")
        checks.check("preview-size", pw == 480 and ph == 640, f"{pw}x{ph}")
        if tw and th:
            checks.check("thumb-longest-cap", max(tw, th) <= 320, str(max(tw, th)))
        if pw and ph:
            checks.check("preview-longest-cap", max(pw, ph) <= 1600, str(max(pw, ph)))
        sizes = {
            "thumb": {
                "width": tw,
                "height": th,
                "bytes": thumb_path.stat().st_size if thumb_path.is_file() else 0,
            },
            "preview": {
                "width": pw,
                "height": ph,
                "bytes": preview_path.stat().st_size if preview_path.is_file() else 0,
            },
        }
        (artifacts / "sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", encoding="utf-8")

        checks.check(
            "history-unchanged-by-renditions",
            history_len(isolated) == history_after_scan,
            f"{history_len(isolated)} vs {history_after_scan}",
        )

        listed_status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
        listed_by_id = {item.get("id"): item for item in listed} if listed_status == 200 and isinstance(listed, list) else {}
        if png_item:
            after_png = listed_by_id.get(png_item["id"]) or png_item
            st = ((after_png.get("renditions") or {}).get("status") or {})
            rend = after_png.get("renditions") or {}
            checks.check("png-thumb-still-queued", st.get("thumb") == "queued", str(st))
            checks.check("png-paths-null", rend.get("thumb") is None and rend.get("preview") is None)
        if clip:
            after_clip = listed_by_id.get(clip["id"]) or clip
            st = ((after_clip.get("renditions") or {}).get("status") or {})
            rend = after_clip.get("renditions") or {}
            checks.check("video-poster-still-queued", st.get("poster") == "queued", str(st))
            checks.check("video-paths-null", rend.get("poster") is None and rend.get("proxy") is None)
        if broken:
            after_broken = listed_by_id.get(broken["id"]) or broken
            st = ((after_broken.get("renditions") or {}).get("status") or {})
            rend = after_broken.get("renditions") or {}
            checks.check("broken-still-error", st.get("thumb") == "error" and st.get("preview") == "error", str(st))
            checks.check("broken-still-null", rend.get("thumb") is None and rend.get("preview") is None)
            checks.check(
                "broken-no-webp",
                not (isolated / "renditions" / broken["id"] / "thumb.webp").exists()
                and not (isolated / "renditions" / broken["id"] / "preview.webp").exists(),
            )

        base = url.rstrip("/") + "/api/media/" + oriented_id
        thumb_rec = request_media(base + "?which=thumb")
        preview_rec = request_media(base + "?which=preview")
        original_rec = request_media(base + "?which=original")
        range_rec = request_media(base + "?which=thumb", headers={"Range": "bytes=0-0"})
        bad_rec = request_media(base + "?which=thumb", headers={"Range": "bytes=5-1"})
        multi_rec = request_media(base + "?which=thumb", headers={"Range": "bytes=0-0,1-1"})
        unit_rec = request_media(base + "?which=thumb", headers={"Range": "items=0-0"})
        missing_which = request_media(base)
        unknown_which = request_media(base + "?which=nope")
        unknown_id = request_media(url.rstrip("/") + "/api/media/missing?which=original")
        motion_rec = request_media(base + "?which=original&component=motion")
        poster_rec = request_media(base + "?which=poster")

        original_path = media / "b" / "oriented.jpg"
        original_digest = sha256_file(original_path) if original_path.is_file() else ""
        checks.check("thumb-200", thumb_rec["status"] == 200, str(thumb_rec["status"]))
        checks.check("thumb-type", thumb_rec["contentType"] == "image/webp", str(thumb_rec["contentType"]))
        if thumb_path.is_file():
            checks.check(
                "thumb-length",
                thumb_rec["contentLength"] == str(thumb_path.stat().st_size)
                and thumb_rec["bodyLen"] == thumb_path.stat().st_size,
                str(thumb_rec["contentLength"]),
            )
        checks.check("preview-200", preview_rec["status"] == 200, str(preview_rec["status"]))
        checks.check("preview-type", preview_rec["contentType"] == "image/webp", str(preview_rec["contentType"]))
        if preview_path.is_file():
            checks.check(
                "preview-length",
                preview_rec["contentLength"] == str(preview_path.stat().st_size)
                and preview_rec["bodyLen"] == preview_path.stat().st_size,
            )
        checks.check("original-200", original_rec["status"] == 200, str(original_rec["status"]))
        checks.check("original-type", original_rec["contentType"] == "image/jpeg", str(original_rec["contentType"]))
        checks.check(
            "original-sha256",
            original_rec["bodySha256"] == original_digest,
            original_rec["bodySha256"],
        )
        checks.check("range-206", range_rec["status"] == 206, str(range_rec["status"]))
        if thumb_path.is_file():
            length = thumb_path.stat().st_size
            first = thumb_path.read_bytes()[:1]
            checks.check(
                "range-content-range",
                range_rec["contentRange"] == f"bytes 0-0/{length}",
                str(range_rec["contentRange"]),
            )
            checks.check("range-content-length", range_rec["contentLength"] == "1", str(range_rec["contentLength"]))
            checks.check("range-body", range_rec["body"] == first, str(range_rec["firstByte"]))
        checks.check(
            "bad-range",
            bad_rec["status"] == 416 and bad_rec.get("json") == {"error": "invalid-range"},
            str(bad_rec.get("json")),
        )
        checks.check(
            "multi-range",
            multi_rec["status"] == 416 and multi_rec.get("json") == {"error": "invalid-range"},
        )
        checks.check(
            "non-bytes-range",
            unit_rec["status"] == 416 and unit_rec.get("json") == {"error": "invalid-range"},
        )
        checks.check(
            "missing-which",
            missing_which["status"] == 400 and missing_which.get("json") == {"error": "invalid-argument"},
        )
        checks.check(
            "unknown-which",
            unknown_which["status"] == 400 and unknown_which.get("json") == {"error": "invalid-argument"},
        )
        checks.check(
            "unknown-id",
            unknown_id["status"] == 404 and unknown_id.get("json") == {"error": "not-found"},
            str(unknown_id.get("json")),
        )
        log_text = (isolated / "logs" / "server.log").read_text(encoding="utf-8") if (isolated / "logs" / "server.log").exists() else ""
        log_ok = False
        for line in log_text.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and "/api/media/missing?which=original" in parts[1] and parts[2] == "not-found" and "T" in parts[0]:
                log_ok = True
        checks.check("unknown-id-logged", log_ok, log_text[-400:])
        checks.check(
            "motion-on-photo",
            motion_rec["status"] == 400 and motion_rec.get("json") == {"error": "invalid-argument"},
        )
        checks.check(
            "poster-unavailable",
            poster_rec["status"] == 404 and poster_rec.get("json") == {"error": "preview-unavailable"},
        )
        if broken:
            broken_thumb = request_media(url.rstrip("/") + "/api/media/" + broken["id"] + "?which=thumb")
            checks.check(
                "broken-thumb-unavailable",
                broken_thumb["status"] == 404 and broken_thumb.get("json") == {"error": "preview-unavailable"},
            )

        png_path = artifacts / "first-still.png"
        try:
            sync_playwright = ensure_playwright()
            with sync_playwright() as p:
                browser = None
                last_launch = None
                for kwargs in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
                    try:
                        browser = p.chromium.launch(**kwargs)
                        break
                    except Exception as exc:
                        last_launch = exc
                if browser is None:
                    raise RuntimeError(f"chromium launch failed: {last_launch}")
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_selector(f'[data-filename="oriented.jpg"]', timeout=30000)
                empty_visible = page.locator("#empty").is_visible()
                checks.check("empty-hidden-when-items", empty_visible is False)
                page.locator('[data-filename="oriented.jpg"]').click()
                page.wait_for_function(
                    """(id) => {
                        const img = document.querySelector('#viewer-image');
                        return !!(
                            img &&
                            !img.hidden &&
                            img.complete &&
                            img.naturalWidth > 0 &&
                            (img.src || '').includes(id) &&
                            (img.src || '').includes('which=preview')
                        );
                    }""",
                    arg=oriented_id,
                    timeout=30000,
                )
                page.screenshot(path=str(png_path), full_page=False)
                page.keyboard.press("Escape")
                page.wait_for_function(
                    "() => document.getElementById('viewer') && document.getElementById('viewer').hidden === true",
                    timeout=5000,
                )
                browser.close()
            checks.check("first-still-written", png_path.is_file() and png_path.stat().st_size > 0)
            if png_path.is_file():
                from PIL import Image

                with Image.open(png_path) as image:
                    checks.check("first-still-size", image.size == (1280, 720), str(image.size))
                    checks.check("first-still-png", image.format == "PNG", str(image.format))
        except Exception as exc:
            checks.check("browser-preview", False, str(exc))

        deleted_id = oriented_id
        deleted_path = isolated / "renditions" / deleted_id / "preview.webp" if deleted_id else None
        if deleted_path is not None and deleted_path.is_file():
            deleted_path.unlink()
        if deleted_id:
            deleted = request_media(url.rstrip("/") + "/api/media/" + deleted_id + "?which=preview")
        else:
            deleted = {"status": None, "json": None, "error": "no-item"}
        checks.check(
            "deleted-preview-unavailable",
            deleted.get("status") == 404 and deleted.get("json") == {"error": "preview-unavailable"},
            str(deleted.get("json")),
        )
        if deleted_id:
            disk_item = json.loads(
                (isolated / "catalog" / "items" / f"{deleted_id}.json").read_text(encoding="utf-8")
            )
            st = ((disk_item.get("renditions") or {}).get("status") or {})
            checks.check("deleted-status-unchanged", st.get("preview") == "ready", str(st))
            checks.check("deleted-not-recreated", deleted_path is not None and not deleted_path.exists())
        media_out = {
            "thumb": public_media(thumb_rec),
            "preview": public_media(preview_rec),
            "original": public_media(original_rec),
            "range": public_media(range_rec),
            "badRange": public_media(bad_rec),
            "unknownId": public_media(unknown_id),
            "deletedPreview": public_media(deleted) if "body" in deleted else deleted,
        }
        (artifacts / "media-responses.json").write_text(
            json.dumps(media_out, indent=2) + "\n", encoding="utf-8"
        )

        after_originals = original_hashes(media)
        checks.check("originals-unchanged", before_originals == after_originals)
    finally:
        stop_owned(server)
        for proc in owned:
            if proc is not server:
                stop_owned(proc)

    return write_result("S03", "slice", checks, artifacts, commands)
