"""Still and video rendition files. Decode with ffmpeg; publish without history."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import (
    item_rel,
    iter_item_ids,
    load_item,
    try_load_item,
    try_load_source,
)
from library.errors import fail
from library.media import PHOTO_SUFFIXES, VIDEO_SUFFIXES, ffprobe_json, file_suffix
from library.paths import library_path
from library.records import PREVIEW_STORES, clone, ordered_item
from library.settings import defaults, load_settings_file, settings_path
from library.volumes import location_file, location_matches_stat, volume_file_path

STILL_SLOTS = ("thumb", "preview")
VIDEO_SLOTS = ("poster", "proxy", "playback")
SAFE_VIDEO_CODECS = frozenset({"h264"})
SAFE_AUDIO_CODECS = frozenset({"aac", "mp3"})
SAFE_MP4_SUFFIXES = frozenset({".mp4", ".m4v"})
PROXY_CRF = 28
PROXY_PRESET = "veryfast"
PROXY_MAXRATE = "800k"
PROXY_BUFSIZE = "1600k"
PLAYBACK_MAX_WIDTH = 1280
PLAYBACK_CRF = 23
PLAYBACK_PRESET = "veryfast"
PLAYBACK_AUDIO_BITRATE = "128k"
PLAYBACK_MAXRATE = "2M"
PLAYBACK_BUFSIZE = "4M"
PLAYBACK_REMUX_MAX_BYTES = 80 * 1024 * 1024
_swept_tmp_roots: set[str] = set()


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


def _stream_codecs(source: Path) -> tuple[str | None, str | None]:
    payload = ffprobe_json(source)
    if not payload:
        return None, None
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    vcodec = video.get("codec_name") if isinstance(video, dict) else None
    acodec = audio.get("codec_name") if isinstance(audio, dict) else None
    if type(vcodec) is not str:
        vcodec = None
    if type(acodec) is not str:
        acodec = None
    return vcodec, acodec


def _video_width(source: Path) -> int | None:
    payload = ffprobe_json(source)
    if not payload:
        return None
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not isinstance(video, dict):
        return None
    width = video.get("width")
    return width if type(width) is int and width > 0 else None


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def cleanup_tmp_siblings(dest: Path) -> int:
    """Remove leftover `<name>.*.tmp` next to dest (killed ffmpeg leftovers)."""
    parent = dest.parent
    if not parent.is_dir():
        return 0
    removed = 0
    for path in parent.glob(f"{dest.name}.*.tmp"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def sweep_orphan_tmps(root: Path) -> int:
    """Delete leftover encode temps under library-data/renditions."""
    folder = root / "renditions"
    if not folder.is_dir():
        return 0
    removed = 0
    for path in folder.rglob("*.tmp"):
        try:
            if path.is_file():
                path.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def sweep_library_rendition_tmps(root: Path) -> int:
    key = str(root.resolve())
    if key in _swept_tmp_roots:
        return 0
    _swept_tmp_roots.add(key)
    return sweep_orphan_tmps(root)


def browser_safe_mp4(source: Path) -> bool:
    if file_suffix(source) not in SAFE_MP4_SUFFIXES:
        return False
    video, audio = _stream_codecs(source)
    if video not in SAFE_VIDEO_CODECS:
        return False
    return audio is None or audio in SAFE_AUDIO_CODECS


def can_remux_to_mp4(source: Path) -> bool:
    video, audio = _stream_codecs(source)
    if video not in SAFE_VIDEO_CODECS:
        return False
    return audio is None or audio in SAFE_AUDIO_CODECS


def _run_ffmpeg(args: list[str], dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cleanup_tmp_siblings(dest)
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        proc = subprocess.run(args + [str(tmp)], capture_output=True, check=False)
        if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size <= 0:
            if tmp.exists():
                tmp.unlink()
            cleanup_tmp_siblings(dest)
            return False
        tmp.replace(dest)
        cleanup_tmp_siblings(dest)
        return dest.is_file() and dest.stat().st_size > 0
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        cleanup_tmp_siblings(dest)
        return False


def should_remux_playback(source: Path) -> bool:
    """Remux only when it cannot silently duplicate a large phone clip."""
    if not can_remux_to_mp4(source):
        return False
    width = _video_width(source)
    if width is None or width > PLAYBACK_MAX_WIDTH:
        return False
    return _file_size(source) <= PLAYBACK_REMUX_MAX_BYTES


def write_playback(source: Path, dest: Path) -> str:
    """Write size-capped H.264+AAC MP4. Returns ready|not-applicable|error."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cleanup_tmp_siblings(dest)
    if browser_safe_mp4(source):
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        return "not-applicable"
    if should_remux_playback(source):
        remux = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
        ]
        if _run_ffmpeg(remux, dest):
            return "ready"
    transcode = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        PLAYBACK_PRESET,
        "-crf",
        str(PLAYBACK_CRF),
        "-maxrate",
        PLAYBACK_MAXRATE,
        "-bufsize",
        PLAYBACK_BUFSIZE,
        "-vf",
        f"scale='trunc(min(iw,{PLAYBACK_MAX_WIDTH})/2)*2':-2",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        PLAYBACK_AUDIO_BITRATE,
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
    ]
    if _run_ffmpeg(transcode, dest):
        return "ready"
    return "error"


