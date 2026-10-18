"""Load and save catalog JSON; pending hash publication."""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from library.atomic import load_json, transact
from library.errors import fail
from library.records import (
    clone,
    location_key,
    make_file_entry,
    ordered_item,
    ordered_person,
    ordered_place,
    ordered_source,
    ordered_thing,
    read_file_entry,
    read_item,
    read_person,
    read_place,
    read_source,
    read_thing,
    renditions_for,
)
from library.volumes import same_origin, source_available


def catalog_root(root: Path) -> Path:
    return root / "catalog"


def items_dir(root: Path) -> Path:
    return catalog_root(root) / "items"


def sources_dir(root: Path) -> Path:
    return catalog_root(root) / "sources"


def places_dir(root: Path) -> Path:
    return catalog_root(root) / "places"


def people_dir(root: Path) -> Path:
    return catalog_root(root) / "people"


def things_dir(root: Path) -> Path:
    return catalog_root(root) / "things"


def ensure_catalog_dirs(root: Path) -> None:
    items_dir(root).mkdir(parents=True, exist_ok=True)
    sources_dir(root).mkdir(parents=True, exist_ok=True)
    places_dir(root).mkdir(parents=True, exist_ok=True)
    people_dir(root).mkdir(parents=True, exist_ok=True)
    things_dir(root).mkdir(parents=True, exist_ok=True)


def item_rel(item_id: str) -> str:
    return f"catalog/items/{item_id}.json"


def source_rel(source_id: str) -> str:
    return f"catalog/sources/{source_id}.json"


def place_rel(place_id: str) -> str:
    return f"catalog/places/{place_id}.json"


def person_rel(person_id: str) -> str:
    return f"catalog/people/{person_id}.json"


def thing_rel(thing_id: str) -> str:
    return f"catalog/things/{thing_id}.json"


def iter_source_ids(root: Path) -> list[str]:
    folder = sources_dir(root)
    if not folder.exists():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def iter_item_ids(root: Path) -> list[str]:
    folder = items_dir(root)
    if not folder.exists():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def load_item(root: Path, item_id: str) -> dict[str, Any]:
    path = items_dir(root) / f"{item_id}.json"
    try:
        return read_item(load_json(path))
    except FileNotFoundError as exc:
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc


def load_source(root: Path, source_id: str) -> dict[str, Any]:
    found = try_load_source(root, source_id)
    if found is None:
        raise fail("not-found")
    return found


_CATALOG_OVERLAY: ContextVar[dict[str, Any] | None] = ContextVar("catalog_overlay", default=None)


@contextmanager
def catalog_overlay():
    token = _CATALOG_OVERLAY.set({})
    try:
        yield
    finally:
        _CATALOG_OVERLAY.reset(token)


def note_catalog_overlay(relative: str, payload: Any) -> None:
    overlay = _CATALOG_OVERLAY.get()
    if overlay is not None:
        overlay[relative] = payload


def drop_catalog_overlay(relative: str) -> None:
    overlay = _CATALOG_OVERLAY.get()
    if overlay is not None:
        overlay.pop(relative, None)


def _overlay_payload(relative: str) -> Any:
    overlay = _CATALOG_OVERLAY.get()
    if overlay is None or relative not in overlay:
        return _MISSING
    return overlay[relative]


class _Missing:
    pass


_MISSING = _Missing()


def successor_item_id(root: Path, item_id: str) -> str | None:
    """Hash id for a pending record that was already published and removed.

    The pending file is the record while it exists. After hash publication
    deletes it, a caller that still holds the pending id follows the source
    file row to the hash item. A pending id with no published item stays unresolved.
    """
    if type(item_id) is not str or not item_id.startswith("pending-"):
        return None
    if (items_dir(root) / f"{item_id}.json").is_file():
        return None
    source_id, _, digest = item_id[len("pending-") :].partition("-")
    if not source_id.startswith("src_") or len(digest) != 64:
        return None
    entry = _journal_entry(root, source_id, digest)
    if entry is None:
        entry = _folded_entry(root, source_id, digest)
    if not isinstance(entry, dict):
        return None
    successor = entry.get("itemId")
    if (
        type(successor) is not str
        or not successor
        or successor == item_id
        or successor.startswith("pending-")
    ):
        return None
    if not (items_dir(root) / f"{successor}.json").is_file():
        return None
    return successor


