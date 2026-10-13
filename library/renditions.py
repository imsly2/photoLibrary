"""Still and video rendition files. Decode with ffmpeg; publish without history."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import item_rel, iter_item_ids, load_item, try_load_item
from library.media import PHOTO_SUFFIXES, VIDEO_SUFFIXES, file_suffix
from library.records import clone, ordered_item
from library.settings import defaults, load_settings_file, settings_path
from library.volumes import location_file, location_matches_stat

STILL_SLOTS = ("thumb", "preview")
VIDEO_SLOTS = ("poster", "proxy")


def _settings_caps(root: Path) -> tuple[int, int, int]:
    path = settings_path(root)
    if not path.exists():
        data = defaults()
    else:
        data = load_settings_file(root)
    return int(data["thumbPx"]), int(data["previewPx"]), int(data["proxyWidth"])


def _primary_still_path(item: dict[str, Any], root: Path) -> Path | None:
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == "still"
    ]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or "",
        )
    )
    for loc in candidates:
        path = location_file(loc, root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return path
    return None


def _primary_motion_path(item: dict[str, Any], root: Path) -> Path | None:
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == "motion"
    ]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or "",
        )
    )
    for loc in candidates:
        path = location_file(loc, root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return path
    return None


def _scale_filter(cap: int) -> str:
    return (
        f"scale="
        f"'if(gte(iw,ih),min(iw,{cap}),-2)':"
        f"'if(lt(iw,ih),min(ih,{cap}),-2)'"
    )


def write_webp(source: Path, dest: Path, cap: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vf",
                _scale_filter(cap),
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


def write_proxy(source: Path, dest: Path, cap: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-an",
                "-c:v",
                "libx264",
                "-vf",
                f"scale='trunc(min(iw,{cap})/2)*2':-2",
                "-pix_fmt",
                "yuv420p",
                "-f",
                "mp4",
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


def _slot_rel(item_id: str, slot: str) -> str:
    if slot == "proxy":
        return f"renditions/{item_id}/proxy.mp4"
    return f"renditions/{item_id}/{slot}.webp"


def next_rendition_job(root: Path) -> tuple[str, str, Path, int] | None:
    thumb_px, preview_px, proxy_width = _settings_caps(root)
    still_caps = {"thumb": thumb_px, "preview": preview_px}
    for item_id in iter_item_ids(root):
        if item_id.startswith("pending-"):
            continue
        item = load_item(root, item_id)
        kind = item.get("kind")
        status = (item.get("renditions") or {}).get("status") or {}
        if kind == "photo":
            source = _primary_still_path(item, root)
            if source is None or file_suffix(source) not in PHOTO_SUFFIXES:
                continue
            for slot in STILL_SLOTS:
                if status.get(slot) != "queued":
                    continue
                return item_id, slot, source, still_caps[slot]
        elif kind == "video":
            source = _primary_motion_path(item, root)
            if source is None or file_suffix(source) not in VIDEO_SUFFIXES:
                continue
            if status.get("poster") == "queued":
                return item_id, "poster", source, thumb_px
            if status.get("proxy") == "queued":
                return item_id, "proxy", source, proxy_width
    return None


def publish_ready(root: Path, item_id: str, slot: str, relative: str) -> None:
    before = try_load_item(root, item_id)
    if before is None:
        return
    after = clone(before)
    rend = after["renditions"]
    rend[slot] = relative
    rend["status"][slot] = "ready"
    after = ordered_item(after)
    transact(
        root,
        [{"path": item_rel(item_id), "before": before, "after": after}],
    )


def publish_error(root: Path, item_id: str, slot: str) -> None:
    before = try_load_item(root, item_id)
    if before is None:
        return
    after = clone(before)
    rend = after["renditions"]
    rend[slot] = None
    rend["status"][slot] = "error"
    after = ordered_item(after)
    transact(
        root,
        [{"path": item_rel(item_id), "before": before, "after": after}],
    )


def _clear_empty(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size <= 0:
            path.unlink()
    except OSError:
        pass


def drain_step(root: Path) -> bool:
    job = next_rendition_job(root)
    if job is None:
        return False
    item_id, slot, source, cap = job
    relative = _slot_rel(item_id, slot)
    dest = root / Path(*relative.split("/"))
    writer = write_proxy if slot == "proxy" else write_webp
    if not writer(source, dest, cap):
        _clear_empty(dest)
        publish_error(root, item_id, slot)
        return True
    publish_ready(root, item_id, slot, relative)
    return True
