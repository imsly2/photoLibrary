"""Linked serve-from-there scan: pending id, then hash id."""

from __future__ import annotations

import cProfile
import json
import os
import pstats
import time
from contextlib import nullcontext
from contextvars import ContextVar
import unicodedata
from pathlib import Path
from typing import Any, Callable

from library import item_store
from library.atomic import maybe_test_barrier, transact
from library.catalog_io import (
    catalog_overlay,
    drop_catalog_overlay,
    ensure_catalog_dirs,
    find_source_by_origin,
    fold_source_changes,
    item_rel,
    load_source,
    new_source_id,
    pair_live_items,
    place_rel,
    note_catalog_overlay,
    note_source_write,
    plan_source_file,
    relative_from_origin,
    source_rel,
    try_load_item,
    try_load_place,
    try_load_source,
)
from library.errors import fail
from library.history import extend_current_operation, make_history_entry, plan_append
from library.media import (
    HEIF_SUFFIXES,
    default_component,
    file_suffix,
    heif_has_valid_brand,
    is_allowed_media,
    media_kind,
    mtime_iso,
    read_content_identifier,
    read_source,
    sha256_text,
)
from library.metadata import read_capture
from library.places import named_place_update, resolve_place
from library.recent import remember_recent
from library.paths import normalize_root, roots_equal
from library.records import (
    clone,
    location_key,
    make_file_entry,
    make_item,
    make_location,
    make_source,
    ordered_item,
    ordered_source,
    browser_ready_still,
    renditions_for,
)
from library.settings import defaults, load_settings_file, settings_path
from library.volumes import last_known_text, path_from_volume_root, volume_of_path

ProgressFn = Callable[[str, str], None]
BetweenFn = Callable[[], None]


