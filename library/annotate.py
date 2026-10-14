"""Annotate people/places/things and merge people."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import (
    item_read,
    item_rel,
    iter_item_ids,
    load_item,
    load_people,
    load_person,
    load_places,
    load_things,
    new_person_id,
    new_place_id,
    new_thing_id,
    person_rel,
    place_rel,
    thing_rel,
    try_load_person,
    try_load_place,
    try_load_thing,
)
from library.errors import fail
from library.history import (
    load_entry,
    load_state,
    make_history_entry,
    plan_append,
)
from library.records import (
    clone,
    ordered_item,
    ordered_person,
    ordered_place,
    ordered_thing,
    read_item,
)


def normalize_name(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def display_name(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip())


def _require_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    return value


def read_box_arg(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        raise fail("invalid-argument")
    nums: list[float] = []
    for item in value:
        if type(item) is bool or not isinstance(item, (int, float)):
            raise fail("invalid-argument")
        nums.append(float(item))
    x, y, width, height = nums
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise fail("invalid-argument")
    if x + width > 1 or y + height > 1:
        raise fail("invalid-argument")
    return nums


def _optional_box(entry: dict[str, Any]) -> list[float] | None:
    if "box" not in entry:
        return None
    return read_box_arg(entry["box"])


def _optional_text(value: Any, *, allow_null: bool) -> str | None:
    if value is None:
        if allow_null:
            return None
        raise fail("invalid-argument")
    if type(value) is not str:
        raise fail("invalid-argument")
    text = display_name(value)
    if text == "":
        raise fail("invalid-argument")
    return text


def read_annotate_payload(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"people", "places", "things"}
    if extra:
        raise fail("invalid-argument")
    people = data.get("people")
    places = data.get("places")
    things = data.get("things")
    if people is None and places is None and things is None:
        raise fail("invalid-argument")
    if people is None:
        people = []
    if places is None:
        places = []
    if things is None:
        things = []
    if not isinstance(people, list) or not isinstance(places, list) or not isinstance(things, list):
        raise fail("invalid-argument")
    if len(places) > 1:
        raise fail("invalid-argument")
    if people == [] and places == [] and things == []:
        raise fail("invalid-argument")
    return {
        "people": [_read_person_entry(entry) for entry in people],
        "places": [_read_place_entry(entry) for entry in places],
        "things": [_read_thing_entry(entry) for entry in things],
    }


def _read_id(value: Any) -> str:
    if type(value) is not str or value == "":
        raise fail("invalid-argument")
    return value


def _read_person_entry(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"id", "name", "box"}
    if extra:
        raise fail("invalid-argument")
    if "id" not in data and "name" not in data:
        raise fail("invalid-argument")
    out: dict[str, Any] = {}
    if "id" in data:
        out["id"] = _read_id(data["id"])
    if "name" in data:
        out["name"] = _optional_text(data["name"], allow_null=True)
    box = _optional_box(data)
    if box is not None:
        out["box"] = box
    return out


def _read_place_entry(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"id", "name"}
    if extra:
        raise fail("invalid-argument")
    if "id" not in data and "name" not in data:
        raise fail("invalid-argument")
    out: dict[str, Any] = {}
    if "id" in data:
        out["id"] = _read_id(data["id"])
    if "name" in data:
        out["name"] = _optional_text(data["name"], allow_null=True)
    return out


def _read_thing_entry(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"id", "name", "aliases", "box"}
    if extra:
        raise fail("invalid-argument")
    if "id" not in data and "name" not in data:
        raise fail("invalid-argument")
    out: dict[str, Any] = {}
    if "id" in data:
        out["id"] = _read_id(data["id"])
    if "name" in data:
        out["name"] = _optional_text(data["name"], allow_null=False)
    if "aliases" in data:
        aliases = data["aliases"]
        if not isinstance(aliases, list):
            raise fail("invalid-argument")
        out["aliases"] = []
        for alias in aliases:
            text = _optional_text(alias, allow_null=False)
            if text is None:
                raise fail("invalid-argument")
            out["aliases"].append(text)
    box = _optional_box(data)
    if box is not None:
        out["box"] = box
    return out


def read_merge_payload(value: Any) -> dict[str, str]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"keepId", "dropId"}
    if extra:
        raise fail("invalid-argument")
    keep = data.get("keepId")
    drop = data.get("dropId")
    if type(keep) is not str or keep == "" or type(drop) is not str or drop == "":
        raise fail("invalid-argument")
    if keep == drop:
        raise fail("invalid-argument")
    return {"keepId": keep, "dropId": drop}


def _face_key(face: dict[str, Any]) -> tuple[str, tuple[float, ...] | None]:
    box = face.get("box")
    return (face["personId"], tuple(box) if box is not None else None)


def _thing_key(ref: dict[str, Any]) -> tuple[str, tuple[float, ...] | None]:
    box = ref.get("box")
    return (ref["thingId"], tuple(box) if box is not None else None)


def collapse_faces(faces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[float, ...] | None]] = set()
    out: list[dict[str, Any]] = []
    for face in faces:
        key = _face_key(face)
        if key in seen:
            continue
        seen.add(key)
        out.append(face)
    return out


def collapse_things(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[float, ...] | None]] = set()
    out: list[dict[str, Any]] = []
    for ref in refs:
        key = _thing_key(ref)
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


def _smallest_named(records: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    needle = normalize_name(name)
    matches = [rec for rec in records if rec.get("name") and normalize_name(rec["name"]) == needle]
    if not matches:
        return None
    matches.sort(key=lambda rec: rec["id"])
    return matches[0]


def _smallest_thing(records: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    needle = normalize_name(name)
    matches: list[dict[str, Any]] = []
    for rec in records:
        names = [rec.get("name") or ""]
        names.extend(rec.get("aliases") or [])
        if any(normalize_name(item) == needle for item in names if item):
            matches.append(rec)
    if not matches:
        return None
    matches.sort(key=lambda rec: rec["id"])
    return matches[0]


def _append_aliases(thing: dict[str, Any], aliases: list[str]) -> dict[str, Any]:
    existing = [normalize_name(thing["name"])]
    existing.extend(normalize_name(alias) for alias in thing.get("aliases") or [])
    out = list(thing.get("aliases") or [])
    for alias in aliases:
        folded = normalize_name(alias)
        if folded in existing:
            continue
        existing.append(folded)
        out.append(alias)
    thing = clone(thing)
    thing["aliases"] = out
    return ordered_thing(thing)


def _record_change(
    changes: list[dict[str, Any]],
    path: str,
    before: Any,
    after: Any,
) -> None:
    for change in changes:
        if change["path"] == path:
            change["after"] = after
            return
    changes.append({"path": path, "before": before, "after": after})


def _resolve_person(
    root: Path,
    entry: dict[str, Any],
    changes: list[dict[str, Any]],
) -> str:
    if "id" in entry:
        person_id = entry["id"]
        current = None
        for change in changes:
            if change["path"] == person_rel(person_id) and change["after"] is not None:
                current = change["after"]
        if current is None:
            current = try_load_person(root, person_id)
        if current is None:
            raise fail("not-found")
        if "name" in entry:
            updated = ordered_person({**current, "name": entry["name"]})
            if updated != current:
                _record_change(changes, person_rel(person_id), current, updated)
        return person_id
    name = entry.get("name")
    if name is None:
        person_id = new_person_id(root)
        while any(change["path"] == person_rel(person_id) for change in changes):
            person_id = new_person_id(root)
        created = ordered_person({"schemaVersion": 1, "id": person_id, "name": None})
        _record_change(changes, person_rel(person_id), None, created)
        return person_id
    people = load_people(root)
    for change in changes:
        path = change["path"]
        if path.startswith("catalog/people/") and change["after"] is not None:
            people = [rec for rec in people if rec["id"] != change["after"]["id"]]
            people.append(change["after"])
    matched = _smallest_named(people, name)
    if matched is not None:
        return matched["id"]
    person_id = new_person_id(root)
    while any(change["path"] == person_rel(person_id) for change in changes):
        person_id = new_person_id(root)
    created = ordered_person({"schemaVersion": 1, "id": person_id, "name": name})
    _record_change(changes, person_rel(person_id), None, created)
    return person_id


def _resolve_thing(
    root: Path,
    entry: dict[str, Any],
    changes: list[dict[str, Any]],
) -> str:
    aliases = entry.get("aliases") or []
    if "id" in entry:
        thing_id = entry["id"]
        current = None
        for change in changes:
            if change["path"] == thing_rel(thing_id) and change["after"] is not None:
                current = change["after"]
        if current is None:
            current = try_load_thing(root, thing_id)
        if current is None:
            raise fail("not-found")
        updated = clone(current)
        if "name" in entry:
            updated["name"] = entry["name"]
        if aliases:
            updated = _append_aliases(updated, aliases)
        else:
            updated = ordered_thing(updated)
        if updated != current:
            _record_change(changes, thing_rel(thing_id), current, updated)
        return thing_id
    name = entry["name"]
    things = load_things(root)
    for change in changes:
        path = change["path"]
        if path.startswith("catalog/things/") and change["after"] is not None:
            things = [rec for rec in things if rec["id"] != change["after"]["id"]]
            things.append(change["after"])
    matched = _smallest_thing(things, name)
    if matched is not None:
        updated = _append_aliases(matched, aliases) if aliases else matched
        if updated != matched:
            _record_change(changes, thing_rel(matched["id"]), matched, updated)
        return matched["id"]
    thing_id = new_thing_id(root)
    while any(change["path"] == thing_rel(thing_id) for change in changes):
        thing_id = new_thing_id(root)
    created = ordered_thing(
        {"schemaVersion": 1, "id": thing_id, "name": name, "aliases": aliases}
    )
    _record_change(changes, thing_rel(thing_id), None, created)
    return thing_id


def _resolve_place(
    root: Path,
    entry: dict[str, Any],
    item: dict[str, Any],
    changes: list[dict[str, Any]],
) -> str:
    if "id" in entry:
        place_id = entry["id"]
        current = try_load_place(root, place_id)
        if current is None:
            raise fail("not-found")
        if "name" in entry:
            updated = ordered_place(
                {
                    "schemaVersion": 1,
                    "id": place_id,
                    "name": entry["name"],
                    "latitude": current["latitude"],
                    "longitude": current["longitude"],
                }
            )
            if updated != current:
                _record_change(changes, place_rel(place_id), current, updated)
        return place_id
    name = entry.get("name")
    current_id = item.get("placeId")
    if type(current_id) is str and current_id:
        current = try_load_place(root, current_id)
        if current is not None:
            updated = ordered_place(
                {
                    "schemaVersion": 1,
                    "id": current_id,
                    "name": name,
                    "latitude": current["latitude"],
                    "longitude": current["longitude"],
                }
            )
            if updated != current:
                _record_change(changes, place_rel(current_id), current, updated)
            return current_id
    if type(name) is str:
        places = load_places(root)
        matched = _smallest_named(places, name)
        if matched is not None:
            return matched["id"]
    place_id = new_place_id(root)
    created = ordered_place(
        {
            "schemaVersion": 1,
            "id": place_id,
            "name": name,
            "latitude": None,
            "longitude": None,
        }
    )
    _record_change(changes, place_rel(place_id), None, created)
    return place_id


def apply_annotate(root: Path, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    parsed = read_annotate_payload(payload)
    item = load_item(root, item_id)
    before_item = clone(item)
    changes: list[dict[str, Any]] = []
    faces = list(item.get("faces") or [])
    things = list(item.get("things") or [])
    for entry in parsed["people"]:
        person_id = _resolve_person(root, entry, changes)
        face: dict[str, Any] = {"personId": person_id}
        if "box" in entry:
            face["box"] = entry["box"]
        faces.append(face)
    for entry in parsed["things"]:
        thing_id = _resolve_thing(root, entry, changes)
        ref: dict[str, Any] = {"thingId": thing_id}
        if "box" in entry:
            ref["box"] = entry["box"]
        things.append(ref)
    item["faces"] = collapse_faces(faces)
    item["things"] = collapse_things(things)
    if parsed["places"]:
        item["placeId"] = _resolve_place(root, parsed["places"][0], item, changes)
    after_item = ordered_item(item)
    if after_item != before_item:
        changes.append(
            {"path": item_rel(item_id), "before": before_item, "after": after_item}
        )
    if not changes:
        return item_read(after_item, root)
    entry = make_history_entry(root, "annotate", changes)
    transact(root, plan_append(root, entry) + changes)
    return item_read(load_item(root, item_id), root)


def apply_people_merge(root: Path, keep_id: str, drop_id: str) -> dict[str, Any]:
    if type(keep_id) is not str or type(drop_id) is not str or not keep_id or not drop_id:
        raise fail("invalid-argument")
    if keep_id == drop_id:
        raise fail("invalid-argument")
    keep = load_person(root, keep_id)
    drop = load_person(root, drop_id)
    changes: list[dict[str, Any]] = []
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        before = clone(item)
        rewritten: list[dict[str, Any]] = []
        for face in item.get("faces") or []:
            face = clone(face)
            if face.get("personId") == drop_id:
                face["personId"] = keep_id
            rewritten.append(face)
        item["faces"] = collapse_faces(rewritten)
        after = ordered_item(item)
        if after != before:
            changes.append({"path": item_rel(item_id), "before": before, "after": after})
    changes.append({"path": person_rel(drop_id), "before": drop, "after": None})
    try:
        from library.faces import plan_merge_index

        index_change = plan_merge_index(root, keep_id, drop_id)
        if index_change is not None:
            changes.append(index_change)
    except ImportError:
        pass
    entry = make_history_entry(root, "people-merge", changes)
    transact(root, plan_append(root, entry) + changes)
    return ordered_person(keep)


def rebase_item_snapshot(snapshot: Any, published: dict[str, Any]) -> Any:
    if snapshot is None:
        return None
    if not isinstance(snapshot, dict):
        return snapshot
    try:
        item = read_item(snapshot)
    except Exception:
        return snapshot
    out = clone(published)
    out["faces"] = clone(item.get("faces") or [])
    out["things"] = clone(item.get("things") or [])
    out["placeId"] = item.get("placeId")
    return ordered_item(out)


def plan_absorb_item_refs(
    root: Path,
    old_id: str,
    published: dict[str, Any],
    *,
    skip_entry_id: str | None = None,
) -> list[dict[str, Any]]:
    old_path = item_rel(old_id)
    new_path = item_rel(published["id"])
    if old_path == new_path:
        return []
    state = load_state(root)
    changes: list[dict[str, Any]] = []
    for entry_id in state["entries"][: state["cursor"]]:
        if skip_entry_id is not None and entry_id == skip_entry_id:
            continue
        entry = load_entry(root, entry_id)
        rewritten = False
        new_entry_changes: list[dict[str, Any]] = []
        for change in entry.get("changes") or []:
            if change.get("path") == old_path:
                new_entry_changes.append(
                    {
                        "path": new_path,
                        "before": rebase_item_snapshot(change.get("before"), published),
                        "after": rebase_item_snapshot(change.get("after"), published),
                    }
                )
                rewritten = True
            else:
                new_entry_changes.append(change)
        if not rewritten:
            continue
        after_entry = clone(entry)
        after_entry["changes"] = new_entry_changes
        changes.append(
            {
                "path": f"undo/entries/{entry_id}.json",
                "before": entry,
                "after": after_entry,
            }
        )
    return changes


def plan_rebase_pending(
    root: Path,
    pending_id: str,
    published: dict[str, Any],
) -> list[dict[str, Any]]:
    pending_path = item_rel(pending_id)
    hash_path = item_rel(published["id"])
    if pending_path == hash_path:
        return []
    state = load_state(root)
    changes: list[dict[str, Any]] = []
    for entry_id in state["entries"][: state["cursor"]]:
        entry = load_entry(root, entry_id)
        if entry.get("operation") != "annotate":
            continue
        rewritten = False
        new_entry_changes: list[dict[str, Any]] = []
        for change in entry.get("changes") or []:
            if change.get("path") == pending_path:
                new_entry_changes.append(
                    {
                        "path": hash_path,
                        "before": rebase_item_snapshot(change.get("before"), published),
                        "after": rebase_item_snapshot(change.get("after"), published),
                    }
                )
                rewritten = True
            else:
                new_entry_changes.append(change)
        if not rewritten:
            continue
        after_entry = clone(entry)
        after_entry["changes"] = new_entry_changes
        changes.append(
            {
                "path": f"undo/entries/{entry_id}.json",
                "before": entry,
                "after": after_entry,
            }
        )
    return changes


def cli_payload_from_flags(
    *,
    json_path: str | None,
    person: str | None,
    thing: str | None,
    place: str | None,
) -> dict[str, Any]:
    if json_path:
        path = Path(json_path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise fail("invalid-argument") from exc
        import json

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise fail("invalid-argument") from exc
        if not isinstance(payload, dict):
            raise fail("invalid-argument")
        return payload
    payload: dict[str, Any] = {}
    if person is not None:
        payload["people"] = [{"name": person}]
    if thing is not None:
        payload["things"] = [{"name": thing}]
    if place is not None:
        payload["places"] = [{"name": place}]
    if not payload:
        raise fail("invalid-argument")
    return payload
