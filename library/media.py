"""Byte identity, allowed extensions, and embedded content identifiers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
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


# Files up to this size are kept in memory after hashing so the same pass
# also serves EXIF and the content identifier. Phone photos are 2-12 MB;
# videos stream through the hash and go to ffprobe instead.
KEEP_BYTES_MAX = 96 * 1024 * 1024


@dataclass(frozen=True)
class SourceRead:
    """One pass over a file: its identity, and the bytes when small enough to keep."""

    size: int
    modified: str
    sha256: str
    data: bytes | None

    def bytes_or_read(self, path: Path) -> bytes:
        return self.data if self.data is not None else path.read_bytes()


def read_source(path: Path) -> SourceRead:
    """Hash a file in one read, keeping the bytes for the parsers that follow."""
    stat = path.stat()
    modified = mtime_iso(path)
    digest = hashlib.sha256()
    if stat.st_size <= KEEP_BYTES_MAX:
        data = path.read_bytes()
        digest.update(data)
        return SourceRead(stat.st_size, modified, digest.hexdigest(), data)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return SourceRead(stat.st_size, modified, digest.hexdigest(), None)


# One still decode, probe or WebP encode. A hung decoder (ffmpeg blocked on a
# pipe nobody reads, a stuck USB drive) must fail, not stall the only
# processing thread forever, which is what happened to the live server.
STILL_TIMEOUT_S = 120.0
# Proxy / playback encodes of long phone clips.
VIDEO_TIMEOUT_S = 1800.0
TIMEOUT_RETURNCODE = -9
profile_counters = {"ffmpeg_runs": 0, "ffmpeg_timeouts": 0}


def run_ffmpeg(
    cmd: list[str],
    *,
    timeout: float = STILL_TIMEOUT_S,
    text: bool = False,
    **popen_kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run ffmpeg/ffprobe with stdin closed, output captured and a hard timeout.

    ffmpeg gets ``-nostdin`` so it never polls the server's inherited stdin.
    On timeout, or if the Python side fails while collecting output (the
    MemoryError case), the child is killed and a CompletedProcess with
    ``TIMEOUT_RETURNCODE`` comes back; callers already treat nonzero as failure.
    """
    cmd = [str(part) for part in cmd]
    if cmd and Path(cmd[0]).stem.lower() == "ffmpeg" and "-nostdin" not in cmd:
        cmd.insert(1, "-nostdin")
    profile_counters["ffmpeg_runs"] += 1
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        **popen_kwargs,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except Exception as exc:
        profile_counters["ffmpeg_timeouts"] += 1
        proc.kill()
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        import sys

        print(
            f"ffmpeg gave up ({type(exc).__name__}) after {timeout:.0f}s: {' '.join(cmd)[:300]}",
            file=sys.stderr,
            flush=True,
        )
        empty = "" if text else b""
        return subprocess.CompletedProcess(cmd, TIMEOUT_RETURNCODE, empty, empty)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


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


def heif_has_valid_brand(path: Path, data: bytes | None = None) -> bool:
    if data is None:
        with open(path, "rb") as handle:
            data = handle.read(256 * 1024)
    brands = read_ftyp_brands(data[: 256 * 1024])
    return any(brand.strip() in VALID_HEIF_BRANDS for brand in brands)


# Recent successful probes keyed by (path, size, mtime). A scan asks for the
# content identifier and the capture metadata of the same video back to back,
# and the preview encoder probes it again moments later.
_PROBE_MEMO_MAX = 256
_probe_memo: OrderedDict[tuple[str, int, int], dict[str, Any]] = OrderedDict()


def ffprobe_json(path: Path) -> dict[str, Any] | None:
    try:
        stat = path.stat()
        key: tuple[str, int, int] | None = (str(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        key = None
    if key is not None and key in _probe_memo:
        _probe_memo.move_to_end(key)
        return json.loads(json.dumps(_probe_memo[key]))
    payload = _ffprobe_json_uncached(path)
    if key is not None and payload is not None:
        _probe_memo[key] = payload
        while len(_probe_memo) > _PROBE_MEMO_MAX:
            _probe_memo.popitem(last=False)
        return json.loads(json.dumps(payload))
    return payload


def _ffprobe_json_uncached(path: Path) -> dict[str, Any] | None:
    proc = run_ffmpeg(
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
        text=True,
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


def read_content_identifier(path: Path, data: bytes | None = None) -> str | None:
    suffix = file_suffix(path)
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_xmp_content_identifier(path.read_bytes() if data is None else data)
    if suffix in VIDEO_SUFFIXES:
        return video_content_identifier(path)
    return None
