"""JPEG thumb and preview WebP jobs. ffmpeg only; drain while serve runs."""

from __future__ import annotations

import os
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import item_rel, iter_item_ids, try_load_item
from library.paths import library_path
from library.records import clone, ordered_item
from library.volumes import resolve_component_path

JPEG_SUFFIXES = frozenset({".jpg", ".jpeg"})
ROTATED = frozenset({5, 6, 7, 8})


def still_path_name(item: dict[str, Any]) -> str:
    filename = item.get("filename") or ""
    for loc in item.get("locations") or []:
        if loc.get("component") == "still" and loc.get("role") == "primary":
            return (
                loc.get("lastKnownPath")
                or loc.get("pathFromVolumeRoot")
                or loc.get("libraryRelativePath")
                or filename
            )
    return filename


def is_jpeg_photo(item: dict[str, Any]) -> bool:
    if item.get("kind") != "photo":
        return False
    suffix = Path(still_path_name(item)).suffix.lower()
    if suffix not in JPEG_SUFFIXES:
        suffix = Path(item.get("filename") or "").suffix.lower()
    return suffix in JPEG_SUFFIXES


def oriented_frame(width: int, height: int, orientation: int | None) -> tuple[int, int]:
    if orientation in ROTATED:
        return height, width
    return width, height


def even_down(value: int) -> int:
    if value <= 1:
        return max(value, 1)
    if value % 2:
        return value - 1
    return value


def fit_longest(width: int, height: int, cap: int) -> tuple[int, int]:
    longest = max(width, height)
    if longest > cap:
        scale = cap / longest
        out_w = int(width * scale)
        out_h = int(height * scale)
    else:
        out_w = width
        out_h = height
    return max(even_down(out_w), 1), max(even_down(out_h), 1)


def target_size(item: dict[str, Any], cap: int) -> tuple[int, int] | None:
    meta = item.get("metadata") or {}
    width = meta.get("width")
    height = meta.get("height")
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        return None
    orientation = meta.get("orientation")
    if orientation is not None and type(orientation) is not int:
        orientation = None
    ow, oh = oriented_frame(width, height, orientation)
    return fit_longest(ow, oh, cap)


def write_webp(src: Path, dest: Path, width: int, height: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.stem}.{uuid.uuid4().hex}.tmp.webp")
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vf",
        f"scale={width}:{height}",
        "-frames:v",
        "1",
        "-an",
        "-f",
        "webp",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    try:
        if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size <= 0:
            if tmp.exists():
                tmp.unlink()
            return False
        os.replace(tmp, dest)
        return dest.is_file() and dest.stat().st_size > 0
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def _queued_slots(item: dict[str, Any]) -> list[str]:
    status = (item.get("renditions") or {}).get("status") or {}
    return [slot for slot in ("thumb", "preview") if status.get(slot) == "queued"]


def _publish(root: Path, item_id: str, updates: dict[str, tuple[str | None, str]]) -> None:
    before = try_load_item(root, item_id)
    if before is None:
        return
    after = clone(before)
    changed = False
    for slot, (relative, status) in updates.items():
        if after["renditions"]["status"].get(slot) != "queued":
            continue
        after["renditions"][slot] = relative
        after["renditions"]["status"][slot] = status
        changed = True
    if not changed:
        return
    after = ordered_item(after)
    transact(
        root,
        [{"path": item_rel(item_id), "before": before, "after": after}],
    )


def generate_jpeg_item(
    root: Path,
    item: dict[str, Any],
    thumb_px: int,
    preview_px: int,
    lock: threading.Lock | None = None,
) -> None:
    slots = _queued_slots(item)
    if not slots:
        return
    src = resolve_component_path(item, "still", root)
    if src is None:
        return
    item_id = item["id"]
    caps = {"thumb": thumb_px, "preview": preview_px}
    updates: dict[str, tuple[str | None, str]] = {}
    for slot in slots:
        size = target_size(item, caps[slot])
        if size is None:
            updates[slot] = (None, "error")
            continue
        relative = f"renditions/{item_id}/{slot}.webp"
        dest = library_path(root, relative)
        if write_webp(src, dest, size[0], size[1]):
            updates[slot] = (relative, "ready")
        else:
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            updates[slot] = (None, "error")
    if not updates:
        return
    if lock is not None:
        with lock:
            _publish(root, item_id, updates)
    else:
        _publish(root, item_id, updates)


def drain_queued_jpegs(
    root: Path,
    thumb_px: int,
    preview_px: int,
    lock: threading.Lock | None = None,
) -> None:
    def jobs() -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for item_id in iter_item_ids(root):
            item = try_load_item(root, item_id)
            if item is None or not is_jpeg_photo(item):
                continue
            if _queued_slots(item):
                found.append(item)
        return found

    pending = jobs() if lock is None else None
    if lock is not None:
        with lock:
            pending = jobs()
    assert pending is not None
    for item in pending:
        generate_jpeg_item(root, item, thumb_px, preview_px, lock)


def rendition_loop(library: Any, lock: threading.Lock, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            with lock:
                settings = library.ensure_settings()
                thumb_px = int(settings["thumbPx"])
                preview_px = int(settings["previewPx"])
            drain_queued_jpegs(library.root, thumb_px, preview_px, lock)
        except Exception:
            pass
        stop.wait(0.25)
