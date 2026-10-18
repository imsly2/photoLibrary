"""Processed picture data that travels inside a served folder.

Serve-from-folder sources with previewStore with-source keep a copy of their
generated records in `<folder>/.library/catalog/`. Another Library can add
that folder and show the finished pictures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json, dumps_canonical, load_json, transact
from library.catalog_io import (
    iter_source_ids,
    source_rel,
    try_load_person,
    try_load_place,
    try_load_source,
    try_load_thing,
)
from library.favorites import FAVORITES_REL, load_favorites
from library.history import make_history_entry, plan_append
from library.records import (
    clone,
    ordered_item,
    ordered_person,
    ordered_place,
    ordered_source,
    ordered_thing,
    read_item,
    read_person,
    read_place,
    read_source,
    read_thing,
)


def is_portable(source: dict[str, Any] | None) -> bool:
    return (
        isinstance(source, dict)
        and source.get("mode") == "serve-from-there"
        and source.get("previewStore") == "with-source"
    )


def bundle_dir(folder: Path) -> Path:
    return folder / ".library" / "catalog"


_FOLDER_CACHE: dict[tuple[Any, ...], Path] = {}
_MIRROR_TEXT: dict[str, str] = {}


def _folder_key(root: Path, source: dict[str, Any]) -> tuple[Any, ...]:
    origin = source.get("origin") or {}
    return (
        str(root),
        source.get("id"),
        source.get("mode"),
        source.get("copyRoot"),
        origin.get("volumeSerial"),
        origin.get("pathFromVolumeRoot"),
        origin.get("lastKnownPath"),
    )


def folder_for_source(root: Path, source: dict[str, Any]) -> Path | None:
    key = _folder_key(root, source)
    cached = _FOLDER_CACHE.get(key)
    if cached is not None and cached.is_dir():
        return cached
    found = _folder_uncached(root, source)
    if found is not None:
        _FOLDER_CACHE[key] = found
    return found


def _folder_uncached(root: Path, source: dict[str, Any]) -> Path | None:
    from library.renditions import source_preview_root

    if source.get("mode") != "copy-here":
        origin = source.get("origin") or {}
        last = origin.get("lastKnownPath")
        serial = origin.get("volumeSerial")
        if type(last) is str and last.strip() and type(serial) is str:
            path = Path(last)
            if path.is_dir():
                try:
                    from library.volumes import volume_of_path

                    found_serial, _volume_root = volume_of_path(path)
                except Exception:
                    found_serial = None
                if found_serial == serial:
                    return path
    found = source_preview_root(source, root)
    if found is not None and found.is_dir():
        return found
    last = (source.get("origin") or {}).get("lastKnownPath")
    if type(last) is str and last.strip():
        path = Path(last)
        if path.is_dir():
            return path
    return None


def _write_json(path: Path, obj: Any) -> None:
    text = dumps_canonical(obj)
    key = str(path)
    if _MIRROR_TEXT.get(key) == text:
        return
    atomic_write_json(path, obj)
    _MIRROR_TEXT[key] = text


def flush(root: Path) -> None:
    """Write each portable folder's source snapshot. Call when a scan ends or the drain goes idle."""
    for source in _portable_sources(root):
        _write_source(root, source)


def sync_bundles(root: Path) -> None:
    """Copy source, items, and related records into each portable folder."""
    for source in _portable_sources(root):
        export_source(root, source["id"])


def mirror_changes(root: Path, changes: list[dict[str, Any]]) -> None:
    """Copy catalog writes for a portable folder into that folder."""
    source_ids: set[str] = set()
    favorites = False
    faces = False
    for change in changes:
        path = change.get("path") or ""
        if not isinstance(path, str):
            continue
        if path == FAVORITES_REL:
            favorites = True
            continue
        if path == "models/faces/index.json":
            faces = True
            continue
        if path.startswith("catalog/sources/") and path.endswith(".json") and ".files/" not in path:
            body = change.get("after") if change.get("after") is not None else change.get("before")
            if isinstance(body, dict) and type(body.get("id")) is str:
                source_ids.add(body["id"])
            continue
        if path.startswith("catalog/items/") and path.endswith(".json"):
            body = change.get("after") if change.get("after") is not None else change.get("before")
            if isinstance(body, dict):
                _mirror_item(root, body, deleted=change.get("after") is None)
                if body.get("faces"):
                    faces = True
            continue
        kind = _entity_kind(path)
        if kind is None:
            continue
        body = change.get("after") if change.get("after") is not None else change.get("before")
        if isinstance(body, dict):
            _refresh_entity(root, kind, body, deleted=change.get("after") is None)
    for source_id in source_ids:
        source = try_load_source(root, source_id)
        if is_portable(source):
            _write_source(root, source)
    if not favorites and not faces:
        return
    for source in _portable_sources(root):
        folder = folder_for_source(root, source)
        if folder is None:
            continue
        if favorites:
            _write_favorites(root, source, folder)
        if faces:
            _write_faces(root, source, folder)


