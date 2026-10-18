"""Library-owned capture metadata. Independent of the QA stills reader."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from library.media import (
    HEIF_SUFFIXES,
    PHOTO_SUFFIXES,
    VIDEO_SUFFIXES,
    ffprobe_json,
    ffprobe_tags,
    file_suffix,
    heif_has_valid_brand,
)
from library.records import empty_metadata, read_metadata

ISO6709_RE = re.compile(
    r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)\/$"
)
EXIF_DT_RE = re.compile(
    r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$"
)
OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")
DASHED_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
COMPACT_DATE_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")


def mtime_captured_at(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        text = value.decode("ascii", "replace").strip()
        return text or None
    if type(value) is str:
        text = value.strip()
        return text or None
    return str(value).strip() or None


def _int_in_range(value: Any, lo: int, hi: int) -> int | None:
    if type(value) is bool or not isinstance(value, (int, float)):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
    number = int(value)
    if number < lo or number > hi:
        return None
    return number


def valid_gregorian(year: int, month: int, day: int) -> bool:
    try:
        datetime(year, month, day)
    except ValueError:
        return False
    return True


def parse_exif_datetime(raw: str | None, offset: str | None) -> str | None:
    text = _text(raw)
    if text is None:
        return None
    match = EXIF_DT_RE.match(text)
    if not match:
        return None
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    zone = _text(offset)
    if zone is None or zone == "Z":
        if zone == "Z":
            return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    off = OFFSET_RE.match(zone)
    if not off:
        return None
    sign, hours, minutes = off.group(1), int(off.group(2)), int(off.group(3))
    if hours > 14 or minutes > 59:
        return None
    delta = timedelta(hours=hours, minutes=minutes)
    if sign == "-":
        delta = -delta
    aware = dt.replace(tzinfo=timezone(delta))
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_instant(raw: str | None) -> str | None:
    text = _text(raw)
    if text is None:
        return None
    text = text.split(";")[0].strip()
    text = re.sub(r"\.\d+(?=Z$)", "", text)
    text = re.sub(r"\.\d+(?=[+-]\d{2}:\d{2}$)", "", text)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%dT%H:%M:%S")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def filename_captured_at(name: str) -> str | None:
    found: list[tuple[int, int, int, int]] = []
    for match in DASHED_DATE_RE.finditer(name):
        found.append(
            (match.start(), int(match.group(1)), int(match.group(2)), int(match.group(3)))
        )
    for match in COMPACT_DATE_RE.finditer(name):
        raw = match.group(1)
        found.append((match.start(), int(raw[:4]), int(raw[4:6]), int(raw[6:8])))
    found.sort(key=lambda item: item[0])
    for _start, year, month, day in found:
        if valid_gregorian(year, month, day):
            return f"{year:04d}-{month:02d}-{day:02d}T00:00:00"
    return None


def _gps_to_deg(values: Any, ref: Any) -> float | None:
    if not values:
        return None
    parts = []
    for item in values:
        try:
            parts.append(float(item))
        except (TypeError, ValueError):
            return None
    if len(parts) < 3:
        return None
    deg = parts[0] + parts[1] / 60.0 + parts[2] / 3600.0
    text = _text(ref) or ""
    if text in {"S", "W"}:
        deg = -deg
    return deg


def parse_iso6709(value: str | None) -> tuple[float | None, float | None]:
    text = _text(value)
    if text is None:
        return None, None
    match = ISO6709_RE.match(text)
    if not match:
        return None, None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None, None
    return lat, lon


def _join_name(*parts: str | None) -> str | None:
    cleaned = [part for part in (_text(p) for p in parts) if part]
    if not cleaned:
        return None
    if len(cleaned) == 2 and cleaned[1].startswith(cleaned[0]):
        return cleaned[1]
    return " ".join(cleaned)


JPEG_SOF = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
TIFF_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
TAG_ORIENTATION = 0x0112
TAG_MAKE = 0x010F
TAG_MODEL = 0x0110
TAG_EXIF_IFD = 0x8769
TAG_GPS_IFD = 0x8825
TAG_DATETIME_ORIGINAL = 0x9003
TAG_DATETIME_DIGITIZED = 0x9004
TAG_OFFSET_ORIGINAL = 0x9011
TAG_OFFSET_DIGITIZED = 0x9012
TAG_LENS_MAKE = 0xA433
TAG_LENS_MODEL = 0xA434


def _u16(data: bytes, offset: int, endian: str) -> int:
    return int.from_bytes(data[offset : offset + 2], endian)


def _u32(data: bytes, offset: int, endian: str) -> int:
    return int.from_bytes(data[offset : offset + 4], endian)


def _iter_jpeg_segments(data: bytes):
    if not data.startswith(b"\xff\xd8"):
        return
    index = 2
    length = len(data)
    while index + 4 <= length:
        if data[index] != 0xFF:
            return
        marker = data[index + 1]
        if marker == 0xDA:
            return
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            index += 2
            continue
        seglen = int.from_bytes(data[index + 2 : index + 4], "big")
        if seglen < 2 or index + 2 + seglen > length:
            return
        yield marker, data[index + 4 : index + 2 + seglen]
        index += 2 + seglen


def _jpeg_size_and_exif(data: bytes) -> tuple[int | None, int | None, bytes | None]:
    width = None
    height = None
    tiff = None
    for marker, payload in _iter_jpeg_segments(data):
        if marker in JPEG_SOF and len(payload) >= 5:
            height = int.from_bytes(payload[1:3], "big") or None
            width = int.from_bytes(payload[3:5], "big") or None
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00") and tiff is None:
            tiff = payload[6:]
    return width, height, tiff


def _tiff_entry(tiff: bytes, offset: int, endian: str) -> Any:
    typ = _u16(tiff, offset + 2, endian)
    count = _u32(tiff, offset + 4, endian)
    unit = TIFF_TYPE_SIZE.get(typ)
    if unit is None or count > 1_000_000:
        return None
    size = unit * count
    inline = offset + 8
    if size <= 4:
        raw = tiff[inline : inline + size]
    else:
        ptr = _u32(tiff, inline, endian)
        if ptr + size > len(tiff):
            return None
        raw = tiff[ptr : ptr + size]
    if len(raw) < size:
        return None
    signed = typ in {9, 10}
    if typ == 2:
        return raw.split(b"\x00", 1)[0].decode("ascii", "replace")
    if typ in {1, 7}:
        return raw
    if typ in {3, 4, 9}:
        values = [
            int.from_bytes(raw[i : i + unit], endian, signed=signed)
            for i in range(0, size, unit)
        ]
        return values[0] if count == 1 else values
    if typ in {5, 10}:
        values = []
        for i in range(0, size, 8):
            num = int.from_bytes(raw[i : i + 4], endian, signed=signed)
            den = int.from_bytes(raw[i + 4 : i + 8], endian, signed=signed)
            values.append(num / den if den else 0.0)
        return values
    return None


def _read_ifd(tiff: bytes, offset: int, endian: str) -> dict[int, Any]:
    if offset + 2 > len(tiff):
        return {}
    count = _u16(tiff, offset, endian)
    out: dict[int, Any] = {}
    for index in range(count):
        entry = offset + 2 + index * 12
        if entry + 12 > len(tiff):
            break
        tag = _u16(tiff, entry, endian)
        out[tag] = _tiff_entry(tiff, entry, endian)
    return out


def _parse_tiff(tiff: bytes) -> dict[str, Any]:
    if len(tiff) < 8 or tiff[:2] not in {b"II", b"MM"}:
        return {}
    endian = "little" if tiff[:2] == b"II" else "big"
    if _u16(tiff, 2, endian) != 42:
        return {}
    ifd0 = _read_ifd(tiff, _u32(tiff, 4, endian), endian)
    exif = {}
    gps = {}
    exif_off = _ifd_offset(ifd0.get(TAG_EXIF_IFD))
    gps_off = _ifd_offset(ifd0.get(TAG_GPS_IFD))
    if exif_off is not None:
        exif = _read_ifd(tiff, exif_off, endian)
    if gps_off is not None:
        gps = _read_ifd(tiff, gps_off, endian)
    return {"ifd0": ifd0, "exif": exif, "gps": gps}


def _apply_gps(meta: dict[str, Any], gps: dict[int, Any]) -> None:
    latitude = _gps_to_deg(gps.get(2), gps.get(1))
    longitude = _gps_to_deg(gps.get(4), gps.get(3))
    if latitude is not None and not (-90 <= latitude <= 90):
        latitude = None
    if longitude is not None and not (-180 <= longitude <= 180):
        longitude = None
    if latitude is not None and longitude is not None:
        meta["latitude"] = latitude
        meta["longitude"] = longitude


def _still_from_jpeg(path: Path, data: bytes | None = None) -> dict[str, Any]:
    meta = empty_metadata()
    if data is None:
        data = path.read_bytes()
    width, height, tiff = _jpeg_size_and_exif(data)
    if width is not None:
        meta["width"] = width
    if height is not None:
        meta["height"] = height
    captured = None
    parsed = _parse_tiff(tiff) if tiff else {}
    ifd0 = parsed.get("ifd0") or {}
    exif = parsed.get("exif") or {}
    gps = parsed.get("gps") or {}
    meta["orientation"] = _int_in_range(ifd0.get(TAG_ORIENTATION), 1, 8)
    meta["camera"] = _join_name(_text(ifd0.get(TAG_MAKE)), _text(ifd0.get(TAG_MODEL)))
    meta["lens"] = _join_name(_text(exif.get(TAG_LENS_MAKE)), _text(exif.get(TAG_LENS_MODEL)))
    captured = parse_exif_datetime(
        _text(exif.get(TAG_DATETIME_ORIGINAL)),
        _text(exif.get(TAG_OFFSET_ORIGINAL)),
    )
    if captured is None:
        captured = parse_exif_datetime(
            _text(exif.get(TAG_DATETIME_DIGITIZED)),
            _text(exif.get(TAG_OFFSET_DIGITIZED)),
        )
    _apply_gps(meta, gps)
    return {"metadata": meta, "exifCapturedAt": captured}


_HEAD_BYTES = 128 * 1024


def quick_captured_at(path: Path) -> str:
    """Capture time cheap enough to order a whole folder before reading it.

    JPEG EXIF sits in the first few KB; other files fall back to the filename
    or modified time. ``read_capture`` still decides the recorded value.
    """
    if file_suffix(path) in {".jpg", ".jpeg"}:
        try:
            with open(path, "rb") as handle:
                head = handle.read(_HEAD_BYTES)
            _, _, tiff = _jpeg_size_and_exif(head)
            exif = (_parse_tiff(tiff) if tiff else {}).get("exif") or {}
            captured = parse_exif_datetime(
                _text(exif.get(TAG_DATETIME_ORIGINAL)), _text(exif.get(TAG_OFFSET_ORIGINAL))
            ) or parse_exif_datetime(
                _text(exif.get(TAG_DATETIME_DIGITIZED)), _text(exif.get(TAG_OFFSET_DIGITIZED))
            )
            if captured:
                return captured
        except (OSError, ValueError, IndexError):
            pass
    try:
        return filename_captured_at(path.name) or mtime_captured_at(path)
    except OSError:
        return ""


def exif_orientation(path: Path) -> int:
    """EXIF orientation 1-8 from a JPEG's first 128 KB; 1 for anything else."""
    if file_suffix(path) not in {".jpg", ".jpeg"}:
        return 1
    try:
        with open(path, "rb") as handle:
            _, _, tiff = _jpeg_size_and_exif(handle.read(_HEAD_BYTES))
        ifd0 = (_parse_tiff(tiff) if tiff else {}).get("ifd0") or {}
    except (OSError, ValueError, IndexError):
        return 1
    return _int_in_range(ifd0.get(TAG_ORIENTATION), 1, 8) or 1