def write_proxy(source: Path, dest: Path, cap: int) -> bool:
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        PROXY_PRESET,
        "-crf",
        str(PROXY_CRF),
        "-maxrate",
        PROXY_MAXRATE,
        "-bufsize",
        PROXY_BUFSIZE,
        "-vf",
        f"scale='trunc(min(iw,{cap})/2)*2':-2",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
    ]
    return _run_ffmpeg(args, dest)


def slot_filename(slot: str) -> str:
    if slot in {"proxy", "playback"}:
        return f"{slot}.mp4"
    return f"{slot}.webp"


def slot_relative(store: str, item_id: str, slot: str) -> str:
    name = slot_filename(slot)
    if store == "with-server":
        return f"renditions/{item_id}/{name}"
    return f".library/renditions/{item_id}/{name}"


def _current_settings(root: Path) -> dict[str, Any]:
    path = settings_path(root)
    if not path.exists():
        return defaults()
    return load_settings_file(root)


def effective_preview_store(source: dict[str, Any] | None, settings: dict[str, Any]) -> str:
    if source is not None:
        override = source.get("previewStore")
        if override in PREVIEW_STORES:
            return override
    store = settings.get("previewStore")
    if store in PREVIEW_STORES:
        return store
    return "with-server"


def source_preview_root(source: dict[str, Any], library_root: Path) -> Path | None:
    """Folder that with-source writes use. Copied sources use copyRoot, never the old disk."""
    if source.get("mode") == "copy-here":
        copy_root = source.get("copyRoot")
        if type(copy_root) is not str or not copy_root:
            return None
        try:
            return library_path(library_root, copy_root)
        except Exception:
            return None
    origin = source.get("origin") or {}
    serial = origin.get("volumeSerial")
    rel = origin.get("pathFromVolumeRoot")
    if type(serial) is not str or type(rel) is not str:
        return None
    return volume_file_path(serial, rel)


def _safe_join(base: Path, relative: str) -> Path | None:
    rel = relative.replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    try:
        out = (base / Path(*rel.split("/"))).resolve()
        out.relative_to(base.resolve())
    except Exception:
        return None
    return out


def store_dir(store: str, source: dict[str, Any] | None, library_root: Path, item_id: str) -> Path | None:
    if store == "with-server":
        try:
            return library_path(library_root, f"renditions/{item_id}")
        except Exception:
            return None
    if source is None:
        return None
    root = source_preview_root(source, library_root)
    if root is None:
        return None
    return _safe_join(root, f".library/renditions/{item_id}")