def _journal_entry(root: Path, source_id: str, digest: str) -> dict[str, Any] | None:
    path = _journal_dir(root, source_id) / f"{digest}.json"
    if not path.is_file():
        return None
    body = load_json(path)
    if not isinstance(body, dict):
        return None
    entry = body.get("entry")
    return entry if isinstance(entry, dict) else None


def _folded_entry(root: Path, source_id: str, digest: str) -> dict[str, Any] | None:
    from library.media import sha256_text

    source = try_load_source(root, source_id)
    if source is None:
        return None
    for rel, entry in (source.get("files") or {}).items():
        if sha256_text(str(rel).replace("\\", "/")) == digest:
            return entry
    return None


def try_load_item(root: Path, item_id: str) -> dict[str, Any] | None:
    relative = item_rel(item_id)
    overlaid = _overlay_payload(relative)
    if overlaid is not _MISSING:
        return None if overlaid is None else read_item(clone(overlaid))
    path = items_dir(root) / f"{item_id}.json"
    if not path.exists():
        return None
    return read_item(load_json(path))


def try_load_source(root: Path, source_id: str) -> dict[str, Any] | None:
    path = sources_dir(root) / f"{source_id}.json"
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime_ns
    except OSError as exc:
        raise fail("io-error") from exc
    key = _source_cache_key(root, source_id)
    slot = _SOURCE_CACHE.get(key)
    if slot is not None and slot["mtime"] == mtime:
        return _source_view(slot["source"])
    source = read_source(load_json(path))
    journals = _read_journals(root, source_id)
    files = dict(source["files"])
    for rel, body in journals.items():
        entry = body.get("entry")
        if entry is None:
            files.pop(rel, None)
        else:
            files[rel] = read_file_entry(entry)
    source = dict(source)
    source["files"] = files
    _SOURCE_CACHE[key] = {"mtime": mtime, "source": source, "journals": journals}
    return _source_view(source)


_SOURCE_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _source_cache_key(root: Path, source_id: str) -> tuple[str, str]:
    return (str(root.resolve()), source_id)


def _source_view(source: dict[str, Any]) -> dict[str, Any]:
    out = dict(source)
    out["origin"] = dict(source.get("origin") or {})
    scan = dict(source.get("scan") or {})
    if isinstance(scan.get("errors"), list):
        scan["errors"] = list(scan["errors"])
    out["scan"] = scan
    out["files"] = {rel: dict(entry) for rel, entry in (source.get("files") or {}).items()}
    return out


def _journal_dir(root: Path, source_id: str) -> Path:
    return sources_dir(root) / f"{source_id}.files"


def source_file_rel(source_id: str, rel: str) -> str:
    from library.media import sha256_text

    digest = sha256_text(rel.replace("\\", "/"))
    return f"catalog/sources/{source_id}.files/{digest}.json"


def _read_journals(root: Path, source_id: str) -> dict[str, dict[str, Any]]:
    folder = _journal_dir(root, source_id)
    found: dict[str, dict[str, Any]] = {}
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.json")):
        body = load_json(path)
        if not isinstance(body, dict) or type(body.get("rel")) is not str:
            raise fail("invalid-catalog")
        found[body["rel"]] = body
    return found