def export_source(root: Path, source_id: str) -> bool:
    """Write one portable source's generated records into its picture folder."""
    source = try_load_source(root, source_id)
    if not is_portable(source) or source is None:
        return False
    folder = folder_for_source(root, source)
    if folder is None:
        return False
    _write_source(root, source)
    catalog = bundle_dir(folder)
    for item_id in _item_ids(source):
        from library.catalog_io import try_load_item

        item = try_load_item(root, item_id)
        if item is None:
            continue
        _write_json(catalog / "items" / f"{item_id}.json", ordered_item(item))
        _mirror_related(root, catalog, item)
    _write_favorites(root, source, folder)
    _write_faces(root, source, folder)
    _write_objects(root, source, folder)
    return True


def mirror_objects(root: Path) -> None:
    for source in _portable_sources(root):
        folder = folder_for_source(root, source)
        if folder is not None:
            _write_objects(root, source, folder)


def adopt_folder(root: Path, scan_path: Path) -> dict[str, Any] | None:
    """Return the source for a folder that already carries its processed catalog.

    A source id this library already has is returned unchanged so the caller
    can point it at the folder's current path. A new id is imported.
    """
    path = bundle_dir(scan_path) / "source.json"
    if not path.is_file():
        return None
    try:
        bundled = read_source(load_json(path))
    except Exception:
        return None
    existing = try_load_source(root, bundled["id"])
    if existing is not None:
        return existing
    try:
        return _import_bundle(root, scan_path, bundled)
    except Exception:
        return None


def _import_bundle(root: Path, scan_path: Path, bundled: dict[str, Any]) -> dict[str, Any] | None:
    from library.volumes import last_known_text, path_from_volume_root, volume_of_path

    serial, volume_root = volume_of_path(scan_path)
    origin_rel = path_from_volume_root(scan_path, volume_root)
    new_origin = {
        "volumeSerial": serial,
        "pathFromVolumeRoot": origin_rel,
        "lastKnownPath": last_known_text(scan_path),
    }
    old_root = str((bundled.get("origin") or {}).get("pathFromVolumeRoot") or "")
    source_id = bundled["id"]
    catalog = bundle_dir(scan_path)
    imported: dict[str, dict[str, Any]] = {}
    for path in _json_files(catalog / "items"):
        try:
            item = _rebind_item(read_item(load_json(path)), source_id, old_root, new_origin)
        except Exception:
            continue
        if item["id"].startswith("pending-"):
            continue
        imported[item["id"]] = item
    source = clone(bundled)
    source["origin"] = new_origin
    source["mode"] = "serve-from-there"
    source["previewStore"] = "with-source"
    source["files"] = {
        rel: entry
        for rel, entry in (bundled.get("files") or {}).items()
        if type(entry.get("itemId")) is str and entry["itemId"] in imported
    }
    source = ordered_source(source)
    changes: list[dict[str, Any]] = [
        {"path": source_rel(source_id), "before": None, "after": source}
    ]
    for item in imported.values():
        from library.catalog_io import item_rel, try_load_item

        if try_load_item(root, item["id"]) is not None:
            continue
        changes.append({"path": item_rel(item["id"]), "before": None, "after": item})
    _queue_new_entities(root, catalog, "people", read_person, ordered_person, changes)
    _queue_new_entities(root, catalog, "places", read_place, ordered_place, changes)
    _queue_new_entities(root, catalog, "things", read_thing, ordered_thing, changes)
    hearts = _bundle_favorites(catalog)
    if hearts:
        current = load_favorites(root)
        merged_ids = sorted(set(current["itemIds"]) | hearts)
        if merged_ids != current["itemIds"]:
            merged = {"schemaVersion": 1, "itemIds": merged_ids}
            changes.append({"path": FAVORITES_REL, "before": current, "after": merged})
    entry = make_history_entry(root, "scan", changes)
    transact(root, plan_append(root, entry) + changes)
    _merge_faces(root, catalog)
    _merge_objects(root, catalog)
    return try_load_source(root, source_id)


def _queue_new_entities(root, catalog, kind, reader, orderer, changes) -> None:
    from library.catalog_io import person_rel, place_rel, thing_rel

    rel_for = {"people": person_rel, "places": place_rel, "things": thing_rel}[kind]
    seen = {"people": try_load_person, "places": try_load_place, "things": try_load_thing}[kind]
    for path in _json_files(catalog / kind):
        try:
            record = orderer(reader(load_json(path)))
        except Exception:
            continue
        if seen(root, record["id"]) is not None:
            continue
        changes.append({"path": rel_for(record["id"]), "before": None, "after": record})


