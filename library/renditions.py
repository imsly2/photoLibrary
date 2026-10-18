"""Still and video rendition files. Decode with ffmpeg; publish without history."""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from library import folder_library, processing_log
from library.atomic import transact
from library.catalog_io import (
    item_rel,
    iter_item_ids,
    load_item,
    try_load_item,
    try_load_source,
    try_load_source_head,
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
# One video encode (proxy, else playback) after this many viewer previews,
# so a long preview backlog cannot postpone the single clip forever.
_VIDEO_EVERY_PREVIEWS = 6
# Encodes yield the CPU to the browser and to the server's request threads.
_FFMPEG_PRIORITY: dict[str, Any] = (
    {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS} if os.name == "nt" else {}
)
# (root key, item id) an encoder thread is working on; pickers skip them.
_in_flight: set[tuple[str, str]] = set()
last_published_slot: str | None = None
profile_counters = {
    "pick_calls": 0,
    "pick_seconds": 0.0,
    "encode_calls": 0,
    "encode_seconds": 0.0,
}


def reset_profile_counters() -> None:
    global last_published_slot
    last_published_slot = None
    for key in profile_counters:
        profile_counters[key] = 0


def _account_encode(started: float) -> None:
    profile_counters["encode_calls"] += 1
    profile_counters["encode_seconds"] += time.perf_counter() - started


def encoder_count() -> int:
    """How many files encode at once: half the processor threads, 1..6."""
    return max(1, min(6, (os.cpu_count() or 2) // 2))


def encoding(root: Path) -> bool:
    """Some encoder thread is still working on this library."""
    from library.item_index import root_key

    key = root_key(root)
    return any(claim[0] == key for claim in _in_flight)


def _settings(root: Path) -> dict[str, Any]:
    return load_settings_file(root) if settings_path(root).exists() else defaults()


def _settings_caps(data: dict[str, Any]) -> tuple[int, int, int]:
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
        f"'if(lt(iw,ih),min(ih,{cap}),-2)':flags=bilinear"
    )


# libwebp method 2 rather than the default 4: same quality setting, much less
# encode time per photo for slightly larger files.
WEBP_ENCODE = ("-compression_level", "2", "-f", "webp")


def write_webp(source: Path, dest: Path, cap: int) -> bool:
    started = time.perf_counter()
    try:
        return _write_webp(source, dest, cap)
    finally:
        _account_encode(started)


def _write_webp(source: Path, dest: Path, cap: int) -> bool:
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
                *WEBP_ENCODE,
                str(tmp),
            ],
            capture_output=True,
            check=False,
            **_FFMPEG_PRIORITY,
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
    for path in parent.glob(f"{glob.escape(dest.name)}.*.tmp"):
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
        proc = subprocess.run(args + [str(tmp)], capture_output=True, check=False, **_FFMPEG_PRIORITY)
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
    started = time.perf_counter()
    try:
        return _write_playback(source, dest)
    finally:
        _account_encode(started)


def _write_playback(source: Path, dest: Path) -> str:
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
    started = time.perf_counter()
    try:
        return _write_proxy(source, dest, cap)
    finally:
        _account_encode(started)


def _write_proxy(source: Path, dest: Path, cap: int) -> bool:
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


FOLDER_STORES = folder_library.STORES


def _folder_target(root: Path, item: dict[str, Any], slot: str) -> tuple[str, Path | None, str | None]:
    """F23 (store, path, recorded name) for this slot; path None when unreachable.

    An F23 item keeps its recorded folder library so its files stay together;
    any other item goes where the settings send new files now.
    """
    rend = item.get("renditions") or {}
    source = try_load_source_head(root, rend.get("sourceId") or "")
    if source is None:
        return folder_library.FOLDER_SERVER, None, None
    recorded = rend.get("store")
    store = recorded if recorded in FOLDER_STORES else folder_library.current_store(root, source)
    library = folder_library.for_source(root, source, store)
    rel = folder_library.item_rel(source, item)
    if library is None or rel is None:
        return store, None, None
    name = folder_library.derived_name(rel, slot)
    return store, library.path(name), name


def slot_target(root: Path, item: dict[str, Any], slot: str) -> tuple[str, Path | None, str | None]:
    """Where a new file for this slot goes: (store, path, recorded relative).

    Items with ready files in an old layout keep it until migration moves them;
    everything else is written to an F23 folder library.
    """
    rend = item.get("renditions") or {}
    recorded = rend.get("store")
    if recorded in PREVIEW_STORES and ready_slots(item):
        owner = try_load_source(root, rend.get("sourceId") or "")
        folder = store_dir(recorded, owner, root, item["id"])
        dest = None if folder is None else folder / slot_filename(slot)
        return recorded, dest, slot_relative(recorded, item["id"], slot)
    return _folder_target(root, item, slot)


def _folder_file(root: Path, rend: dict[str, Any], relative: str) -> Path | None:
    library = folder_library.for_source_id(root, str(rend.get("sourceId") or ""), rend.get("store"))
    if library is None:
        return None
    try:
        return library.path(relative)
    except ValueError:
        return None


def rendition_abs(item: dict[str, Any], slot: str, library_root: Path) -> Path | None:
    rend = item.get("renditions") or {}
    relative = rend.get(slot)
    if type(relative) is str and relative:
        store = rend.get("store")
        if store in FOLDER_STORES:
            found = _usable_file(_folder_file(library_root, rend, relative))
            if found is not None:
                return found
        elif store == "with-server":
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
    found = _usable_file(_folder_target(library_root, item, slot)[1])
    if found is not None:
        return found
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


def note_wanted(root: Path, item_id: str) -> None:
    """Viewer opened this item. The next drain step does its preview first."""
    from library.item_index import note_wanted as remember

    remember(root, item_id)


MISSING_SWEEP_SEC = 30.0
_last_missing_sweep: dict[str, float] = {}
_missing_hinted: set[str] = set()


def note_missing(root: Path) -> None:
    """A media request found no file; the next idle drain step sweeps right away."""
    from library.item_index import root_key

    _missing_hinted.add(root_key(root))


def requeue_missing_renditions(root: Path, *, io_context=nullcontext) -> bool:
    """Queue again every ready slot whose file is gone (e.g. a deleted .library/).

    Runs when hinted by a failed media request, otherwise every MISSING_SWEEP_SEC.
    Folders that are not reachable right now are skipped, never requeued.
    """
    from library.item_index import iter_items, root_key

    key = root_key(root)
    now = time.monotonic()
    if key not in _missing_hinted and now - _last_missing_sweep.get(key, -MISSING_SWEEP_SEC) < MISSING_SWEEP_SEC:
        return False
    _missing_hinted.discard(key)
    _last_missing_sweep[key] = now
    folders: dict[str, Path | None] = {}
    expected: list[tuple[str, str, Path]] = []
    for item in iter_items(root):
        rend = item.get("renditions") or {}
        status = rend.get("status") or {}
        for slot in STILL_SLOTS + VIDEO_SLOTS:
            relative = rend.get(slot)
            if status.get(slot) != "ready" or type(relative) is not str or not relative:
                continue
            if rend.get("store") in FOLDER_STORES:
                source_id = rend.get("sourceId") or ""
                lib_key = f"{rend['store']}:{source_id}"
                if lib_key not in folders:
                    library = folder_library.for_source_id(root, source_id, rend["store"])
                    folders[lib_key] = None if library is None else library.dir
                if folders[lib_key] is None:
                    continue
                path = _folder_file(root, rend, relative)
                if path is None:
                    continue
            elif rend.get("store") == "with-server":
                try:
                    path = library_path(root, relative)
                except Exception:
                    continue
            else:
                source_id = rend.get("sourceId") or ""
                if source_id not in folders:
                    source = try_load_source(root, source_id)
                    folder = None if source is None else source_preview_root(source, root)
                    folders[source_id] = folder if folder is not None and folder.is_dir() else None
                folder = folders[source_id]
                path = None if folder is None else _safe_join(folder, relative)
                if path is None:
                    continue
            expected.append((item["id"], slot, path))
    with io_context():
        missing = [(item_id, slot) for item_id, slot, path in expected if _usable_file(path) is None]
    requeued = False
    for item_id, slot in missing:
        current = try_load_item(root, item_id)
        if current is None or ((current.get("renditions") or {}).get("status") or {}).get(slot) != "ready":
            continue
        if rendition_abs(current, slot, root) is not None:
            continue
        publish_slot_status(root, item_id, slot, "queued", None)
        requeued = True
    return requeued


def _ready_preview_sibling(dest: Path) -> Path | None:
    """Thumb can be a downscale of a preview ffmpeg already oriented."""
    if not dest.name.endswith("thumb.webp"):
        return None
    preview = dest.with_name(dest.name[: -len("thumb.webp")] + "preview.webp")
    try:
        if preview.is_file() and preview.stat().st_size > 0:
            return preview
    except OSError:
        return None
    return None


def _job_if_ready(
    root: Path,
    item: dict[str, Any],
    slot: str,
    caps: dict[str, int],
) -> tuple[str, str, Path, int] | None:
    item_id = item.get("id")
    if type(item_id) is not str or not item_id or item_id.startswith("pending-"):
        return None
    source = (
        _primary_still_path(item, root)
        if slot in STILL_SLOTS
        else _primary_motion_path(item, root)
    )
    suffixes = PHOTO_SUFFIXES if slot in STILL_SLOTS else VIDEO_SUFFIXES
    if source is None or file_suffix(source) not in suffixes:
        return None
    return item_id, slot, source, caps[slot]


def next_rendition_job(root: Path) -> tuple[str, str, Path, int] | None:
    profile_counters["pick_calls"] += 1
    started = time.perf_counter()
    try:
        return _next_rendition_job(root)
    finally:
        profile_counters["pick_seconds"] += time.perf_counter() - started


def _next_rendition_job(root: Path) -> tuple[str, str, Path, int] | None:
    from library.grid_order import descending
    from library.item_index import resync, root_key, set_grid_order, wanted_ids

    settings = _settings(root)
    thumb_px, preview_px, proxy_width = _settings_caps(settings)
    caps = {
        "thumb": thumb_px,
        "poster": thumb_px,
        "preview": preview_px,
        "proxy": proxy_width,
        "playback": 0,
    }
    cache = resync(root)
    set_grid_order(root, settings["sort"], descending(settings))
    key = root_key(root)

    def take(item_id: str, slot: str) -> tuple[str, str, Path, int] | None:
        if item_id not in cache.queued.get(slot, ()) or (key, item_id) in _in_flight:
            return None
        item = cache.items.get(item_id)
        if item is None:
            return None
        return _job_if_ready(root, item, slot, caps)

    # A picture opened in the viewer gets its 1600px preview on the next step,
    # including while thumbs are queued and while a scan is still running.
    for item_id in wanted_ids(root):
        item = cache.items.get(item_id)
        if item is None:
            continue
        if item.get("kind") == "video":
            slots = ("poster", "proxy", "playback")
        else:
            slots = ("preview",)
        for slot in slots:
            job = take(item_id, slot)
            if job is not None:
                return job

    for slot in ("thumb", "poster"):
        for item_id in cache.in_grid_order(slot):
            job = take(item_id, slot)
            if job is not None:
                return job

    video_waiting = bool(cache.queued["proxy"] or cache.queued["playback"])
    if video_waiting and cache.since_video >= _VIDEO_EVERY_PREVIEWS:
        for slot in ("proxy", "playback"):
            for item_id in cache.in_grid_order(slot):
                job = take(item_id, slot)
                if job is not None:
                    return job

    for slot in ("preview", "proxy", "playback"):
        for item_id in cache.in_grid_order(slot):
            job = take(item_id, slot)
            if job is not None:
                return job
    return None


def _note_fairness(root: Path, slot: str) -> None:
    from library.item_index import _caches, root_key

    cache = _caches.get(root_key(root))
    if cache is None:
        return
    if slot == "preview":
        cache.since_video += 1
    elif slot in {"proxy", "playback"}:
        cache.since_video = 0


def adopt_ready_files(root: Path, source: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Mark with-source slots ready when the preview file is already in the folder."""
    item_id = item.get("id")
    if type(item_id) is not str or not item_id or item_id.startswith("pending-"):
        return item
    adopted = _adopt_folder_files(root, source, item)
    if adopted is not None:
        return adopted
    store = effective_preview_store(source, _current_settings(root))
    if store != "with-source":
        return item
    rend = clone(item.get("renditions") or {})
    status = dict(rend.get("status") or {})
    changed = False
    for slot, state in list(status.items()):
        if state not in {"queued", "error"}:
            continue
        folder = store_dir("with-source", source, root, item_id)
        if folder is None:
            continue
        dest = folder / slot_filename(slot)
        try:
            present = dest.is_file() and dest.stat().st_size > 0
        except OSError:
            present = False
        if not present:
            continue
        rend[slot] = slot_relative("with-source", item_id, slot)
        status[slot] = "ready"
        changed = True
    if not changed:
        return item
    rend["store"] = "with-source"
    rend["sourceId"] = source.get("id") or rend.get("sourceId")
    rend["status"] = status
    updated = clone(item)
    updated["renditions"] = rend
    return ordered_item(updated)


def _adopt_folder_files(root: Path, source: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    """Mark waiting slots ready when the F23 file is already in the folder library."""
    rend = clone(item.get("renditions") or {})
    if rend.get("store") in PREVIEW_STORES and ready_slots(item):
        return None
    store = rend.get("store")
    if store not in FOLDER_STORES:
        store = folder_library.current_store(root, source)
    library = folder_library.for_source(root, source, store)
    rel = folder_library.item_rel(source, item)
    if library is None or rel is None:
        return None
    status = dict(rend.get("status") or {})
    changed = False
    for slot, state in list(status.items()):
        if state not in {"queued", "error"} or slot not in folder_library.SUFFIXES:
            continue
        name = folder_library.derived_name(rel, slot)
        if _usable_file(library.path(name)) is None:
            continue
        rend[slot] = name
        status[slot] = "ready"
        changed = True
    if not changed:
        return None
    rend["store"] = store
    rend["sourceId"] = source.get("id") or rend.get("sourceId")
    rend["status"] = status
    updated = clone(item)
    updated["renditions"] = rend
    return ordered_item(updated)


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
    _publish_change(root, item_rel(item_id), before, after)


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
    _publish_change(root, item_rel(item_id), before, after)


_pending_mirrors: dict[str, list[dict[str, Any]]] = {}


def _publish_change(root: Path, relative: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    """Replace one item file. The temp is fsynced before the replace.

    One file, no transaction manifest. The portable copy waits until the
    rendition queue is idle. `before` is unused; callers still pass it so the
    publication site reads as a before/after edit.
    """
    del before
    from library import item_store
    from library.item_index import remember_write, root_key

    item_id = item_store.item_id_of(relative)
    if item_id is None:
        raise ValueError(f"not an item record: {relative}")
    item_store.write(root, item_id, after, sync=True)
    remember_write(root, item_id, after)
    _pending_mirrors.setdefault(root_key(root), []).append(after)


def settle_rendition_publications(root: Path) -> None:
    """Copy published items into portable folders once the rendition queue is idle.

    Item bytes are already durable. This uses portable.mirror_changes for the
    records written since the last idle point, then portable.flush for each
    folder's source snapshot.
    """
    from library.item_index import root_key
    from library.portable import flush, mirror_changes

    remembered = _pending_mirrors.pop(root_key(root), [])
    changes: list[dict[str, Any]] = []
    for item in remembered:
        item_id = item.get("id")
        if type(item_id) is str:
            changes.append({"path": item_rel(item_id), "before": None, "after": item})
    if changes:
        try:
            mirror_changes(root, changes)
        except Exception:
            pass
    try:
        flush(root)
    except Exception:
        pass


def _clear_empty(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size <= 0:
            path.unlink()
    except OSError:
        pass


def _job_destination(root: Path, item: dict[str, Any], slot: str) -> tuple[str, Path | None]:
    store, dest, _relative = slot_target(root, item, slot)
    return store, dest


def _source_signature(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def drain_step(root: Path, *, io_context=nullcontext, sweep: bool = True) -> bool:
    """Encode one queued file. Caller holds the catalog lock; encoding releases it.

    Several threads may call this at once (``encoder_count``); each claims its
    item so no two encode the same picture. ``sweep=False`` (the extra encoder
    threads) skips the idle missing-file sweep and publication settling.
    """
    global last_published_slot
    last_published_slot = None
    sweep_library_rendition_tmps(root)
    job = next_rendition_job(root)
    if job is None:
        if not sweep or encoding(root):
            return False
        if requeue_missing_renditions(root, io_context=io_context):
            return True
        settle_rendition_publications(root)
        return False
    item_id, slot, source, cap = job
    from library.item_index import root_key

    claim = (root_key(root), item_id)
    _in_flight.add(claim)
    try:
        return _encode_job(root, item_id, slot, source, cap, io_context)
    finally:
        _in_flight.discard(claim)


def _encode_job(root: Path, item_id: str, slot: str, source: Path, cap: int, io_context) -> bool:
    global last_published_slot
    last_published_slot = slot
    item = try_load_item(root, item_id)
    if item is None:
        return False
    from library.activity import note_item, clear

    note_item("renditions", "Previews", item, derivative=slot)
    store, dest = _job_destination(root, item, slot)
    if dest is None:
        publish_error(root, item_id, slot)
        clear()
        return True
    before_renditions = clone(item.get("renditions") or {})
    before_locations = clone(item.get("locations") or [])
    _note_fairness(root, slot)
    stage = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.tmp")
    owner_id = before_renditions.get("sourceId") or ""
    owner = try_load_source(root, owner_id)
    owner_origin = clone(owner.get("origin")) if owner else None
    outcome = "error"
    encode_sec = None
    signature = None
    try:
        with io_context():
            try:
                cleanup_tmp_siblings(dest)
                signature = _source_signature(source)
                if slot == "playback" and browser_safe_mp4(source):
                    outcome = "not-applicable"
                elif dest.is_file() and dest.stat().st_size > 0:
                    outcome = "existing"
                elif slot == "playback":
                    outcome = write_playback(source, stage)
                else:
                    writer = write_proxy if slot == "proxy" else write_webp
                    encode_source = source
                    # A viewer preview is already oriented. Scaling that webp
                    # avoids a second full decode of the original JPEG.
                    if slot == "thumb" and writer is write_webp:
                        sibling = _ready_preview_sibling(dest)
                        if sibling is not None:
                            encode_source = sibling
                    started = time.perf_counter()
                    outcome = "ready" if writer(encode_source, stage, cap) else "error"
                    encode_sec = time.perf_counter() - started
            except OSError:
                outcome = "error"
        current = try_load_item(root, item_id)
        if current is None:
            return True
        # Annotation changes survive: publish helpers clone the fresh record.
        # A removed/replaced item, relocated store, or changed original invalidates
        # this computation; leave current queue state for the next drain step.
        current_renditions = current.get("renditions") or {}
        if current_renditions != before_renditions or current.get("locations") != before_locations:
            return True
        current_owner = try_load_source(root, owner_id)
        if (current_owner.get("origin") if current_owner else None) != owner_origin:
            return True
        current_source = (_primary_still_path(current, root) if slot in STILL_SLOTS
                          else _primary_motion_path(current, root))
        if current_source != source or _job_destination(root, current, slot) != (store, dest):
            return True
        try:
            if signature is not None and _source_signature(source) != signature:
                return True
        except OSError:
            outcome = "error"
        if outcome == "ready":
            os.replace(stage, dest)
        if outcome in {"ready", "existing"}:
            publish_ready(root, item_id, slot, slot_target(root, current, slot)[2], store)
        elif outcome == "not-applicable":
            dest.unlink(missing_ok=True)
            publish_not_applicable(root, item_id, slot)
        else:
            publish_error(root, item_id, slot)
        processing_log.note_slot(slot, outcome, encode_sec)
        return True
    finally:
        try:
            stage.unlink(missing_ok=True)
        except OSError:
            pass
        clear()


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
            # Restoration writes the location recorded by undo. Lookup fallback
            # is for serving readable files and could select the relocated copy.
            rend = item.get("renditions") or {}
            relative = rend.get(slot)
            if type(relative) is not str or not relative:
                continue
            if rend.get("store") in FOLDER_STORES:
                dest = _folder_file(root, rend, relative)
            elif rend.get("store") == "with-server":
                dest = library_path(root, relative)
            else:
                owner = try_load_source(root, rend.get("sourceId") or "")
                source_root = source_preview_root(owner, root) if owner else None
                dest = _safe_join(source_root, relative) if source_root else None
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
        rend = item.get("renditions") or {}
        owner = try_load_source(root, rend.get("sourceId") or "")
        dest_store = effective_preview_store(owner, settings)
        if rend.get("store") in FOLDER_STORES:
            dest_store = folder_library.store_for(dest_store)
            library = folder_library.for_source(root, owner, dest_store)
            dests = None if library is None else {slot: library.path(rend[slot]) for slot in slots}
        else:
            dest_folder = store_dir(dest_store, owner, root, item_id)
            dests = None if dest_folder is None else {slot: dest_folder / slot_filename(slot) for slot in slots}
        if dests is None:
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
        already = dest_store == rend.get("store")
        if already:
            all_there = True
            for slot, src in old_files.items():
                dest = dests[slot]
                if src.resolve() != dest.resolve() or not dest.is_file() or dest.stat().st_size <= 0:
                    all_there = False
                    break
            if all_there:
                continue
        written: list[Path] = []
        try:
            for slot, src in old_files.items():
                dest = dests[slot]
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
        if dest_store not in FOLDER_STORES:
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
        pending_copies.append({"item_id": item_id, "old_files": old_files, "dests": dests})

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
            for slot, src in move["old_files"].items():
                dest = move["dests"][slot]
                try:
                    if src.exists() and src.resolve() != dest.resolve():
                        src.unlink()
                except OSError:
                    pass
                parent = src.parent
                try:
                    if parent.exists() and parent != dest.parent and not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass

    if failures:
        if "unavailable" in failures:
            raise fail("unavailable")
        raise fail("io-error")
    return {"ok": True}
