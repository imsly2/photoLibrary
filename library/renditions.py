"""JPEG thumb and preview files. Decode with ffmpeg; publish without history."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import item_rel, iter_item_ids, load_item, try_load_item
from library.media import file_suffix
from library.records import clone, ordered_item
from library.settings import defaults, load_settings_file, settings_path
from library.volumes import location_file, location_matches_stat

JPEG_SUFFIXES = frozenset({".jpg", ".jpeg"})
STILL_SLOTS = ("thumb", "preview")


def _settings_caps(root: Path) -> tuple[int, int]:
    path = settings_path(root)
    if not path.exists():
        data = defaults()
    else:
        data = load_settings_file(root)
    return int(data["thumbPx"]), int(data["previewPx"])


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


def _is_jpeg_photo(item: dict[str, Any], root: Path) -> bool:
    if item.get("kind") != "photo":
        return False
    path = _primary_still_path(item, root)
    if path is None:
        return False
    return file_suffix(path) in JPEG_SUFFIXES


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


def _slot_rel(item_id: str, slot: str) -> str:
    return f"renditions/{item_id}/{slot}.webp"


def next_jpeg_job(root: Path) -> tuple[str, str, Path, int] | None:
    thumb_px, preview_px = _settings_caps(root)
    caps = {"thumb": thumb_px, "preview": preview_px}
    for item_id in iter_item_ids(root):
        if item_id.startswith("pending-"):
            continue
        item = load_item(root, item_id)
        if not _is_jpeg_photo(item, root):
            continue
        status = (item.get("renditions") or {}).get("status") or {}
        source = _primary_still_path(item, root)
        if source is None:
            continue
        for slot in STILL_SLOTS:
            if status.get(slot) != "queued":
                continue
            return item_id, slot, source, caps[slot]
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


def drain_step(root: Path) -> bool:
    job = next_jpeg_job(root)
    if job is None:
        return False
    item_id, slot, source, cap = job
    relative = _slot_rel(item_id, slot)
    dest = root / Path(*relative.split("/"))
    if not write_webp(source, dest, cap):
        return True
    publish_ready(root, item_id, slot, relative)
    return True
