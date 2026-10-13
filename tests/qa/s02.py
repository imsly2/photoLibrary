"""Slice S02 / Check F6 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import piexif
from PIL import Image

from library.media import sha256_file
from tests.qa.probe import metadata_matches, probe_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    copy_committed_fixtures,
    run_library,
    write_isolated_port,
    find_free_port,
)
from tests.qa.s01 import load_items, load_sources, parse_summary

THREE_JPEG = ("a/IMG_1042.jpg", "a/near.jpg", "b/far.jpg")
NO_PLACE = (
    "b/no-exif.jpg",
    "b/created.jpg",
    "b/holiday_20200102.jpg",
    "b/holiday_2020-01-03.jpg",
    "b/oriented.jpg",
)
EXPECTED_CAPTURE = {
    "a/IMG_1042.jpg": ("2024-06-12T15:04:00", "exif"),
    "a/near.jpg": ("2024-06-12T15:05:00", "exif"),
    "b/far.jpg": ("2023-06-12T15:04:00", "exif"),
    "b/no-exif.jpg": ("2022-02-03T04:05:06Z", "mtime"),
    "b/created.jpg": ("2024-07-04T12:00:00", "exif"),
    "b/holiday_20200102.jpg": ("2020-01-02T00:00:00", "filename"),
    "b/holiday_2020-01-03.jpg": ("2020-01-03T00:00:00", "filename"),
    "b/oriented.jpg": ("2024-06-12T15:06:00", "exif"),
    "a/clip.mp4": ("2024-06-12T15:07:00Z", "exif"),
    "live/LIVE_0001.jpg": ("2024-06-13T10:00:00", "exif"),
}
PLACE_ID_RE = re.compile(r"^place_[0-9a-f]{12}$")
OFFSET_ORIGINAL = getattr(piexif.ExifIFD, "OffsetTimeOriginal", 36881)
FRAME = 1.0 / 30.0


def pin_mtime(path: Path, iso: str) -> None:
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def copy_rels(src_media: Path, dest: Path, rels: tuple[str, ...] | list[str]) -> None:
    for rel in rels:
        target = dest / Path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_media / Path(rel), target)


def write_test_jpeg(
    path: Path,
    label: str,
    *,
    datetime_original: str | None = None,
    offset_original: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    mtime: str = "2022-01-01T00:00:00Z",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    color = (40 + digest[0] % 180, 40 + digest[1] % 180, 40 + digest[2] % 180)
    image = Image.new("RGB", (64, 48), color)
    zeroth: dict[int, Any] = {piexif.ImageIFD.Orientation: 1}
    exif: dict[int, Any] = {}
    gps: dict[int, Any] = {}
    if datetime_original:
        exif[piexif.ExifIFD.DateTimeOriginal] = datetime_original.encode("ascii")
    if offset_original:
        exif[OFFSET_ORIGINAL] = offset_original.encode("ascii")
    if latitude is not None and longitude is not None:
        abs_lat = abs(latitude)
        abs_lon = abs(longitude)
        def dms(value: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
            deg = int(value)
            minutes_f = (value - deg) * 60
            minutes = int(minutes_f)
            seconds = (minutes_f - minutes) * 60
            return ((deg, 1), (minutes, 1), (int(round(seconds * 10000)), 10000))

        gps[piexif.GPSIFD.GPSLatitudeRef] = b"N" if latitude >= 0 else b"S"
        gps[piexif.GPSIFD.GPSLatitude] = dms(abs_lat)
        gps[piexif.GPSIFD.GPSLongitudeRef] = b"E" if longitude >= 0 else b"W"
        gps[piexif.GPSIFD.GPSLongitude] = dms(abs_lon)
    payload = piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps})
    image.save(path, format="JPEG", quality=92, exif=payload)
    pin_mtime(path, mtime)


def load_places(root: Path) -> list[dict[str, Any]]:
    folder = root / "catalog" / "places"
    if not folder.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def items_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def item_for_rel(source: dict[str, Any], by_id: dict[str, dict[str, Any]], rel: str) -> dict[str, Any] | None:
    entry = (source.get("files") or {}).get(rel)
    if not entry:
        return None
    return by_id.get(entry.get("itemId"))


def near(got: Any, want: float, tol: float = 1e-4) -> bool:
    try:
        return abs(float(got) - want) <= tol
    except (TypeError, ValueError):
        return False


def duration_ok(got: Any, want: float) -> bool:
    try:
        return abs(float(got) - want) <= FRAME
    except (TypeError, ValueError):
        return False


def snapshot_json_dir(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for path in src.glob("*.json"):
        shutil.copy2(path, dest / path.name)


def parse_items(stdout: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    index = stdout.find("[")
    while index != -1:
        try:
            obj, end = decoder.raw_decode(stdout, index)
        except json.JSONDecodeError:
            index = stdout.find("[", index + 1)
            continue
        if isinstance(obj, list):
            return obj
        index = stdout.find("[", end)
    return []


def no_probe_import(mod: Any) -> bool:
    source = inspect.getsource(mod)
    return "import tests.qa.probe" not in source and "from tests.qa.probe" not in source


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
            "metadata.json": str(artifacts / "metadata.json"),
            "items": str(artifacts / "items"),
            "places": str(artifacts / "places"),
            "extraction-dumps": str(artifacts / "extraction-dumps"),
        },
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1


def run_proofs(root: Path, artifacts: Path, ident: str, kind: str) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    import library.metadata as lib_metadata
    import library.places as lib_places
    import library.scan as lib_scan

    checks.check("library-metadata-no-probe", no_probe_import(lib_metadata))
    checks.check("library-places-no-probe", no_probe_import(lib_places))
    checks.check("library-scan-no-probe", no_probe_import(lib_scan))

    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"

    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    write_isolated_port(isolated, find_free_port())

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
    places = load_places(isolated)
    checks.check("one-source", len(sources) == 1, str(len(sources)))
    source = sources[0] if sources else {}
    by_id = items_by_id(items)

    dumps = artifacts / "extraction-dumps"
    dumps.mkdir(parents=True, exist_ok=True)
    meta_out: dict[str, Any] = {}

    for rel, (captured, cap_source) in EXPECTED_CAPTURE.items():
        item = item_for_rel(source, by_id, rel)
        if rel == "live/LIVE_0001.jpg" and item is None:
            item = next((i for i in items if i.get("filename") == "LIVE_0001.jpg"), None)
        checks.check(f"item-present:{rel}", item is not None)
        if item is None:
            continue
        checks.check(
            f"capturedAt:{rel}",
            item.get("capturedAt") == captured,
            f"{item.get('capturedAt')!r} != {captured!r}",
        )
        checks.check(
            f"capturedAtSource:{rel}",
            item.get("capturedAtSource") == cap_source,
            str(item.get("capturedAtSource")),
        )
        md = item.get("metadata") or {}
        probe = probe_file(media / Path(rel))
        (dumps / (rel.replace("/", "__") + ".json")).write_text(
            json.dumps(probe, indent=2) + "\n", encoding="utf-8"
        )
        expected_view = {
            "width": probe.get("width"),
            "height": probe.get("height"),
            "orientation": probe.get("orientation"),
            "durationSec": probe.get("durationSec"),
            "latitude": probe.get("latitude"),
            "longitude": probe.get("longitude"),
        }
        actual_view = {key: md.get(key) for key in expected_view}
        problems = metadata_matches(expected_view, actual_view)
        checks.check(f"metadata:{rel}", problems == [], str(problems))
        checks.check(f"camera-null:{rel}", md.get("camera") is None)
        checks.check(f"lens-null:{rel}", md.get("lens") is None)
        meta_out[rel] = {
            "id": item.get("id"),
            "capturedAt": item.get("capturedAt"),
            "capturedAtSource": item.get("capturedAtSource"),
            "placeId": item.get("placeId"),
            "metadata": md,
        }

    oriented = item_for_rel(source, by_id, "b/oriented.jpg")
    if oriented:
        md = oriented.get("metadata") or {}
        checks.check("oriented-width", md.get("width") == 640, str(md.get("width")))
        checks.check("oriented-height", md.get("height") == 480, str(md.get("height")))
        checks.check("oriented-orientation", md.get("orientation") == 6, str(md.get("orientation")))

    clip = item_for_rel(source, by_id, "a/clip.mp4")
    if clip:
        checks.check("clip-duration", duration_ok((clip.get("metadata") or {}).get("durationSec"), 2.0))
        checks.check(
            "clip-gps",
            near((clip.get("metadata") or {}).get("latitude"), 41.88)
            and near((clip.get("metadata") or {}).get("longitude"), -87.63),
            str(clip.get("metadata")),
        )

    img = item_for_rel(source, by_id, "a/IMG_1042.jpg")
    near_item = item_for_rel(source, by_id, "a/near.jpg")
    far_item = item_for_rel(source, by_id, "b/far.jpg")
    clip_item = item_for_rel(source, by_id, "a/clip.mp4")
    checks.check("img-source-exif", bool(img) and img.get("capturedAtSource") == "exif")
    if img and near_item and far_item:
        checks.check("img-place-id-shape", bool(PLACE_ID_RE.match(str(img.get("placeId") or ""))))
        checks.check("near-same-place", near_item.get("placeId") == img.get("placeId"))
        checks.check("far-different-place", far_item.get("placeId") != img.get("placeId"))
        checks.check("far-place-id-shape", bool(PLACE_ID_RE.match(str(far_item.get("placeId") or ""))))
        if clip_item:
            checks.check("clip-joins-img-place", clip_item.get("placeId") == img.get("placeId"))
        img_place = next((p for p in places if p.get("id") == img.get("placeId")), None)
        far_place = next((p for p in places if p.get("id") == far_item.get("placeId")), None)
        checks.check("img-place-present", img_place is not None)
        checks.check("far-place-present", far_place is not None)
        if img_place:
            checks.check("img-place-name-null", img_place.get("name") is None)
            checks.check(
                "img-place-coords",
                near(img_place.get("latitude"), 41.88) and near(img_place.get("longitude"), -87.63),
                str(img_place),
            )
        if far_place:
            checks.check("far-place-name-null", far_place.get("name") is None)
            checks.check(
                "far-place-coords",
                near(far_place.get("latitude"), 41.925) and near(far_place.get("longitude"), -87.63),
                str(far_place),
            )
    for rel in NO_PLACE:
        item = item_for_rel(source, by_id, rel)
        checks.check(f"no-place:{rel}", item is not None and item.get("placeId") is None)

    snapshot_json_dir(isolated / "catalog" / "items", artifacts / "items")
    snapshot_json_dir(isolated / "catalog" / "places", artifacts / "places")
    (artifacts / "metadata.json").write_text(json.dumps(meta_out, indent=2) + "\n", encoding="utf-8")

    before_places = {p["id"]: p for p in places}
    before_capture = {item["id"]: (item.get("capturedAt"), item.get("placeId")) for item in items}
    second = run_library(isolated, ["scan", str(media), "--serve-from-there"], timeout=300)
    commands.append("python -m library scan <media> --serve-from-there #2")
    summary2 = parse_summary(second.stdout) if second.stdout.strip() else {}
    checks.check("rescan-added-0", summary2.get("added") == 0, str(summary2.get("added")))
    checks.check(
        "rescan-skipped",
        isinstance(summary2.get("skipped"), int) and summary2.get("skipped", 0) > 0,
        str(summary2.get("skipped")),
    )
    after_items = load_items(isolated)
    after_places = load_places(isolated)
    after_capture = {item["id"]: (item.get("capturedAt"), item.get("placeId")) for item in after_items}
    checks.check("rescan-keeps-capture", before_capture == after_capture)
    checks.check(
        "rescan-keeps-places",
        {p["id"]: p for p in after_places} == before_places,
    )

    subset_media = artifacts / "three-jpeg-media"
    if subset_media.exists():
        shutil.rmtree(subset_media)
    copy_rels(media, subset_media, THREE_JPEG)
    subset_root = artifacts / "three-jpeg-library-data"
    if subset_root.exists():
        shutil.rmtree(subset_root)
    prepare_root(subset_root)
    write_isolated_port(subset_root, find_free_port())
    subset_scan = run_library(
        subset_root, ["scan", str(subset_media), "--serve-from-there"], timeout=120
    )
    commands.append("python -m library scan <three-jpeg> --serve-from-there")
    subset_summary = parse_summary(subset_scan.stdout) if subset_scan.stdout.strip() else {}
    checks.check(
        "subset-scan-ok",
        subset_scan.returncode == 0 and subset_summary.get("added") == 3,
        f"exit={subset_scan.returncode} {subset_summary}",
    )
    subset_source = (load_sources(subset_root) or [{}])[0]
    subset_items = load_items(subset_root)
    subset_places = load_places(subset_root)
    subset_by_id = items_by_id(subset_items)
    checks.check("subset-two-places", len(subset_places) == 2, str(len(subset_places)))
    s_img = item_for_rel(subset_source, subset_by_id, "a/IMG_1042.jpg")
    s_near = item_for_rel(subset_source, subset_by_id, "a/near.jpg")
    s_far = item_for_rel(subset_source, subset_by_id, "b/far.jpg")
    if s_img and s_near and s_far:
        checks.check("subset-near-same-place", s_near.get("placeId") == s_img.get("placeId"))
        checks.check("subset-far-other-place", s_far.get("placeId") != s_img.get("placeId"))
        shared = next((p for p in subset_places if p.get("id") == s_img.get("placeId")), None)
        checks.check(
            "subset-shared-seed-coords",
            shared is not None
            and near(shared.get("latitude"), 41.88)
            and near(shared.get("longitude"), -87.63),
            str(shared),
        )
        if shared:
            checks.check("subset-shared-name-null", shared.get("name") is None)

    edge_media = artifacts / "date-edge-media"
    if edge_media.exists():
        shutil.rmtree(edge_media)
    edge_media.mkdir(parents=True)
    write_test_jpeg(
        edge_media / "offset.jpg",
        "offset",
        datetime_original="2024:06:12 15:04:00",
        offset_original="-05:00",
    )
    write_test_jpeg(edge_media / "left_20200102_2021-03-04.jpg", "two-dates")
    write_test_jpeg(
        edge_media / "bad_20201332.jpg",
        "invalid-date",
        mtime="2022-03-04T05:06:07Z",
    )
    tie_first = edge_media / "tie-first.tmp.jpg"
    tie_second = edge_media / "tie-second.tmp.jpg"
    write_test_jpeg(
        tie_first,
        "tie-a",
        datetime_original="2024:09:01 08:00:00",
    )
    write_test_jpeg(
        tie_second,
        "tie-b",
        datetime_original="2024:09:01 08:00:00",
    )
    tie_by_hash = sorted(
        ((sha256_file(path), path) for path in (tie_first, tie_second)),
        key=lambda pair: pair[0],
    )
    tie_by_hash[0][1].rename(edge_media / "tie-z.jpg")
    tie_by_hash[1][1].rename(edge_media / "tie-a.jpg")
    edge_root = artifacts / "date-edge-library-data"
    if edge_root.exists():
        shutil.rmtree(edge_root)
    prepare_root(edge_root)
    write_isolated_port(edge_root, find_free_port())
    edge_scan = run_library(edge_root, ["scan", str(edge_media), "--serve-from-there"], timeout=120)
    commands.append("python -m library scan <date-edge> --serve-from-there")
    checks.check("edge-scan-ok", edge_scan.returncode == 0, edge_scan.stderr)
    edge_source = (load_sources(edge_root) or [{}])[0]
    edge_by_id = items_by_id(load_items(edge_root))
    offset_item = item_for_rel(edge_source, edge_by_id, "offset.jpg")
    two_item = item_for_rel(edge_source, edge_by_id, "left_20200102_2021-03-04.jpg")
    bad_item = item_for_rel(edge_source, edge_by_id, "bad_20201332.jpg")
    checks.check(
        "offset-utc",
        bool(offset_item)
        and offset_item.get("capturedAt") == "2024-06-12T20:04:00Z"
        and offset_item.get("capturedAtSource") == "exif",
        str(offset_item),
    )
    checks.check(
        "filename-leftmost",
        bool(two_item)
        and two_item.get("capturedAt") == "2020-01-02T00:00:00"
        and two_item.get("capturedAtSource") == "filename",
        str(two_item),
    )
    checks.check(
        "invalid-filename-mtime",
        bool(bad_item)
        and bad_item.get("capturedAt") == "2022-03-04T05:06:07Z"
        and bad_item.get("capturedAtSource") == "mtime",
        str(bad_item),
    )
    listed = run_library(edge_root, ["items", "--sort", "date", "--dir", "asc"], timeout=60)
    commands.append("python -m library items --sort date --dir asc")
    payload = parse_items(listed.stdout)
    ties = [item for item in payload if item.get("filename") in {"tie-a.jpg", "tie-z.jpg"}]
    checks.check("tie-pair", len(ties) == 2, str([t.get("filename") for t in ties]))
    if len(ties) == 2:
        checks.check("tie-same-capturedAt", ties[0].get("capturedAt") == ties[1].get("capturedAt"))
        checks.check(
            "tie-lower-id-first",
            ties[0].get("filename") == "tie-z.jpg"
            and ties[1].get("filename") == "tie-a.jpg"
            and ties[0].get("id") < ties[1].get("id"),
            f"{ties[0].get('filename')}:{ties[0].get('id')} then {ties[1].get('filename')}:{ties[1].get('id')}",
        )

    changed_media = artifacts / "changed-media"
    if changed_media.exists():
        shutil.rmtree(changed_media)
    changed_media.mkdir(parents=True)
    first_path = changed_media / "shot.jpg"
    write_test_jpeg(first_path, "changed-before", datetime_original="2024:01:01 00:00:00")
    changed_root = artifacts / "changed-library-data"
    if changed_root.exists():
        shutil.rmtree(changed_root)
    prepare_root(changed_root)
    write_isolated_port(changed_root, find_free_port())
    first_changed = run_library(
        changed_root, ["scan", str(changed_media), "--serve-from-there"], timeout=60
    )
    commands.append("python -m library scan <changed> --serve-from-there")
    checks.check("changed-first-ok", first_changed.returncode == 0, first_changed.stderr)
    old_item = (load_items(changed_root) or [None])[0]
    old_id = old_item.get("id") if old_item else None
    old_captured = old_item.get("capturedAt") if old_item else None
    write_test_jpeg(
        first_path,
        "changed-after",
        datetime_original="2024:08:08 08:08:08",
        mtime="2022-04-05T06:07:08Z",
    )
    second_changed = run_library(
        changed_root, ["scan", str(changed_media), "--serve-from-there"], timeout=60
    )
    commands.append("python -m library scan <changed> --serve-from-there #2")
    changed_summary = parse_summary(second_changed.stdout) if second_changed.stdout.strip() else {}
    checks.check("changed-rescan-added", changed_summary.get("added") == 1, str(changed_summary))
    changed_items = load_items(changed_root)
    changed_source = (load_sources(changed_root) or [{}])[0]
    new_item = item_for_rel(changed_source, items_by_id(changed_items), "shot.jpg")
    kept = next((item for item in changed_items if item.get("id") == old_id), None)
    checks.check("changed-old-kept", kept is not None and kept.get("capturedAt") == old_captured)
    checks.check(
        "changed-new-metadata",
        new_item is not None
        and new_item.get("id") != old_id
        and new_item.get("capturedAt") == "2024-08-08T08:08:08"
        and new_item.get("capturedAtSource") == "exif",
        str(new_item),
    )

    return write_result(ident, kind, checks, artifacts, commands)


def run_slice(root: Path, artifacts: Path) -> int:
    return run_proofs(root, artifacts, "S02", "slice")


def run_check(root: Path, artifacts: Path) -> int:
    return run_proofs(root, artifacts, "F6", "check")