def _merge_faces(root: Path, catalog: Path) -> None:
    path = catalog / "faces.json"
    if not path.is_file():
        return
    try:
        bundled = load_json(path)
    except Exception:
        return
    if not isinstance(bundled, dict):
        return
    from library.atomic import atomic_write_json as write_json
    from library.faces import index_path, load_index

    current = load_index(root) or {
        "schemaVersion": 1,
        "backend": bundled.get("backend") or "insightface",
        "matchThreshold": bundled.get("matchThreshold") or 0.8,
        "people": {},
    }
    people = dict(current.get("people") or {})
    for person_id, rec in (bundled.get("people") or {}).items():
        if not isinstance(rec, dict):
            continue
        existing = dict(people.get(person_id) or {"centroid": [], "faces": []})
        known = {
            (ref.get("itemId"), tuple(ref.get("box") or []))
            for ref in existing.get("faces") or []
            if isinstance(ref, dict)
        }
        faces = list(existing.get("faces") or [])
        for ref in rec.get("faces") or []:
            if not isinstance(ref, dict):
                continue
            key = (ref.get("itemId"), tuple(ref.get("box") or []))
            if key not in known:
                faces.append(ref)
                known.add(key)
        centroid = existing.get("centroid") or rec.get("centroid") or []
        people[person_id] = {"centroid": list(centroid), "faces": faces}
    current = dict(current)
    current["people"] = people
    write_json(index_path(root), current)


def _merge_objects(root: Path, catalog: Path) -> None:
    path = catalog / "objects.json"
    if not path.is_file():
        return
    try:
        bundled = load_json(path)
    except Exception:
        return
    if not isinstance(bundled, dict):
        return
    from library.objects import _load_state, _save_state

    state = _load_state(root)
    items = dict(state.get("items") or {})
    for item_id, rec in (bundled.get("items") or {}).items():
        if type(item_id) is str and isinstance(rec, dict) and item_id not in items:
            items[item_id] = rec
    state["items"] = items
    _save_state(root, state)


def _mirror_item(root: Path, item: dict[str, Any], *, deleted: bool) -> None:
    try:
        item = ordered_item(item)
    except Exception:
        return
    for source in _sources_for_item(root, item):
        folder = folder_for_source(root, source)
        if folder is None:
            continue
        catalog = bundle_dir(folder)
        dest = catalog / "items" / f"{item['id']}.json"
        if deleted or item["id"].startswith("pending-"):
            if dest.is_file():
                dest.unlink()
            continue
        _write_json(dest, item)
        _mirror_related(root, catalog, item)


def _write_source(root: Path, source: dict[str, Any] | None) -> None:
    if not is_portable(source) or source is None:
        return
    folder = folder_for_source(root, source)
    if folder is None:
        return
    _write_json(bundle_dir(folder) / "source.json", ordered_source(source))


def _mirror_related(root: Path, catalog: Path, item: dict[str, Any]) -> None:
    place_id = item.get("placeId")
    if type(place_id) is str:
        place = try_load_place(root, place_id)
        if place is not None:
            _write_json(catalog / "places" / f"{place_id}.json", ordered_place(place))
    for face in item.get("faces") or []:
        person_id = face.get("personId") if isinstance(face, dict) else None
        if type(person_id) is not str:
            continue
        person = try_load_person(root, person_id)
        if person is not None:
            _write_json(catalog / "people" / f"{person_id}.json", ordered_person(person))
    for ref in item.get("things") or []:
        thing_id = ref.get("thingId") if isinstance(ref, dict) else None
        if type(thing_id) is not str:
            continue
        thing = try_load_thing(root, thing_id)
        if thing is not None:
            _write_json(catalog / "things" / f"{thing_id}.json", ordered_thing(thing))


def _refresh_entity(root: Path, kind: str, entity: dict[str, Any], *, deleted: bool) -> None:
    entity_id = entity.get("id")
    if type(entity_id) is not str:
        return
    orderer = {"people": ordered_person, "places": ordered_place, "things": ordered_thing}[kind]
    try:
        entity = orderer(entity)
    except Exception:
        if not deleted:
            return
    for source in _portable_sources(root):
        folder = folder_for_source(root, source)
        if folder is None:
            continue
        dest = bundle_dir(folder) / kind / f"{entity_id}.json"
        if deleted:
            if dest.is_file():
                dest.unlink()
            continue
        if dest.is_file() or _source_uses(root, source, kind, entity_id):
            _write_json(dest, entity)


def _write_favorites(root: Path, source: dict[str, Any], folder: Path) -> None:
    hearts = favorite_ids_for(root, source)
    _write_json(
        bundle_dir(folder) / "favorites.json",
        {"schemaVersion": 1, "itemIds": hearts},
    )


