"""Slice S03 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

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
from tests.qa.s01 import load_items, load_sources, parse_summary

ORIENTED_REL = "b/oriented.jpg"
BROKEN_REL = "formats/broken.heic"
PLACEHOLDER = "Preview is not available"


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


def find_item(items: list[dict[str, Any]], filename: str) -> dict[str, Any] | None:
    matches = [item for item in items if item.get("filename") == filename]
    return matches[0] if len(matches) == 1 else None


def webp_paths(root: Path, item_id: str) -> tuple[Path, Path]:
    folder = root / "renditions" / item_id
    return folder / "thumb.webp", folder / "preview.webp"


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
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None, None
    streams = payload.get("streams") or []
    if not streams:
        return None, None
    width = streams[0].get("width")
    height = streams[0].get("height")
    return width if type(width) is int else None, height if type(height) is int else None


def request_raw(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            return int(resp.status), {k: v for k, v in resp.headers.items()}, body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return int(exc.code), {k: v for k, v in exc.headers.items()}, body


def header_get(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def record_media(status: int, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    parsed: Any = None
    if (header_get(headers, "Content-Type") or "").startswith("application/json"):
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
    length_header = header_get(headers, "Content-Length")
    try:
        length = int(length_header) if length_header is not None else None
    except ValueError:
        length = None
    return {
        "status": status,
        "contentType": header_get(headers, "Content-Type"),
        "contentLength": length,
        "contentRange": header_get(headers, "Content-Range"),
        "bodyLength": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "body": parsed,
    }


def png_size(path: Path) -> tuple[int | None, int | None]:
    if not path.is_file() or path.stat().st_size < 24:
        return None, None
    data = path.read_bytes()[: 24]
    if data[: 8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    sizes: dict[str, Any] = {}
    media_responses: dict[str, Any] = {}
    try:
        sandbox = artifacts / "fixture-sandbox"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        copy_committed_fixtures(sandbox)
        media = sandbox / "media"
        oriented_file = media / Path(ORIENTED_REL)
        original_hash = sha256_file(oriented_file) if oriented_file.is_file() else ""

        isolated = Path(root)
        if isolated.exists():
            shutil.rmtree(isolated)
        prepare_root(isolated)
        isolated_port = find_free_port()
        write_isolated_port(isolated, isolated_port)

        first = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=300)
        commands.append("python -m library scan <media> --serve-from-there")
        summary = parse_summary(first.stdout) if first.stdout.strip() else {}
        checks.check(
            "scan-exit",
            first.returncode == 1 if summary.get("errors") else first.returncode == 0,
            f"exit={first.returncode} stderr={first.stderr!r}",
        )
        error_paths = [err.get("path") for err in (summary.get("errors") or [])]
        checks.check("broken-heic-scan-error", BROKEN_REL in error_paths, str(summary.get("errors")))

        items = load_items(isolated)
        oriented = find_item(items, "oriented.jpg")
        broken = find_item(items, "broken.heic")
        checks.check("oriented-item", oriented is not None)
        checks.check("broken-item", broken is not None)
        if oriented is None:
            return write_result("S03", "slice", checks, artifacts, commands)
        oriented_id = oriented["id"]
        rend = oriented.get("renditions") or {}
        status = rend.get("status") or {}
        checks.check("oriented-store", rend.get("store") == "with-server")
        checks.check(
            "oriented-queued",
            status.get("thumb") == "queued" and status.get("preview") == "queued",
            str(status),
        )
        checks.check(
            "oriented-paths-null",
            rend.get("thumb") is None and rend.get("preview") is None,
            str(rend),
        )
        checks.check(
            "oriented-video-slots",
            status.get("poster") == "not-applicable"
            and status.get("proxy") == "not-applicable"
            and rend.get("poster") is None
            and rend.get("proxy") is None,
        )
        meta = oriented.get("metadata") or {}
        checks.check(
            "oriented-raw-size",
            meta.get("width") == 640 and meta.get("height") == 480,
            str(meta),
        )
        thumb_path, preview_path = webp_paths(isolated, oriented_id)
        checks.check("scan-no-thumb-webp", not thumb_path.exists())
        checks.check("scan-no-preview-webp", not preview_path.exists())
        checks.check("original-unchanged-after-scan", sha256_file(oriented_file) == original_hash)

        if broken is not None:
            br = broken.get("renditions") or {}
            bs = br.get("status") or {}
            checks.check(
                "broken-error",
                bs.get("thumb") == "error" and bs.get("preview") == "error",
                str(bs),
            )
            checks.check(
                "broken-paths-null",
                br.get("thumb") is None and br.get("preview") is None,
            )
            bthumb, bpreview = webp_paths(isolated, broken["id"])
            checks.check("broken-no-webp", not bthumb.exists() and not bpreview.exists())

        png_item = find_item(items, "quad.png")
        checks.check("png-item", png_item is not None)
        if png_item is None:
            checks.check("png-still-queued", False, "missing quad.png item")
            checks.check("png-no-webp", False, "missing quad.png item")
        else:
            ps = (png_item.get("renditions") or {}).get("status") or {}
            checks.check(
                "png-still-queued",
                ps.get("thumb") == "queued" and ps.get("preview") == "queued",
                str(ps),
            )
            pthumb, ppreview = webp_paths(isolated, png_item["id"])
            checks.check("png-no-webp", not pthumb.exists() and not ppreview.exists())

        server = start_server(isolated)
        owned.append(server)
        url = f"http://127.0.0.1:{isolated_port}/"
        health_status, health_body = wait_health(url, server)
        checks.check("serve-health", health_status == 200 and health_body == {"ok": True}, str(health_body))
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/runtime", timeout=2) as resp:
                runtime_body = json.loads(resp.read().decode("utf-8"))
            server_pid = runtime_body.get("pid")
            if type(server_pid) is int:
                owned_pids.append(server_pid)
            checks.check("runtime-pid", type(server_pid) is int and server_pid > 0, str(server_pid))
        except Exception as exc:
            checks.check("runtime-pid", False, str(exc))

        deadline = time.time() + 60
        ready = False
        last_status: dict[str, Any] = {}
        while time.time() < deadline:
            items = load_items(isolated)
            oriented = find_item(items, "oriented.jpg")
            if oriented is not None:
                last_status = (oriented.get("renditions") or {}).get("status") or {}
                thumb_path, preview_path = webp_paths(isolated, oriented["id"])
                if (
                    last_status.get("thumb") == "ready"
                    and last_status.get("preview") == "ready"
                    and thumb_path.is_file()
                    and thumb_path.stat().st_size > 0
                    and preview_path.is_file()
                    and preview_path.stat().st_size > 0
                ):
                    ready = True
                    break
            if server.poll() is not None:
                break
            time.sleep(0.2)
        checks.check("oriented-ready", ready, str(last_status))
        if not ready:
            return write_result("S03", "slice", checks, artifacts, commands)

        items = load_items(isolated)
        oriented = find_item(items, "oriented.jpg")
        assert oriented is not None
        oriented_id = oriented["id"]
        thumb_path, preview_path = webp_paths(isolated, oriented_id)
        rend = oriented.get("renditions") or {}
        checks.check("ready-thumb-rel", rend.get("thumb") == f"renditions/{oriented_id}/thumb.webp")
        checks.check("ready-preview-rel", rend.get("preview") == f"renditions/{oriented_id}/preview.webp")
        meta = oriented.get("metadata") or {}
        checks.check(
            "metadata-stays-raw",
            meta.get("width") == 640 and meta.get("height") == 480,
            str(meta),
        )
        checks.check("original-unchanged-after-ready", sha256_file(oriented_file) == original_hash)

        tw, th = ffprobe_wh(thumb_path)
        pw, ph = ffprobe_wh(preview_path)
        sizes = {
            "thumb": {"width": tw, "height": th, "bytes": thumb_path.stat().st_size},
            "preview": {"width": pw, "height": ph, "bytes": preview_path.stat().st_size},
        }
        (artifacts / "sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", encoding="utf-8")
        checks.check("thumb-size", tw == 240 and th == 320, str(sizes["thumb"]))
        checks.check("preview-size", pw == 480 and ph == 640, str(sizes["preview"]))
        if type(tw) is int and type(th) is int:
            checks.check("thumb-cap", max(tw, th) <= 320)
        else:
            checks.check("thumb-cap", False, "missing ffprobe")
        if type(pw) is int and type(ph) is int:
            checks.check("preview-cap", max(pw, ph) <= 1600)
        else:
            checks.check("preview-cap", False, "missing ffprobe")

        broken = find_item(items, "broken.heic")
        checks.check("broken-after-serve", broken is not None)
        if broken is None:
            checks.check("broken-stays-error", False, "missing broken.heic item")
            checks.check("broken-still-no-webp", False, "missing broken.heic item")
            checks.check("broken-decode-error-kept", False, "missing broken.heic item")
        else:
            bs = (broken.get("renditions") or {}).get("status") or {}
            bthumb, bpreview = webp_paths(isolated, broken["id"])
            checks.check(
                "broken-stays-error",
                bs.get("thumb") == "error" and bs.get("preview") == "error",
                str(bs),
            )
            checks.check("broken-still-no-webp", not bthumb.exists() and not bpreview.exists())
            source = load_sources(isolated)[0] if load_sources(isolated) else {}
            still_errors = [err.get("path") for err in ((source.get("scan") or {}).get("errors") or [])]
            checks.check("broken-decode-error-kept", BROKEN_REL in still_errors, str(still_errors))

        png_item = find_item(items, "quad.png")
        checks.check("png-after-serve", png_item is not None)
        if png_item is None:
            checks.check("png-still-queued-after-serve", False, "missing quad.png item")
            checks.check("png-still-no-webp", False, "missing quad.png item")
        else:
            ps = (png_item.get("renditions") or {}).get("status") or {}
            pthumb, ppreview = webp_paths(isolated, png_item["id"])
            checks.check(
                "png-still-queued-after-serve",
                ps.get("thumb") == "queued" and ps.get("preview") == "queued",
                str(ps),
            )
            checks.check("png-still-no-webp", not pthumb.exists() and not ppreview.exists())

        base = url.rstrip("/")
        thumb_url = f"{base}/api/media/{oriented_id}?which=thumb"
        preview_url = f"{base}/api/media/{oriented_id}?which=preview"
        original_url = f"{base}/api/media/{oriented_id}?which=original"

        t_status, t_headers, t_body = request_raw(thumb_url)
        p_status, p_headers, p_body = request_raw(preview_url)
        o_status, o_headers, o_body = request_raw(original_url)
        r_status, r_headers, r_body = request_raw(thumb_url, {"Range": "bytes=0-0"})
        b_status, b_headers, b_body = request_raw(thumb_url, {"Range": "bytes=1-0"})
        u_status, u_headers, u_body = request_raw(f"{base}/api/media/unknown-s03?which=thumb")

        media_responses["thumb"] = record_media(t_status, t_headers, t_body)
        media_responses["preview"] = record_media(p_status, p_headers, p_body)
        media_responses["original"] = record_media(o_status, o_headers, o_body)
        media_responses["range"] = record_media(r_status, r_headers, r_body)
        media_responses["badRange"] = record_media(b_status, b_headers, b_body)
        media_responses["unknownId"] = record_media(u_status, u_headers, u_body)

        checks.check("thumb-http", t_status == 200 and header_get(t_headers, "Content-Type") == "image/webp")
        checks.check("thumb-length", header_get(t_headers, "Content-Length") == str(len(t_body)) == str(thumb_path.stat().st_size))
        checks.check("thumb-sha", hashlib.sha256(t_body).hexdigest() == sha256_file(thumb_path))
        checks.check("preview-http", p_status == 200 and header_get(p_headers, "Content-Type") == "image/webp")
        checks.check("preview-length", header_get(p_headers, "Content-Length") == str(len(p_body)) == str(preview_path.stat().st_size))
        checks.check("original-http", o_status == 200 and header_get(o_headers, "Content-Type") == "image/jpeg")
        checks.check("original-sha", hashlib.sha256(o_body).hexdigest() == original_hash)
        checks.check("original-length", header_get(o_headers, "Content-Length") == str(len(o_body)))
        checks.check(
            "range-206",
            r_status == 206
            and header_get(r_headers, "Content-Range") == f"bytes 0-0/{len(t_body)}"
            and header_get(r_headers, "Content-Length") == "1"
            and len(r_body) == 1
            and r_body == t_body[:1],
            json.dumps(media_responses["range"]),
        )
        checks.check(
            "bad-range-416",
            b_status == 416 and media_responses["badRange"].get("body") == {"error": "invalid-range"},
            json.dumps(media_responses["badRange"]),
        )
        checks.check(
            "unknown-id-404",
            u_status == 404 and media_responses["unknownId"].get("body") == {"error": "not-found"},
            json.dumps(media_responses["unknownId"]),
        )

        page_html = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        checks.check("page-no-empty-state-copy-baked-pixels", "oriented.jpg" not in page_html)
        checks.check("page-has-script", "/assets/library.js" in page_html)

        browser_ok = False
        browser_detail = ""
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
        else:
            checks.check("playwright-import", True)
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page(viewport={"width": 1280, "height": 720})
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_selector('[data-filename="oriented.jpg"]', timeout=15000)
                    empty = page.locator("text=No pictures yet")
                    checks.check("page-not-empty", empty.count() == 0)
                    page.locator('[data-filename="oriented.jpg"]').click()
                    page.wait_for_function(
                        """() => {
                          const img = document.getElementById('viewer-image');
                          return !!(img && img.getAttribute('src') && img.complete && img.naturalWidth > 0);
                        }""",
                        timeout=15000,
                    )
                    src = page.locator("#viewer-image").get_attribute("src") or ""
                    checks.check("viewer-src-preview", "which=preview" in src, src)
                    shot = artifacts / "first-still.png"
                    page.screenshot(path=str(shot), full_page=False)
                    page.keyboard.press("Escape")
                    page.wait_for_function(
                        "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
                        timeout=5000,
                    )
                    checks.check("esc-closes-viewer", True)
                    browser.close()
                    browser_ok = shot.is_file()
                    browser_detail = str(shot)
            except Exception as exc:
                browser_detail = str(exc)
                checks.check("browser-proof", False, browser_detail)
        shot = artifacts / "first-still.png"
        width, height = png_size(shot)
        checks.check("first-still-exists", shot.is_file() and browser_ok, browser_detail)
        checks.check("first-still-1280x720", width == 1280 and height == 720, f"{width}x{height}")

        preview_path.unlink()
        checks.check("preview-file-deleted", not preview_path.exists())
        d_status, d_headers, d_body = request_raw(preview_url)
        media_responses["deletedPreview"] = record_media(d_status, d_headers, d_body)
        checks.check(
            "deleted-preview-unavailable",
            d_status == 404 and media_responses["deletedPreview"].get("body") == {"error": "preview-unavailable"},
            json.dumps(media_responses["deletedPreview"]),
        )
        after_delete = find_item(load_items(isolated), "oriented.jpg") or {}
        after_status = (after_delete.get("renditions") or {}).get("status") or {}
        checks.check(
            "deleted-preview-status-unchanged",
            after_status.get("preview") == "ready",
            str(after_status),
        )
        checks.check("deleted-preview-not-recreated", not preview_path.exists())
        (artifacts / "media-responses.json").write_text(
            json.dumps(media_responses, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)

    if not (artifacts / "sizes.json").exists():
        (artifacts / "sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", encoding="utf-8")
    if not (artifacts / "media-responses.json").exists():
        (artifacts / "media-responses.json").write_text(
            json.dumps(media_responses, indent=2) + "\n", encoding="utf-8"
        )
    return write_result("S03", "slice", checks, artifacts, commands)
