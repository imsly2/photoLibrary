"""Load and save catalog JSON; pending hash publication."""

from __future__ import annotations

import secrets
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
    path = sources_dir(root) / f"{source_id}.json"
    try:
        return read_source(load_json(path))
    except FileNotFoundError as exc:
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc


def try_load_item(root: Path, item_id: str) -> dict[str, Any] | None:
    path = items_dir(root) / f"{item_id}.json"
    if not path.exists():
        return None
    return read_item(load_json(path))


def try_load_source(root: Path, source_id: str) -> dict[str, Any] | None:
    path = sources_dir(root) / f"{source_id}.json"
    if not path.exists():
        return None
    return read_source(load_json(path))


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
    path = places_dir(root) / f"{place_id}.json"
    if not path.exists():
        return None
    return read_place(load_json(path))


def load_places(root: Path) -> list[dict[str, Any]]:
    return [load_place(root, place_id) for place_id in iter_place_ids(root)]


def new_place_id(root: Path) -> str:
    existing = set(iter_place_ids(root))
    for _ in range(32):
        candidate = "place_" + secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise fail("internal-error")


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
    out = ordered_source(source)
    out["available"] = source_available(source, root)
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


def item_read(item: dict[str, Any], root: Path) -> dict[str, Any]:
    from library.volumes import item_available, item_motion_available

    out = ordered_item(item)
    out["available"] = item_available(item, root)
    out["motionAvailable"] = item_motion_available(item, root)
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
    return out


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


def pending_item_ids(root: Path) -> list[str]:
    return [item_id for item_id in iter_item_ids(root) if item_id.startswith("pending-")]


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
        before_source = clone(source)
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
            {
                "path": source_rel(source_id),
                "before": before_source,
                "after": ordered_source(source),
            },
        ]
        transact(root, extend_current_operation(root, changes))
        finished.append(published["id"])
    return finished


def pair_live_items(root: Path, source_id: str) -> None:
    from library.history import extend_current_operation

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
        if still_item["id"] == motion_item["id"] and still_item["kind"] == "live":
            continue
        before_still = try_load_item(root, still_item["id"])
        before_motion = try_load_item(root, motion_item["id"])
        live = clone(still_item)
        live["kind"] = "live"
        live["id"] = still_item["id"]
        for loc in motion_item["locations"]:
            live = merge_location(live, loc)
        live = merge_associations(live, motion_item)
        live["renditions"] = renditions_for(
            "live",
            still_item["renditions"]["sourceId"],
            store=still_item["renditions"].get("store") or "with-server",
        )
        live = ordered_item(live)
        source = load_source(root, source_id)
        before_source = clone(source)
        for rel, entry in list(source["files"].items()):
            if entry["itemId"] == motion_item["id"]:
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
        changes = [
            {"path": item_rel(live["id"]), "before": before_still, "after": live},
        ]
        if motion_item["id"] != live["id"]:
            changes.append(
                {"path": item_rel(motion_item["id"]), "before": before_motion, "after": None}
            )
        changes.append(
            {
                "path": source_rel(source_id),
                "before": before_source,
                "after": ordered_source(source),
            }
        )
        transact(root, extend_current_operation(root, changes))
