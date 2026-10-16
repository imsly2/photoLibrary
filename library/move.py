"""Move selected originals to a registered folder. Never overwrite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from library.atomic import maybe_test_barrier, transact
from library.catalog_io import (
    item_rel,
    iter_source_ids,
    load_item,
    load_source,
    source_rel,
    try_load_source,
)
from library.copy import collision_dest, library_rel_of, make_library_location, origin_dir
from library.errors import fail
from library.favorites import read_item_ids
from library.history import make_history_entry, plan_append, plan_extend_entry
from library.index import rebuild_sqlite
from library.media import mtime_iso, sha256_file
from library.paths import normalize_root
from library.records import clone, make_file_entry, make_location, ordered_item, ordered_source
from library.renditions import copy_verified, rendition_abs, slot_filename, store_dir
from library.sources import resolve_source_folder
from library.volumes import last_known_text, location_file, location_matches_stat


def same_path(a: Path, b: Path) -> bool:
    return os.path.normcase(str(normalize_root(a))) == os.path.normcase(str(normalize_root(b)))


def is_under(child: Path, parent: Path) -> bool:
    try:
        normalize_root(child).relative_to(normalize_root(parent))
        return True
    except ValueError:
        return False


def source_files_root(source: dict[str, Any], root: Path) -> Path | None:
    if source.get("mode") == "copy-here":
        copy_root = source.get("copyRoot")
        if type(copy_root) is not str or not copy_root:
            return None
        from library.paths import library_path

        try:
            path = library_path(root, copy_root)
        except Exception:
            return None
        return path if path.is_dir() else None
    folder = resolve_source_folder(source, root)
    if folder is not None:
        try:
            if folder.is_dir():
                return folder
        except OSError:
            pass
    mounted = origin_dir(source)
    if mounted is not None:
        try:
            if mounted.is_dir():
                return mounted
        except OSError:
            return None
    return None


def _reject_hidden_dest(dest: Path) -> None:
    parts = {part.lower() for part in dest.parts}
    if ".library" in parts:
        raise fail("invalid-argument")


def resolve_destination(root: Path, body: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    source_id = body.get("sourceId")
    destination = body.get("destination")
    subpath = body.get("subpath")
    if source_id is not None and type(source_id) is not str:
        raise fail("invalid-argument")
    if destination is not None and type(destination) is not str:
        raise fail("invalid-argument")
    if subpath is not None and type(subpath) is not str:
        raise fail("invalid-argument")
    if type(destination) is str and destination.strip():
        dest = Path(destination).expanduser()
        if dest.exists() and dest.is_dir():
            dest = normalize_root(dest)
        elif dest.exists():
            raise fail("invalid-argument")
        else:
            raise fail("invalid-argument")
        _reject_hidden_dest(dest)
        source = _source_for_dest(root, dest)
        return source, dest
    if type(source_id) is str and source_id:
        source = load_source(root, source_id)
        base = source_files_root(source, root)
        if base is None:
            raise fail("unavailable")
        dest = normalize_root(base)
        if type(subpath) is str and subpath.strip():
            rel = subpath.replace("\\", "/").strip("/")
            if not rel or ".." in Path(rel).parts:
                raise fail("invalid-argument")
            dest = dest / Path(*rel.split("/"))
            dest.mkdir(parents=True, exist_ok=True)
            dest = normalize_root(dest)
        if not dest.is_dir():
            raise fail("invalid-argument")
        _reject_hidden_dest(dest)
        if not is_under(dest, base):
            raise fail("invalid-argument")
        return source, dest
    raise fail("invalid-argument")


def _source_for_dest(root: Path, dest: Path) -> dict[str, Any]:
    matches: list[tuple[dict[str, Any], Path]] = []
    for source_id in iter_source_ids(root):
        source = load_source(root, source_id)
        folder = source_files_root(source, root)
        if folder is None:
            continue
        folder = normalize_root(folder)
        if same_path(dest, folder) or is_under(dest, folder):
            matches.append((source, folder))
    if not matches:
        raise fail("invalid-argument")
    matches.sort(key=lambda pair: len(str(pair[1])), reverse=True)
    return matches[0][0]


def primary_current_files(item: dict[str, Any], root: Path) -> list[tuple[dict[str, Any], Path]]:
    found: list[tuple[dict[str, Any], Path]] = []
    for component in ("still", "motion"):
        candidates = [
            loc
            for loc in item.get("locations") or []
            if loc.get("current") is True and loc.get("component") == component
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
            if not location_matches_stat(loc, path):
                continue
            found.append((loc, path))
            break
    return found


def _file_key(source: dict[str, Any], item_id: str, component: str) -> str | None:
    for key, entry in (source.get("files") or {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("itemId") == item_id and entry.get("component") == component:
            return key
    return None


def _rel_from_source(source_root: Path, path: Path) -> str:
    rel = normalize_root(path).relative_to(normalize_root(source_root)).as_posix()
    if rel == ".":
        return ""
    return rel


def _same_device(src: Path, dest_dir: Path) -> bool:
    if os.environ.get("LIBRARY_TEST") == "1" and os.environ.get("LIBRARY_TEST_CROSS_DRIVE") == "1":
        return False
    try:
        return src.stat().st_dev == dest_dir.stat().st_dev
    except OSError:
        return False


def _hash_copy(src: Path, dest: Path) -> None:
    expected = sha256_file(src)
    copy_verified(src, dest)
    if sha256_file(dest) != expected:
        try:
            dest.unlink()
        except OSError:
            pass
        raise fail("io-error")


def _choose_dest_file(dest_dir: Path, src: Path) -> tuple[Path, str]:
    candidate = dest_dir / src.name
    if same_path(src, candidate):
        return candidate, "already"
    if candidate.exists():
        try:
            if sha256_file(candidate) == sha256_file(src):
                return candidate, "already"
        except OSError:
            pass
        renamed = collision_dest(candidate)
        return renamed, "renamed"
    return candidate, "moved"


def _relocate_bytes(src: Path, dest: Path) -> str:
    if same_path(src, dest):
        return "already"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise fail("io-error")
    if _same_device(src, dest.parent):
        os.rename(src, dest)
        return "renamed-bytes"
    _hash_copy(src, dest)
    return "copied"


def _rollback_bytes(src: Path, dest: Path, method: str) -> None:
    try:
        if method == "renamed-bytes" and dest.exists() and not src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.rename(dest, src)
        elif method == "copied" and dest.exists():
            dest.unlink()
    except OSError:
        pass


def _new_location(
    dest_source: dict[str, Any],
    dest_path: Path,
    loc: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    try:
        size = dest_path.stat().st_size
        modified = mtime_iso(dest_path)
    except OSError as exc:
        raise fail("io-error") from exc
    digest = loc.get("sha256")
    if dest_source.get("mode") == "copy-here":
        return make_library_location(
            source_id=dest_source["id"],
            role=loc.get("role") or "primary",
            component=loc["component"],
            library_relative_path=library_rel_of(root, dest_path),
            last_known_path=last_known_text(dest_path),
            size_bytes=size,
            modified_at=modified,
            sha256=digest if type(digest) is str else None,
        )
    origin = dest_source.get("origin") or {}
    serial = origin.get("volumeSerial")
    if type(serial) is not str:
        raise fail("invalid-catalog")
    source_root = source_files_root(dest_source, root)
    if source_root is None:
        raise fail("unavailable")
    rel = _rel_from_source(source_root, dest_path)
    origin_rel = origin.get("pathFromVolumeRoot")
    if type(origin_rel) is not str:
        origin_rel = ""
    if origin_rel:
        path_from_vol = (origin_rel.rstrip("/") + "/" + rel).strip("/") if rel else origin_rel
    else:
        path_from_vol = rel
    return make_location(
        source_id=dest_source["id"],
        role=loc.get("role") or "primary",
        component=loc["component"],
        volume_serial=serial,
        path_from_volume_root=path_from_vol,
        last_known_path=last_known_text(dest_path),
        size_bytes=size,
        modified_at=modified,
        sha256=digest if type(digest) is str else None,
    )


def _transfer_renditions(
    root: Path,
    item: dict[str, Any],
    dest_source: dict[str, Any],
) -> tuple[dict[str, Any], list[tuple[Path, Path, str]]]:
    rend = clone(item.get("renditions") or {})
    store = rend.get("store")
    ops: list[tuple[Path, Path, str]] = []
    if store != "with-source":
        rend["sourceId"] = dest_source["id"]
        after = clone(item)
        after["renditions"] = rend
        return after, ops
    old_source = try_load_source(root, rend.get("sourceId") or "")
    old_dir = store_dir("with-source", old_source, root, item["id"]) if old_source else None
    new_dir = store_dir("with-source", dest_source, root, item["id"])
    rend["sourceId"] = dest_source["id"]
    after = clone(item)
    after["renditions"] = rend
    if old_dir is None or new_dir is None or not old_dir.is_dir():
        return after, ops
    if same_path(old_dir, new_dir):
        return after, ops
    new_dir.mkdir(parents=True, exist_ok=True)
    status = rend.get("status") or {}
    for slot, state in status.items():
        if state != "ready":
            continue
        src = rendition_abs(item, slot, root)
        if src is None or not src.is_file():
            src = old_dir / slot_filename(slot)
        if not src.is_file():
            continue
        dest = new_dir / slot_filename(slot)
        if same_path(src, dest):
            continue
        if dest.exists():
            continue
        method = _relocate_bytes(src, dest)
        ops.append((src, dest, method))
    return after, ops


def _plan_source_files(
    root: Path,
    item: dict[str, Any],
    dest_source: dict[str, Any],
    dest_root: Path,
    moves: list[tuple[dict[str, Any], Path, Path]],
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    touched: set[str] = {dest_source["id"]}
    for loc, _src, dest_path in moves:
        old_id = loc.get("sourceId")
        if type(old_id) is str and old_id:
            touched.add(old_id)
    for source_id in touched:
        source = try_load_source(root, source_id)
        if source is None:
            continue
        by_id[source_id] = clone(source)
    dest_after = by_id[dest_source["id"]]
    dest_files = dict(dest_after.get("files") or {})
    for loc, _src, dest_path in moves:
        old_id = loc.get("sourceId")
        component = loc["component"]
        if type(old_id) is str and old_id in by_id and old_id != dest_source["id"]:
            old_files = dict(by_id[old_id].get("files") or {})
            key = _file_key(by_id[old_id], item["id"], component)
            if key is not None:
                old_files.pop(key, None)
                by_id[old_id]["files"] = old_files
        elif type(old_id) is str and old_id == dest_source["id"]:
            key = _file_key(dest_after, item["id"], component)
            if key is not None:
                dest_files.pop(key, None)
        new_key = _rel_from_source(dest_root, dest_path)
        try:
            size = dest_path.stat().st_size
            modified = mtime_iso(dest_path)
        except OSError as exc:
            raise fail("io-error") from exc
        library_dest = None
        if dest_source.get("mode") == "copy-here":
            library_dest = library_rel_of(root, dest_path)
        dest_files[new_key] = make_file_entry(
            item_id=item["id"],
            component=component,
            size_bytes=size,
            modified_at=modified,
            sha256=loc.get("sha256") if type(loc.get("sha256")) is str else None,
            state="indexed",
            destination=library_dest,
        )
    dest_after["files"] = dest_files
    by_id[dest_source["id"]] = dest_after
    return by_id


def _persist_item_move(
    root: Path,
    entry_id: str | None,
    item_before: dict[str, Any],
    item_after: dict[str, Any],
    sources_before: dict[str, dict[str, Any]],
    sources_after: dict[str, dict[str, Any]],
) -> str:
    changes: list[dict[str, Any]] = [
        {
            "path": item_rel(item_after["id"]),
            "before": ordered_item(item_before),
            "after": ordered_item(item_after),
        }
    ]
    for source_id, after in sources_after.items():
        before = sources_before.get(source_id)
        if before is None:
            before = try_load_source(root, source_id)
        if before is None:
            continue
        before_ord = ordered_source(before)
        after_ord = ordered_source(after)
        if before_ord == after_ord:
            continue
        changes.append(
            {
                "path": source_rel(source_id),
                "before": before_ord,
                "after": after_ord,
            }
        )
    if entry_id is None:
        entry = make_history_entry(root, "move", changes)
        transact(root, plan_append(root, entry) + changes)
        return entry["id"]
    transact(root, plan_extend_entry(root, entry_id, changes))
    return entry_id


def read_move_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise fail("invalid-argument")
    extra = set(body) - {"itemIds", "destination", "sourceId", "subpath"}
    if extra:
        raise fail("invalid-argument")
    return {
        "itemIds": read_item_ids(body.get("itemIds")),
        "destination": body.get("destination"),
        "sourceId": body.get("sourceId"),
        "subpath": body.get("subpath"),
    }


def move_items(root: Path, item_ids: list[str], dest_spec: dict[str, Any]) -> dict[str, Any]:
    ids = read_item_ids(item_ids)
    for item_id in ids:
        load_item(root, item_id)
    dest_source, dest_dir = resolve_destination(root, dest_spec)
    dest_root = source_files_root(dest_source, root)
    if dest_root is None:
        raise fail("unavailable")
    dest_dir = normalize_root(dest_dir)
    dest_root = normalize_root(dest_root)
    moved: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    entry_id: str | None = None
    for item_id in ids:
        item = load_item(root, item_id)
        files = primary_current_files(item, root)
        if not files:
            skipped.append({"id": item_id, "reason": "unavailable"})
            continue
        planned: list[tuple[dict[str, Any], Path, Path, str]] = []
        for loc, src in files:
            dest_file, kind = _choose_dest_file(dest_dir, src)
            planned.append((loc, src, dest_file, kind))
        if planned and all(kind == "already" for _loc, _src, _dest, kind in planned):
            skipped.append({"id": item_id, "reason": "already-there"})
            continue
        byte_ops: list[tuple[Path, Path, str]] = []
        rend_ops: list[tuple[Path, Path, str]] = []
        committed = False
        try:
            for loc, src, dest_file, kind in planned:
                if kind == "already" and same_path(src, dest_file):
                    continue
                if kind == "already":
                    continue
                method = _relocate_bytes(src, dest_file)
                byte_ops.append((src, dest_file, method))
            maybe_test_barrier("move-after-bytes")
            item_with_rend, rend_ops = _transfer_renditions(root, item, dest_source)
            replacements: dict[tuple[Any, ...], dict[str, Any]] = {}
            file_moves: list[tuple[dict[str, Any], Path, Path]] = []
            for loc, src, dest_file, kind in planned:
                final_path = dest_file if dest_file.exists() else src
                replacements[
                    (
                        loc.get("sourceId"),
                        loc.get("component"),
                        loc.get("libraryRelativePath"),
                        loc.get("pathFromVolumeRoot"),
                    )
                ] = _new_location(dest_source, final_path, loc, root)
                file_moves.append((loc, src, final_path))
            after = clone(item_with_rend)
            new_locs: list[dict[str, Any]] = []
            for loc in after.get("locations") or []:
                key = (
                    loc.get("sourceId"),
                    loc.get("component"),
                    loc.get("libraryRelativePath"),
                    loc.get("pathFromVolumeRoot"),
                )
                new_locs.append(replacements.get(key, loc))
            after["locations"] = new_locs
            after = ordered_item(after)
            sources_after = _plan_source_files(root, item, dest_source, dest_root, file_moves)
            sources_before = {
                source_id: load_source(root, source_id) for source_id in sources_after
            }
            entry_id = _persist_item_move(
                root, entry_id, item, after, sources_before, sources_after
            )
            committed = True
            for src, dest_file, method in byte_ops:
                if method == "copied" and src.exists():
                    try:
                        src.unlink()
                    except OSError:
                        pass
            for src, dest_file, method in rend_ops:
                if method == "copied" and src.exists():
                    try:
                        src.unlink()
                    except OSError:
                        pass
                    try:
                        if src.parent.is_dir() and not any(src.parent.iterdir()):
                            src.parent.rmdir()
                    except OSError:
                        pass
            maybe_test_barrier("move-after-item")
            row = {
                "id": item_id,
                "files": [
                    {
                        "from": str(src),
                        "to": str(dest_file),
                        "filename": dest_file.name,
                        "renamed": kind == "renamed",
                    }
                    for loc, src, dest_file, kind in planned
                ],
            }
            moved.append(row)
        except BaseException as exc:
            if not committed:
                for src, dest_file, method in reversed(rend_ops):
                    _rollback_bytes(src, dest_file, method)
                for src, dest_file, method in reversed(byte_ops):
                    _rollback_bytes(src, dest_file, method)
            if isinstance(exc, SystemExit):
                raise
            code = getattr(exc, "code", None)
            failed.append({"id": item_id, "error": code or "io-error"})
    if entry_id is not None:
        rebuild_sqlite(root, use_barrier=False)
    return {
        "ok": True,
        "destination": str(dest_dir),
        "sourceId": dest_source["id"],
        "moved": moved,
        "skipped": skipped,
        "failed": failed,
    }
