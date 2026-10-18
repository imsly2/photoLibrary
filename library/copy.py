"""Copy originals onto this drive. Never overwrite; resume by hash."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from library.atomic import maybe_test_barrier, transact
from library.catalog_io import (
    item_rel,
    load_source,
    source_rel,
    try_load_item,
    try_load_source,
)
from library.errors import fail
from library.history import latest_entry_id, load_entry, make_history_entry, plan_append, plan_extend_entry
from library.media import default_component, media_kind, mtime_iso, sha256_file
from library.paths import library_path, normalize_root
from library.records import (
    clone,
    make_file_entry,
    ordered_item,
    ordered_source,
    read_source,
)
from library.volumes import last_known_text, volume_file_path

UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


def safe_name(name: str) -> str:
    cleaned = UNSAFE_NAME.sub("_", name).strip(" .")
    if not cleaned or cleaned in {".", ".."} or cleaned.upper() in WINDOWS_RESERVED:
        return "folder"
    return cleaned


def copy_root_rel(name: str, source_id: str) -> str:
    return f"originals/{safe_name(name)}-{source_id}"


def is_partial_name(name: str, source_id: str | None = None) -> bool:
    if source_id is not None:
        return name.endswith(f".partial-{source_id}")
    return ".partial-" in name


def partial_path(dest: Path, source_id: str) -> Path:
    return dest.with_name(dest.name + f".partial-{source_id}")


def collision_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    index = 2
    while True:
        candidate = dest.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def library_rel_of(root: Path, path: Path) -> str:
    return normalize_root(path).relative_to(normalize_root(root)).as_posix()


def choose_destination(root: Path, copy_root: str, rel: str, existing: str | None) -> str:
    if type(existing) is str and existing:
        return existing
    dest = library_path(root, f"{copy_root}/{rel}")
    dest = collision_dest(dest)
    return library_rel_of(root, dest)


def make_library_location(
    *,
    source_id: str,
    role: str,
    component: str,
    library_relative_path: str,
    last_known_path: str,
    size_bytes: int,
    modified_at: str,
    sha256: str | None,
) -> dict[str, Any]:
    return {
        "sourceId": source_id,
        "role": role,
        "component": component,
        "kind": "library-relative",
        "current": True,
        "libraryRelativePath": library_relative_path,
        "volumeSerial": None,
        "pathFromVolumeRoot": None,
        "lastKnownPath": last_known_path,
        "sizeBytes": size_bytes,
        "modifiedAt": modified_at,
        "sha256": sha256,
    }


def _extend_current(root: Path, changes: list[dict[str, Any]]) -> None:
    entry_id = latest_entry_id(root)
    if entry_id is None:
        transact(root, changes)
        return
    entry = load_entry(root, entry_id)
    if entry.get("operation") in {"scan", "copy-here"}:
        transact(root, plan_extend_entry(root, entry_id, changes))
        return
    transact(root, changes)


def persist_source(root: Path, source: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    after = ordered_source(source)
    _extend_current(
        root,
        [
            {
                "path": source_rel(after["id"]),
                "before": before,
                "after": after,
            }
        ],
    )
    return after


def dest_matches_hash(root: Path, dest_rel: str, digest: str) -> bool:
    try:
        path = library_path(root, dest_rel)
    except Exception:
        return False
    if not path.is_file():
        return False
    try:
        return sha256_file(path) == digest
    except OSError:
        return False


def write_via_partial(src: Path, dest: Path, source_id: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = partial_path(dest, source_id)
    if partial.exists():
        try:
            partial.unlink()
        except OSError as exc:
            raise fail("io-error") from exc
    expected = sha256_file(src)
    if dest.exists() and sha256_file(dest) == expected:
        if partial.exists():
            partial.unlink()
        return
    if partial.exists():
        try:
            if sha256_file(partial) == expected:
                maybe_test_barrier("copy-partial")
                if dest.exists():
                    if sha256_file(dest) == expected:
                        partial.unlink()
                        return
                    raise fail("io-error")
                os.replace(partial, dest)
                return
            partial.unlink()
        except OSError as exc:
            raise fail("io-error") from exc
    try:
        # Copy read-only attributes after syncing, so read-only originals remain
        # readable inputs without making the destination descriptor unwritable.
        shutil.copyfile(src, partial)
        # Windows requires a writable descriptor for FlushFileBuffers/fsync.
        # r+b preserves every copied byte and does not truncate the partial.
        with open(partial, "r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copystat(src, partial)
        maybe_test_barrier("copy-partial")
        if sha256_file(partial) != expected:
            raise fail("io-error")
        if dest.exists():
            if sha256_file(dest) == expected:
                partial.unlink()
                return
            raise fail("io-error")
        os.replace(partial, dest)
    except Exception:
        raise


def copy_one_file(
    root: Path,
    source: dict[str, Any],
    rel: str,
    src_path: Path,
    *,
    item_id: str | None = None,
) -> dict[str, Any]:
    source = read_source(try_load_source(root, source["id"]) or source)
    copy_root = source.get("copyRoot")
    if type(copy_root) is not str or not copy_root:
        raise fail("invalid-catalog")
    try:
        size = src_path.stat().st_size
        modified = mtime_iso(src_path)
        digest = sha256_file(src_path)
    except OSError as exc:
        raise fail("io-error") from exc
    kind = media_kind(src_path)
    component = default_component(kind)
    existing = source["files"].get(rel)
    dest_rel = choose_destination(
        root,
        copy_root,
        rel,
        existing.get("destination") if existing else None,
    )
    if item_id is None:
        if existing and existing.get("itemId"):
            item_id = existing["itemId"]
        else:
            from library.scan import pending_id

            item_id = pending_id(source["id"], rel)
    if dest_matches_hash(root, dest_rel, digest):
        before = clone(source)
        source["files"][rel] = make_file_entry(
            item_id=item_id,
            component=component,
            size_bytes=size,
            modified_at=modified,
            sha256=digest,
            state="copied" if existing is None or existing.get("state") != "indexed" else existing["state"],
            destination=dest_rel,
        )
        if existing is not None and existing.get("state") == "indexed":
            source["files"][rel] = make_file_entry(
                item_id=existing["itemId"],
                component=existing["component"],
                size_bytes=existing["sizeBytes"],
                modified_at=existing["modifiedAt"],
                sha256=existing.get("sha256") or digest,
                state="indexed",
                destination=dest_rel,
            )
        return persist_source(root, source, before)

    before = clone(source)
    source["files"][rel] = make_file_entry(
        item_id=item_id,
        component=component,
        size_bytes=size,
        modified_at=modified,
        sha256=digest,
        state="pending",
        destination=dest_rel,
    )
    persist_source(root, source, before)
    dest = library_path(root, dest_rel)
    write_via_partial(src_path, dest, source["id"])
    leftover = partial_path(dest, source["id"])
    if leftover.exists() and dest.exists():
        leftover.unlink()
    source = read_source(load_source(root, source["id"]))
    before = clone(source)
    source["files"][rel] = make_file_entry(
        item_id=item_id,
        component=component,
        size_bytes=size,
        modified_at=modified,
        sha256=digest,
        state="copied",
        destination=dest_rel,
    )
    return persist_source(root, source, before)


def promote_copied_location(item: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    item = clone(item)
    kept: list[dict[str, Any]] = []
    for loc in item["locations"]:
        same = (
            loc["sourceId"] == incoming["sourceId"]
            and loc["component"] == incoming["component"]
            and loc.get("kind") == "library-relative"
            and loc.get("libraryRelativePath") == incoming["libraryRelativePath"]
        )
        if same:
            continue
        if (
            loc["sourceId"] == incoming["sourceId"]
            and loc["component"] == incoming["component"]
            and loc.get("current") is True
            and loc.get("role") == "primary"
        ):
            loc = clone(loc)
            loc["role"] = "alternate"
        kept.append(loc)
    item["locations"] = [incoming] + kept
    return ordered_item(item)


def origin_dir(source: dict[str, Any]) -> Path | None:
    origin = source.get("origin") or {}
    serial = origin.get("volumeSerial")
    rel = origin.get("pathFromVolumeRoot")
    if type(serial) is not str or type(rel) is not str:
        return None
    return volume_file_path(serial, rel)


def update_item_for_copy(root: Path, source: dict[str, Any], rel: str) -> None:
    entry = source["files"].get(rel)
    if entry is None or not entry.get("destination") or not entry.get("itemId"):
        return
    item_id = entry["itemId"]
    if type(item_id) is not str or item_id.startswith("pending-"):
        return
    item = try_load_item(root, item_id)
    if item is None:
        return
    dest_rel = entry["destination"]
    dest = library_path(root, dest_rel)
    if not dest.is_file():
        return
    loc = make_library_location(
        source_id=source["id"],
        role="primary",
        component=entry["component"],
        library_relative_path=dest_rel,
        last_known_path=last_known_text(dest),
        size_bytes=dest.stat().st_size,
        modified_at=mtime_iso(dest),
        sha256=entry.get("sha256") or sha256_file(dest),
    )
    already = any(
        existing.get("kind") == "library-relative"
        and existing.get("libraryRelativePath") == dest_rel
        and existing.get("component") == loc["component"]
        and existing.get("role") == "primary"
        for existing in item["locations"]
    )
    if already:
        return
    before = clone(item)
    published = promote_copied_location(item, loc)
    _extend_current(
        root,
        [
            {
                "path": item_rel(published["id"]),
                "before": before,
                "after": published,
            }
        ],
    )


def ensure_copy_root(source: dict[str, Any]) -> str:
    copy_root = source.get("copyRoot")
    if type(copy_root) is str and copy_root:
        return copy_root
    copy_root = copy_root_rel(source["name"], source["id"])
    source["copyRoot"] = copy_root
    source["mode"] = "copy-here"
    return copy_root


def convert_linked_source(root: Path, source_id: str) -> dict[str, Any]:
    from library.scan import iter_media_files, _index_file, _place_match_meters

    source = load_source(root, source_id)
    if source["mode"] == "copy-here" and type(source.get("copyRoot")) is str and source["copyRoot"]:
        return source
    origin = origin_dir(source)
    if origin is None or not origin.is_dir():
        raise fail("unavailable")
    before = clone(source)
    ensure_copy_root(source)
    source["mode"] = "copy-here"
    source["scan"] = {"state": "running", "added": 0, "skipped": 0, "errors": []}
    source = ordered_source(source)
    changes = [
        {"path": source_rel(source["id"]), "before": before, "after": source},
    ]
    entry = make_history_entry(root, "copy-here", changes)
    transact(root, plan_append(root, entry) + changes)

    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    match_meters = _place_match_meters(root)
    files = iter_media_files(origin, root)
    for rel, path in files:
        source = try_load_source(root, source_id) or source
        entry = source["files"].get(rel)
        try:
            source = copy_one_file(
                root,
                source,
                rel,
                path,
                item_id=entry["itemId"] if entry else None,
            )
            source = try_load_source(root, source_id) or source
            current = source["files"].get(rel)
            if current and current.get("state") == "indexed" and dest_matches_hash(
                root, current.get("destination") or "", current.get("sha256") or ""
            ):
                update_item_for_copy(root, source, rel)
                skipped += 1
                continue
            if current and current.get("itemId") and not str(current["itemId"]).startswith("pending-"):
                update_item_for_copy(root, source, rel)
                source = try_load_source(root, source_id) or source
                before_source = clone(source)
                source["files"][rel] = make_file_entry(
                    item_id=current["itemId"],
                    component=current["component"],
                    size_bytes=current["sizeBytes"],
                    modified_at=current["modifiedAt"],
                    sha256=current["sha256"],
                    state="indexed",
                    destination=current["destination"],
                )
                persist_source(root, source, before_source)
                added += 1
            else:
                dest_rel = (source["files"].get(rel) or {}).get("destination")
                if not dest_rel:
                    raise fail("io-error")
                dest = library_path(root, dest_rel)
                _index_file(root, source, rel, dest, match_meters, original_name=Path(rel).name)
                added += 1
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "decode-error":
                added += 1
                errors.append({"path": rel, "error": "decode-error"})
                continue
            if code in {"io-error", "invalid-argument"}:
                errors.append({"path": rel, "error": code})
                continue
            if isinstance(exc, SystemExit):
                raise
            errors.append({"path": rel, "error": "io-error"})

    source = try_load_source(root, source_id) or source
    before = clone(source)
    source["scan"] = {
        "state": "error" if errors else "complete",
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
    persist_source(root, source, before)
    from library.catalog_io import pair_live_items
    from library.index import rebuild_sqlite

    pair_live_items(root, source_id)
    rebuild_sqlite(root, use_barrier=True)
    return load_source(root, source_id)


def copy_media_files(
    root: Path,
    source: dict[str, Any],
    scan_path: Path,
    files: list[tuple[str, Path]],
    between=None,
) -> dict[str, Any]:
    for rel, path in files:
        source = try_load_source(root, source["id"]) or source
        entry = source["files"].get(rel)
        if (
            entry
            and entry.get("destination")
            and entry.get("state") in {"copied", "indexed"}
            and dest_matches_hash(root, entry["destination"], entry.get("sha256") or "")
        ):
            if between is not None:
                between()
            continue
        source = copy_one_file(
            root,
            source,
            rel,
            path,
            item_id=entry["itemId"] if entry else None,
        )
        if between is not None:
            between()
    return try_load_source(root, source["id"]) or source
