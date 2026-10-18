"""Linked serve-from-there scan: pending id, then hash id."""

from __future__ import annotations

import os
from contextlib import nullcontext
import unicodedata
from pathlib import Path
from typing import Any, Callable

from library.atomic import maybe_test_barrier, transact
from library.catalog_io import (
    ensure_catalog_dirs,
    find_source_by_origin,
    item_rel,
    load_source,
    new_source_id,
    pair_live_items,
    place_rel,
    relative_from_origin,
    source_rel,
    try_load_item,
    try_load_place,
    try_load_source,
)
from library.errors import fail
from library.history import latest_entry_id, load_entry, make_history_entry, plan_append, plan_extend_entry
from library.media import (
    HEIF_SUFFIXES,
    default_component,
    file_suffix,
    heif_has_valid_brand,
    is_allowed_media,
    media_kind,
    mtime_iso,
    read_content_identifier,
    sha256_file,
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
    read_source,
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
    return (
        entry.get("state") == "indexed"
        and entry.get("sizeBytes") == stat.st_size
        and entry.get("modifiedAt") == mtime_iso(check)
    )


def _extend(root: Path, changes: list[dict[str, Any]]) -> None:
    entry_id = latest_entry_id(root)
    if entry_id is None:
        transact(root, changes)
        return
    entry = load_entry(root, entry_id)
    if entry.get("operation") in {"scan", "copy-here"}:
        transact(root, plan_extend_entry(root, entry_id, changes))
        return
    transact(root, changes)


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
        try:
            size = path.stat().st_size
            modified = mtime_iso(path)
            digest = sha256_file(path)
            later = path.stat()
            if later.st_size != size or mtime_iso(path) != modified:
                raise fail("io-error")
        except OSError as exc:
            raise fail("io-error") from exc
        decode_error = file_suffix(path) in HEIF_SUFFIXES and not heif_has_valid_brand(path)
        content_id = None
        try:
            content_id = read_content_identifier(path)
        except OSError:
            content_id = None
        try:
            captured_at, captured_source, metadata = read_capture(path)
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
    settings = load_settings_file(root) if settings_path(root).exists() else defaults()
    from library.renditions import effective_preview_store

    store = effective_preview_store(source, settings)
    item = make_item(
        item_id=pending,
        kind=kind,
        filename=original_name if original_name is not None else path.name,
        captured_at=captured_at,
        captured_at_source=captured_source,
        content_identifier=content_id,
        locations=[location],
        renditions=renditions_for(kind, source_id, decode_error=decode_error, store=store),
        place_id=place_id,
        metadata=metadata,
        faces=(existing_pending.get("faces") if existing_pending else None),
        things=(existing_pending.get("things") if existing_pending else None),
    )
    before_source = clone(source)
    source["files"][rel] = make_file_entry(
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
        {
            "path": source_rel(source_id),
            "before": before_source,
            "after": ordered_source(source),
        },
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
        between()
    from library.annotate import plan_rebase_pending
    from library.catalog_io import publish_pending

    current = try_load_item(root, pending) or item
    published = publish_pending(root, current)
    from library.renditions import adopt_ready_files

    published = adopt_ready_files(root, source, published)
    digest = published["id"]
    existing = try_load_item(root, digest)
    before_source = clone(try_load_source(root, source_id) or source)
    source = read_source(before_source)
    source["files"][rel] = make_file_entry(
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
            {
                "path": source_rel(source_id),
                "before": before_source,
                "after": ordered_source(source),
            },
            *_retire_replaced_location(root, prev_item_id, published["id"], location),
            *plan_rebase_pending(root, pending, published),
        ],
    )
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
    scan_path = assert_scan_path_allowed(scan_path, root)
    if on_progress is None:
        on_progress = _default_progress
    if source is None:
        source = _start_source(root, scan_path, preview_store)
    if between is not None:
        between()
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    added_ids: list[str] = []
    match_meters = _place_match_meters(root)
    from library.activity import note as note_activity
    note_activity("scan", detail="Discovering pictures")
    with io_context():
        files = iter_media_files(scan_path, root)
    total = len(files)
    from library.activity import note as note_activity

    for index, (rel, path) in enumerate(files, start=1):
        if between is not None:
            between()
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
            item_id = _index_file(root, source, rel, path, match_meters, between=between, io_context=io_context)
            added += 1
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
    pair_live_items(root, source["id"])
    remember_recent(root, added_ids)
    source = try_load_source(root, source["id"]) or source
    before = clone(source)
    source["scan"] = {
        "state": "error" if errors else "complete",
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
    _extend(
        root,
        [
            {
                "path": source_rel(source["id"]),
                "before": before,
                "after": ordered_source(source),
            }
        ],
    )
    maybe_test_barrier("catalog-committed")
    from library.index import rebuild_sqlite

    rebuild_sqlite(root, use_barrier=True)
    source = try_load_source(root, source["id"]) or source
    from library.activity import clear as clear_activity

    clear_activity("scan")
    return source


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
    from library.copy import convert_linked_source, copy_media_files
    from library.paths import library_path

    scan_path = assert_scan_path_allowed(scan_path, root)
    if on_progress is None:
        on_progress = _default_progress
    if source is None:
        serial, volume_root = volume_of_path(scan_path)
        origin_rel = path_from_volume_root(scan_path, volume_root)
        existing = find_source_by_origin(root, serial, origin_rel)
        if existing is not None and existing.get("mode") == "serve-from-there":
            convert_linked_source(root, existing["id"])
        source = _start_source(root, scan_path, preview_store, mode="copy-here")
    if between is not None:
        between()
    from library.activity import note as note_activity
    note_activity("scan", detail="Discovering pictures")
    with io_context():
        files = iter_media_files(scan_path, root)
    source = copy_media_files(root, source, scan_path, files, between=between)
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    added_ids: list[str] = []
    match_meters = _place_match_meters(root)
    total = len(files)
    from library.activity import note as note_activity

    for index, (rel, path) in enumerate(files, start=1):
        if between is not None:
            between()
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
            item_id = _index_file(
                root,
                source,
                rel,
                dest_path,
                match_meters,
                original_name=Path(rel).name,
                between=between,
                io_context=io_context,
            )
            added += 1
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
    pair_live_items(root, source["id"])
    remember_recent(root, added_ids)
    source = try_load_source(root, source["id"]) or source
    before = clone(source)
    source["scan"] = {
        "state": "error" if errors else "complete",
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
    _extend(
        root,
        [
            {
                "path": source_rel(source["id"]),
                "before": before,
                "after": ordered_source(source),
            }
        ],
    )
    maybe_test_barrier("catalog-committed")
    from library.index import rebuild_sqlite

    rebuild_sqlite(root, use_barrier=True)
    source = try_load_source(root, source["id"]) or source
    from library.activity import clear as clear_activity

    clear_activity("scan")
    return source