def favorite_ids_for(root: Path, source: dict[str, Any]) -> list[str]:
    hearts = set(load_favorites(root)["itemIds"])
    return sorted(item_id for item_id in _item_ids(source) if item_id in hearts)


def _write_faces(root: Path, source: dict[str, Any], folder: Path) -> None:
    from library.faces import load_index

    index = load_index(root)
    if not isinstance(index, dict):
        return
    wanted = set(_item_ids(source))
    people: dict[str, Any] = {}
    for person_id, rec in (index.get("people") or {}).items():
        if not isinstance(rec, dict):
            continue
        faces = [
            ref
            for ref in (rec.get("faces") or [])
            if isinstance(ref, dict) and ref.get("itemId") in wanted
        ]
        if not faces:
            continue
        people[str(person_id)] = {"centroid": list(rec.get("centroid") or []), "faces": faces}
    if not people:
        return
    _write_json(
        bundle_dir(folder) / "faces.json",
        {
            "schemaVersion": 1,
            "backend": index.get("backend"),
            "matchThreshold": index.get("matchThreshold"),
            "people": people,
        },
    )


def _write_objects(root: Path, source: dict[str, Any], folder: Path) -> None:
    from library.objects import _load_state

    state = _load_state(root)
    wanted = set(_item_ids(source))
    mine = {
        item_id: rec
        for item_id, rec in (state.get("items") or {}).items()
        if item_id in wanted and isinstance(rec, dict)
    }
    if not mine:
        return
    _write_json(
        bundle_dir(folder) / "objects.json",
        {"schemaVersion": 1, "items": mine},
    )


def _sources_for_item(root: Path, item: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for loc in item.get("locations") or []:
        source_id = loc.get("sourceId") if isinstance(loc, dict) else None
        if type(source_id) is not str or source_id in seen:
            continue
        seen.add(source_id)
        source = try_load_source(root, source_id)
        if is_portable(source) and source is not None:
            found.append(source)
    return found


def _portable_sources(root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for source_id in iter_source_ids(root):
        source = try_load_source(root, source_id)
        if is_portable(source) and source is not None:
            found.append(source)
    return found


def _item_ids(source: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for entry in (source.get("files") or {}).values():
        item_id = entry.get("itemId") if isinstance(entry, dict) else None
        if type(item_id) is str and item_id and not item_id.startswith("pending-"):
            ids.append(item_id)
    return ids


def _source_uses(root: Path, source: dict[str, Any], kind: str, entity_id: str) -> bool:
    from library.catalog_io import try_load_item

    for item_id in _item_ids(source):
        item = try_load_item(root, item_id)
        if item is None:
            continue
        if kind == "places" and item.get("placeId") == entity_id:
            return True
        if kind == "people" and any(
            isinstance(face, dict) and face.get("personId") == entity_id for face in item.get("faces") or []
        ):
            return True
        if kind == "things" and any(
            isinstance(ref, dict) and ref.get("thingId") == entity_id for ref in item.get("things") or []
        ):
            return True
    return False


def _entity_kind(path: str) -> str | None:
    for kind in ("people", "places", "things"):
        prefix = f"catalog/{kind}/"
        if path.startswith(prefix) and path.endswith(".json"):
            return kind
    return None


def _json_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.json") if path.is_file())


def _bundle_favorites(catalog: Path) -> set[str]:
    path = catalog / "favorites.json"
    if not path.is_file():
        return set()
    try:
        data = load_json(path)
    except Exception:
        return set()
    ids = data.get("itemIds") if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return set()
    return {item_id for item_id in ids if type(item_id) is str and item_id}


def _rebind_item(
    item: dict[str, Any],
    source_id: str,
    old_root: str,
    new_origin: dict[str, str],
) -> dict[str, Any]:
    item = clone(item)
    old = old_root.replace("\\", "/").strip("/")
    new_root = new_origin["pathFromVolumeRoot"].replace("\\", "/").strip("/")
    base = Path(new_origin["lastKnownPath"])
    for loc in item["locations"]:
        if loc.get("sourceId") != source_id or loc.get("kind") != "volume":
            continue
        rel = str(loc.get("pathFromVolumeRoot") or "").replace("\\", "/").strip("/")
        if old and (rel == old or rel.startswith(old + "/")):
            suffix = rel[len(old) :].lstrip("/")
        else:
            suffix = ""
        loc["volumeSerial"] = new_origin["volumeSerial"]
        if suffix and new_root:
            loc["pathFromVolumeRoot"] = f"{new_root}/{suffix}"
        else:
            loc["pathFromVolumeRoot"] = suffix or new_root
        loc["lastKnownPath"] = str(base.joinpath(*suffix.split("/"))) if suffix else str(base)
    return ordered_item(item)
