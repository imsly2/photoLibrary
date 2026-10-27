"""One person's faces, pinned, in time order.

The player asks for a timeline, then one aligned JPEG per photo. Alignment
reads the face box already stored on the item. It does not run detection
and it does not write the catalog. Saving a video writes a new mp4 and opens it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from library.catalog_io import iter_item_ids, load_item, try_load_person, try_load_place
from library.errors import fail
from library.paths import library_path

FILM_SIZE = 640
DEFAULT_SECONDS = 0.45
_STEM_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# 5x7 glyphs, '#' is ink. Digits, hyphen, and space cover a calendar date.
_GLYPHS = {
    "0": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "  ## ", " #   ", "#    ", "#####"],
    "3": [" ### ", "#   #", "    #", " ### ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "-": ["     ", "     ", "     ", " ### ", "     ", "     ", "     "],
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
}


def films_dir(root: Path) -> Path:
    return root / "films"


def _person(root: Path, person_id: str) -> dict[str, Any]:
    person = try_load_person(root, person_id)
    if person is None:
        raise fail("not-found")
    return person


def _face_for(item: dict[str, Any], person_id: str) -> dict[str, Any] | None:
    faces = [
        face
        for face in (item.get("faces") or [])
        if face.get("personId") == person_id and isinstance(face.get("box"), list)
    ]
    if not faces:
        return None
    faces.sort(key=lambda face: (0 if face.get("landmarks") else 1, face["box"][0], face["box"][1]))
    return faces[0]


def _coords(root: Path, item: dict[str, Any]) -> tuple[Any, Any, str, str | None]:
    place_id = item.get("placeId")
    name = ""
    lat = None
    lon = None
    if isinstance(place_id, str) and place_id:
        place = try_load_place(root, place_id)
        if place is not None:
            name = place.get("name") or ""
            lat = place.get("latitude")
            lon = place.get("longitude")
    if lat is None or lon is None:
        meta = item.get("metadata") or {}
        if lat is None:
            lat = meta.get("latitude")
        if lon is None:
            lon = meta.get("longitude")
    if not isinstance(place_id, str):
        place_id = None
    return lat, lon, name if isinstance(name, str) else "", place_id


def person_timeline(root: Path, person_id: str) -> dict[str, Any]:
    person = _person(root, person_id)
    frames: list[dict[str, Any]] = []
    for item_id in iter_item_ids(root):
        try:
            item = load_item(root, item_id)
        except Exception:
            continue
        face = _face_for(item, person_id)
        if face is None:
            continue
        lat, lon, place_name, place_id = _coords(root, item)
        frames.append(
            {
                "itemId": item_id,
                "capturedAt": item.get("capturedAt") or "",
                "filename": item.get("filename") or "",
                "placeId": place_id,
                "placeName": place_name,
                "latitude": lat,
                "longitude": lon,
                "hasLandmarks": isinstance(face.get("landmarks"), list) and len(face["landmarks"]) == 5,
            }
        )
    frames.sort(key=lambda row: (row["capturedAt"], row["itemId"]))
    return {
        "ok": True,
        "personId": person_id,
        "name": person.get("name"),
        "frames": frames,
    }


def align_eyes(image: Any, left_xy: Any, right_xy: Any, size: int = 640) -> Any:
    """Put both eyes on one horizontal line and scale from the distance between them.

    Width and height share that scale, so the picture is not stretched.
    ``left_xy`` and ``right_xy`` are pixel coordinates on ``image``.
    """
    import math

    import numpy as np

    height, width = image.shape[:2]
    lx, ly = (float(v) for v in left_xy)
    rx, ry = (float(v) for v in right_xy)
    dist = math.hypot(rx - lx, ry - ly)
    if dist < 1:
        raise fail("preview-unavailable")
    target = size * 0.22
    scale = target / dist
    angle = math.atan2(ry - ly, rx - lx)
    ca = math.cos(angle)
    sa = math.sin(angle)
    mid_x = (lx + rx) / 2.0
    mid_y = (ly + ry) / 2.0
    dest_x = size * 0.5
    dest_y = size * 0.42
    out = np.zeros((size, size, 3), dtype=np.uint8)
    ys, xs = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    dx = xs - dest_x
    dy = ys - dest_y
    src_x = np.clip(np.rint(mid_x + (ca * dx - sa * dy) / scale).astype(np.int32), 0, max(0, width - 1))
    src_y = np.clip(np.rint(mid_y + (sa * dx + ca * dy) / scale).astype(np.int32), 0, max(0, height - 1))
    out[:, :] = image[src_y, src_x]
    return out


def align_box(image: Any, box: list[float], size: int = 640, typical_side: float | None = None) -> Any:
    """Put the face box in the middle of a square frame. Pixels stay square.

    ``box`` is x, y, width, height, each 0–1 on this image. Scale uses the
    box area, pulled toward ``typical_side`` (that person's usual face size)
    so one tight box and one loose box do not zoom the face by double.
    """
    import math

    import numpy as np

    height, width = image.shape[:2]
    x, y, bw, bh = (float(v) for v in box)
    bw = max(bw, 1e-6)
    bh = max(bh, 1e-6)
    actual = math.sqrt(bw * bh)
    typical = actual if typical_side is None or typical_side <= 0 else float(typical_side)
    used = math.exp(0.3 * math.log(actual) + 0.7 * math.log(typical))
    face_px = max(used * math.sqrt(float(width * height)), 1.0)
    scale = (size * 0.46) / face_px
    cx = (x + bw / 2.0) * width
    cy = (y + bh / 2.0) * height
    dest = size * 0.5
    out = np.zeros((size, size, 3), dtype=np.uint8)
    ys, xs = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    src_x = np.clip(np.rint(cx + (xs - dest) / scale).astype(np.int32), 0, max(0, width - 1))
    src_y = np.clip(np.rint(cy + (ys - dest) / scale).astype(np.int32), 0, max(0, height - 1))
    out[:, :] = image[src_y, src_x]
    return out


_side_cache: dict[tuple[str, str], float] = {}


def _median_box_side(root: Path, person_id: str) -> float:
    """Usual face size for this person, as sqrt(box width * box height)."""
    import math

    key = (str(root), person_id)
    hit = _side_cache.get(key)
    if hit is not None:
        return hit
    sides: list[float] = []
    for item_id in iter_item_ids(root):
        try:
            item = load_item(root, item_id)
        except Exception:
            continue
        face = _face_for(item, person_id)
        if face is None:
            continue
        box = face.get("box")
        if not isinstance(box, list) or len(box) != 4:
            continue
        sides.append(math.sqrt(max(float(box[2]), 1e-6) * max(float(box[3]), 1e-6)))
    sides.sort()
    median = sides[len(sides) // 2] if sides else 0.15
    _side_cache[key] = median
    return median


def _still_bytes(root: Path, item: dict[str, Any]) -> tuple[int, int, bytes] | None:
    from library.faces import _still_path
    from library.media import decode_still_rgb

    rend = item.get("renditions") or {}
    preview = rend.get("preview")
    candidates: list[Path] = []
    if isinstance(preview, str) and preview:
        path = library_path(root, preview)
        if path.is_file():
            candidates.append(path)
    original = _still_path(item, root)
    if original is not None and original not in candidates:
        candidates.append(original)
    for path in candidates:
        try:
            return decode_still_rgb(path, 1600)
        except Exception:
            continue
    return None


def _cache_path(root: Path, person_id: str, item_id: str, kind: str) -> Path:
    return films_dir(root) / "cache" / person_id / f"{item_id}.{kind}.jpg"


def _paint_date(image: Any, text: str) -> None:
    if not text:
        return
    np = __import__("numpy")
    scale = 4
    glyph_w = 5 * scale
    gap = scale
    height, width = image.shape[:2]
    text = text[:16]
    bar_h = 7 * scale + scale * 4
    y0 = max(0, height - bar_h - scale * 2)
    x0 = scale * 3
    image[y0 : min(height, y0 + bar_h), 0:width] = (image[y0 : min(height, y0 + bar_h), 0:width] * 0.35).astype(np.uint8)
    x = x0
    for ch in text:
        rows = _GLYPHS.get(ch)
        if rows is None:
            x += glyph_w + gap
            continue
        for gy, row in enumerate(rows):
            for gx, bit in enumerate(row):
                if bit != "#":
                    continue
                py = y0 + scale * 2 + gy * scale
                px = x + gx * scale
                image[py : py + scale, px : px + scale] = (245, 245, 245)
        x += glyph_w + gap
        if x >= width - glyph_w:
            break


def _jpeg(image: Any) -> bytes:
    import tempfile

    from library.media import run_ffmpeg

    np = __import__("numpy")
    rgb = np.ascontiguousarray(image, dtype=np.uint8)
    height, width = rgb.shape[:2]
    raw_fd, raw_name = tempfile.mkstemp(suffix=".rgb")
    os.close(raw_fd)
    raw_fd = -1
    jpg_fd, jpg_name = tempfile.mkstemp(suffix=".jpg")
    os.close(jpg_fd)
    try:
        Path(raw_name).write_bytes(rgb.tobytes())
        proc = run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                f"{width}x{height}",
                "-i",
                raw_name,
                "-frames:v",
                "1",
                "-q:v",
                "3",
                jpg_name,
            ]
        )
        data = Path(jpg_name).read_bytes() if proc.returncode == 0 else b""
    finally:
        if raw_fd >= 0:
            os.close(raw_fd)
        Path(raw_name).unlink(missing_ok=True)
        Path(jpg_name).unlink(missing_ok=True)
    if not data.startswith(b"\xff\xd8"):
        raise fail("decode-error")
    return data


def render_frame(root: Path, person_id: str, item_id: str) -> bytes:
    _person(root, person_id)
    try:
        item = load_item(root, item_id)
    except Exception as exc:
        raise fail("not-found") from exc
    face = _face_for(item, person_id)
    if face is None:
        raise fail("not-found")
    box = face.get("box")
    if not isinstance(box, list) or len(box) != 4:
        raise fail("preview-unavailable")
    landmarks = face.get("landmarks")
    eyes = isinstance(landmarks, list) and len(landmarks) == 5
    cache = _cache_path(root, person_id, item_id, "eyes" if eyes else "box")
    if cache.is_file():
        cached = cache.read_bytes()
        if cached.startswith(b"\xff\xd8"):
            return cached
    loaded = _still_bytes(root, item)
    if loaded is None:
        raise fail("preview-unavailable")
    width, height, rgb = loaded
    import numpy as np

    image = np.frombuffer(rgb, dtype=np.uint8).reshape((height, width, 3)).copy()
    if eyes:
        left = (float(landmarks[0][0]) * width, float(landmarks[0][1]) * height)
        right = (float(landmarks[1][0]) * width, float(landmarks[1][1]) * height)
        eye_dist = ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
        box_w = max(float(box[2]) * width, 1.0)
        if eye_dist >= max(8.0, box_w * 0.2):
            portrait = align_eyes(image, left, right, FILM_SIZE)
        else:
            portrait = align_box(image, box, FILM_SIZE, _median_box_side(root, person_id))
    else:
        portrait = align_box(image, box, FILM_SIZE, _median_box_side(root, person_id))
    captured = item.get("capturedAt") or ""
    _paint_date(portrait, captured[:10])
    jpeg = _jpeg(portrait)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(jpeg)
    except OSError:
        pass
    return jpeg


def _seconds(value: Any) -> float:
    if value is None:
        return DEFAULT_SECONDS
    if type(value) is bool or not isinstance(value, (int, float)):
        raise fail("invalid-argument")
    number = float(value)
    if number < 0.15 or number > 3:
        raise fail("invalid-argument")
    return number


def _stem(name: str | None) -> str:
    text = (name or "").strip() or "Unnamed"
    text = _STEM_BAD.sub("", text).strip().rstrip(".")
    return (text or "Unnamed") + " over time"


def _unique_mp4(folder: Path, stem: str) -> Path:
    path = folder / f"{stem}.mp4"
    n = 2
    while path.exists():
        path = folder / f"{stem} {n}.mp4"
        n += 1
    return path


def _open_file(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return
        subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        return


def export_film(root: Path, person_id: str, seconds: Any = None) -> dict[str, Any]:
    from library.media import run_ffmpeg

    hold = _seconds(seconds)
    timeline = person_timeline(root, person_id)
    frames = timeline["frames"]
    if not frames:
        raise fail("not-found")
    folder = films_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    work = folder / "_frames"
    if work.exists():
        for old in work.glob("*.jpg"):
            old.unlink()
    else:
        work.mkdir(parents=True)
    written = 0
    for index, frame in enumerate(frames):
        try:
            jpeg = render_frame(root, person_id, frame["itemId"])
        except Exception:
            continue
        (work / f"{written:04d}.jpg").write_bytes(jpeg)
        written += 1
    if written == 0:
        raise fail("preview-unavailable")
    dest = _unique_mp4(folder, _stem(timeline.get("name")))
    rate = f"{1.0 / hold:.6f}".rstrip("0").rstrip(".")
    proc = run_ffmpeg(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            rate,
            "-i",
            str(work / "%04d.jpg"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        timeout=max(120.0, written * 2),
    )
    if proc.returncode != 0 or not dest.is_file():
        raise fail("decode-error")
    _open_file(dest)
    return {"ok": True, "path": str(dest), "frames": written, "seconds": hold}
