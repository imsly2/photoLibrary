"""Slice S10 / Check F12 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    assert_no_pillow_in_server,
    copy_committed_fixtures,
)
from tests.qa.s01 import hash_tree, parse_summary
from tests.qa.s03 import find_item, png_size
from tests.qa.s04 import collect_console
from tests.qa.s05 import pin_media_from_manifest
from tests.qa.s08 import copy_rels, fresh_root, run_library, write_result
from tests.qa.s09 import start_owned, wait_catalog, wait_viewer_closed, wait_viewer_still

GPS_RELS = (
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/far.jpg",
    "b/no-exif.jpg",
)
GPS_NAMES = ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg")
EMPTY_REL = ("b/no-exif.jpg",)
BLOCKED_HOSTS = (
    "google",
    "mapbox",
    "osm",
    "openstreetmap",
    "nominatim",
    "geocode",
)
EMPTY_TEXT = "No locations to show"


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def scan_folder(root: Path, folder: Path, commands: list[str]) -> dict[str, Any]:
    proc = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    commands.append("python -m library scan <folder> --serve-from-there")
    summary = parse_summary(proc.stdout) if proc.stdout.strip() else {}
    return {"proc": proc, "summary": summary}


def yaw_delta(before: float, after: float) -> float:
    delta = after - before
    while delta > 180:
        delta -= 360
    while delta < -180:
        delta += 360
    return delta


def blocked_url(url: str, origin: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if url.startswith(origin):
        return None
    host = (parsed.hostname or "").lower()
    for token in BLOCKED_HOSTS:
        if token in host or token in url.lower():
            return f"blocked:{token}:{url}"
    return f"off-origin:{url}"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def prove_places_api(
    checks: Checks,
    base: str,
    items: list[dict[str, Any]],
    artifacts: Path,
    commands: list[str],
) -> dict[str, Any]:
    status, places = request_json(base + "/api/places", timeout=5)
    commands.append("GET /api/places")
    checks.check("places-http-200", status == 200 and isinstance(places, list), str(status))
    write_json(artifacts / "places.json", places)
    checks.check("places-count-two", isinstance(places, list) and len(places) == 2, str(places))

    no_exif = find_item(items, "no-exif.jpg") or {}
    checks.check("no-exif-item", bool(no_exif.get("id")), str(no_exif))
    checks.check("no-exif-no-place", no_exif.get("placeId") in {None, ""}, str(no_exif.get("placeId")))
    place_ids = {rec.get("id") for rec in places} if isinstance(places, list) else set()
    checks.check("places-omit-no-exif", no_exif.get("placeId") not in place_ids, str(place_ids))

    by_name = {item.get("filename"): item for item in items}
    chicago_ids = {
        (by_name.get("IMG_1042.jpg") or {}).get("placeId"),
        (by_name.get("near.jpg") or {}).get("placeId"),
    }
    far_id = (by_name.get("far.jpg") or {}).get("placeId")
    checks.check("chicago-same-place", len(chicago_ids) == 1 and None not in chicago_ids, str(chicago_ids))
    checks.check("far-other-place", type(far_id) is str and far_id and far_id not in chicago_ids, str(far_id))
    chicago_id = next(iter(chicago_ids)) if chicago_ids else ""

    keys_ok = True
    for rec in places if isinstance(places, list) else []:
        if set(rec) != {"id", "latitude", "longitude", "name", "itemCount", "newestItemId"}:
            keys_ok = False
        if rec.get("latitude") is None or rec.get("longitude") is None:
            keys_ok = False
    checks.check("places-fields", keys_ok, json.dumps(places))

    items_by_place: dict[str, Any] = {}
    for rec in places if isinstance(places, list) else []:
        pid = rec["id"]
        p_status, p_items = request_json(base + "/api/items?place=" + pid, timeout=5)
        commands.append(f"GET /api/items?place={pid}")
        items_by_place[pid] = p_items
        names = [item.get("filename") for item in p_items] if isinstance(p_items, list) else []
        checks.check(f"items-place-http-{pid}", p_status == 200, str(p_status))
        only = all(item.get("placeId") == pid for item in p_items) if isinstance(p_items, list) else False
        checks.check(f"items-place-only-{pid}", only, json.dumps(names))
        if pid == chicago_id:
            checks.check(
                "chicago-items",
                set(names) == {"IMG_1042.jpg", "near.jpg"},
                json.dumps(names),
            )
            near = find_item(p_items, "near.jpg") if isinstance(p_items, list) else None
            checks.check("chicago-newest-near", rec.get("newestItemId") == (near or {}).get("id"), str(rec.get("newestItemId")))
            checks.check("chicago-count-2", rec.get("itemCount") == 2, str(rec.get("itemCount")))
        if pid == far_id:
            checks.check("far-items", names == ["far.jpg"], json.dumps(names))
            checks.check("far-count-1", rec.get("itemCount") == 1, str(rec.get("itemCount")))
    write_json(artifacts / "items-place.json", items_by_place)
    return {"places": places, "chicagoId": chicago_id, "farId": far_id, "itemsByPlace": items_by_place}


def wait_globe_ready(page: Any, timeout: int = 15000) -> None:
    page.wait_for_function(
        """() => {
          const canvas = document.getElementById('globe-canvas');
          const view = document.getElementById('globe-view');
          return document.body.dataset.view === 'globe'
            && view && !view.hidden
            && canvas && canvas.dataset.ready === '1'
            && canvas.dataset.webgl === '1';
        }""",
        timeout=timeout,
    )


def capture_network(page: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def on_request(req: Any) -> None:
        records.append(
            {
                "url": req.url,
                "method": req.method,
                "resourceType": req.resource_type,
            }
        )

    page.on("request", on_request)
    return records


def prove_globe_page(
    checks: Checks,
    page: Any,
    url: str,
    items: list[dict[str, Any]],
    places_doc: dict[str, Any],
    artifacts: Path,
    include_click: bool,
) -> dict[str, Any]:
    network = capture_network(page)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("#view-globe", timeout=8000)
    checks.check("library-view-default", page.evaluate("() => document.body.dataset.view") == "library")
    page.locator("#view-globe").click()
    wait_globe_ready(page)
    page.wait_for_function(
        "() => window.libraryGlobe && window.libraryGlobe.getClusters().length > 0",
        timeout=10000,
    )
    page.wait_for_timeout(200)
    globe_png = artifacts / "globe.png"
    page.screenshot(path=str(globe_png), full_page=False)
    gw, gh = png_size(globe_png)
    checks.check("globe-png-size", gw == 1280 and gh == 720, f"{gw}x{gh}")
    checks.check(
        "globe-texture-local",
        page.evaluate("() => document.getElementById('globe-canvas').dataset.texture") == "/assets/earth.png",
    )

    clusters = page.evaluate("() => window.libraryGlobe.getClusters()")
    places = places_doc.get("places") or []
    by_id = {rec["id"]: rec for rec in places}
    members_doc: dict[str, Any] = {
        "clusters": clusters,
        "rulePixels": 32,
        "places": [
            {
                "id": rec.get("id"),
                "itemCount": rec.get("itemCount"),
                "newestItemId": rec.get("newestItemId"),
            }
            for rec in places
        ],
    }
    if clusters:
        first = clusters[0]
        pairwise = first.get("pairwise") or []
        within = all(dist <= 32 + 1e-6 for dist in pairwise) if pairwise else len(first.get("placeIds") or []) == 1
        members_doc["within32"] = within
        members_doc["centroid"] = first.get("centroid")
        if len(places) == 2 and len(first.get("placeIds") or []) < 2:
            canvas = page.evaluate(
                """() => {
                  const r = document.getElementById('globe-canvas').getBoundingClientRect();
                  return {x: r.left + r.width / 2, y: r.top + r.height / 2};
                }"""
            )
            for _ in range(12):
                page.mouse.move(canvas["x"], canvas["y"])
                page.mouse.wheel(0, 120)
                page.wait_for_timeout(80)
                clusters = page.evaluate("() => window.libraryGlobe.getClusters()")
                if clusters and len(clusters[0].get("placeIds") or []) >= 2:
                    break
            members_doc["clusters"] = clusters
            first = clusters[0] if clusters else first
            pairwise = first.get("pairwise") or []
            within = all(dist <= 32 + 1e-6 for dist in pairwise) if pairwise else False
            members_doc["within32"] = within
        checks.check("cluster-present", bool(clusters), json.dumps(clusters))
        checks.check(
            "cluster-two-places",
            len(first.get("placeIds") or []) == 2,
            json.dumps(first.get("placeIds")),
        )
        checks.check("cluster-count-3", first.get("itemCount") == 3, str(first.get("itemCount")))
        expected_counts = sorted(rec.get("itemCount") for rec in places)
        got_counts = sorted(first.get("itemCounts") or [])
        checks.check("cluster-member-counts", got_counts == expected_counts, json.dumps(got_counts))
        checks.check("cluster-within-32", bool(members_doc.get("within32")), json.dumps(pairwise))
    else:
        checks.check("cluster-present", False, "no clusters")

    cluster_png = artifacts / "cluster.png"
    page.screenshot(path=str(cluster_png), full_page=False)
    cw, ch = png_size(cluster_png)
    checks.check("cluster-png-size", cw == 1280 and ch == 720, f"{cw}x{ch}")

    pick = page.evaluate(
        """() => {
          const canvas = document.getElementById('globe-canvas');
          const r = canvas.getBoundingClientRect();
          const clusters = window.libraryGlobe.getClusters();
          const cx = r.width / 2;
          const cy = r.height / 2;
          let best = null;
          let bestScore = Infinity;
          for (let row = 2; row <= 8; row += 1) {
            for (let col = 2; col <= 8; col += 1) {
              const x = r.width * (col / 10);
              const y = r.height * (row / 10);
              const got = window.libraryGlobe.pick(x, y);
              if (!got || !got.hit) {
                continue;
              }
              let pinDist = Infinity;
              for (let c = 0; c < clusters.length; c++) {
                pinDist = Math.min(pinDist, Math.hypot(x - clusters[c].centroid.x, y - clusters[c].centroid.y));
              }
              if (pinDist < 48) {
                continue;
              }
              const fromCenter = Math.hypot(x - cx, y - cy);
              const score = Math.abs(fromCenter - 90);
              if (score < bestScore) {
                bestScore = score;
                best = {x: x, y: y, lat: got.lat, lon: got.lon, clientX: r.left + x, clientY: r.top + y};
              }
            }
          }
          return best;
        }"""
    )
    checks.check("globe-pick-hit", bool(pick), json.dumps(pick))
    if pick:
        before = page.evaluate("() => window.libraryGlobe.getCamera()")
        page.mouse.move(pick["clientX"], pick["clientY"])
        page.mouse.down()
        page.mouse.move(pick["clientX"] + 40, pick["clientY"])
        page.mouse.up()
        page.wait_for_timeout(150)
        after = page.evaluate("() => window.libraryGlobe.getCamera()")
        delta = yaw_delta(before["yawDeg"], after["yawDeg"])
        rate = abs(delta) / 40
        members_doc["rotation"] = {
            "before": before,
            "after": after,
            "dx": 40,
            "deltaYawDeg": delta,
            "degPerPixel": rate,
        }
        checks.check("drag-0.25-deg-per-px", abs(rate - 0.25) <= 0.03, json.dumps(members_doc["rotation"]))

        pick2 = page.evaluate(
            """() => {
              const canvas = document.getElementById('globe-canvas');
              const r = canvas.getBoundingClientRect();
              const clusters = window.libraryGlobe.getClusters();
              const cx = r.width / 2;
              const cy = r.height / 2;
              let best = null;
              let bestScore = Infinity;
              for (let row = 2; row <= 8; row += 1) {
                for (let col = 2; col <= 8; col += 1) {
                  const x = r.width * (col / 10);
                  const y = r.height * (row / 10);
                  const got = window.libraryGlobe.pick(x, y);
                  if (!got || !got.hit) {
                    continue;
                  }
                  let pinDist = Infinity;
                  for (let c = 0; c < clusters.length; c++) {
                    pinDist = Math.min(pinDist, Math.hypot(x - clusters[c].centroid.x, y - clusters[c].centroid.y));
                  }
                  if (pinDist < 48) {
                    continue;
                  }
                  const fromCenter = Math.hypot(x - cx, y - cy);
                  const score = Math.abs(fromCenter - 90);
                  if (score < bestScore) {
                    bestScore = score;
                    best = {x: x, y: y, lat: got.lat, lon: got.lon, clientX: r.left + x, clientY: r.top + y};
                  }
                }
              }
              return best;
            }"""
        )
        if not pick2:
            pick2 = pick
        page.mouse.move(pick2["clientX"], pick2["clientY"])
        page.mouse.wheel(0, -100)
        page.wait_for_timeout(160)
        zoom = page.evaluate(
            """(info) => {
              const proj = window.libraryGlobe.project(info.lat, info.lon);
              return {
                x: proj.x,
                y: proj.y,
                visible: proj.visible,
                drift: Math.hypot(proj.x - info.x, proj.y - info.y),
              };
            }""",
            {"lat": pick2["lat"], "lon": pick2["lon"], "x": pick2["x"], "y": pick2["y"]},
        )
        members_doc["zoomAnchor"] = {"before": pick2, "after": zoom}
        checks.check("zoom-anchor-le-2px", (zoom or {}).get("drift", 99) <= 2, json.dumps(zoom))

    write_json(artifacts / "cluster-members.json", members_doc)

    origin_base = url.rstrip("/")
    leaks = []
    local_texture = False
    for rec in network:
        href = rec.get("url") or ""
        if href.endswith("/assets/earth.png") and href.startswith(origin_base):
            local_texture = True
        leak = blocked_url(href, origin_base)
        if leak:
            leaks.append(leak)
    write_json(artifacts / "offline-network.json", network)
    checks.check("offline-no-external", leaks == [], json.dumps(leaks))
    checks.check("offline-earth-png", local_texture, json.dumps([rec.get("url") for rec in network]))

    click_doc: dict[str, Any] = {}
    if include_click:
        page.wait_for_selector(".globe-cluster", timeout=8000)
        page.locator(".globe-cluster").first.click()
        wait_viewer_still(page)
        viewer_name = page.evaluate(
            """() => {
              const viewer = document.getElementById('viewer');
              const img = document.getElementById('viewer-image');
              const src = (img && img.getAttribute('src')) || '';
              return {
                open: viewer && !viewer.hidden,
                src: src,
                view: document.body.dataset.view,
                place: document.getElementById('grid').dataset.place || '',
              };
            }"""
        )
        near = find_item(items, "near.jpg") or {}
        checks.check("cluster-opens-viewer", bool(viewer_name.get("open")), json.dumps(viewer_name))
        checks.check(
            "cluster-opens-newest-near",
            near.get("id") and ("/api/media/" + near["id"]) in (viewer_name.get("src") or ""),
            json.dumps(viewer_name),
        )
        page.keyboard.press("Escape")
        wait_viewer_closed(page)
        after_esc = page.evaluate(
            """() => {
              const cells = Array.from(document.querySelectorAll('#grid .cell')).map((cell) => ({
                id: cell.dataset.id,
                filename: cell.dataset.filename,
              }));
              return {
                view: document.body.dataset.view,
                viewerHidden: document.getElementById('viewer').hidden,
                place: document.getElementById('grid').dataset.place || '',
                filenames: cells.map((cell) => cell.filename),
                ids: cells.map((cell) => cell.id),
              };
            }"""
        )
        expected_ids = {places_doc["chicagoId"], places_doc["farId"]}
        filter_ids = set((after_esc.get("place") or "").split(",")) - {""}
        checks.check("esc-viewer-closed", after_esc.get("viewerHidden") is True, json.dumps(after_esc))
        checks.check("esc-library-grid", after_esc.get("view") == "library", json.dumps(after_esc))
        checks.check("esc-place-filter", filter_ids == expected_ids, json.dumps(after_esc))
        checks.check(
            "esc-grid-only-cluster",
            set(after_esc.get("filenames") or []) == {"IMG_1042.jpg", "near.jpg", "far.jpg"},
            json.dumps(after_esc.get("filenames")),
        )
        page.locator("#view-globe").click()
        wait_globe_ready(page)
        again = page.evaluate(
            """() => ({
              view: document.body.dataset.view,
              globeHidden: document.getElementById('globe-view').hidden,
              workspaceHidden: document.querySelector('.workspace').hidden,
              viewerHidden: document.getElementById('viewer').hidden,
            })"""
        )
        checks.check(
            "globe-again-shows-globe",
            again.get("view") == "globe" and again.get("globeHidden") is False and again.get("workspaceHidden") is True,
            json.dumps(again),
        )
        click_doc = {"viewer": viewer_name, "afterEsc": after_esc, "globeAgain": again}
    return {"network": network, "clusters": members_doc, "click": click_doc}


def prove_empty_globe(checks: Checks, artifacts: Path, media_src: Path, commands: list[str]) -> None:
    folder = copy_rels(media_src, artifacts / "s10-empty-media", EMPTY_REL)
    root = fresh_root(artifacts / "s10-empty-root")
    scanned = scan_folder(root, folder, commands)
    checks.check("empty-scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
    server, url, pids = start_owned(root)
    try:
        wait_catalog(url.rstrip("/"), ("no-exif.jpg",))
        status, places = request_json(url.rstrip("/") + "/api/places", timeout=5)
        commands.append("GET /api/places empty")
        checks.check("empty-places-http", status == 200 and places == [], str(places))
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("empty-playwright", False, str(exc))
            return
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            page.locator("#view-globe").click()
            page.wait_for_function(
                """() => {
                  const empty = document.getElementById('globe-empty');
                  return document.body.dataset.view === 'globe' && empty && !empty.hidden
                    && empty.textContent === 'No locations to show';
                }""",
                timeout=10000,
            )
            text = page.evaluate("() => (document.getElementById('globe-empty') || {}).textContent || ''")
            checks.check("empty-globe-text", text == EMPTY_TEXT, text)
            browser.close()
    finally:
        from tests.qa.s00 import stop_owned

        stop_owned(server, extra_pids=pids)


def prove_webgl_failure(checks: Checks, url: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        checks.check("webgl-playwright", False, str(exc))
        return
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script(
            """
            (() => {
              const orig = HTMLCanvasElement.prototype.getContext;
              HTMLCanvasElement.prototype.getContext = function (type, attrs) {
                if (type && String(type).toLowerCase().indexOf('webgl') !== -1) {
                  return null;
                }
                return orig.call(this, type, attrs);
              };
            })();
            """
        )
        page.goto(url, wait_until="domcontentloaded")
        page.locator("#view-globe").click()
        page.wait_for_function(
            """() => {
              const err = document.getElementById('globe-error');
              return document.body.dataset.view === 'globe' && err && !err.hidden && (err.textContent || '').length > 0;
            }""",
            timeout=10000,
        )
        info = page.evaluate(
            """() => ({
              error: (document.getElementById('globe-error') || {}).textContent || '',
              hidden: document.getElementById('globe-error').hidden,
              hasMap: !!document.querySelector('iframe, [data-map], .leaflet-container, .mapboxgl-map'),
            })"""
        )
        checks.check("webgl-inline-error", bool(info.get("error")) and info.get("hidden") is False, json.dumps(info))
        checks.check("webgl-no-other-map", info.get("hasMap") is False, json.dumps(info))
        browser.close()


def run_session(
    artifacts: Path,
    checks: Checks,
    commands: list[str],
    *,
    include_empty: bool,
    include_webgl: bool,
) -> dict[str, str]:
    extra = {
        "globe.png": str(artifacts / "globe.png"),
        "cluster.png": str(artifacts / "cluster.png"),
        "cluster-members.json": str(artifacts / "cluster-members.json"),
        "offline-network.json": str(artifacts / "offline-network.json"),
        "places.json": str(artifacts / "places.json"),
        "items-place.json": str(artifacts / "items-place.json"),
    }
    media_src = prepare_media(artifacts)
    before = hash_tree(media_src)
    folder = copy_rels(media_src, artifacts / "s10-media", GPS_RELS)
    root = fresh_root(artifacts / "s10-root")
    scanned = scan_folder(root, folder, commands)
    checks.check("scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
    server, url, pids = start_owned(root)
    try:
        items = wait_catalog(url.rstrip("/"), GPS_NAMES)
        checks.check("catalog-four", len(items) == 4, str(len(items)))
        places_doc = prove_places_api(checks, url.rstrip("/"), items, artifacts, commands)
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return extra
        checks.check("playwright-import", True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            errors = collect_console(page)
            prove_globe_page(checks, page, url, items, places_doc, artifacts, include_click=True)
            unexpected = [message for message in errors if "status of 400" not in message]
            checks.check("no-console-errors", unexpected == [], json.dumps(errors))
            browser.close()
        if include_webgl:
            prove_webgl_failure(checks, url)
    finally:
        from tests.qa.s00 import stop_owned

        stop_owned(server, extra_pids=pids)
    if include_empty:
        prove_empty_globe(checks, artifacts, media_src, commands)
    html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
    js = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
    globe_js = (PRODUCT_ROOT / "library" / "web" / "assets" / "globe.js").read_text(encoding="utf-8")
    checks.check("page-has-globe", 'id="view-globe"' in html and 'id="globe-view"' in html)
    checks.check("page-no-settings", "Settings" not in html and "view-settings" not in html)
    checks.check("page-no-play", 'id="view-play"' not in html and "globe/tour" not in js and "globe/tour" not in globe_js)
    checks.check("texture-shipped", (PRODUCT_ROOT / "library" / "web" / "assets" / "earth.png").is_file())
    checks.check("texture-license", (PRODUCT_ROOT / "library" / "web" / "assets" / "earth-LICENSE.txt").is_file())
    checks.check("original-fixture-bytes", hash_tree(media_src) == before)
    assert_no_pillow_in_server(checks)
    return extra


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(artifacts, checks, commands, include_empty=True, include_webgl=True)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("s10-runner", False, str(exc))
    return write_result("S10", "slice", checks, artifacts, commands, extra)


def run_check_f12(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(artifacts, checks, commands, include_empty=False, include_webgl=False)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("f12-runner", False, str(exc))
    return write_result("F12", "check", checks, artifacts, commands, extra)
