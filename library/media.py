"""Byte identity, allowed extensions, and embedded content identifiers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from library.errors import fail

PHOTO_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}
)
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"})
ALLOWED_SUFFIXES = PHOTO_SUFFIXES | VIDEO_SUFFIXES
HEIF_SUFFIXES = frozenset({".heic", ".heif"})
VALID_HEIF_BRANDS = frozenset({"heic", "heix", "heif", "mif1"})

APPLE_XMP_NS = "http://ns.apple.com/exif/1.0/"
CONTENT_ID_RE = re.compile(
    r"ContentIdentifier(?:\s*=\s*\"([^\"]+)\"|>\s*([^<]+)<)",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mtime_iso(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def file_suffix(path: Path) -> str:
    return path.suffix.lower()


def is_allowed_media(path: Path) -> bool:
    return file_suffix(path) in ALLOWED_SUFFIXES


def media_kind(path: Path) -> str:
    suffix = file_suffix(path)
    if suffix in PHOTO_SUFFIXES:
        return "photo"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    raise fail("invalid-argument")


def default_component(kind: str) -> str:
    if kind == "video":
        return "motion"
    return "still"


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


def heif_has_valid_brand(path: Path) -> bool:
    data = path.read_bytes()[: 256 * 1024]
    brands = read_ftyp_brands(data)
    return any(brand.strip() in VALID_HEIF_BRANDS for brand in brands)


def ffprobe_json(path: Path) -> dict[str, Any] | None:
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
        return None
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None


def ffprobe_tags(payload: dict[str, Any]) -> dict[str, Any]:
    tags: dict[str, Any] = dict((payload.get("format") or {}).get("tags") or {})
    for stream in payload.get("streams") or []:
        tags.update(stream.get("tags") or {})
    return tags


def video_content_identifier(path: Path) -> str | None:
    payload = ffprobe_json(path)
    if payload is None:
        return None
    value = ffprobe_tags(payload).get("com.apple.quicktime.content.identifier")
    if type(value) is str and value.strip():
        return value.strip()
    return None


def read_content_identifier(path: Path) -> str | None:
    suffix = file_suffix(path)
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_xmp_content_identifier(path.read_bytes())
    if suffix in VIDEO_SUFFIXES:
        return video_content_identifier(path)
    return None