def _usable_file(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        if path.is_file() and path.stat().st_size > 0:
            return path
    except OSError:
        return None
    return None


def rendition_abs(item: dict[str, Any], slot: str, library_root: Path) -> Path | None:
    rend = item.get("renditions") or {}
    relative = rend.get(slot)
    if type(relative) is str and relative:
        store = rend.get("store")
        if store == "with-server":
            try:
                found = _usable_file(library_path(library_root, relative))
                if found is not None:
                    return found
            except Exception:
                pass
        else:
            source = try_load_source(library_root, rend.get("sourceId") or "")
            if source is not None:
                root = source_preview_root(source, library_root)
                if root is not None:
                    found = _usable_file(_safe_join(root, relative))
                    if found is not None:
                        return found
    return find_existing_rendition(item, slot, library_root)


def find_existing_rendition(item: dict[str, Any], slot: str, library_root: Path) -> Path | None:
    item_id = item.get("id")
    if type(item_id) is not str or not item_id:
        return None
    rend = item.get("renditions") or {}
    source = try_load_source(library_root, rend.get("sourceId") or "")
    stores: list[str] = []
    recorded = rend.get("store")
    if recorded in PREVIEW_STORES:
        stores.append(recorded)
    if "with-server" not in stores:
        stores.append("with-server")
    if "with-source" not in stores:
        stores.append("with-source")
    seen: set[str] = set()
    for store in stores:
        if store in seen:
            continue
        seen.add(store)
        dest_dir = store_dir(store, source, library_root, item_id)
        if dest_dir is None:
            continue
        found = _usable_file(dest_dir / slot_filename(slot))
        if found is not None:
            return found
    return None


def ready_slots(item: dict[str, Any]) -> list[str]:
    rend = item.get("renditions") or {}
    status = rend.get("status") or {}
    out: list[str] = []
    for slot in ("thumb", "preview", "poster", "proxy", "playback"):
        if status.get(slot) == "ready" and type(rend.get(slot)) is str and rend.get(slot):
            out.append(slot)
    return out


def copy_verified(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(src, "rb") as incoming, open(tmp, "wb") as outgoing:
            while True:
                chunk = incoming.read(65536)
                if not chunk:
                    break
                outgoing.write(chunk)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if not tmp.is_file() or tmp.stat().st_size <= 0:
            if tmp.exists():
                tmp.unlink()
            raise fail("io-error")
        os.replace(tmp, dest)
        if not dest.is_file() or dest.stat().st_size <= 0:
            raise fail("io-error")
    except OSError as exc:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise fail("io-error") from exc


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
            if status.get("playback") == "queued":
                return item_id, "playback", source, 0
        elif kind == "live":
            still_source = _primary_still_path(item, root)
            if still_source is not None and file_suffix(still_source) in PHOTO_SUFFIXES:
                for slot in STILL_SLOTS:
                    if status.get(slot) != "queued":
                        continue
                    return item_id, slot, still_source, still_caps[slot]
            motion_source = _primary_motion_path(item, root)
            if motion_source is not None and file_suffix(motion_source) in VIDEO_SUFFIXES:
                if status.get("poster") == "queued":
                    return item_id, "poster", motion_source, thumb_px
                if status.get("proxy") == "queued":
                    return item_id, "proxy", motion_source, proxy_width
                if status.get("playback") == "queued":
                    return item_id, "playback", motion_source, 0
    return None


def publish_ready(root: Path, item_id: str, slot: str, relative: str, store: str) -> None:
    before = try_load_item(root, item_id)
    if before is None:
        return
    after = clone(before)
    rend = after["renditions"]
    rend[slot] = relative
    rend["status"][slot] = "ready"
    rend["store"] = store
    after = ordered_item(after)
    transact(
        root,
        [{"path": item_rel(item_id), "before": before, "after": after}],
    )


def publish_error(root: Path, item_id: str, slot: str) -> None:
    publish_slot_status(root, item_id, slot, "error", None)


def publish_not_applicable(root: Path, item_id: str, slot: str) -> None:
    publish_slot_status(root, item_id, slot, "not-applicable", None)


def publish_slot_status(root: Path, item_id: str, slot: str, status: str, relative: str | None) -> None:
    before = try_load_item(root, item_id)
    if before is None:
        return
    after = clone(before)
    rend = after["renditions"]
    rend[slot] = relative
    rend["status"][slot] = status
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
    sweep_library_rendition_tmps(root)
    job = next_rendition_job(root)
    if job is None:
        return False
    item_id, slot, source, cap = job
    item = try_load_item(root, item_id)
    if item is None:
        return False
    from library.activity import note_item

    note_item("renditions", "Previews", item)
    owner = try_load_source(root, (item.get("renditions") or {}).get("sourceId") or "")
    settings = _current_settings(root)
    if ready_slots(item):
        store = (item.get("renditions") or {}).get("store") or "with-server"
    else:
        store = effective_preview_store(owner, settings)
    relative = slot_relative(store, item_id, slot)
    dest_dir = store_dir(store, owner, root, item_id)
    if dest_dir is None:
        publish_error(root, item_id, slot)
        return True
    dest = dest_dir / slot_filename(slot)
    cleanup_tmp_siblings(dest)
    if dest.is_file() and dest.stat().st_size > 0:
        if slot == "playback" and browser_safe_mp4(source):
            try:
                dest.unlink()
            except OSError:
                pass
            publish_not_applicable(root, item_id, slot)
            return True
        publish_ready(root, item_id, slot, relative, store)
        return True
    if slot == "playback":
        outcome = write_playback(source, dest)
        if outcome == "ready":
            publish_ready(root, item_id, slot, relative, store)
        elif outcome == "not-applicable":
            _clear_empty(dest)
            publish_not_applicable(root, item_id, slot)
        else:
            _clear_empty(dest)
            publish_error(root, item_id, slot)
        return True
    writer = write_proxy if slot == "proxy" else write_webp
    if not writer(source, dest, cap):
        _clear_empty(dest)
        publish_error(root, item_id, slot)
        return True
    publish_ready(root, item_id, slot, relative, store)
    return True


def _slot_from_name(name: str) -> str | None:
    if name == "proxy.mp4":
        return "proxy"
    if name == "playback.mp4":
        return "playback"
    if name.endswith(".webp"):
        slot = name[: -len(".webp")]
        if slot in {"thumb", "preview", "poster"}:
            return slot
    return None


def restore_relocate_files(root: Path, entry_id: str) -> None:
    folder = root / "undo" / "files" / entry_id
    if not folder.exists():
        return
    for item_dir in folder.iterdir():
        if not item_dir.is_dir():
            continue
        item = try_load_item(root, item_dir.name)
        if item is None:
            continue
        for file in item_dir.iterdir():
            if not file.is_file() or file.stat().st_size <= 0:
                continue
            slot = _slot_from_name(file.name)
            if slot is None:
                continue
            dest = rendition_abs(item, slot, root)
            if dest is None:
                continue
            copy_verified(file, dest)


def relocate(root: Path) -> dict[str, bool]:
    from library.history import make_history_entry, plan_append

    settings = _current_settings(root)
    failures: list[str] = []
    successful: list[dict[str, Any]] = []
    pending_copies: list[dict[str, Any]] = []

    for item_id in iter_item_ids(root):
        if item_id.startswith("pending-"):
            continue
        item = try_load_item(root, item_id)
        if item is None:
            continue
        slots = ready_slots(item)
        if not slots:
            continue
        owner_id = (item.get("renditions") or {}).get("sourceId")
        owner = try_load_source(root, owner_id or "")
        dest_store = effective_preview_store(owner, settings)
        dest_folder = store_dir(dest_store, owner, root, item_id)
        if dest_folder is None:
            failures.append("unavailable")
            continue
        old_files: dict[str, Path] = {}
        unreadable = False
        for slot in slots:
            path = rendition_abs(item, slot, root)
            if path is None or not path.is_file() or path.stat().st_size <= 0:
                unreadable = True
                break
            old_files[slot] = path
        if unreadable:
            failures.append("unavailable")
            continue
        already = dest_store == (item.get("renditions") or {}).get("store")
        if already:
            all_there = True
            for slot, src in old_files.items():
                dest = dest_folder / slot_filename(slot)
                if src.resolve() != dest.resolve() or not dest.is_file() or dest.stat().st_size <= 0:
                    all_there = False
                    break
            if all_there:
                continue
        written: list[Path] = []
        try:
            for slot, src in old_files.items():
                dest = dest_folder / slot_filename(slot)
                if src.resolve() == dest.resolve():
                    continue
                copy_verified(src, dest)
                written.append(dest)
        except Exception:
            for path in written:
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    pass
            failures.append("io-error")
            continue
        after = clone(item)
        after["renditions"]["store"] = dest_store
        for slot in slots:
            after["renditions"][slot] = slot_relative(dest_store, item_id, slot)
        after = ordered_item(after)
        successful.append(
            {
                "path": item_rel(item_id),
                "before": item,
                "after": after,
            }
        )
        pending_copies.append(
            {
                "item_id": item_id,
                "old_files": old_files,
                "dest_folder": dest_folder,
            }
        )

    if successful:
        entry = make_history_entry(root, "relocate", successful)
        entry_id = entry["id"]
        undo_root = root / "undo" / "files" / entry_id
        try:
            for move in pending_copies:
                item_dir = undo_root / move["item_id"]
                item_dir.mkdir(parents=True, exist_ok=True)
                for slot, src in move["old_files"].items():
                    copy_verified(src, item_dir / slot_filename(slot))
        except Exception as exc:
            if undo_root.exists():
                shutil.rmtree(undo_root, ignore_errors=True)
            raise fail("io-error") from exc
        transact(root, plan_append(root, entry) + successful)
        for move in pending_copies:
            dest_folder = move["dest_folder"]
            for slot, src in move["old_files"].items():
                dest = dest_folder / slot_filename(slot)
                try:
                    if src.exists() and src.resolve() != dest.resolve():
                        src.unlink()
                except OSError:
                    pass
                parent = src.parent
                try:
                    if parent.exists() and parent != dest_folder and not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass

    if failures:
        if "unavailable" in failures:
            raise fail("unavailable")
        raise fail("io-error")
    return {"ok": True}