def _copy_journal(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if body is None:
        return None
    entry = body.get("entry")
    return {"rel": body.get("rel"), "entry": None if entry is None else dict(entry)}


def note_source_write(root: Path, relative: str, payload: Any) -> None:
    """Keep the merged-source cache aligned with a transaction that just landed."""
    prefix = "catalog/sources/"
    if not relative.startswith(prefix) or not relative.endswith(".json"):
        return
    rest = relative[len(prefix) :]
    if ".files/" in rest:
        source_id, _, _name = rest.partition(".files/")
        slot = _SOURCE_CACHE.get(_source_cache_key(root, source_id))
        if slot is None:
            return
        if not isinstance(payload, dict) or type(payload.get("rel")) is not str:
            _SOURCE_CACHE.pop(_source_cache_key(root, source_id), None)
            return
        rel = payload["rel"]
        entry = payload.get("entry")
        if entry is None:
            slot["source"]["files"].pop(rel, None)
        else:
            slot["source"]["files"][rel] = dict(entry)
        slot["journals"][rel] = payload
        return
    source_id = rest[: -len(".json")]
    if source_id and "/" not in source_id:
        _SOURCE_CACHE.pop(_source_cache_key(root, source_id), None)


def plan_source_file(root: Path, source_id: str, rel: str, entry: dict[str, Any] | None) -> dict[str, Any]:
    """One file-row write. Constant size, independent of how many files the source already has."""
    path = source_file_rel(source_id, rel)
    key = _source_cache_key(root, source_id)
    slot = _SOURCE_CACHE.get(key)
    if slot is not None and rel in slot["journals"]:
        before = _copy_journal(slot["journals"].get(rel))
    else:
        file_path = _journal_dir(root, source_id) / Path(path).name
        before = load_json(file_path) if file_path.is_file() else None
    after_entry = None if entry is None else dict(entry)
    return {"path": path, "before": before, "after": {"rel": rel, "entry": after_entry}}


def fold_source_changes(root: Path, source: dict[str, Any]) -> list[dict[str, Any]]:
    """Write the merged source once and delete the per-file journals."""
    source_id = source["id"]
    raw_path = sources_dir(root) / f"{source_id}.json"
    raw = load_json(raw_path) if raw_path.is_file() else None
    changes: list[dict[str, Any]] = [
        {"path": source_rel(source_id), "before": raw, "after": ordered_source(source)}
    ]
    folder = _journal_dir(root, source_id)
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            changes.append(
                {
                    "path": f"catalog/sources/{source_id}.files/{path.name}",
                    "before": load_json(path),
                    "after": None,
                }
            )
    return changes


def fold_open_journals(root: Path) -> None:
    """Merge leftover per-file journals into each source file."""
    from library.history import extend_current_operation

    base = sources_dir(root)
    if not base.is_dir():
        return
    for journal_dir in sorted(path for path in base.glob("*.files") if path.is_dir()):
        if not any(journal_dir.glob("*.json")):
            continue
        source_id = journal_dir.name[: -len(".files")]
        source = try_load_source(root, source_id)
        if source is None:
            continue
        transact(root, extend_current_operation(root, fold_source_changes(root, source)))


def iter_place_ids(root: Path) -> list[str]:
    folder = places_dir(root)
    if not folder.exists():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def load_place(root: Path, place_id: str) -> dict[str, Any]:
    path = places_dir(root) / f"{place_id}.json"
    try:
        return read_place(load_json(path))
    except FileNotFoundError as exc:
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc


def try_load_place(root: Path, place_id: str) -> dict[str, Any] | None:
    relative = place_rel(place_id)
    overlaid = _overlay_payload(relative)
    if overlaid is not _MISSING:
        return None if overlaid is None else read_place(clone(overlaid))
    path = places_dir(root) / f"{place_id}.json"
    if not path.exists():
        return None
    return read_place(load_json(path))


def load_places(root: Path) -> list[dict[str, Any]]:
    places = {place["id"]: place for place in (load_place(root, place_id) for place_id in iter_place_ids(root))}
    overlay = _CATALOG_OVERLAY.get()
    if overlay is None:
        return list(places.values())
    prefix = "catalog/places/"
    for relative, payload in overlay.items():
        if not relative.startswith(prefix) or not relative.endswith(".json"):
            continue
        place_id = relative[len(prefix) : -len(".json")]
        if payload is None:
            places.pop(place_id, None)
        else:
            places[place_id] = read_place(clone(payload))
    return list(places.values())


def new_place_id(root: Path) -> str:
    existing = set(iter_place_ids(root))
    overlay = _CATALOG_OVERLAY.get()
    if overlay is not None:
        prefix = "catalog/places/"
        for relative, payload in overlay.items():
            if payload is not None and relative.startswith(prefix) and relative.endswith(".json"):
                existing.add(relative[len(prefix) : -len(".json")])
    for _ in range(32):
        candidate = "place_" + secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise fail("internal-error")


def iter_person_ids(root: Path) -> list[str]:
    folder = people_dir(root)
    if not folder.exists():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def iter_thing_ids(root: Path) -> list[str]:
    folder = things_dir(root)
    if not folder.exists():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def load_person(root: Path, person_id: str) -> dict[str, Any]:
    path = people_dir(root) / f"{person_id}.json"
    try:
        return read_person(load_json(path))
    except FileNotFoundError as exc:
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc


def load_thing(root: Path, thing_id: str) -> dict[str, Any]:
    path = things_dir(root) / f"{thing_id}.json"
    try:
        return read_thing(load_json(path))
    except FileNotFoundError as exc:
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc


def new_person_id(root: Path) -> str:
    existing = set(iter_person_ids(root))
    for _ in range(32):
        candidate = "person_" + secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise fail("internal-error")


def new_thing_id(root: Path) -> str:
    existing = set(iter_thing_ids(root))
    for _ in range(32):
        candidate = "thing_" + secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise fail("internal-error")


def load_people(root: Path) -> list[dict[str, Any]]:
    return [load_person(root, person_id) for person_id in iter_person_ids(root)]


def load_things(root: Path) -> list[dict[str, Any]]:
    return [load_thing(root, thing_id) for thing_id in iter_thing_ids(root)]


def new_source_id(root: Path) -> str:
    existing = set(iter_source_ids(root))
    for _ in range(32):
        candidate = "src_" + secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise fail("internal-error")


def find_source_by_origin(root: Path, serial: str, path_from_root: str) -> dict[str, Any] | None:
    for source_id in iter_source_ids(root):
        source = load_source(root, source_id)
        if same_origin(source, serial, path_from_root):
            return source
    return None


def file_key_for_location(source: dict[str, Any], item_id: str, location: dict[str, Any]) -> str | None:
    for key, entry in (source.get("files") or {}).items():
        if entry.get("itemId") == item_id:
            return key
    dest = location.get("libraryRelativePath")
    if type(dest) is str and dest:
        for key, entry in (source.get("files") or {}).items():
            if entry.get("destination") == dest:
                return key
    path = location.get("pathFromVolumeRoot")
    if type(path) is str:
        return relative_from_origin(source, path)
    return None


def relative_from_origin(source: dict[str, Any], path_from_volume_root: str) -> str:
    origin = source["origin"]["pathFromVolumeRoot"]
    if origin == "":
        return path_from_volume_root
    prefix = origin.rstrip("/") + "/"
    if path_from_volume_root.startswith(prefix):
        return path_from_volume_root[len(prefix) :]
    if path_from_volume_root == origin:
        return ""
    return path_from_volume_root


def source_read(source: dict[str, Any], root: Path) -> dict[str, Any]:
    from library.sources import source_stats

    out = ordered_source(source)
    out["available"] = source_available(source, root)
    origin = out.get("origin") or {}
    last = origin.get("lastKnownPath")
    out["path"] = last if type(last) is str else ""
    out["stats"] = source_stats(source, root)
    return out


def try_load_person(root: Path, person_id: str) -> dict[str, Any] | None:
    path = people_dir(root) / f"{person_id}.json"
    if not path.exists():
        return None
    return read_person(load_json(path))


def try_load_thing(root: Path, thing_id: str) -> dict[str, Any] | None:
    path = things_dir(root) / f"{thing_id}.json"
    if not path.exists():
        return None
    return read_thing(load_json(path))


def item_read(
    item: dict[str, Any],
    root: Path,
    favorites: set[str] | None = None,
) -> dict[str, Any]:
    from library.favorites import favorite_ids
    from library.volumes import item_available, item_motion_available

    out = ordered_item(item)
    out["available"] = item_available(item, root)
    out["motionAvailable"] = item_motion_available(item, root)
    out.update(_last_known_read(item))
    marked = favorite_ids(root) if favorites is None else favorites
    out["favorite"] = item.get("id") in marked
    places: list[dict[str, Any]] = []
    place_id = item.get("placeId")
    if type(place_id) is str and place_id:
        place = try_load_place(root, place_id)
        if place is not None:
            places = [ordered_place(place)]
    people: list[dict[str, Any]] = []
    seen_people: set[str] = set()
    for face in item.get("faces") or []:
        person_id = face.get("personId")
        if type(person_id) is not str or person_id in seen_people:
            continue
        person = try_load_person(root, person_id)
        if person is not None:
            people.append(ordered_person(person))
            seen_people.add(person_id)
    people.sort(key=lambda rec: rec["id"])
    things: list[dict[str, Any]] = []
    seen_things: set[str] = set()
    for ref in item.get("things") or []:
        thing_id = ref.get("thingId")
        if type(thing_id) is not str or thing_id in seen_things:
            continue
        thing = try_load_thing(root, thing_id)
        if thing is not None:
            things.append(ordered_thing(thing))
            seen_things.add(thing_id)
    things.sort(key=lambda rec: rec["id"])
    out["entities"] = {"people": people, "places": places, "things": things}
    from library.rating import quality_view

    out["rating"] = quality_view(item)
    return out


def _last_known_read(item: dict[str, Any]) -> dict[str, Any]:
    from library.favorites import existing_folder, existing_original

    locs = [loc for loc in item.get("locations") or [] if loc.get("current") is True]
    locs.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("lastKnownPath") or "",
        )
    )
    last = ""
    last_file = False
    last_folder = ""
    for loc in locs:
        path = loc.get("lastKnownPath")
        if type(path) is not str or not path:
            continue
        if not last:
            last = path
        if existing_original(Path(path)) is not None:
            last_file = True
        folder = existing_folder(Path(path).parent)
        if folder is not None and not last_folder:
            last_folder = str(folder)
    return {
        "lastKnownPath": last,
        "lastKnownFile": last_file,
        "lastKnownFolder": last_folder,
    }


