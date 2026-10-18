"""User tags are Things: list, create, apply, remove."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.annotate import (
    _record_change,
    _resolve_thing,
    clone,
    collapse_things,
    display_name,
    normalize_name,
)
from library.atomic import transact
from library.catalog_io import (
    item_read,
    item_rel,
    iter_item_ids,
    load_item,
    load_things,
    thing_rel,
    try_load_thing,
)
from library.errors import fail
from library.history import make_history_entry, plan_append
from library.records import ordered_item, ordered_thing


def _require_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    return value


def _thing_ids_on_item(item: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for ref in item.get("things") or []:
        thing_id = ref.get("thingId")
        if type(thing_id) is str and thing_id:
            out.add(thing_id)
    return out


def tags_index(root: Path) -> dict[str, Any]:
    from library.item_index import iter_items

    counts: dict[str, set[str]] = {}
    # Called on every catalog refresh: use the in-memory records, not the disk.
    for item in iter_items(root):
        for thing_id in _thing_ids_on_item(item):
            counts.setdefault(thing_id, set()).add(item["id"])
    rows: list[dict[str, Any]] = []
    for thing in load_things(root):
        rows.append(tag_row(thing, len(counts.get(thing["id"]) or [])))
    rows.sort(key=lambda rec: ((rec.get("name") or "").casefold(), rec["id"]))
    return {"tags": rows}


def tag_row(thing: dict[str, Any], item_count: int) -> dict[str, Any]:
    return {
        "id": thing["id"],
        "name": thing.get("name"),
        "aliases": list(thing.get("aliases") or []),
        "itemCount": item_count,
    }


def _count_thing(root: Path, thing_id: str) -> int:
    count = 0
    for item_id in iter_item_ids(root):
        if thing_id in _thing_ids_on_item(load_item(root, item_id)):
            count += 1
    return count


def _read_name(value: Any) -> str:
    if type(value) is not str:
        raise fail("invalid-argument")
    name = display_name(value)
    if name == "":
        raise fail("invalid-argument")
    return name


def read_create_payload(value: Any) -> str:
    data = _require_dict(value)
    extra = set(data.keys()) - {"name"}
    if extra or "name" not in data:
        raise fail("invalid-argument")
    return _read_name(data["name"])


def _token_to_entry(token: Any) -> dict[str, Any]:
    if type(token) is str:
        text = token.strip()
        if text == "":
            raise fail("invalid-argument")
        if text.startswith("thing_"):
            return {"id": text}
        return {"name": display_name(text)}
    data = _require_dict(token)
    extra = set(data.keys()) - {"id", "name"}
    if extra:
        raise fail("invalid-argument")
    if "id" in data:
        if type(data["id"]) is not str or data["id"] == "":
            raise fail("invalid-argument")
        return {"id": data["id"]}
    if "name" in data:
        return {"name": _read_name(data["name"])}
    raise fail("invalid-argument")


def read_apply_payload(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"itemIds", "add", "remove"}
    if extra:
        raise fail("invalid-argument")
    raw_ids = data.get("itemIds")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise fail("invalid-argument")
    item_ids: list[str] = []
    seen: set[str] = set()
    for item_id in raw_ids:
        if type(item_id) is not str or item_id == "":
            raise fail("invalid-argument")
        if item_id in seen:
            continue
        seen.add(item_id)
        item_ids.append(item_id)
    add = data.get("add") or []
    remove = data.get("remove") or []
    if not isinstance(add, list) or not isinstance(remove, list):
        raise fail("invalid-argument")
    if add == [] and remove == []:
        raise fail("invalid-argument")
    return {
        "itemIds": item_ids,
        "add": [_token_to_entry(token) for token in add],
        "remove": [_token_to_entry(token) for token in remove],
    }


def _resolve_existing(root: Path, entry: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    if "id" in entry:
        thing_id = entry["id"]
        for change in changes:
            if change["path"] == thing_rel(thing_id) and change["after"] is not None:
                return thing_id
        if try_load_thing(root, thing_id) is None:
            raise fail("not-found")
        return thing_id
    name = entry.get("name")
    if type(name) is not str or name == "":
        raise fail("invalid-argument")
    needle = normalize_name(name)
    things = load_things(root)
    for change in changes:
        path = change["path"]
        if path.startswith("catalog/things/") and change["after"] is not None:
            things = [rec for rec in things if rec["id"] != change["after"]["id"]]
            things.append(change["after"])
    matches: list[dict[str, Any]] = []
    for rec in things:
        names = [rec.get("name") or ""]
        names.extend(rec.get("aliases") or [])
        if any(normalize_name(item) == needle for item in names if item):
            matches.append(rec)
    if not matches:
        raise fail("not-found")
    matches.sort(key=lambda rec: rec["id"])
    return matches[0]["id"]


def create_tag(root: Path, payload: Any) -> dict[str, Any]:
    name = _read_name(payload) if type(payload) is str else read_create_payload(payload)
    changes: list[dict[str, Any]] = []
    thing_id = _resolve_thing(root, {"name": name}, changes)
    if changes:
        entry = make_history_entry(root, "tags", changes)
        transact(root, plan_append(root, entry) + changes)
    thing = try_load_thing(root, thing_id)
    if thing is None:
        raise fail("internal-error")
    return tag_row(thing, _count_thing(root, thing_id))


def apply_tags(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = read_apply_payload(payload)
    changes: list[dict[str, Any]] = []
    add_ids: list[str] = []
    for entry in parsed["add"]:
        add_ids.append(_resolve_thing(root, entry, changes))
    remove_ids = {_resolve_existing(root, entry, changes) for entry in parsed["remove"]}
    updated: list[dict[str, Any]] = []
    for item_id in parsed["itemIds"]:
        item = load_item(root, item_id)
        before = clone(item)
        things = list(item.get("things") or [])
        if remove_ids:
            things = [ref for ref in things if ref.get("thingId") not in remove_ids]
        for thing_id in add_ids:
            things.append({"thingId": thing_id})
        item["things"] = collapse_things(things)
        after = ordered_item(item)
        if after != before:
            _record_change(changes, item_rel(item_id), before, after)
        updated.append(item_read(after, root))
    if not changes:
        return {"ok": True, "items": updated}
    entry = make_history_entry(root, "tags", changes)
    transact(root, plan_append(root, entry) + changes)
    return {
        "ok": True,
        "items": [item_read(load_item(root, item_id), root) for item_id in parsed["itemIds"]],
    }
