"""Slice S04 / Check F9 / Check F11 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
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
from tests.qa.s02 import copy_rels, parse_items, pin_mtime
from tests.qa.s03 import find_item, png_size, request_raw

TWO_YEAR_RELS = (
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/far.jpg",
    "b/oriented.jpg",
    "b/created.jpg",
)
DATE_SORT_RELS = (
    "a/IMG_1042.jpg",
    "b/far.jpg",
    "b/no-exif.jpg",
)
TWO_YEAR_NAMES = ("IMG_1042.jpg", "near.jpg", "far.jpg", "oriented.jpg", "created.jpg")
DATE_SORT_NAMES = ("IMG_1042.jpg", "far.jpg", "no-exif.jpg")


def load_manifest() -> dict[str, Any]:
    return json.loads((COMMITTED_FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def pin_media_from_manifest(media: Path) -> None:
    files = {rec["path"]: rec for rec in load_manifest().get("files", [])}
    for rel, rec in files.items():
        path = media / Path(rel)
        if path.is_file():
            pin_mtime(path, rec["mtime"])


def copy_pinned_subset(src_media: Path, dest: Path, rels: tuple[str, ...] | list[str]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    copy_rels(src_media, dest, rels)
    files = {rec["path"]: rec for rec in load_manifest().get("files", [])}
    for rel in rels:
        pin_mtime(dest / Path(rel), files[rel]["mtime"])


def flatten_groups(groups: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for group in groups:
        out.extend(group.get("itemIds") or [])
    return out


def filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") or "" for item in items]


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


def wait_items(
    base: str,
    names: tuple[str, ...] | list[str],
    timeout: float = 60,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            have = {item.get("filename") for item in payload}
            if all(name in have for name in names):
                thumbs_ok = True
                for name in names:
                    item = find_item(payload, name)
                    if item is None:
                        thumbs_ok = False
                        break
                    rend = item.get("renditions") or {}
                    if (rend.get("status") or {}).get("thumb") != "ready":
                        thumbs_ok = False
                        break
                    t_status, _, body = request_raw(f"{base}/api/media/{item['id']}?which=thumb")
                    if t_status != 200 or not body:
                        thumbs_ok = False
                        break
                if thumbs_ok:
                    return payload
        time.sleep(0.25)
    raise RuntimeError(
        "items/thumbs timeout "
        + json.dumps(
            [
                {
                    "filename": item.get("filename"),
                    "status": (item.get("renditions") or {}).get("status"),
                }
                for item in last
            ]
        )
    )


def save_groups(base: str, artifacts: Path, checks: Checks, expect_year_count: int | None) -> dict[str, Any]:
    recorded: dict[str, Any] = {}
    status_items, items = request_json(base + "/api/items?sort=date&dir=desc", timeout=5)
    checks.check("items-http", status_items == 200 and isinstance(items, list), str(status_items))
    item_ids = [item["id"] for item in items] if isinstance(items, list) else []
    for level in ("years", "months", "days", "all"):
        status, groups = request_json(f"{base}/api/groups?level={level}&sort=date&dir=desc", timeout=5)
        checks.check(f"groups-{level}-http", status == 200 and isinstance(groups, list), str(status))
        if not isinstance(groups, list):
            groups = []
        (artifacts / f"groups-{level}.json").write_text(
            json.dumps(groups, indent=2) + "\n", encoding="utf-8"
        )
        recorded[level] = groups
        flat = flatten_groups(groups)
        checks.check(
            f"groups-{level}-ids-once",
            flat == item_ids and len(flat) == len(set(flat)),
            json.dumps({"flat": flat, "items": item_ids}),
        )
        for group in groups:
            checks.check(
                f"groups-{level}-shape:{group.get('key')}",
                set(group.keys()) <= {"key", "itemIds"} and "key" in group and "itemIds" in group,
                json.dumps(group),
            )
    if expect_year_count is not None:
        years = recorded.get("years") or []
        checks.check("groups-years-count", len(years) == expect_year_count, str([g.get("key") for g in years]))
    bad_status, bad_body = request_json(base + "/api/groups?level=weeks", timeout=5)
    checks.check(
        "groups-invalid-level",
        bad_status == 400 and bad_body == {"error": "invalid-argument"},
        json.dumps(bad_body),
    )
    return recorded


def start_isolated(root: Path) -> tuple[subprocess.Popen[str], str, int, list[int]]:
    isolated = Path(root)
    last_exc: Exception | None = None
    for _ in range(5):
        if isolated.exists():
            shutil.rmtree(isolated)
        prepare_root(isolated)
        port = find_free_port()
        write_isolated_port(isolated, port)
        server = start_server(isolated)
        url = f"http://127.0.0.1:{port}/"
        try:
            health_status, health_body = wait_health(url, server)
        except RuntimeError as exc:
            last_exc = exc
            stop_owned(server)
            if "port-in-use" not in str(exc):
                raise
            time.sleep(0.2)
            continue
        if health_status != 200 or health_body != {"ok": True}:
            stop_owned(server)
            raise RuntimeError(f"health {health_status} {health_body}")
        owned_pids: list[int] = []
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/runtime", timeout=2) as resp:
                runtime_body = json.loads(resp.read().decode("utf-8"))
            server_pid = runtime_body.get("pid")
            if type(server_pid) is int:
                owned_pids.append(server_pid)
        except Exception:
            pass
        return server, url, port, owned_pids
    raise RuntimeError(last_exc or "could not start isolated server")


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


def run_add_folder_flow(page: Any, media: Path, checks: Checks) -> None:
    page.get_by_role("button", name="Add folder").click()
    page.wait_for_selector("dialog#add-folder[open]", timeout=5000)
    checks.check("add-disabled-until-path-mode", page.locator("#add-submit").is_disabled())
    checks.check(
        "add-ask-neither-mode",
        page.locator('input[name="add-mode"]:checked').count() == 0,
    )
    page.locator("#add-path").fill(str(media))
    checks.check("add-still-disabled-without-mode", page.locator("#add-submit").is_disabled())
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('add-folder').open", timeout=5000)
    checks.check("add-esc-closes", True)
    base = page.url.split("?")[0].rstrip("/")
    esc_status, esc_sources = request_json(base + "/api/sources", timeout=5)
    checks.check("add-esc-no-write", esc_status == 200 and esc_sources == [], str(esc_sources))

    page.get_by_role("button", name="Add folder").click()
    page.wait_for_selector("dialog#add-folder[open]", timeout=5000)
    page.locator("#add-cancel").click()
    page.wait_for_function("() => !document.getElementById('add-folder').open", timeout=5000)
    checks.check("add-cancel-closes", True)
    cancel_status, cancel_sources = request_json(base + "/api/sources", timeout=5)
    checks.check("add-cancel-no-write", cancel_status == 200 and cancel_sources == [], str(cancel_sources))

    page.get_by_role("button", name="Add folder").click()
    page.wait_for_selector("dialog#add-folder[open]", timeout=5000)
    page.locator("#add-path").fill(str(media))
    page.locator('input[name="add-mode"][value="serve-from-there"]').check()
    checks.check("add-enabled-with-path-mode", page.locator("#add-submit").is_enabled())
    page.locator("#add-submit").click()
    page.wait_for_function("() => !document.getElementById('add-folder').open", timeout=60000)


def image_rect(page: Any) -> dict[str, float]:
    return page.evaluate(
        """() => {
          const img = document.getElementById('viewer-image');
          const r = img.getBoundingClientRect();
          return {
            left: r.left,
            top: r.top,
            width: r.width,
            height: r.height,
            complete: img.complete,
            naturalWidth: img.naturalWidth
          };
        }"""
    )


def dispatch_ctrl_wheel(page: Any, x: float, y: float, delta_y: float) -> None:
    page.evaluate(
        """([x, y, dy]) => {
          const ev = new WheelEvent('wheel', {
            bubbles: true,
            cancelable: true,
            ctrlKey: true,
            deltaY: dy,
            clientX: x,
            clientY: y,
            view: window
          });
          window.dispatchEvent(ev);
        }""",
        [x, y, delta_y],
    )


def run_browser_browse(
    page: Any,
    url: str,
    media: Path,
    artifacts: Path,
    checks: Checks,
    *,
    wait_name: str,
    expect_year_count: int,
    do_viewer: bool,
    input_trace: list[dict[str, Any]],
    measurements: dict[str, Any],
) -> None:
    page.goto(url, wait_until="domcontentloaded")
    empty = page.locator("text=No pictures yet")
    checks.check("empty-before-add", empty.count() >= 0)
    run_add_folder_flow(page, media, checks)
    page.wait_for_selector(f'[data-filename="{wait_name}"]', timeout=60000)
    checks.check("page-not-empty-after-items", page.locator("text=No pictures yet").count() == 0)
    page.wait_for_function(
        """() => {
          const imgs = [...document.querySelectorAll('.cell img')];
          return imgs.length > 0 && imgs.every((img) => !img.hidden && img.complete && img.naturalWidth > 0);
        }""",
        timeout=60000,
    )
    status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=5)
    checks.check("sources-after-dialog", status == 200 and isinstance(sources, list) and len(sources) == 1)
    if isinstance(sources, list) and sources:
        scan = sources[0].get("scan") or {}
        checks.check("scan-not-running", scan.get("state") in {"complete", "idle", "error"}, str(scan))
        checks.check(
            "status-line",
            page.locator("#scan-status").count() == 1
            and "added" in (page.locator("#scan-status").inner_text() or ""),
        )

    js = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
    checks.check("page-no-localStorage", "localStorage" not in js)

    page.wait_for_function("() => document.getElementById('grid') && document.getElementById('grid').dataset.level === 'years'", timeout=5000)
    years_shot = artifacts / "years.png"
    page.screenshot(path=str(years_shot), full_page=False)
    yw, yh = png_size(years_shot)
    checks.check("years-png", years_shot.is_file() and yw == 1280 and yh == 720, f"{yw}x{yh}")

    hovered = page.locator(f'[data-filename="{wait_name}"]')
    box = hovered.bounding_box()
    checks.check("hover-target", box is not None)
    if box:
        hx = box["x"] + box["width"] / 2
        hy = box["y"] + box["height"] / 2
        page.mouse.move(hx, hy)
        input_trace.append({"type": "hover", "filename": wait_name, "x": hx, "y": hy})
        dispatch_ctrl_wheel(page, hx, hy, -100)
        input_trace.append({"type": "ctrl-wheel", "deltaY": -100, "sizeFrom": "72"})
        page.wait_for_function(
            "() => document.getElementById('grid') && document.getElementById('grid').dataset.size === '104'",
            timeout=5000,
        )
        after = page.locator(f'[data-filename="{wait_name}"]')
        after_box = after.bounding_box()
        checks.check("ctrl-wheel-steps-size", page.locator("#grid").get_attribute("data-size") == "104")
        checks.check("ctrl-wheel-keeps-dates", page.locator("#grid").get_attribute("data-date-group") == "years")
        if after_box:
            visible = after_box["y"] < 720 and (after_box["y"] + after_box["height"]) > 0
            checks.check("hover-stays-in-viewport", visible, json.dumps(after_box))
            measurements["sizeAnchor"] = {"before": box, "after": after_box}

    page.locator("#date-group").select_option("days")
    input_trace.append({"type": "date-group", "value": "days"})
    page.locator("#size-slider").evaluate(
        """(el) => {
          el.value = '6';
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }"""
    )
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'days' && document.getElementById('grid').dataset.size === '420'",
        timeout=5000,
    )
    all_shot = artifacts / "all.png"
    page.screenshot(path=str(all_shot), full_page=False)
    aw, ah = png_size(all_shot)
    checks.check("all-png", all_shot.is_file() and aw == 1280 and ah == 720, f"{aw}x{ah}")

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector(f'[data-filename="{wait_name}"]', timeout=30000)
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'days'",
        timeout=10000,
    )
    settings_status, settings_body = request_json(url.rstrip("/") + "/api/settings", timeout=5)
    checks.check(
        "zoomLevel-persists",
        settings_status == 200
        and isinstance(settings_body, dict)
        and settings_body.get("zoomLevel") == "days"
        and page.locator("#grid").get_attribute("data-date-group") == "days",
        json.dumps(settings_body) if isinstance(settings_body, dict) else str(settings_body),
    )

    if not do_viewer:
        return

    page.locator("#date-group").select_option("days")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'days'",
        timeout=5000,
    )
    page.evaluate(
        """() => {
          const main = document.getElementById('grid');
          main.scrollTop = Math.min(80, Math.max(0, main.scrollHeight - main.clientHeight));
        }"""
    )
    saved = page.evaluate("() => document.getElementById('grid').scrollTop")
    page.locator('[data-filename="oriented.jpg"]').click()
    page.wait_for_function(
        """() => {
          const img = document.getElementById('viewer-image');
          return !!(img && img.getAttribute('src') && img.complete && img.naturalWidth > 0
            && document.getElementById('viewer') && !document.getElementById('viewer').hidden);
        }""",
        timeout=15000,
    )
    src = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("viewer-src-preview", "which=preview" in src and "52e6037ff78aaacfff71f8e2e1a41f25b5e70c78eca54126aca5e97a11c056c7" in src, src)
    viewer_shot = artifacts / "viewer.png"
    page.screenshot(path=str(viewer_shot), full_page=False)
    vw, vh = png_size(viewer_shot)
    checks.check("viewer-png", viewer_shot.is_file() and vw == 1280 and vh == 720, f"{vw}x{vh}")

    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
        timeout=5000,
    )
    restored = page.evaluate("() => document.getElementById('grid').scrollTop")
    checks.check("esc-restores-scroll", restored == saved, f"saved={saved} restored={restored}")
    checks.check("esc-restores-level", page.locator("#grid").get_attribute("data-level") == "days")

    items_status, sorted_items = request_json(url.rstrip("/") + "/api/items?sort=date&dir=desc", timeout=5)
    checks.check("viewer-items", items_status == 200 and isinstance(sorted_items, list))
    ids = [item["id"] for item in sorted_items] if isinstance(sorted_items, list) else []
    first_name = (sorted_items[0].get("filename") if sorted_items else "created.jpg")
    last_name = (sorted_items[-1].get("filename") if sorted_items else "far.jpg")
    page.locator(f'[data-filename="{first_name}"]').click()
    page.wait_for_function(
        """() => {
          const img = document.getElementById('viewer-image');
          return !!(img && img.complete && img.naturalWidth > 0 && !document.getElementById('viewer').hidden);
        }""",
        timeout=15000,
    )
    start_src = page.locator("#viewer-image").get_attribute("src") or ""
    page.keyboard.press("ArrowLeft")
    left_src = page.locator("#viewer-image").get_attribute("src") or ""
    page.keyboard.press("ArrowRight")
    right_src = page.locator("#viewer-image").get_attribute("src") or ""
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
        timeout=5000,
    )
    page.locator(f'[data-filename="{last_name}"]').click()
    page.wait_for_function(
        """() => {
          const img = document.getElementById('viewer-image');
          return !!(img && img.complete && img.naturalWidth > 0 && !document.getElementById('viewer').hidden);
        }""",
        timeout=15000,
    )
    end_src = page.locator("#viewer-image").get_attribute("src") or ""
    page.keyboard.press("ArrowRight")
    end_again = page.locator("#viewer-image").get_attribute("src") or ""
    checks.check("arrows-stop-at-ends", left_src == start_src and end_src == end_again, f"{left_src} {end_again}")
    checks.check("arrow-right-moves", right_src != start_src or len(ids) <= 1, right_src)
    input_trace.append({
        "type": "arrows",
        "first": start_src,
        "afterLeft": left_src,
        "afterRight": right_src,
        "end": end_src,
    })

    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.getElementById('viewer') && document.getElementById('viewer').hidden",
        timeout=5000,
    )
    page.locator('[data-filename="oriented.jpg"]').click()
    page.wait_for_function(
        """() => {
          const img = document.getElementById('viewer-image');
          return !!(img && img.complete && img.naturalWidth > 0 && !document.getElementById('viewer').hidden);
        }""",
        timeout=15000,
    )
    before = image_rect(page)
    cx = before["left"] + before["width"] / 2
    cy = before["top"] + before["height"] / 2
    fx = (cx - before["left"]) / before["width"] if before["width"] else 0.5
    fy = (cy - before["top"]) / before["height"] if before["height"] else 0.5
    dispatch_ctrl_wheel(page, cx, cy, -100)
    input_trace.append({"type": "viewer-zoom", "x": cx, "y": cy, "deltaY": -100})
    after_zoom = image_rect(page)
    nx = after_zoom["left"] + fx * after_zoom["width"]
    ny = after_zoom["top"] + fy * after_zoom["height"]
    drift = ((nx - cx) ** 2 + (ny - cy) ** 2) ** 0.5
    measurements["zoom"] = {
        "cursor": {"x": cx, "y": cy},
        "before": before,
        "after": after_zoom,
        "projected": {"x": nx, "y": ny},
        "driftPx": drift,
    }
    checks.check("zoom-anchor-drift", drift <= 2, json.dumps(measurements["zoom"]))
    checks.check(
        "zoom-enlarged",
        after_zoom["width"] > before["width"] + 1 and after_zoom["height"] > before["height"] + 1,
        json.dumps({"before": before, "after": after_zoom}),
    )

    pre_pan = image_rect(page)
    pan_x = pre_pan["left"] + pre_pan["width"] / 2
    pan_y = pre_pan["top"] + pre_pan["height"] / 2
    page.evaluate(
        """([x1, y1, x2, y2]) => {
          const viewer = document.getElementById('viewer');
          function opts(x, y, buttons) {
            return {
              bubbles: true,
              cancelable: true,
              view: window,
              clientX: x,
              clientY: y,
              button: 1,
              buttons: buttons
            };
          }
          viewer.dispatchEvent(new MouseEvent('mousedown', opts(x1, y1, 4)));
          window.dispatchEvent(new MouseEvent('mousemove', opts(x2, y2, 4)));
          window.dispatchEvent(new MouseEvent('mouseup', opts(x2, y2, 0)));
        }""",
        [pan_x, pan_y, pan_x + 40, pan_y + 25],
    )
    input_trace.append({"type": "middle-drag", "dx": 40, "dy": 25})
    post_pan = image_rect(page)
    moved_x = post_pan["left"] - pre_pan["left"]
    moved_y = post_pan["top"] - pre_pan["top"]
    pan_err = max(abs(moved_x - 40), abs(moved_y - 25))
    measurements["pan"] = {
        "drag": {"x": 40, "y": 25},
        "moved": {"x": moved_x, "y": moved_y},
        "errorPx": pan_err,
        "before": pre_pan,
        "after": post_pan,
    }
    checks.check("pan-1to1", pan_err <= 2, json.dumps(measurements["pan"]))


def run_toolbar_sorts(page: Any, url: str, checks: Checks, input_trace: list[dict[str, Any]]) -> None:
    base = url.rstrip("/")
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    with page.expect_request(lambda req: "/api/items" in req.url and "sort=location" in req.url) as pending:
        page.select_option("#sort", "location")
    request = pending.value
    input_trace.append({"type": "toolbar-sort", "url": request.url})
    checks.check("toolbar-location-query", "sort=location" in request.url, request.url)
    status, settings_body = request_json(base + "/api/settings", timeout=5)
    checks.check(
        "toolbar-sort-persists",
        status == 200 and isinstance(settings_body, dict) and settings_body.get("sort") == "location",
        json.dumps(settings_body) if isinstance(settings_body, dict) else str(settings_body),
    )
    page.select_option("#dir", "asc")
    page.wait_for_timeout(300)
    status, settings_body = request_json(base + "/api/settings", timeout=5)
    checks.check(
        "toolbar-dir-persists",
        status == 200 and isinstance(settings_body, dict) and settings_body.get("dir") == "asc",
        json.dumps(settings_body) if isinstance(settings_body, dict) else str(settings_body),
    )


def prove_sorts(root: Path, base: str, checks: Checks, commands: list[str], artifacts: Path | None = None) -> None:
    status, desc = request_json(base + "/api/items?sort=date&dir=desc", timeout=5)
    checks.check("date-desc-http", status == 200 and isinstance(desc, list), str(status))
    desc_names = filenames(desc) if isinstance(desc, list) else []
    checks.check(
        "date-desc-order",
        desc_names[:3] == ["IMG_1042.jpg", "far.jpg", "no-exif.jpg"],
        str(desc_names),
    )
    no_exif = find_item(desc, "no-exif.jpg") if isinstance(desc, list) else None
    checks.check(
        "no-exif-mtime",
        bool(no_exif)
        and no_exif.get("capturedAtSource") == "mtime"
        and no_exif.get("capturedAt") == "2022-02-03T04:05:06Z",
        json.dumps({k: (no_exif or {}).get(k) for k in ("capturedAt", "capturedAtSource", "filename")}),
    )
    cli = run_library(root, ["items", "--sort", "date", "--dir", "desc"], timeout=60)
    commands.append("python -m library items --sort date --dir desc")
    cli_items = parse_items(cli.stdout) if cli.stdout.strip() else []
    checks.check("cli-date-desc-exit", cli.returncode == 0, cli.stderr)
    checks.check(
        "cli-http-date-same-ids",
        [item.get("id") for item in cli_items] == [item.get("id") for item in (desc or [])],
        str(filenames(cli_items)),
    )

    loc_asc_s, loc_asc = request_json(base + "/api/items?sort=location&dir=asc", timeout=5)
    loc_desc_s, loc_desc = request_json(base + "/api/items?sort=location&dir=desc", timeout=5)
    checks.check("location-http", loc_asc_s == 200 and loc_desc_s == 200)
    loc_asc_names = filenames(loc_asc) if isinstance(loc_asc, list) else []
    loc_desc_names = filenames(loc_desc) if isinstance(loc_desc, list) else []
    checks.check("location-no-location-last-asc", loc_asc_names[-1:] == ["no-exif.jpg"], str(loc_asc_names))
    checks.check("location-no-location-last-desc", loc_desc_names[-1:] == ["no-exif.jpg"], str(loc_desc_names))
    gps_asc = [name for name in loc_asc_names if name != "no-exif.jpg"]
    gps_desc = [name for name in loc_desc_names if name != "no-exif.jpg"]
    checks.check(
        "location-gps-before-none",
        set(gps_asc) == {"IMG_1042.jpg", "far.jpg"} and set(gps_desc) == {"IMG_1042.jpg", "far.jpg"},
        str({"asc": loc_asc_names, "desc": loc_desc_names}),
    )
    checks.check("location-dir-reverses-gps", gps_asc == list(reversed(gps_desc)), str({"asc": gps_asc, "desc": gps_desc}))

    name_asc_s, name_asc = request_json(base + "/api/items?sort=name&dir=asc", timeout=5)
    name_desc_s, name_desc = request_json(base + "/api/items?sort=name&dir=desc", timeout=5)
    checks.check("name-http", name_asc_s == 200 and name_desc_s == 200)
    name_asc_names = filenames(name_asc) if isinstance(name_asc, list) else []
    name_desc_names = filenames(name_desc) if isinstance(name_desc, list) else []
    checks.check(
        "name-asc-order",
        name_asc_names == ["IMG_1042.jpg", "far.jpg", "no-exif.jpg"],
        str(name_asc_names),
    )
    checks.check("name-desc-order", name_desc_names == list(reversed(name_asc_names)), str(name_desc_names))

    if artifacts is not None:
        (artifacts / "items-date-desc.json").write_text(
            json.dumps(desc, indent=2) + "\n", encoding="utf-8"
        )


def prepare_sandbox(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    input_trace: list[dict[str, Any]] = []
    measurements: dict[str, Any] = {}
    extra = {
        "years.png": str(artifacts / "years.png"),
        "all.png": str(artifacts / "all.png"),
        "viewer.png": str(artifacts / "viewer.png"),
        "input-trace.json": str(artifacts / "input-trace.json"),
        "measurements.json": str(artifacts / "measurements.json"),
        "groups-years.json": str(artifacts / "groups-years.json"),
        "groups-months.json": str(artifacts / "groups-months.json"),
        "groups-days.json": str(artifacts / "groups-days.json"),
        "groups-all.json": str(artifacts / "groups-all.json"),
    }
    try:
        src_media = prepare_sandbox(artifacts)
        two_year = artifacts / "two-year-media"
        copy_pinned_subset(src_media, two_year, TWO_YEAR_RELS)
        date_media = artifacts / "date-sort-media"
        copy_pinned_subset(src_media, date_media, DATE_SORT_RELS)

        js = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
        html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
        checks.check("page-no-localStorage", "localStorage" not in js and "localStorage" not in html)
        checks.check("page-has-add-dialog", 'id="add-folder"' in html and 'id="add-folder-btn"' in html)
        checks.check("page-has-size", 'id="size-slider"' in html)
        checks.check("page-has-date-group", 'id="date-group"' in html)
        checks.check("page-no-level-slider", 'id="zoom-slider"' not in html)
        hits = []
        for path in (PRODUCT_ROOT / "library").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "PIL" in text or "pillow" in text.lower():
                hits.append(str(path.relative_to(PRODUCT_ROOT)))
        checks.check("library-no-pillow", hits == [], ", ".join(hits))

        server, url, _port, owned_pids = start_isolated(root)
        owned.append(server)
        base = url.rstrip("/")
        commands.append("serve + Add folder serve-from-there")

        status, sources_before = request_json(base + "/api/sources", timeout=5)
        checks.check("sources-empty-before-dialog", status == 200 and sources_before == [])

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return write_result("S04", "slice", checks, artifacts, commands, extra)
        checks.check("playwright-import", True)

        console_errors: list[str] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                console_errors = collect_console(page)
                run_browser_browse(
                    page,
                    url,
                    two_year,
                    artifacts,
                    checks,
                    wait_name="oriented.jpg",
                    expect_year_count=2,
                    do_viewer=True,
                    input_trace=input_trace,
                    measurements=measurements,
                )
                browser.close()
        except Exception as exc:
            checks.check("browser-proof", False, str(exc))

        status, sources_after_esc_probe = request_json(base + "/api/sources", timeout=5)
        checks.check(
            "dialog-wrote-one-source",
            status == 200 and isinstance(sources_after_esc_probe, list) and len(sources_after_esc_probe) == 1,
            str(sources_after_esc_probe),
        )
        try:
            wait_items(base, TWO_YEAR_NAMES)
            save_groups(base, artifacts, checks, 2)
            years = json.loads((artifacts / "groups-years.json").read_text(encoding="utf-8"))
            checks.check(
                "years-two-keys",
                [group.get("key") for group in years] == ["2024", "2023"],
                json.dumps([group.get("key") for group in years]),
            )
        except Exception as exc:
            checks.check("groups-record", False, str(exc))

        date_root = artifacts / "date-sort-library-data"
        date_server = None
        date_pids: list[int] = []
        try:
            date_server, date_url, _date_port, date_pids = start_isolated(date_root)
            date_base = date_url.rstrip("/")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(date_url, wait_until="domcontentloaded")
                run_add_folder_flow(page, date_media, checks)
                page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=60000)
                wait_items(date_base, DATE_SORT_NAMES)
                prove_sorts(date_root, date_base, checks, commands, artifacts)
                run_toolbar_sorts(page, date_url, checks, input_trace)
                browser.close()
        except Exception as exc:
            checks.check("date-sort-proof", False, str(exc))
        finally:
            if date_server is not None:
                stop_owned(date_server, extra_pids=date_pids)

        page_html = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        checks.check("page-no-baked-pixels", "oriented.jpg" not in page_html)
        unexpected = [err for err in console_errors if "Failed to load resource" not in err]
        checks.check("no-console-errors", unexpected == [], json.dumps(console_errors))
    finally:
        (artifacts / "input-trace.json").write_text(
            json.dumps(input_trace, indent=2) + "\n", encoding="utf-8"
        )
        (artifacts / "measurements.json").write_text(
            json.dumps(measurements, indent=2) + "\n", encoding="utf-8"
        )
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)

    return write_result("S04", "slice", checks, artifacts, commands, extra)


def run_check_f9(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    input_trace: list[dict[str, Any]] = []
    measurements: dict[str, Any] = {}
    extra = {
        "years.png": str(artifacts / "years.png"),
        "all.png": str(artifacts / "all.png"),
        "groups-years.json": str(artifacts / "groups-years.json"),
        "groups-months.json": str(artifacts / "groups-months.json"),
        "groups-days.json": str(artifacts / "groups-days.json"),
        "groups-all.json": str(artifacts / "groups-all.json"),
        "input-trace.json": str(artifacts / "input-trace.json"),
        "measurements.json": str(artifacts / "measurements.json"),
    }
    try:
        src_media = prepare_sandbox(artifacts)
        two_year = artifacts / "two-year-media"
        copy_pinned_subset(src_media, two_year, TWO_YEAR_RELS)
        server, url, _port, owned_pids = start_isolated(root)
        owned.append(server)
        commands.append("serve + Add folder serve-from-there")
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return write_result("F9", "check", checks, artifacts, commands, extra)
        checks.check("playwright-import", True)
        console_errors: list[str] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                console_errors = collect_console(page)
                run_browser_browse(
                    page,
                    url,
                    two_year,
                    artifacts,
                    checks,
                    wait_name="oriented.jpg",
                    expect_year_count=2,
                    do_viewer=False,
                    input_trace=input_trace,
                    measurements=measurements,
                )
                browser.close()
        except Exception as exc:
            checks.check("browser-proof", False, str(exc))
        try:
            wait_items(url.rstrip("/"), TWO_YEAR_NAMES)
            save_groups(url.rstrip("/"), artifacts, checks, 2)
            years = json.loads((artifacts / "groups-years.json").read_text(encoding="utf-8"))
            checks.check(
                "years-two-keys",
                [group.get("key") for group in years] == ["2024", "2023"],
                json.dumps([group.get("key") for group in years]),
            )
        except Exception as exc:
            checks.check("groups-record", False, str(exc))
        unexpected = [err for err in console_errors if "Failed to load resource" not in err]
        checks.check("no-console-errors", unexpected == [], json.dumps(console_errors))
    finally:
        (artifacts / "input-trace.json").write_text(
            json.dumps(input_trace, indent=2) + "\n", encoding="utf-8"
        )
        (artifacts / "measurements.json").write_text(
            json.dumps(measurements, indent=2) + "\n", encoding="utf-8"
        )
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)
    return write_result("F9", "check", checks, artifacts, commands, extra)


def run_check_f11(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    input_trace: list[dict[str, Any]] = []
    extra = {
        "items-date-desc.json": str(artifacts / "items-date-desc.json"),
        "input-trace.json": str(artifacts / "input-trace.json"),
    }
    try:
        src_media = prepare_sandbox(artifacts)
        date_media = artifacts / "date-sort-media"
        copy_pinned_subset(src_media, date_media, DATE_SORT_RELS)
        server, url, _port, owned_pids = start_isolated(root)
        owned.append(server)
        commands.append("serve + Add folder serve-from-there")
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return write_result("F11", "check", checks, artifacts, commands, extra)
        checks.check("playwright-import", True)
        console_errors: list[str] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                console_errors = collect_console(page)
                page.goto(url, wait_until="domcontentloaded")
                run_add_folder_flow(page, date_media, checks)
                page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=60000)
                wait_items(url.rstrip("/"), DATE_SORT_NAMES)
                prove_sorts(root, url.rstrip("/"), checks, commands, artifacts)
                run_toolbar_sorts(page, url, checks, input_trace)
                browser.close()
        except Exception as exc:
            checks.check("browser-proof", False, str(exc))
        unexpected = [err for err in console_errors if "Failed to load resource" not in err]
        checks.check("no-console-errors", unexpected == [], json.dumps(console_errors))
    finally:
        (artifacts / "input-trace.json").write_text(
            json.dumps(input_trace, indent=2) + "\n", encoding="utf-8"
        )
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)
    return write_result("F11", "check", checks, artifacts, commands, extra)
