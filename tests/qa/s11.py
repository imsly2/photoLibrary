"""Slice S11 / Check F13 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from library.httpjson import request_json
from tests.qa.s00 import PRODUCT_ROOT, Checks, assert_no_pillow_in_server
from tests.qa.s01 import hash_tree, rendition_file
from tests.qa.s03 import find_item, png_size
from tests.qa.s04 import collect_console
from tests.qa.s06 import set_settings
from tests.qa.s08 import copy_rels, fresh_root, run_library, write_result
from tests.qa.s09 import start_owned, wait_catalog
from tests.qa.s10 import (
    blocked_url,
    capture_network,
    scan_folder,
    wait_globe_ready,
    write_json,
    yaw_delta,
)

TOUR_RELS = (
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/far.jpg",
    "b/no-exif.jpg",
    "a/clip.mp4",
)
TOUR_NAMES = ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg", "clip.mp4")
EMPTY_REL = ("b/no-exif.jpg",)
EMPTY_TEXT = "No locations to show"
MOTION_ORBIT = 2
MOTION_PICTURE = 1


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    from tests.qa.s00 import copy_committed_fixtures
    from tests.qa.s05 import pin_media_from_manifest

    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def tour_snapshot(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const canvas = document.getElementById('globe-canvas');
          const img = document.getElementById('globe-tour-image');
          const vid = document.getElementById('globe-tour-video');
          const media = document.getElementById('globe-tour-media');
          const empty = document.getElementById('globe-empty');
          const camera = window.libraryGlobe ? window.libraryGlobe.getCamera() : null;
          const tour = window.libraryGlobe && window.libraryGlobe.getTour ? window.libraryGlobe.getTour() : null;
          return {
            view: document.body.dataset.view,
            globeHidden: document.getElementById('globe-view').hidden,
            tour: canvas ? canvas.dataset.tour : '',
            phase: canvas ? canvas.dataset.tourPhase : '',
            placeId: canvas ? (canvas.dataset.tourPlaceId || '') : '',
            itemId: canvas ? (canvas.dataset.tourItemId || '') : '',
            camera: camera,
            tourState: tour,
            imageSrc: img && !img.hidden ? (img.currentSrc || img.src || '') : '',
            videoSrc: vid && !vid.hidden ? (vid.currentSrc || vid.src || '') : '',
            videoMuted: vid ? vid.muted === true : null,
            videoPaused: vid ? vid.paused : null,
            videoTime: vid ? vid.currentTime : null,
            mediaHidden: media ? media.hidden : true,
            emptyHidden: empty ? empty.hidden : true,
            emptyText: empty ? (empty.textContent || '') : '',
            playVisible: !!(document.getElementById('globe-play')),
          };
        }"""
    )


def snapshot_and_escape(page: Any) -> dict[str, Any]:
    """Capture the tour pose and dispatch Escape in the same turn."""
    return page.evaluate(
        """() => {
          const canvas = document.getElementById('globe-canvas');
          const img = document.getElementById('globe-tour-image');
          const vid = document.getElementById('globe-tour-video');
          const media = document.getElementById('globe-tour-media');
          const empty = document.getElementById('globe-empty');
          const camera = window.libraryGlobe ? window.libraryGlobe.getCamera() : null;
          const tour = window.libraryGlobe && window.libraryGlobe.getTour ? window.libraryGlobe.getTour() : null;
          const snap = {
            view: document.body.dataset.view,
            globeHidden: document.getElementById('globe-view').hidden,
            tour: canvas ? canvas.dataset.tour : '',
            phase: canvas ? canvas.dataset.tourPhase : '',
            placeId: canvas ? (canvas.dataset.tourPlaceId || '') : '',
            itemId: canvas ? (canvas.dataset.tourItemId || '') : '',
            camera: camera,
            tourState: tour,
            imageSrc: img && !img.hidden ? (img.currentSrc || img.src || '') : '',
            videoSrc: vid && !vid.hidden ? (vid.currentSrc || vid.src || '') : '',
            videoMuted: vid ? vid.muted === true : null,
            videoPaused: vid ? vid.paused : null,
            videoTime: vid ? vid.currentTime : null,
            mediaHidden: media ? media.hidden : true,
            emptyHidden: empty ? empty.hidden : true,
            emptyText: empty ? (empty.textContent || '') : '',
            playVisible: !!(document.getElementById('globe-play')),
          };
          document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Escape',
            code: 'Escape',
            keyCode: 27,
            which: 27,
            bubbles: true,
            cancelable: true,
          }));
          return snap;
        }"""
    )