def is_link_or_junction(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
    except OSError:
        return False
    return False


def normalize_rel(rel: str) -> str:
    return unicodedata.normalize("NFC", rel.replace("\\", "/"))


def pending_id(source_id: str, rel: str) -> str:
    digest = sha256_text(normalize_rel(rel))
    return f"pending-{source_id}-{digest}"


def assert_scan_path_allowed(scan_path: Path, library_root: Path) -> Path:
    scan = normalize_root(scan_path)
    data = normalize_root(library_root)
    if not scan.exists() or not scan.is_dir():
        raise fail("invalid-argument")
    if roots_equal(scan, data):
        raise fail("invalid-argument")
    try:
        scan.relative_to(data)
        raise fail("invalid-argument")
    except ValueError:
        pass
    if is_link_or_junction(scan):
        raise fail("invalid-argument")
    return scan


def _skip_dir(path: Path, library_root: Path) -> bool:
    if path.name == ".library":
        return True
    if is_link_or_junction(path):
        return True
    try:
        if roots_equal(path, library_root):
            return True
    except OSError:
        return True
    return False


def iter_media_files(scan_path: Path, library_root: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    scan_path = normalize_root(scan_path)
    for dirpath, dirnames, filenames in os.walk(scan_path, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not _skip_dir(current / name, library_root)
        )
        for name in filenames:
            path = current / name
            if is_link_or_junction(path):
                continue
            if ".partial-" in name:
                continue
            if not is_allowed_media(path):
                continue
            rel = normalize_rel(path.relative_to(scan_path).as_posix())
            found.append((rel, path))
    found.sort(key=lambda item: item[0])
    return found


def _in_grid_order(
    root: Path, source: dict[str, Any], files: list[tuple[str, Path]]
) -> list[tuple[str, Path]]:
    """Unchanged files first (they are skipped), then new ones in grid order,
    so each new tile lands below the ones already showing."""
    from library.grid_order import descending
    from library.metadata import quick_captured_at

    settings = load_settings_file(root) if settings_path(root).exists() else defaults()
    known = source.get("files") or {}
    unchanged = [row for row in files if _unchanged(known.get(row[0]), row[1], root)]
    if len(unchanged) == len(files):
        return files
    seen = {rel for rel, _ in unchanged}
    fresh = [row for row in files if row[0] not in seen]
    if settings["sort"] == "name":
        fresh.sort(key=lambda row: (Path(row[0]).name, row[0]), reverse=descending(settings))
    else:
        dates = {rel: quick_captured_at(path) for rel, path in fresh}
        fresh.sort(key=lambda row: (dates[row[0]], row[0]), reverse=descending(settings))
    return unchanged + fresh


def _place_match_meters(root: Path) -> float:
    path = settings_path(root)
    if not path.exists():
        return float(defaults()["placeMatchMeters"])
    return float(load_settings_file(root)["placeMatchMeters"])


def _unchanged(entry: dict[str, Any] | None, path: Path, root: Path | None = None) -> bool:
    if entry is None:
        return False
    check = path
    dest = entry.get("destination")
    if type(dest) is str and dest and root is not None:
        from library.paths import library_path

        try:
            check = library_path(root, dest)
        except Exception:
            return False
    try:
        stat = check.stat()
    except OSError:
        return False
    if not (
        entry.get("state") == "indexed"
        and entry.get("sizeBytes") == stat.st_size
        and entry.get("modifiedAt") == mtime_iso(check)
    ):
        return False
    item_id = entry.get("itemId")
    if root is not None and type(item_id) is str and not item_id.startswith("pending-"):
        # A deleted folder library took this record with it: read the picture again.
        return item_store.path_for(root, item_id).is_file()
    return True


_SCAN_BATCH: ContextVar[list[dict[str, Any]] | None] = ContextVar("scan_batch", default=None)
_BATCH_LIMIT = 48


_YIELD_INTERVAL = 0.5


def _due_for_pending_pause(between: BetweenFn | None, last: float) -> bool:
    """True when this file should stop on its pending id so readers can attach."""
    if between is None:
        return False
    if not last:
        return True
    return time.perf_counter() - last >= _YIELD_INTERVAL


def _flush_scan_batch(root: Path) -> None:
    batch = _SCAN_BATCH.get()
    if not batch:
        return
    changes = list(batch)
    transact(root, extend_current_operation(root, changes))
    batch.clear()
    for change in changes:
        path = change.get("path")
        if type(path) is str:
            drop_catalog_overlay(path)


def _extend(root: Path, changes: list[dict[str, Any]]) -> None:
    batch = _SCAN_BATCH.get()
    if batch is None:
        transact(root, extend_current_operation(root, changes))
        return
    for change in changes:
        path = change.get("path")
        if type(path) is not str:
            continue
        note_catalog_overlay(path, change.get("after"))
        if ".files/" in path:
            note_source_write(root, path, change.get("after"))
    batch.extend(changes)
    if len(batch) >= _BATCH_LIMIT:
        _flush_scan_batch(root)


def _fold_scan_source(
    root: Path,
    source: dict[str, Any],
    *,
    added: int,
    skipped: int,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    current = try_load_source(root, source["id"]) or source
    current["scan"] = {
        "state": "error" if errors else "complete",
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
    _extend(root, fold_source_changes(root, current))
    return try_load_source(root, source["id"]) or current


def _hash_barrier_armed() -> bool:
    return os.environ.get("LIBRARY_TEST") == "1" and os.environ.get("LIBRARY_TEST_BARRIER") == "hash-publication"


_profile_on: ContextVar[bool] = ContextVar("scan_profile_on", default=False)
_profile_yields: list[dict[str, float]] = []
_profile_files: list[float] = []


def note_scan_yield(sleep_s: float, wait_s: float) -> None:
    if _profile_on.get():
        _profile_yields.append({"sleep": sleep_s, "wait": wait_s})


def _note_scan_file() -> None:
    if _profile_on.get():
        _profile_files.append(time.perf_counter())


def _observe_progress(on_progress: ProgressFn) -> ProgressFn:
    if not _profile_on.get():
        return on_progress

    def wrapped(kind: str, rel: str) -> None:
        on_progress(kind, rel)
        _note_scan_file()

    return wrapped


def _profile_target() -> Path | None:
    raw = os.environ.get("LIBRARY_PROFILE_SCAN", "").strip()
    if not raw:
        return None
    return Path(raw)


def _write_scan_profile(prof: cProfile.Profile | None, target: Path, seconds: float) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    prof_path = target if target.suffix == ".prof" else target.with_suffix(".prof")
    json_path = prof_path.with_suffix(".json")
    rows: list[dict[str, Any]] = []
    if prof is not None:
        prof.dump_stats(str(prof_path))
        for (filename, line, func), (_cc, nc, tt, ct, _callers) in pstats.Stats(prof).stats.items():
            rows.append(
                {
                    "func": func,
                    "file": filename,
                    "line": line,
                    "calls": nc,
                    "tottime": round(tt, 4),
                    "cumtime": round(ct, 4),
                }
            )
    rows.sort(key=lambda row: row["tottime"], reverse=True)
    deltas: list[float] = []
    previous = _profile_t0[0]
    for stamp in _profile_files:
        deltas.append(round(stamp - previous, 4))
        previous = stamp
    sleep = sum(row["sleep"] for row in _profile_yields)
    wait = sum(row["wait"] for row in _profile_yields)
    n = len(deltas)
    tenth = max(1, n // 10)
    def _mean(group: list[float]) -> float | None:
        return round(sum(group) / len(group), 4) if group else None
    payload = {
        "seconds": round(seconds, 3),
        "files": n,
        "perFile": deltas,
        "perFileMean": _mean(deltas),
        "firstTenthMean": _mean(deltas[:tenth]),
        "lastTenthMean": _mean(deltas[-tenth:]),
        "lastToFirst": (
            round((_mean(deltas[-tenth:]) or 0) / _mean(deltas[:tenth]), 3)
            if _mean(deltas[:tenth])
            else None
        ),
        "yields": {
            "n": len(_profile_yields),
            "sleepSec": round(sleep, 3),
            "waitSec": round(wait, 3),
            "sleepMeanMs": round(1000 * sleep / len(_profile_yields), 2) if _profile_yields else 0,
            "waitMeanMs": round(1000 * wait / len(_profile_yields), 2) if _profile_yields else 0,
        },
        "functions": rows[:40],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


_profile_t0: list[float] = [0.0]


def _run_scoped_scan(
    root: Path,
    body: Callable[[], dict[str, Any]],
    *,
    batch: bool,
) -> dict[str, Any]:
    target = _profile_target()
    cpu = os.environ.get("LIBRARY_PROFILE_CPU", "1") != "0"
    prof = cProfile.Profile() if target is not None and cpu else None
    token = _profile_on.set(target is not None)
    _profile_yields.clear()
    _profile_files.clear()
    _profile_t0[0] = time.perf_counter()
    if prof is not None:
        prof.enable()
    started = time.perf_counter()
    try:
        return _scoped_scan(root, body, batch=batch)
    finally:
        seconds = time.perf_counter() - started
        if prof is not None:
            prof.disable()
        _profile_on.reset(token)
        if target is not None:
            _write_scan_profile(prof, target, seconds)


def _scoped_scan(
    root: Path,
    body: Callable[[], dict[str, Any]],
    *,
    batch: bool,
) -> dict[str, Any]:
    from library.atomic import checkpoint_transactions, holding_open_transactions, relaxed_durability
    from library.history import batching_history, seal_latest
    from library.portable import sync_bundles
    from library.volumes import volume_lookup_scope

    batch_token = _SCAN_BATCH.set([] if batch else None)
    try:
        with holding_open_transactions(root):
            try:
                with batching_history(), volume_lookup_scope(), relaxed_durability(), catalog_overlay():
                    try:
                        source = body()
                    finally:
                        _flush_scan_batch(root)
                        from library.catalog_io import fold_open_journals

                        fold_open_journals(root)
                        checkpoint_transactions(root)
            finally:
                seal_latest(root)
    finally:
        _SCAN_BATCH.reset(batch_token)
        from library.activity import clear as clear_activity

        # Catalog files are already durable. Portable copy and the sqlite
        # rebuild keep running; readers can see the scan finish without waiting.
        clear_activity("scan")
        sync_bundles(root)
    maybe_test_barrier("catalog-committed")
    from library.index import rebuild_sqlite

    rebuild_sqlite(root, use_barrier=True)
    source_id = source.get("id") if isinstance(source, dict) else None
    if type(source_id) is str:
        source = try_load_source(root, source_id) or source
    return source


def _start_source(
    root: Path,
    scan_path: Path,
    preview_store: str | None,
    mode: str = "serve-from-there",
) -> dict[str, Any]:
    from library.copy import copy_root_rel

    ensure_catalog_dirs(root)
    serial, volume_root = volume_of_path(scan_path)
    origin_rel = path_from_volume_root(scan_path, volume_root)
    existing = find_source_by_origin(root, serial, origin_rel)
    if existing is None and mode == "serve-from-there":
        from library.portable import adopt_folder

        existing = adopt_folder(root, scan_path)
    origin = {
        "volumeSerial": serial,
        "pathFromVolumeRoot": origin_rel,
        "lastKnownPath": last_known_text(scan_path),
    }
    if existing is None:
        source_id = new_source_id(root)
        copy_root = copy_root_rel(scan_path.name, source_id) if mode == "copy-here" else None
        source = make_source(
            source_id=source_id,
            name=scan_path.name,
            mode=mode,
            origin=origin,
            copy_root=copy_root,
            preview_store=preview_store,
            files={},
            scan={"state": "running", "added": 0, "skipped": 0, "errors": []},
        )
        changes = [
            {"path": source_rel(source["id"]), "before": None, "after": source},
        ]
        entry = make_history_entry(root, "scan", changes)
        transact(root, plan_append(root, entry) + changes)
        item_store.invalidate(root)
        return source
    before = clone(existing)
    existing["origin"] = origin
    existing["scan"] = {"state": "running", "added": 0, "skipped": 0, "errors": []}
    if preview_store is not None:
        existing["previewStore"] = preview_store
    if mode == "copy-here":
        existing["mode"] = "copy-here"
        if not existing.get("copyRoot"):
            existing["copyRoot"] = copy_root_rel(existing["name"], existing["id"])
    source = ordered_source(existing)
    changes = [
        {"path": source_rel(source["id"]), "before": before, "after": source},
    ]
    entry = make_history_entry(root, "scan", changes)
    transact(root, plan_append(root, entry) + changes)
    item_store.invalidate(root)
    return source


def start_rescan_source(root: Path, source_id: str) -> tuple[dict[str, Any], Path]:
    """Reset scan on an existing source. Does not create a second source."""
    from library.sources import resolve_source_folder

    source = load_source(root, source_id)
    folder = resolve_source_folder(source, root)
    if folder is None:
        raise fail("unavailable")
    folder = assert_scan_path_allowed(folder, root)
    before = clone(source)
    origin = dict(source.get("origin") or {})
    origin["lastKnownPath"] = last_known_text(folder)
    try:
        serial, volume_root = volume_of_path(folder)
        origin["volumeSerial"] = serial
        origin["pathFromVolumeRoot"] = path_from_volume_root(folder, volume_root)
    except Exception:
        pass
    source["origin"] = origin
    source["scan"] = {"state": "running", "added": 0, "skipped": 0, "errors": []}
    source = ordered_source(source)
    changes = [
        {"path": source_rel(source["id"]), "before": before, "after": source},
    ]
    entry = make_history_entry(root, "scan", changes)
    transact(root, plan_append(root, entry) + changes)
    return source, folder


def _retry_error_renditions(root: Path, entry: dict[str, Any] | None, path: Path) -> None:
    if entry is None:
        return
    item_id = entry.get("itemId")
    if type(item_id) is not str or item_id.startswith("pending-"):
        return
    if file_suffix(path) in HEIF_SUFFIXES and not heif_has_valid_brand(path):
        return
    item = try_load_item(root, item_id)
    if item is None:
        return
    status = ((item.get("renditions") or {}).get("status") or {})
    slots = [slot for slot in ("thumb", "preview", "poster", "proxy", "playback") if status.get(slot) == "error"]
    if not slots:
        return
    before = clone(item)
    after = clone(item)
    for slot in slots:
        after["renditions"][slot] = None
        after["renditions"]["status"][slot] = "queued"
    transact(
        root,
        [{"path": item_rel(item_id), "before": before, "after": ordered_item(after)}],
    )


def _retire_replaced_location(
    root: Path,
    prev_item_id: str | None,
    new_item_id: str,
    incoming: dict[str, Any],
) -> list[dict[str, Any]]:
    if type(prev_item_id) is not str or not prev_item_id:
        return []
    if prev_item_id.startswith("pending-") or prev_item_id == new_item_id:
        return []
    old = try_load_item(root, prev_item_id)
    if old is None:
        return []
    before = clone(old)
    after = clone(old)
    key = location_key(incoming)
    changed = False
    for loc in after["locations"]:
        if location_key(loc) == key and loc.get("current") is True:
            loc["current"] = False
            changed = True
    if not changed:
        return []
    return [
        {
            "path": item_rel(prev_item_id),
            "before": before,
            "after": ordered_item(after),
        }
    ]


def _index_file(
    root: Path,
    source: dict[str, Any],
    rel: str,
    path: Path,
    match_meters: float,
    *,
    original_name: str | None = None,
    between: BetweenFn | None = None,
    io_context=nullcontext,
) -> str:
    from library.copy import make_library_location

    with io_context():
        kind = media_kind(path)
        component = default_component(kind)
        # One pass over the file: the hash, EXIF and the content identifier all
        # come from the same bytes instead of three reads of a slow drive.
        try:
            source_read = read_source(path)
            size, modified, digest = source_read.size, source_read.modified, source_read.sha256
            later = path.stat()
            if later.st_size != size or mtime_iso(path) != modified:
                raise fail("io-error")
        except OSError as exc:
            raise fail("io-error") from exc
        data = source_read.data
        decode_error = file_suffix(path) in HEIF_SUFFIXES and not heif_has_valid_brand(path, data)
        content_id = None
        try:
            content_id = read_content_identifier(path, data)
        except OSError:
            content_id = None
        try:
            captured_at, captured_source, metadata = read_capture(path, data)
        except OSError:
            captured_at, captured_source, metadata = modified, "mtime", None
        if path.stat().st_size != size or mtime_iso(path) != modified:
            raise fail("io-error")
    source = try_load_source(root, source["id"]) or source
    prev_entry = (source.get("files") or {}).get(rel)
    prev_item_id = prev_entry.get("itemId") if prev_entry else None
    source_id = source["id"]
    pending = pending_id(source_id, rel)
    dest_rel = (source.get("files") or {}).get(rel, {}).get("destination")
    if source.get("mode") == "copy-here" and type(dest_rel) is str and dest_rel:
        location = make_library_location(
            source_id=source_id,
            role="primary",
            component=component,
            library_relative_path=dest_rel,
            last_known_path=last_known_text(path),
            size_bytes=size,
            modified_at=modified,
            sha256=digest,
        )
    else:
        serial = source["origin"]["volumeSerial"]
        path_from_root = path_from_volume_root(path, volume_of_path(path)[1])
        location = make_location(
            source_id=source_id,
            role="primary",
            component=component,
            volume_serial=serial,
            path_from_volume_root=path_from_root,
            last_known_path=last_known_text(path),
            size_bytes=size,
            modified_at=modified,
            sha256=digest,
        )
    latitude = None if metadata is None else metadata.get("latitude")
    longitude = None if metadata is None else metadata.get("longitude")
    place_id = None
    new_place: dict[str, Any] | None = None
    if latitude is not None and longitude is not None:
        place_id, new_place = resolve_place(
            root, float(latitude), float(longitude), match_meters
        )
    existing_pending = try_load_item(root, pending)
    if existing_pending is not None and existing_pending.get("placeId"):
        place_id = existing_pending["placeId"]
        new_place = named_place_update(root, place_id)
    from library.folder_library import current_store

    store = current_store(root, source)
    item = make_item(
        item_id=pending,
        kind=kind,
        filename=original_name if original_name is not None else path.name,
        captured_at=captured_at,
        captured_at_source=captured_source,
        content_identifier=content_id,
        locations=[location],
        renditions=renditions_for(
            kind, source_id, decode_error=decode_error, store=store,
            browser_still=browser_ready_still(file_suffix(path), metadata),
        ),
        place_id=place_id,
        metadata=metadata,
        faces=(existing_pending.get("faces") if existing_pending else None),
        things=(existing_pending.get("things") if existing_pending else None),
    )
    # Pause on the pending id only when a caller is waiting at between(), or the
    # hash barrier is armed. Other files publish the hash in one batched write.
    if between is None and not _hash_barrier_armed():
        from library.annotate import plan_rebase_pending
        from library.catalog_io import publish_pending
        from library.renditions import adopt_ready_files

        published = adopt_ready_files(root, source, publish_pending(root, item))
        changes = [
            {
                "path": item_rel(published["id"]),
                "before": try_load_item(root, published["id"]),
                "after": published,
            },
            plan_source_file(
                root,
                source_id,
                rel,
                make_file_entry(
                    item_id=published["id"],
                    component=component,
                    size_bytes=size,
                    modified_at=modified,
                    sha256=published["id"],
                    state="indexed",
                    destination=dest_rel if type(dest_rel) is str else None,
                ),
            ),
            *_retire_replaced_location(root, prev_item_id, published["id"], location),
            *plan_rebase_pending(root, pending, published),
        ]
        if existing_pending is not None:
            changes.append({"path": item_rel(pending), "before": existing_pending, "after": None})
        if new_place is not None:
            existing_place = try_load_place(root, new_place["id"])
            if existing_place != new_place:
                changes.append(
                    {"path": place_rel(new_place["id"]), "before": existing_place, "after": new_place}
                )
        _extend(root, changes)
        if decode_error:
            raise fail("decode-error")
        return published["id"]
    pending_entry = make_file_entry(
        item_id=pending,
        component=component,
        size_bytes=size,
        modified_at=modified,
        sha256=digest,
        state="pending",
        destination=dest_rel if type(dest_rel) is str else None,
    )
    changes: list[dict[str, Any]] = [
        {"path": item_rel(pending), "before": existing_pending, "after": item},
        plan_source_file(root, source_id, rel, pending_entry),
    ]
    if new_place is not None:
        existing_place = try_load_place(root, new_place["id"])
        if existing_place != new_place:
            changes.append(
                {
                    "path": place_rel(new_place["id"]),
                    "before": existing_place,
                    "after": new_place,
                }
            )
    _extend(root, changes)
    maybe_test_barrier("hash-publication")
    if between is not None:
        _flush_scan_batch(root)
        between()
    from library.annotate import plan_rebase_pending
    from library.catalog_io import publish_pending

    current = try_load_item(root, pending) or item
    published = publish_pending(root, current)
    from library.renditions import adopt_ready_files

    published = adopt_ready_files(root, source, published)
    digest = published["id"]
    existing = try_load_item(root, digest)
    indexed_entry = make_file_entry(
        item_id=published["id"],
        component=component,
        size_bytes=size,
        modified_at=modified,
        sha256=digest,
        state="indexed",
        destination=dest_rel if type(dest_rel) is str else None,
    )
    _extend(
        root,
        [
            {
                "path": item_rel(published["id"]),
                "before": existing,
                "after": published,
            },
            {"path": item_rel(pending), "before": current, "after": None},
            plan_source_file(root, source_id, rel, indexed_entry),
            *_retire_replaced_location(root, prev_item_id, published["id"], location),
            *plan_rebase_pending(root, pending, published),
        ],
    )
    if between is not None:
        _flush_scan_batch(root)
        between()
    if decode_error:
        raise fail("decode-error")
    return published["id"]


def _record_added_id(added_ids: list[str], item_id: str) -> None:
    if type(item_id) is str and item_id and item_id not in added_ids:
        added_ids.append(item_id)


def _default_progress(kind: str, rel: str) -> None:
    print(f"{kind} {rel}", flush=True)


def start_scan_source(
    root: Path,
    scan_path: Path,
    mode: str,
    preview_store: str | None,
) -> dict[str, Any]:
    scan_path = assert_scan_path_allowed(scan_path, root)
    if mode == "copy-here":
        from library.copy import convert_linked_source

        serial, volume_root = volume_of_path(scan_path)
        origin_rel = path_from_volume_root(scan_path, volume_root)
        existing = find_source_by_origin(root, serial, origin_rel)
        if existing is not None and existing.get("mode") == "serve-from-there":
            convert_linked_source(root, existing["id"])
        return _start_source(root, scan_path, preview_store, mode="copy-here")
    return _start_source(root, scan_path, preview_store)


def scan_serve_from_there(
    root: Path,
    scan_path: Path,
    *,
    preview_store: str | None = None,
    on_progress: ProgressFn | None = None,
    between: BetweenFn | None = None,
    io_context=nullcontext,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not getattr(scan_serve_from_there, "_inner", False):

        def run() -> dict[str, Any]:
            scan_serve_from_there._inner = True
            try:
                return scan_serve_from_there(
                    root,
                    scan_path,
                    preview_store=preview_store,
                    on_progress=on_progress,
                    between=between,
                    io_context=io_context,
                    source=source,
                )
            finally:
                scan_serve_from_there._inner = False

        return _run_scoped_scan(root, run, batch=not _hash_barrier_armed())
    scan_path = assert_scan_path_allowed(scan_path, root)
    if on_progress is None:
        on_progress = _default_progress
    on_progress = _observe_progress(on_progress)
    if source is None:
        source = _start_source(root, scan_path, preview_store)
    yield_at = 0.0
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    added_ids: list[str] = []
    match_meters = _place_match_meters(root)
    from library.activity import note as note_activity
    note_activity("scan", detail="Discovering pictures")
    with io_context():
        files = _in_grid_order(root, source, iter_media_files(scan_path, root))
    total = len(files)
    from library.activity import note as note_activity

    for index, (rel, path) in enumerate(files, start=1):
        note_activity(
            "scan",
            detail="Reading pictures",
            file=Path(rel).name,
            done=index - 1,
            total=total,
        )
        source = try_load_source(root, source["id"]) or source
        entry = source["files"].get(rel)
        if _unchanged(entry, path, root):
            skipped += 1
            _retry_error_renditions(root, entry, path)
            if on_progress is not None:
                on_progress("skipped", rel)
            continue
        try:
            pause = _due_for_pending_pause(between, yield_at)
            item_id = _index_file(
                root,
                source,
                rel,
                path,
                match_meters,
                between=between if pause else None,
                io_context=io_context,
            )
            added += 1
            if pause:
                yield_at = time.perf_counter()
            _record_added_id(added_ids, item_id)
            if on_progress is not None:
                on_progress("added", rel)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "decode-error":
                added += 1
                entry = ((try_load_source(root, source["id"]) or source).get("files") or {}).get(rel) or {}
                _record_added_id(added_ids, entry.get("itemId") or "")
                errors.append({"path": rel, "error": "decode-error"})
                if on_progress is not None:
                    on_progress("added", rel)
                continue
            if code in {"io-error", "invalid-argument"}:
                errors.append({"path": rel, "error": code})
                continue
            errors.append({"path": rel, "error": "io-error"})
    _flush_scan_batch(root)
    pair_live_items(root, source["id"])
    remember_recent(root, added_ids)
    return _fold_scan_source(root, source, added=added, skipped=skipped, errors=errors)


def scan_copy_here(
    root: Path,
    scan_path: Path,
    *,
    preview_store: str | None = None,
    on_progress: ProgressFn | None = None,
    between: BetweenFn | None = None,
    io_context=nullcontext,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not getattr(scan_copy_here, "_inner", False):

        def run() -> dict[str, Any]:
            scan_copy_here._inner = True
            try:
                return scan_copy_here(
                    root,
                    scan_path,
                    preview_store=preview_store,
                    on_progress=on_progress,
                    between=between,
                    io_context=io_context,
                    source=source,
                )
            finally:
                scan_copy_here._inner = False

        return _run_scoped_scan(root, run, batch=not _hash_barrier_armed())
    from library.copy import convert_linked_source, copy_media_files
    from library.paths import library_path

    scan_path = assert_scan_path_allowed(scan_path, root)
    if on_progress is None:
        on_progress = _default_progress
    on_progress = _observe_progress(on_progress)
    if source is None:
        serial, volume_root = volume_of_path(scan_path)
        origin_rel = path_from_volume_root(scan_path, volume_root)
        existing = find_source_by_origin(root, serial, origin_rel)
        if existing is not None and existing.get("mode") == "serve-from-there":
            convert_linked_source(root, existing["id"])
        source = _start_source(root, scan_path, preview_store, mode="copy-here")
    yield_at = 0.0
    from library.activity import note as note_activity
    note_activity("scan", detail="Discovering pictures")
    with io_context():
        files = _in_grid_order(root, source, iter_media_files(scan_path, root))
    source = copy_media_files(root, source, scan_path, files, between=between)
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    added_ids: list[str] = []
    match_meters = _place_match_meters(root)
    total = len(files)
    from library.activity import note as note_activity

    for index, (rel, path) in enumerate(files, start=1):
        note_activity(
            "scan",
            detail="Reading pictures",
            file=Path(rel).name,
            done=index - 1,
            total=total,
        )
        source = try_load_source(root, source["id"]) or source
        entry = source["files"].get(rel)
        if not entry or type(entry.get("destination")) is not str:
            errors.append({"path": rel, "error": "io-error"})
            continue
        dest_path = path
        if entry and type(entry.get("destination")) is str:
            try:
                dest_path = library_path(root, entry["destination"])
            except Exception:
                dest_path = path
        if _unchanged(entry, dest_path, root):
            skipped += 1
            _retry_error_renditions(root, entry, dest_path)
            if on_progress is not None:
                on_progress("skipped", rel)
            continue
        try:
            pause = _due_for_pending_pause(between, yield_at)
            item_id = _index_file(
                root,
                source,
                rel,
                dest_path,
                match_meters,
                original_name=Path(rel).name,
                between=between if pause else None,
                io_context=io_context,
            )
            added += 1
            if pause:
                yield_at = time.perf_counter()
            _record_added_id(added_ids, item_id)
            if on_progress is not None:
                on_progress("added", rel)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "decode-error":
                added += 1
                entry = ((try_load_source(root, source["id"]) or source).get("files") or {}).get(rel) or {}
                _record_added_id(added_ids, entry.get("itemId") or "")
                errors.append({"path": rel, "error": "decode-error"})
                if on_progress is not None:
                    on_progress("added", rel)
                continue
            if code in {"io-error", "invalid-argument"}:
                errors.append({"path": rel, "error": code})
                continue
            errors.append({"path": rel, "error": "io-error"})
    _flush_scan_batch(root)
    pair_live_items(root, source["id"])
    remember_recent(root, added_ids)
    return _fold_scan_source(root, source, added=added, skipped=skipped, errors=errors)
