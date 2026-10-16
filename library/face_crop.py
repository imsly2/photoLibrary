"""Square face crops for the People picker. Decode with ffmpeg."""

from __future__ import annotations

import hashlib
import math
import subprocess
import uuid
from pathlib import Path

from library.errors import fail
from library.media import ffprobe_json
from library.paths import library_path

FACE_CROP_PX = 256
FACE_CROP_PAD = 0.28
CACHE_REL = "cache/faces"


def parse_face_box(raw: str | None) -> list[float]:
    if type(raw) is not str or not raw.strip():
        raise fail("invalid-argument")
    parts = raw.split(",")
    if len(parts) != 4:
        raise fail("invalid-argument")
    try:
        box = [float(part) for part in parts]
    except ValueError as exc:
        raise fail("invalid-argument") from exc
    if any(not math.isfinite(value) for value in box):
        raise fail("invalid-argument")
    return _clamp_box(box)


def _clamp_box(box: list[float]) -> list[float]:
    x, y, w, h = (float(v) for v in box)
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    w = min(max(w, 0.0), 1.0 - x)
    h = min(max(h, 0.0), 1.0 - y)
    if w <= 0.0 or h <= 0.0:
        raise fail("invalid-argument")
    return [x, y, w, h]


def square_crop_px(
    box: list[float],
    width: int,
    height: int,
    pad: float = FACE_CROP_PAD,
) -> tuple[int, int, int, int]:
    if width <= 0 or height <= 0:
        raise fail("decode-error")
    x, y, w, h = (float(v) for v in box)
    cx = (x + w / 2.0) * float(width)
    cy = (y + h / 2.0) * float(height)
    side = max(w * float(width), h * float(height)) * (1.0 + float(pad))
    side = min(float(width), float(height), max(2.0, side))
    x0 = min(max(cx - side / 2.0, 0.0), float(width) - side)
    y0 = min(max(cy - side / 2.0, 0.0), float(height) - side)
    ix = int(round(x0))
    iy = int(round(y0))
    iside = int(round(side))
    if iside % 2:
        iside -= 1
    iside = max(2, iside)
    if ix + iside > width:
        ix = max(0, width - iside)
    if iy + iside > height:
        iy = max(0, height - iside)
    return ix, iy, iside, iside


def probe_still_size(path: Path) -> tuple[int, int]:
    probe = ffprobe_json(path)
    if probe is None:
        raise fail("decode-error")
    for stream in probe.get("streams") or []:
        if stream.get("codec_type") == "video":
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            if width > 0 and height > 0:
                return width, height
    raise fail("decode-error")


def face_crop_cache_path(root: Path, item_id: str, box: list[float], source: Path) -> Path:
    try:
        stat = source.stat()
        stamp = f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        stamp = "0:0"
    raw = f"{item_id}:{box[0]:.5f},{box[1]:.5f},{box[2]:.5f},{box[3]:.5f}:{stamp}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return library_path(root, CACHE_REL) / f"{item_id}_{digest}.webp"


def write_face_crop(
    source: Path,
    dest: Path,
    box: list[float],
    size: int = FACE_CROP_PX,
) -> bool:
    width, height = probe_still_size(source)
    x, y, side, _ = square_crop_px(box, width, height)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-vf",
                f"crop={side}:{side}:{x}:{y},scale={int(size)}:{int(size)}",
                "-frames:v",
                "1",
                "-f",
                "webp",
                str(tmp),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size <= 0:
            if tmp.exists():
                tmp.unlink()
            return False
        tmp.replace(dest)
        return dest.is_file() and dest.stat().st_size > 0
    except OSError:
        if tmp.exists():
            tmp.unlink()
        return False