def wait_touring(page: Any, on: bool, timeout: int = 10000) -> None:
    wanted = "1" if on else "0"
    page.wait_for_function(
        "wanted => document.getElementById('globe-canvas') && document.getElementById('globe-canvas').dataset.tour === wanted",
        arg=wanted,
        timeout=timeout,
    )


def wait_tour_phase(page: Any, phase: str, timeout: int = 15000) -> None:
    page.wait_for_function(
        """phase => {
          const canvas = document.getElementById('globe-canvas');
          return canvas && canvas.dataset.tour === '1' && canvas.dataset.tourPhase === phase;
        }""",
        arg=phase,
        timeout=timeout,
    )


def open_globe(page: Any, url: str) -> None:
    if page.url.rstrip("/") != url.rstrip("/"):
        page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("#view-globe", timeout=8000)
    page.locator("#view-globe").click()
    wait_globe_ready(page)


def click_play(page: Any) -> None:
    page.locator("#globe-play").click()


def collect_trace(
    page: Any,
    stop_when: Callable[[list[dict[str, Any]], dict[str, Any]], bool],
    timeout: float = 45,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    last: tuple[Any, ...] | None = None
    deadline = time.time() + timeout
    t0 = time.time()
    while time.time() < deadline:
        snap = tour_snapshot(page)
        key = (snap.get("tour"), snap.get("phase"), snap.get("placeId"), snap.get("itemId"), snap.get("mediaHidden"))
        if key != last:
            events.append({"t": round(time.time() - t0, 4), **snap})
            last = key
        elif events:
            prev = events[-1]
            if snap.get("videoTime") is not None:
                prev["videoTime"] = max(prev.get("videoTime") or 0, snap.get("videoTime") or 0)
            if snap.get("videoSrc"):
                prev["videoSrc"] = snap["videoSrc"]
            if snap.get("imageSrc"):
                prev["imageSrc"] = snap["imageSrc"]
            if snap.get("videoMuted") is not None:
                prev["videoMuted"] = snap["videoMuted"]
            if snap.get("camera"):
                prev["cameraEnd"] = snap["camera"]
        if stop_when(events, snap):
            break
        time.sleep(0.04)
    return events


def phase_spans(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for i, event in enumerate(events):
        if event.get("tour") != "1":
            continue
        end = events[i + 1]["t"] if i + 1 < len(events) else event["t"]
        spans.append(
            {
                "phase": event.get("phase"),
                "placeId": event.get("placeId"),
                "itemId": event.get("itemId"),
                "started": event.get("t"),
                "ended": end,
                "durationSec": round(end - event["t"], 4),
                "imageSrc": event.get("imageSrc"),
                "videoSrc": event.get("videoSrc"),
                "videoMuted": event.get("videoMuted"),
                "videoTime": event.get("videoTime"),
            }
        )
    return spans


def save_tour_mp4(page: Any, artifacts: Path, checks: Checks) -> None:
    dest = artifacts / "tour.mp4"
    video = getattr(page, "video", None)
    if video is None:
        checks.check("tour-mp4", False, "no playwright video")
        return
    raw = artifacts / "tour-record.webm"
    try:
        page.close()
        video.save_as(str(raw))
    except Exception as exc:
        checks.check("tour-mp4", False, str(exc))
        return
    if not raw.is_file() or raw.stat().st_size <= 0:
        checks.check("tour-mp4", False, "empty recording")
        return
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 0:
        dest.write_bytes(raw.read_bytes())
    checks.check("tour-mp4", dest.is_file() and dest.stat().st_size > 0, str(dest.stat().st_size if dest.is_file() else 0))


def prove_tour_api(
    checks: Checks,
    base: str,
    items: list[dict[str, Any]],
    artifacts: Path,
    commands: list[str],
) -> dict[str, Any]:
    status, settings = request_json(base + "/api/settings", timeout=5)
    commands.append("GET /api/settings")
    checks.check("settings-http", status == 200 and isinstance(settings, dict), str(status))
    checks.check("tour-orbit-default", (settings or {}).get("tourOrbitSec") == 8, json.dumps(settings))
    checks.check("tour-pictures-default", (settings or {}).get("tourPictures") == 5, json.dumps(settings))
    checks.check("tour-picture-sec-default", (settings or {}).get("tourPictureSec") == 3, json.dumps(settings))

    status, tour = request_json(base + "/api/globe/tour", timeout=5)
    commands.append("GET /api/globe/tour")
    checks.check("tour-http-200", status == 200 and isinstance(tour, list), str(status))
    write_json(artifacts / "tour.json", tour)

    by_name = {item.get("filename"): item for item in items}
    img = by_name.get("IMG_1042.jpg") or {}
    near = by_name.get("near.jpg") or {}
    far = by_name.get("far.jpg") or {}
    clip = by_name.get("clip.mp4") or {}
    no_exif = by_name.get("no-exif.jpg") or {}
    chicago_ids = {img.get("placeId"), near.get("placeId"), clip.get("placeId")}
    checks.check("chicago-same-place", len(chicago_ids) == 1 and None not in chicago_ids, str(chicago_ids))
    chicago_id = next(iter(chicago_ids)) if chicago_ids else ""
    far_id = far.get("placeId")
    checks.check("far-other-place", type(far_id) is str and far_id and far_id != chicago_id, str(far_id))
    checks.check("clip-chicago-place", clip.get("placeId") == img.get("placeId") == chicago_id, str(clip.get("placeId")))
    checks.check("no-exif-no-place", no_exif.get("placeId") in {None, ""}, str(no_exif.get("placeId")))

    fields_ok = True
    for row in tour if isinstance(tour, list) else []:
        if set(row) != {"placeId", "itemIds"}:
            fields_ok = False
        if not isinstance(row.get("itemIds"), list) or not row.get("itemIds"):
            fields_ok = False
    checks.check("tour-fields", fields_ok, json.dumps(tour))
    checks.check("tour-two-places", isinstance(tour, list) and len(tour) == 2, json.dumps(tour))
    place_ids = [row.get("placeId") for row in tour] if isinstance(tour, list) else []
    checks.check("tour-omit-no-exif", no_exif.get("placeId") not in place_ids and no_exif.get("id") not in {
        item_id for row in (tour or []) for item_id in (row.get("itemIds") or [])
    }, json.dumps(place_ids))
    checks.check("tour-place-order", place_ids == [chicago_id, far_id], json.dumps(place_ids))

    chicago_row = next((row for row in tour if row.get("placeId") == chicago_id), {}) if isinstance(tour, list) else {}
    far_row = next((row for row in tour if row.get("placeId") == far_id), {}) if isinstance(tour, list) else {}
    expected_chicago = [clip.get("id"), near.get("id"), img.get("id")]
    checks.check("chicago-items-newest", chicago_row.get("itemIds") == expected_chicago, json.dumps(chicago_row))
    checks.check("far-items-newest", far_row.get("itemIds") == [far.get("id")], json.dumps(far_row))
    cap = (settings or {}).get("tourPictures") or 5
    checks.check(
        "tour-capped",
        all(len(row.get("itemIds") or []) <= cap for row in (tour or [])),
        json.dumps([len(row.get("itemIds") or []) for row in (tour or [])]),
    )

    set_settings(base, {"tourPictures": 2})
    commands.append("PUT /api/settings tourPictures=2")
    status, capped = request_json(base + "/api/globe/tour", timeout=5)
    commands.append("GET /api/globe/tour cap")
    capped_chicago = next((row for row in capped if row.get("placeId") == chicago_id), {}) if isinstance(capped, list) else {}
    checks.check("tour-http-cap", status == 200, str(status))
    checks.check("tour-cap-two", capped_chicago.get("itemIds") == expected_chicago[:2], json.dumps(capped_chicago))
    set_settings(base, {"tourPictures": 5})
    commands.append("PUT /api/settings tourPictures=5")

    status, hidden = request_json(base + "/api/globe/tour?unavailable=0", timeout=5)
    commands.append("GET /api/globe/tour?unavailable=0")
    checks.check(
        "tour-unavailable-0",
        status == 200 and isinstance(hidden, list) and [row.get("placeId") for row in hidden] == place_ids,
        str(status),
    )
    return {
        "tour": tour,
        "chicagoId": chicago_id,
        "farId": far_id,
        "clipId": clip.get("id"),
        "nearId": near.get("id"),
        "imgId": img.get("id"),
        "farItemId": far.get("id"),
    }


def prove_ineligible(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> None:
    folder = copy_rels(media_src, artifacts / "s11-ineligible-media", TOUR_RELS)
    root = fresh_root(artifacts / "s11-ineligible-root")
    scanned = scan_folder(root, folder, commands)
    checks.check("ineligible-scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
    server, url, pids = start_owned(root)
    try:
        items = wait_catalog(url.rstrip("/"), TOUR_NAMES)
        photo = find_item(items, "IMG_1042.jpg") or {}
        near = find_item(items, "near.jpg") or {}
        clip = find_item(items, "clip.mp4") or {}
        preview = (photo.get("renditions") or {}).get("preview")
        preview_path = rendition_file(root, photo, "preview")
        checks.check("ineligible-preview-file", bool(preview_path and preview_path.is_file()), str(preview))
        if preview_path and preview_path.is_file():
            preview_path.unlink()
        status, tour = request_json(url.rstrip("/") + "/api/globe/tour", timeout=5)
        commands.append("GET /api/globe/tour ineligible")
        checks.check("ineligible-http", status == 200 and isinstance(tour, list), str(status))
        chicago = next((row for row in tour if row.get("placeId") == photo.get("placeId")), {}) if isinstance(tour, list) else {}
        ids = chicago.get("itemIds") or []
        checks.check("ineligible-omits-missing-preview", photo.get("id") not in ids, json.dumps(ids))
        checks.check(
            "ineligible-keeps-ready",
            near.get("id") in ids and clip.get("id") in ids,
            json.dumps(ids),
        )
        write_json(artifacts / "ineligible-tour.json", tour)
    finally:
        from tests.qa.s00 import stop_owned

        stop_owned(server, extra_pids=pids)


def prove_empty_play(checks: Checks, artifacts: Path, media_src: Path, commands: list[str]) -> None:
    folder = copy_rels(media_src, artifacts / "s11-empty-media", EMPTY_REL)
    root = fresh_root(artifacts / "s11-empty-root")
    scanned = scan_folder(root, folder, commands)
    checks.check("empty-scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
    server, url, pids = start_owned(root)
    try:
        wait_catalog(url.rstrip("/"), ("no-exif.jpg",))
        status, tour = request_json(url.rstrip("/") + "/api/globe/tour", timeout=5)
        commands.append("GET /api/globe/tour empty")
        checks.check("empty-tour-http", status == 200 and tour == [], json.dumps(tour))
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("empty-playwright", False, str(exc))
            return
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            open_globe(page, url)
            before = tour_snapshot(page)
            click_play(page)
            page.wait_for_timeout(600)
            after = tour_snapshot(page)
            checks.check("empty-play-noop-tour", after.get("tour") == "0", json.dumps(after))
            checks.check(
                "empty-play-camera-still",
                before.get("camera") == after.get("camera"),
                json.dumps({"before": before.get("camera"), "after": after.get("camera")}),
            )
            checks.check(
                "empty-play-message",
                after.get("emptyHidden") is False and after.get("emptyText") == EMPTY_TEXT,
                json.dumps(after),
            )
            checks.check("empty-stays-globe", after.get("view") == "globe" and after.get("globeHidden") is False, json.dumps(after))
            browser.close()
    finally:
        from tests.qa.s00 import stop_owned

        stop_owned(server, extra_pids=pids)


def prove_motion(
    checks: Checks,
    page: Any,
    url: str,
    tour_doc: dict[str, Any],
    artifacts: Path,
) -> list[dict[str, Any]]:
    open_globe(page, url)
    checks.check("globe-play-control", page.locator("#globe-play").is_visible())
    checks.check(
        "play-not-viewer-preview",
        page.evaluate("() => document.getElementById('globe-play') && document.getElementById('play-preview') && document.getElementById('globe-play') !== document.getElementById('play-preview')"),
    )
    click_play(page)
    wait_touring(page, True)
    chicago = tour_doc["chicagoId"]
    far = tour_doc["farId"]
    clip_id = tour_doc["clipId"]

    def stop_when(events: list[dict[str, Any]], snap: dict[str, Any]) -> bool:
        orbits = [event for event in events if event.get("phase") == "orbit" and event.get("tour") == "1"]
        places = []
        for event in events:
            pid = event.get("placeId")
            if pid and pid not in places and event.get("tour") == "1":
                places.append(pid)
        wrapped = len(orbits) >= 3 and any(event.get("placeId") == chicago for event in orbits[2:])
        return wrapped and far in places

    events = collect_trace(page, stop_when, timeout=50)
    spans = phase_spans(events)
    write_json(artifacts / "tour-trace.json", {"events": events, "spans": spans, "settings": {
        "tourOrbitSec": MOTION_ORBIT,
        "tourPictureSec": MOTION_PICTURE,
        "tourPictures": 5,
    }})
    phases = [span["phase"] for span in spans]
    checks.check("trace-has-orbit", "orbit" in phases, json.dumps(phases))
    checks.check("trace-has-ease-in", "ease-in" in phases, json.dumps(phases))
    checks.check("trace-has-media", "media" in phases, json.dumps(phases))
    checks.check("trace-has-ease-out", "ease-out" in phases, json.dumps(phases))
    place_order = []
    for span in spans:
        if span["placeId"] and (not place_order or place_order[-1] != span["placeId"]):
            place_order.append(span["placeId"])
    checks.check("trace-next-place", far in place_order, json.dumps(place_order))
    checks.check(
        "trace-wrap",
        len(place_order) >= 3 and place_order[0] == chicago and place_order[1] == far and place_order[2] == chicago,
        json.dumps(place_order),
    )

    orbit_spans = [span for span in spans if span["phase"] == "orbit"]
    ease_in_spans = [span for span in spans if span["phase"] == "ease-in"]
    ease_out_spans = [span for span in spans if span["phase"] == "ease-out"]
    media_spans = [span for span in spans if span["phase"] == "media"]
    if orbit_spans:
        checks.check(
            "orbit-duration",
            abs(orbit_spans[0]["durationSec"] - MOTION_ORBIT) <= 0.45,
            json.dumps(orbit_spans[0]),
        )
        first = next((event for event in events if event.get("phase") == "orbit"), None)
        end_cam = (first or {}).get("cameraEnd") or (first or {}).get("camera")
        if first and first.get("camera") and end_cam:
            dyaw = abs(yaw_delta(first["camera"]["yawDeg"], end_cam["yawDeg"]))
            rate = dyaw / max(orbit_spans[0]["durationSec"], 0.01)
            checks.check("orbit-6-deg-s", abs(rate - 6) <= 1.2, json.dumps({"dyaw": dyaw, "rate": rate}))
        else:
            checks.check("orbit-6-deg-s", False, "missing camera samples")
    else:
        checks.check("orbit-duration", False, "no orbit")
        checks.check("orbit-6-deg-s", False, "no orbit")
    if ease_in_spans:
        checks.check("ease-in-duration", abs(ease_in_spans[0]["durationSec"] - 1) <= 0.4, json.dumps(ease_in_spans[0]))
    else:
        checks.check("ease-in-duration", False, "no ease-in")
    if ease_out_spans:
        checks.check("ease-out-duration", abs(ease_out_spans[0]["durationSec"] - 1) <= 0.4, json.dumps(ease_out_spans[0]))
    else:
        checks.check("ease-out-duration", False, "no ease-out")

    clip_media = [span for span in media_spans if span.get("itemId") == clip_id]
    checks.check("video-media-present", bool(clip_media), json.dumps([span.get("itemId") for span in media_spans]))
    if clip_media:
        src = clip_media[0].get("videoSrc") or ""
        checks.check("video-uses-proxy", "which=proxy" in src and clip_id in src, src)
        checks.check("video-not-original", "which=original" not in src, src)
        checks.check("video-muted", clip_media[0].get("videoMuted") is True, json.dumps(clip_media[0]))
        vtime = clip_media[0].get("videoTime")
        checks.check(
            "video-timed-not-whole-file",
            vtime is None or vtime <= MOTION_PICTURE + 0.75,
            json.dumps(clip_media[0]),
        )
    any_original = any("which=original" in ((span.get("videoSrc") or "") + (span.get("imageSrc") or "")) for span in spans)
    checks.check("tour-never-original", any_original is False)

    still_media = [span for span in media_spans if span.get("itemId") in {tour_doc["nearId"], tour_doc["imgId"]}]
    if still_media:
        src = still_media[0].get("imageSrc") or ""
        checks.check("still-uses-preview", "which=preview" in src, src)
    else:
        checks.check("still-uses-preview", False, json.dumps([span.get("itemId") for span in media_spans]))
    return events


def prove_esc_and_gestures(checks: Checks, page: Any, url: str, artifacts: Path) -> None:
    open_globe(page, url)
    stopped_camera = None
    for phase in ("orbit", "ease-in", "media", "ease-out"):
        if page.evaluate("() => document.getElementById('globe-canvas').dataset.tour") == "1":
            page.keyboard.press("Escape")
            wait_touring(page, False)
        click_play(page)
        wait_touring(page, True)
        wait_tour_phase(page, phase, timeout=20000)
        before = snapshot_and_escape(page)
        wait_touring(page, False)
        page.wait_for_timeout(250)
        after = tour_snapshot(page)
        checks.check(
            f"esc-{phase}-stops",
            after.get("tour") == "0" and after.get("phase") == "idle",
            json.dumps(after),
        )
        checks.check(
            f"esc-{phase}-stays-globe",
            after.get("view") == "globe" and after.get("globeHidden") is False,
            json.dumps(after),
        )
        checks.check(
            f"esc-{phase}-camera",
            (before.get("camera") or {}) == (after.get("camera") or {}),
            json.dumps({"before": before.get("camera"), "after": after.get("camera")}),
        )
        checks.check(f"esc-{phase}-media-off", after.get("mediaHidden") is True, json.dumps(after))
        stopped_camera = after.get("camera")
    stopped = artifacts / "stopped-globe.png"
    page.screenshot(path=str(stopped), full_page=False)
    width, height = png_size(stopped)
    checks.check("stopped-globe-png", width == 1280 and height == 720, f"{width}x{height}")
    checks.check("stopped-camera-recorded", bool(stopped_camera), json.dumps(stopped_camera))

    click_play(page)
    wait_tour_phase(page, "orbit")
    pick = page.evaluate(
        """() => {
          const canvas = document.getElementById('globe-canvas');
          const r = canvas.getBoundingClientRect();
          for (let row = 3; row <= 7; row += 1) {
            for (let col = 3; col <= 7; col += 1) {
              const x = r.width * (col / 10);
              const y = r.height * (row / 10);
              const got = window.libraryGlobe.pick(x, y);
              if (got && got.hit) {
                return {clientX: r.left + x, clientY: r.top + y};
              }
            }
          }
          return {clientX: r.left + r.width / 2, clientY: r.top + r.height / 2};
        }"""
    )
    before = tour_snapshot(page)
    page.mouse.move(pick["clientX"], pick["clientY"])
    page.mouse.down()
    page.mouse.move(pick["clientX"] + 40, pick["clientY"])
    page.mouse.up()
    page.wait_for_timeout(150)
    after = tour_snapshot(page)
    delta = yaw_delta((before.get("camera") or {}).get("yawDeg", 0), (after.get("camera") or {}).get("yawDeg", 0))
    checks.check("drag-stops-tour", after.get("tour") == "0", json.dumps(after))
    checks.check("drag-applies", abs(abs(delta) / 40 - 0.25) <= 0.05, json.dumps({"delta": delta, "after": after.get("camera")}))

    click_play(page)
    wait_tour_phase(page, "orbit")
    before = tour_snapshot(page)
    page.mouse.move(pick["clientX"], pick["clientY"])
    page.mouse.wheel(0, 120)
    page.wait_for_timeout(160)
    after = tour_snapshot(page)
    checks.check("wheel-stops-tour", after.get("tour") == "0", json.dumps(after))
    checks.check(
        "wheel-applies",
        abs((after.get("camera") or {}).get("distance", 0) - (before.get("camera") or {}).get("distance", 0)) > 0.01,
        json.dumps({"before": before.get("camera"), "after": after.get("camera")}),
    )


def run_session(artifacts: Path, checks: Checks, commands: list[str]) -> dict[str, str]:
    extra = {
        "tour.json": str(artifacts / "tour.json"),
        "tour-trace.json": str(artifacts / "tour-trace.json"),
        "tour.mp4": str(artifacts / "tour.mp4"),
        "stopped-globe.png": str(artifacts / "stopped-globe.png"),
    }
    media_src = prepare_media(artifacts)
    before = hash_tree(media_src)
    folder = copy_rels(media_src, artifacts / "s11-media", TOUR_RELS)
    root = fresh_root(artifacts / "s11-root")
    scanned = scan_folder(root, folder, commands)
    checks.check("scan-exit", scanned["proc"].returncode == 0, scanned["proc"].stderr)
    server, url, pids = start_owned(root)
    try:
        items = wait_catalog(url.rstrip("/"), TOUR_NAMES)
        checks.check("catalog-five", len(items) == 5, str(len(items)))
        clip = find_item(items, "clip.mp4") or {}
        checks.check(
            "clip-proxy-ready",
            ((clip.get("renditions") or {}).get("status") or {}).get("proxy") == "ready",
            json.dumps((clip.get("renditions") or {}).get("status")),
        )
        tour_doc = prove_tour_api(checks, url.rstrip("/"), items, artifacts, commands)
        prove_ineligible(checks, artifacts, media_src, commands)
        set_settings(url.rstrip("/"), {"tourOrbitSec": MOTION_ORBIT, "tourPictureSec": MOTION_PICTURE})
        commands.append("PUT /api/settings tourOrbitSec/tourPictureSec")
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return extra
        checks.check("playwright-import", True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            video_dir = artifacts / "tour-video"
            if video_dir.exists():
                shutil.rmtree(video_dir)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                record_video_dir=str(video_dir),
                record_video_size={"width": 1280, "height": 720},
            )
            page = context.new_page()
            errors = collect_console(page)
            network = capture_network(page)
            prove_motion(checks, page, url, tour_doc, artifacts)
            origin = url.rstrip("/")
            leaks = [blocked_url(rec.get("url") or "", origin) for rec in network]
            leaks = [item for item in leaks if item]
            write_json(artifacts / "offline-network.json", network)
            checks.check("offline-no-external", leaks == [], json.dumps(leaks))
            unexpected = [message for message in errors if "status of 400" not in message]
            checks.check("no-console-errors", unexpected == [], json.dumps(errors))
            save_tour_mp4(page, artifacts, checks)
            context.close()

            page = browser.new_page(viewport={"width": 1280, "height": 720})
            prove_esc_and_gestures(checks, page, url, artifacts)
            page.close()
            browser.close()
    finally:
        from tests.qa.s00 import stop_owned

        stop_owned(server, extra_pids=pids)
    prove_empty_play(checks, artifacts, media_src, commands)
    html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
    checks.check("page-has-globe-play", 'id="globe-play"' in html and "Play" in html)
    checks.check("page-no-view-play", 'id="view-play"' not in html)
    checks.check("page-no-settings", "Settings" not in html and "view-settings" not in html)
    checks.check("original-fixture-bytes", hash_tree(media_src) == before)
    assert_no_pillow_in_server(checks)
    return extra


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(artifacts, checks, commands)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("s11-runner", False, str(exc))
    return write_result("S11", "slice", checks, artifacts, commands, extra)


def run_check_f13(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra: dict[str, str] = {}
    try:
        extra = run_session(artifacts, checks, commands)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("f13-runner", False, str(exc))
    return write_result("F13", "check", checks, artifacts, commands, extra)
