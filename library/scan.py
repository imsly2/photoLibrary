"""Linked serve-from-there scan: pending id, then hash id."""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Any, Callable

from library.atomic import maybe_test_barrier, transact
from library.catalog_io import (
    ensure_catalog_dirs,
    find_source_by_origin,
    item_rel,
    new_source_id,
    pair_live_items,
    place_rel,
    relative_from_origin,
    source_rel,
    try_load_item,
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
from library.places import resolve_place
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
    slots = [slot for slot in ("thumb", "preview", "poster", "proxy") if status.get(slot) == "error"]
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
) -> str:
    from library.copy import make_library_location

    prev_entry = (source.get("files") or {}).get(rel)
    prev_item_id = prev_entry.get("itemId") if prev_entry else None
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
    try:
        captured_at, captured_source, metadata = read_capture(path)
    except OSError:
        captured_at, captured_source, metadata = modified, "mtime", None
    latitude = None if metadata is None else metadata.get("latitude")
    longitude = None if metadata is None else metadata.get("longitude")
    place_id = None
    new_place: dict[str, Any] | None = None
    if latitude is not None and longitude is not None:
        place_id, new_place = resolve_place(
            root, float(latitude), float(longitude), match_meters
        )
    existing_pending = try_load_item(root, pending)
    item = make_item(
        item_id=pending,
        kind=kind,
        filename=original_name if original_name is not None else path.name,
        captured_at=captured_at,
        captured_at_source=captured_source,
        content_identifier=content_id,
        locations=[location],
        renditions=renditions_for(kind, source_id, decode_error=decode_error),
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
        {"path": item_rel(pending), "before": None, "after": item},
        {
            "path": source_rel(source_id),
            "before": before_source,
            "after": ordered_source(source),
        },
    ]
    if new_place is not None:
        changes.append(
            {"path": place_rel(new_place["id"]), "before": None, "after": new_place}
        )
    _extend(root, changes)
    maybe_test_barrier("hash-publication")
    existing = try_load_item(root, digest)
    published = clone(item)
    published["id"] = digest
    if existing is not None:
        from library.catalog_io import merge_associations, merge_location

        published = clone(existing)
        published = merge_location(published, location)
        published = merge_associations(published, item)
        published = ordered_item(published)
    else:
        published = ordered_item(published)
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
            {"path": item_rel(pending), "before": item, "after": None},
            {
                "path": source_rel(source_id),
                "before": before_source,
                "after": ordered_source(source),
            },
            *_retire_replaced_location(root, prev_item_id, published["id"], location),
        ],
    )
    if decode_error:
        raise fail("decode-error")
    return published["id"]


def scan_serve_from_there(
    root: Path,
    scan_path: Path,
    *,
    preview_store: str | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    scan_path = assert_scan_path_allowed(scan_path, root)
    source = _start_source(root, scan_path, preview_store)
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    match_meters = _place_match_meters(root)
    files = iter_media_files(scan_path, root)
    for rel, path in files:
        source = try_load_source(root, source["id"]) or source
        entry = source["files"].get(rel)
        if _unchanged(entry, path, root):
            skipped += 1
            _retry_error_renditions(root, entry, path)
            if on_progress is not None:
                on_progress("skipped", rel)
            continue
        try:
            _index_file(root, source, rel, path, match_meters)
            added += 1
            if on_progress is not None:
                on_progress("added", rel)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "decode-error":
                added += 1
                errors.append({"path": rel, "error": "decode-error"})
                if on_progress is not None:
                    on_progress("added", rel)
                continue
            if code in {"io-error", "invalid-argument"}:
                errors.append({"path": rel, "error": code})
                continue
            errors.append({"path": rel, "error": "io-error"})
    pair_live_items(root, source["id"])
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
    return source


def scan_copy_here(
    root: Path,
    scan_path: Path,
    *,
    preview_store: str | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    from library.copy import convert_linked_source, copy_media_files
    from library.paths import library_path

    scan_path = assert_scan_path_allowed(scan_path, root)
    serial, volume_root = volume_of_path(scan_path)
    origin_rel = path_from_volume_root(scan_path, volume_root)
    existing = find_source_by_origin(root, serial, origin_rel)
    if existing is not None and existing.get("mode") == "serve-from-there":
        convert_linked_source(root, existing["id"])
    source = _start_source(root, scan_path, preview_store, mode="copy-here")
    files = iter_media_files(scan_path, root)
    source = copy_media_files(root, source, scan_path, files)
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    match_meters = _place_match_meters(root)
    for rel, path in files:
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
            _index_file(root, source, rel, dest_path, match_meters, original_name=Path(rel).name)
            added += 1
            if on_progress is not None:
                on_progress("added", rel)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "decode-error":
                added += 1
                errors.append({"path": rel, "error": "decode-error"})
                if on_progress is not None:
                    on_progress("added", rel)
                continue
            if code in {"io-error", "invalid-argument"}:
                errors.append({"path": rel, "error": code})
                continue
            errors.append({"path": rel, "error": "io-error"})
    pair_live_items(root, source["id"])
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
    return source