TAG_THUMB_OFFSET = 0x0201
TAG_THUMB_LENGTH = 0x0202
_SHAPE_TOLERANCE = 0.03


def _upright_exif(orientation: int) -> bytes:
    """APP1 segment holding only an orientation, so the browser turns the picture upright."""
    tiff = b"MM\x00\x2a\x00\x00\x00\x08" + b"\x00\x01"
    tiff += TAG_ORIENTATION.to_bytes(2, "big") + b"\x00\x03\x00\x00\x00\x01"
    tiff += orientation.to_bytes(2, "big") + b"\x00\x00" + b"\x00\x00\x00\x00"
    payload = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload


def camera_thumbnail(path: Path) -> bytes:
    """The small JPEG a camera stores in EXIF, turned upright; b"" when unusable.

    Unusable means not a JPEG, no embedded picture, or a shape more than 3%
    off the photo's (a letterboxed one would show bars).
    """
    if file_suffix(path) not in {".jpg", ".jpeg"}:
        return b""
    try:
        with open(path, "rb") as handle:
            head = handle.read(_HEAD_BYTES)
        width, height, tiff = _jpeg_size_and_exif(head)
        if not tiff or len(tiff) < 8 or tiff[:2] not in {b"II", b"MM"}:
            return b""
        endian = "little" if tiff[:2] == b"II" else "big"
        ifd0_off = _u32(tiff, 4, endian)
        ifd0 = _read_ifd(tiff, ifd0_off, endian)
        ifd1_off = _u32(tiff, ifd0_off + 2 + _u16(tiff, ifd0_off, endian) * 12, endian)
        if not ifd1_off:
            return b""
        ifd1 = _read_ifd(tiff, ifd1_off, endian)
        start, length = ifd1.get(TAG_THUMB_OFFSET), ifd1.get(TAG_THUMB_LENGTH)
        if type(start) is not int or type(length) is not int or length <= 0:
            return b""
        thumb = tiff[start : start + length]
    except (OSError, ValueError, IndexError):
        return b""
    if len(thumb) != length or not thumb.startswith(b"\xff\xd8"):
        return b""
    t_width, t_height, _ = _jpeg_size_and_exif(thumb)
    if not (width and height and t_width and t_height):
        return b""
    if abs(t_width * height / (t_height * width) - 1) > _SHAPE_TOLERANCE:
        return b""
    orientation = _int_in_range(ifd0.get(TAG_ORIENTATION), 1, 8) or 1
    return thumb[:2] + _upright_exif(orientation) + thumb[2:]


