"""Independent metadata reader. Does not import generator write functions."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APPLE_XMP_NS = "http://ns.apple.com/exif/1.0/"
CONTENT_ID_RE = re.compile(
    r"ContentIdentifier(?:\s*=\s*\"([^\"]+)\"|>\s*([^<]+)<)",
    re.IGNORECASE,
)
ISO6709_RE = re.compile(
    r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)\/$"
)
VALID_HEIF_BRANDS = frozenset({"heic", "heix", "heif", "mif1"})
STILL_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp"}
HEIF_SUFFIXES = {".heic", ".heif"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mtime_utc(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_ftyp_brands(data: bytes) -> list[str]:
    index = data.find(b"ftyp")
    if index < 4:
        return []
    size = int.from_bytes(data[index - 4 : index], "big")
    box = data[index - 4 : index - 4 + size] if size >= 16 else data[index - 4 : index + 32]
    if len(box) < 16:
        return []
    brands = [box[8:12].decode("ascii", "replace")]
    compatible = box[16:]
    for offset in range(0, len(compatible) - 3, 4):
        brands.append(compatible[offset : offset + 4].decode("ascii", "replace"))
    return brands


def jpeg_xmp_content_identifier(data: bytes) -> str | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    if APPLE_XMP_NS.encode("ascii") not in data:
        return None
    # Search the XMP packet only.
    start = data.find(b"<x:xmpmeta")
    end = data.find(b"</x:xmpmeta>")
    if start < 0 or end < start:
        blob = data
    else:
        blob = data[start : end + len(b"</x:xmpmeta>")]
    text = blob.decode("utf-8", "replace")
    if APPLE_XMP_NS not in text:
        return None
    match = CONTENT_ID_RE.search(text)
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


def _gps_to_deg(values: Any, ref: Any) -> float | None:
    if not values:
        return None
    parts = []
    for item in values:
        if hasattr(item, "numerator"):
            parts.append(item.numerator / item.denominator)
        elif isinstance(item, tuple) and len(item) == 2:
            parts.append(item[0] / item[1] if item[1] else 0.0)
        else:
            parts.append(float(item))
    if len(parts) < 3:
        return None
    deg = parts[0] + parts[1] / 60.0 + parts[2] / 3600.0
    text = ref.decode("ascii") if isinstance(ref, (bytes, bytearray)) else str(ref)
    if text in {"S", "W"}:
        deg = -deg
    return deg


def _probe_still_pillow(path: Path) -> dict[str, Any]:
    from PIL import Image
    from PIL.ExifTags import Base

    with Image.open(path) as image:
        width, height = image.size
        exif = image.getexif()
        orientation = exif.get(int(Base.Orientation))
        captured = None
        captured_source = None
        try:
            exif_ifd = exif.get_ifd(int(Base.ExifOffset))
        except Exception:
            exif_ifd = {}
        original = exif_ifd.get(int(Base.DateTimeOriginal)) if exif_ifd else None
        digitized = exif_ifd.get(int(Base.DateTimeDigitized)) if exif_ifd else None
        if isinstance(original, bytes):
            original = original.decode("ascii", "replace")
        if isinstance(digitized, bytes):
            digitized = digitized.decode("ascii", "replace")
        if original:
            captured = original
            captured_source = "exif"
        elif digitized:
            captured = digitized
            captured_source = "exif"
        latitude = None
        longitude = None
        try:
            gps = exif.get_ifd(int(Base.GPSInfo))
        except Exception:
            gps = {}
        if gps:
            latitude = _gps_to_deg(gps.get(2), gps.get(1))
            longitude = _gps_to_deg(gps.get(4), gps.get(3))
        return {
            "kind": "photo",
            "width": width,
            "height": height,
            "orientation": orientation,
            "durationSec": None,
            "hasAudio": None,
            "capturedAt": captured,
            "capturedAtSource": captured_source,
            "latitude": latitude,
            "longitude": longitude,
            "contentIdentifier": jpeg_xmp_content_identifier(path.read_bytes())
            if path.suffix.lower() in {".jpg", ".jpeg"}
            else None,
        }


def _ffprobe(path: Path) -> dict[str, Any]:
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
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe-failed")
    return json.loads(proc.stdout)


def _parse_iso6709(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    match = ISO6709_RE.match(value.strip())
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _probe_video(path: Path) -> dict[str, Any]:
    data = _ffprobe(path)
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format") or {}
    tags = dict(fmt.get("tags") or {})
    if video:
        tags.update(video.get("tags") or {})
    duration = fmt.get("duration")
    duration_sec = float(duration) if duration is not None else None
    captured = tags.get("com.apple.quicktime.creationdate") or None
    if not captured:
        raw_ctime = tags.get("creation_time")
        if isinstance(raw_ctime, str) and "T" in raw_ctime:
            captured = raw_ctime.split(";")[0]
            if captured.endswith(".000000Z"):
                captured = captured[: -len(".000000Z")] + "Z"
    captured_source = "exif" if captured else None
    lat, lon = _parse_iso6709(tags.get("com.apple.quicktime.location.ISO6709"))
    content_id = tags.get("com.apple.quicktime.content.identifier")
    return {
        "kind": "video",
        "width": int(video["width"]) if video and video.get("width") else None,
        "height": int(video["height"]) if video and video.get("height") else None,
        "orientation": None,
        "durationSec": duration_sec,
        "hasAudio": bool(audio),
        "capturedAt": captured,
        "capturedAtSource": captured_source,
        "latitude": lat,
        "longitude": lon,
        "contentIdentifier": content_id,
        "tags": tags,
    }


def _probe_heif(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    brands = read_ftyp_brands(data)
    valid_brand = any(brand.strip() in VALID_HEIF_BRANDS for brand in brands)
    jpeg = data.startswith(b"\xff\xd8\xff")
    meta = {
        "kind": "photo",
        "width": None,
        "height": None,
        "orientation": None,
        "durationSec": None,
        "hasAudio": None,
        "capturedAt": None,
        "capturedAtSource": None,
        "latitude": None,
        "longitude": None,
        "contentIdentifier": None,
        "ftypBrands": brands,
        "validHeifBrand": valid_brand,
        "isJpeg": jpeg,
        "validImage": False,
    }
    try:
        probed = _ffprobe(path)
        streams = probed.get("streams") or []
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video and video.get("width") and video.get("height"):
            meta["width"] = int(video["width"])
            meta["height"] = int(video["height"])
            meta["validImage"] = valid_brand and not jpeg
            if not meta["validImage"]:
                meta["kind"] = None
        else:
            meta["kind"] = None
    except Exception as exc:
        meta["ffprobeError"] = str(exc)
        meta["kind"] = None
    if not meta.get("validImage"):
        meta["kind"] = None
    return meta


def probe_file(path: Path) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.lower()
    extraction: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256_file(path),
        "sizeBytes": path.stat().st_size,
        "mtime": mtime_utc(path),
    }
    if suffix in HEIF_SUFFIXES:
        extraction.update(_probe_heif(path))
        return extraction
    if suffix in VIDEO_SUFFIXES:
        extraction.update(_probe_video(path))
        extraction["validImage"] = True
        return extraction
    if suffix in STILL_SUFFIXES:
        try:
            extraction.update(_probe_still_pillow(path))
            extraction["validImage"] = True
        except Exception as exc:
            extraction["validImage"] = False
            extraction["error"] = str(exc)
        if suffix in {".jpg", ".jpeg"}:
            extraction["contentIdentifier"] = jpeg_xmp_content_identifier(path.read_bytes())
            if "kind" not in extraction:
                extraction["kind"] = "photo"
        return extraction
    extraction["validImage"] = False
    extraction["kind"] = None
    return extraction


def expected_view(extraction: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "kind",
        "width",
        "height",
        "orientation",
        "durationSec",
        "hasAudio",
        "capturedAt",
        "capturedAtSource",
        "latitude",
        "longitude",
        "contentIdentifier",
    )
    return {key: extraction.get(key) for key in keys}


def metadata_matches(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Return mismatch descriptions. Duration allows one 30 fps frame."""
    problems: list[str] = []
    frame = 1.0 / 30.0
    for key, want in expected.items():
        got = actual.get(key)
        if key == "durationSec":
            if want is None:
                if got is not None:
                    problems.append(f"{key}: expected null got {got}")
                continue
            if got is None or abs(float(got) - float(want)) > frame:
                problems.append(f"{key}: expected {want}±{frame} got {got}")
            continue
        if key in {"latitude", "longitude"}:
            if want is None:
                if got is not None:
                    problems.append(f"{key}: expected null got {got}")
                continue
            if got is None or abs(float(got) - float(want)) > 1e-4:
                problems.append(f"{key}: expected {want} got {got}")
            continue
        if want != got:
            problems.append(f"{key}: expected {want!r} got {got!r}")
    return problems