def has_primary(item: dict[str, Any], component: str) -> bool:
    return any(
        loc["current"] and loc["component"] == component and loc["role"] == "primary"
        for loc in item["locations"]
    )


def merge_location(item: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    item = clone(item)
    key = location_key(incoming)
    existing = [loc for loc in item["locations"] if location_key(loc) == key]
    if existing:
        return item
    loc = clone(incoming)
    if has_primary(item, loc["component"]) and loc["role"] == "primary":
        loc["role"] = "alternate"
    item["locations"].append(loc)
    return item


def merge_associations(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = clone(existing)
    seen_faces = {(f.get("personId"), tuple(f.get("box") or [])) for f in out["faces"]}
    for face in incoming.get("faces") or []:
        key = (face.get("personId"), tuple(face.get("box") or []))
        if key not in seen_faces:
            out["faces"].append(clone(face))
            seen_faces.add(key)
    seen_things = {(t.get("thingId"), tuple(t.get("box") or [])) for t in out["things"]}
    for thing in incoming.get("things") or []:
        key = (thing.get("thingId"), tuple(thing.get("box") or []))
        if key not in seen_things:
            out["things"].append(clone(thing))
            seen_things.add(key)
    if out["placeId"] is None:
        out["placeId"] = incoming.get("placeId")
    return out


def publish_pending(root: Path, pending: dict[str, Any]) -> dict[str, Any]:
    pending = read_item(pending)
    sha256 = None
    for loc in pending["locations"]:
        if loc.get("sha256"):
            sha256 = loc["sha256"]
            break
    if not sha256:
        return pending
    digest = sha256.lower()
    existing = try_load_item(root, digest)
    published = clone(pending)
    published["id"] = digest
    if existing is None:
        return ordered_item(published)
    merged = clone(existing)
    for loc in published["locations"]:
        merged = merge_location(merged, loc)
    merged = merge_associations(merged, published)
    if merged["kind"] == "photo" and published["kind"] == "video":
        pass
    return ordered_item(merged)


_NO_PENDING: dict[str, int] = {}


def pending_item_ids(root: Path) -> list[str]:
    folder = items_dir(root)
    if not folder.is_dir():
        return []
    try:
        token = folder.stat().st_mtime_ns
    except OSError:
        return []
    key = str(folder)
    if _NO_PENDING.get(key) == token:
        return []
    found = sorted(path.stem for path in folder.glob("pending-*.json") if path.is_file())
    if found:
        _NO_PENDING.pop(key, None)
    else:
        _NO_PENDING[key] = token
    return found


def finish_pending_publications(root: Path) -> list[str]:
    from library.history import extend_current_operation

    finished: list[str] = []
    for item_id in pending_item_ids(root):
        pending = try_load_item(root, item_id)
        if pending is None:
            continue
        sha256 = next((loc.get("sha256") for loc in pending["locations"] if loc.get("sha256")), None)
        if not sha256:
            continue
        source_id = pending["locations"][0]["sourceId"]
        source = try_load_source(root, source_id)
        if source is None:
            continue
        published = publish_pending(root, pending)
        rel = file_key_for_location(source, pending["id"], pending["locations"][0])
        entry = source["files"].get(rel) if rel is not None else None
        if entry is not None:
            entry["itemId"] = published["id"]
            entry["sha256"] = sha256
            entry["state"] = "indexed"
            source["files"][rel] = make_file_entry(**{
                "item_id": entry["itemId"],
                "component": entry["component"],
                "size_bytes": entry["sizeBytes"],
                "modified_at": entry["modifiedAt"],
                "sha256": entry["sha256"],
                "state": entry["state"],
                "destination": entry["destination"],
            })
        changes = [
            {
                "path": item_rel(published["id"]),
                "before": try_load_item(root, published["id"]),
                "after": published,
            },
            {"path": item_rel(pending["id"]), "before": pending, "after": None},
        ]
        from library.history import history_batching

        if history_batching() and rel is not None and source["files"].get(rel) is not None:
            changes.append(plan_source_file(root, source_id, rel, source["files"][rel]))
        else:
            changes.extend(fold_source_changes(root, source))
        from library.annotate import plan_rebase_pending

        changes.extend(plan_rebase_pending(root, pending["id"], published))
        from library.favorites import plan_remap_favorite

        changes.extend(plan_remap_favorite(root, pending["id"], published["id"]))
        transact(root, extend_current_operation(root, changes))
        finished.append(published["id"])
    from library.atomic import transactions_held
    from library.history import history_batching, seal_latest

    if finished and not history_batching() and not transactions_held(root):
        seal_latest(root)
    return finished


def _live_renditions_from_still(still_item: dict[str, Any]) -> dict[str, Any]:
    rend = still_item.get("renditions") or {}
    out = renditions_for(
        "live",
        rend.get("sourceId") or still_item["locations"][0]["sourceId"],
        store=rend.get("store") or "with-server",
    )
    status = rend.get("status") or {}
    for slot in ("thumb", "preview"):
        slot_status = status.get(slot)
        if slot_status in {"ready", "error"}:
            out[slot] = rend.get(slot)
            out["status"][slot] = slot_status
    return out


def pair_live_items(root: Path, source_id: str) -> None:
    from library.annotate import plan_absorb_item_refs
    from library.history import extend_current_operation, latest_entry_id

    stills: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    motions: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id in iter_item_ids(root):
        if item_id.startswith("pending-"):
            continue
        item = load_item(root, item_id)
        cid = item.get("contentIdentifier")
        if type(cid) is not str or not cid:
            continue
        for loc in item["locations"]:
            if loc["sourceId"] != source_id or loc["current"] is not True:
                continue
            path = loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or ""
            if loc["component"] == "still":
                stills.setdefault(cid, []).append((path, item))
            elif loc["component"] == "motion":
                motions.setdefault(cid, []).append((path, item))
    for cid, still_list in stills.items():
        motion_list = motions.get(cid) or []
        if not motion_list:
            continue
        still_list.sort(key=lambda pair: pair[0])
        motion_list.sort(key=lambda pair: pair[0])
        still_item = clone(still_list[0][1])
        motion_item = clone(motion_list[0][1])
        if still_item["id"] == motion_item["id"]:
            continue
        if still_item["kind"] != "photo" or motion_item["kind"] != "video":
            continue
        before_still = try_load_item(root, still_item["id"])
        before_motion = try_load_item(root, motion_item["id"])
        live = clone(still_item)
        live["kind"] = "live"
        live["id"] = still_item["id"]
        for loc in motion_item["locations"]:
            if loc.get("component") == "motion":
                live = merge_location(live, loc)
        live = merge_associations(live, motion_item)
        live["renditions"] = _live_renditions_from_still(still_item)
        live = ordered_item(live)
        source = load_source(root, source_id)
        changed: list[str] = []
        for rel, entry in list(source["files"].items()):
            if entry["itemId"] == motion_item["id"] and entry.get("component") == "motion":
                entry["itemId"] = live["id"]
                entry["component"] = "motion"
                source["files"][rel] = make_file_entry(
                    item_id=entry["itemId"],
                    component=entry["component"],
                    size_bytes=entry["sizeBytes"],
                    modified_at=entry["modifiedAt"],
                    sha256=entry["sha256"],
                    state=entry["state"],
                    destination=entry["destination"],
                )
                changed.append(rel)
        changes = [
            {"path": item_rel(live["id"]), "before": before_still, "after": live},
        ]
        if motion_item["id"] != live["id"]:
            changes.append(
                {"path": item_rel(motion_item["id"]), "before": before_motion, "after": None}
            )
        from library.history import history_batching

        if history_batching():
            for rel in changed:
                changes.append(plan_source_file(root, source_id, rel, source["files"][rel]))
        elif changed:
            changes.extend(fold_source_changes(root, source))
        changes.extend(
            plan_absorb_item_refs(
                root,
                motion_item["id"],
                live,
                skip_entry_id=latest_entry_id(root),
            )
        )
        transact(root, extend_current_operation(root, changes))