def _size_from_ffprobe(path: Path) -> dict[str, Any]:
    meta = empty_metadata()
    payload = ffprobe_json(path)
    if payload is None:
        return {"metadata": meta, "payload": None}
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video:
        width = video.get("width")
        height = video.get("height")
        if isinstance(width, int) and width > 0:
            meta["width"] = width
        if isinstance(height, int) and height > 0:
            meta["height"] = height
    return {"metadata": meta, "payload": payload}


def _still_from_probe(path: Path) -> dict[str, Any]:
    return {"metadata": _size_from_ffprobe(path)["metadata"], "exifCapturedAt": None}


def _ifd_offset(value: Any) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, list) and value and type(value[0]) is int:
        return value[0]
    return None


def _video_from_ffprobe(path: Path) -> dict[str, Any]:
    sized = _size_from_ffprobe(path)
    meta = sized["metadata"]
    payload = sized["payload"]
    if payload is None:
        return {"metadata": meta, "exifCapturedAt": None}
    duration = (payload.get("format") or {}).get("duration")
    try:
        if duration is not None:
            seconds = float(duration)
            if seconds >= 0:
                meta["durationSec"] = seconds
    except (TypeError, ValueError):
        pass
    tags = ffprobe_tags(payload)
    captured = parse_iso_instant(tags.get("com.apple.quicktime.creationdate"))
    if captured is None:
        raw_ctime = tags.get("creation_time")
        if isinstance(raw_ctime, str) and "T" in raw_ctime:
            captured = parse_iso_instant(raw_ctime)
    lat, lon = parse_iso6709(tags.get("com.apple.quicktime.location.ISO6709"))
    meta["latitude"] = lat
    meta["longitude"] = lon
    return {"metadata": meta, "exifCapturedAt": captured}


def _heif_probe(path: Path, data: bytes | None = None) -> dict[str, Any]:
    if not heif_has_valid_brand(path, data):
        return {"metadata": empty_metadata(), "exifCapturedAt": None}
    return _still_from_probe(path)


def read_capture(path: Path, data: bytes | None = None) -> tuple[str, str, dict[str, Any]]:
    """Return capturedAt, capturedAtSource, and metadata for a media file.

    ``data`` is the file's bytes when the caller already holds them (the scan
    hashes each file once and parses EXIF from that same read).
    """
    suffix = file_suffix(path)
    extracted: dict[str, Any] = {"metadata": empty_metadata(), "exifCapturedAt": None}
    try:
        if suffix in HEIF_SUFFIXES:
            extracted = _heif_probe(path, data)
        elif suffix in VIDEO_SUFFIXES:
            extracted = _video_from_ffprobe(path)
        elif suffix in {".jpg", ".jpeg"}:
            extracted = _still_from_jpeg(path, data)
        elif suffix in PHOTO_SUFFIXES:
            extracted = _still_from_probe(path)
    except OSError:
        extracted = {"metadata": empty_metadata(), "exifCapturedAt": None}
    captured = extracted.get("exifCapturedAt")
    source = "exif" if captured else None
    if captured is None:
        captured = filename_captured_at(path.name)
        source = "filename" if captured else None
    if captured is None:
        captured = mtime_captured_at(path)
        source = "mtime"
    metadata = read_metadata({**empty_metadata(), **(extracted.get("metadata") or {})})
    return captured, source or "mtime", metadata

