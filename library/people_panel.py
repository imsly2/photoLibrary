"""People sidebar index and person profile updates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.annotate import clone
from library.atomic import transact
from library.catalog_io import (
    iter_item_ids,
    load_item,
    load_people,
    load_person,
    person_rel,
    try_load_item,
)
from library.errors import fail
from library.history import make_history_entry, plan_append
from library.records import ordered_person

PERSON_OF_INTEREST_MIN = 3


def _face_box(face: dict[str, Any]) -> list[float] | None:
    box = face.get("box")
    if isinstance(box, list) and len(box) == 4:
        return [float(box[0]), float(box[1]), float(box[2]), float(box[3])]
    return None


def _thumbnail_for(
    person: dict[str, Any],
    faces: list[dict[str, Any]],
) -> dict[str, Any] | None:
    chosen = person.get("thumbnailItemId")
    if chosen:
        for face in faces:
            if face.get("itemId") == chosen:
                out: dict[str, Any] = {"itemId": chosen}
                box = _face_box(face)
                if box is not None:
                    out["box"] = box
                return out
    for face in faces:
        box = _face_box(face)
        if box is not None:
            return {"itemId": face["itemId"], "box": box}
    if faces:
        return {"itemId": faces[0]["itemId"]}
    return None


def people_index(root: Path) -> dict[str, Any]:
    faces_by_person: dict[str, list[dict[str, Any]]] = {}
    item_ids_by_person: dict[str, set[str]] = {}
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        seen: set[str] = set()
        for face in item.get("faces") or []:
            person_id = face.get("personId")
            if type(person_id) is not str or not person_id:
                continue
            faces_by_person.setdefault(person_id, []).append(
                {"itemId": item_id, "box": face.get("box")}
            )
            if person_id not in seen:
                item_ids_by_person.setdefault(person_id, set()).add(item_id)
                seen.add(person_id)
    rows: list[dict[str, Any]] = []
    for person in load_people(root):
        person_id = person["id"]
        count = len(item_ids_by_person.get(person_id) or [])
        named = type(person.get("name")) is str and bool(person.get("name"))
        visible = named or count >= PERSON_OF_INTEREST_MIN
        rows.append(
            {
                "id": person_id,
                "name": person.get("name"),
                "itemCount": count,
                "visible": visible,
                "named": named,
                "thumbnail": _thumbnail_for(person, faces_by_person.get(person_id) or []),
                "thumbnailItemId": person.get("thumbnailItemId"),
            }
        )
    rows.sort(
        key=lambda rec: (
            0 if rec["named"] else 1,
            (rec["name"] or "").casefold(),
            -int(rec["itemCount"]),
            rec["id"],
        )
    )
    return {
        "personOfInterestMin": PERSON_OF_INTEREST_MIN,
        "people": rows,
    }


def person_row(root: Path, person_id: str) -> dict[str, Any]:
    payload = people_index(root)
    for rec in payload["people"]:
        if rec["id"] == person_id:
            return rec
    raise fail("not-found")


def read_person_update(body: Any) -> dict[str, Any]:
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise fail("invalid-argument")
    extra = set(body) - {"name", "thumbnailItemId"}
    if extra:
        raise fail("invalid-argument")
    if "name" not in body and "thumbnailItemId" not in body:
        raise fail("invalid-argument")
    out: dict[str, Any] = {}
    if "name" in body:
        name = body["name"]
        if name is not None and (type(name) is not str or name.strip() == ""):
            raise fail("invalid-argument")
        out["name"] = name.strip() if type(name) is str else None
    if "thumbnailItemId" in body:
        thumb = body["thumbnailItemId"]
        if thumb is not None and (type(thumb) is not str or thumb == ""):
            raise fail("invalid-argument")
        out["thumbnailItemId"] = thumb
    return out


def apply_person_update(root: Path, person_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if type(person_id) is not str or not person_id:
        raise fail("invalid-argument")
    parsed = read_person_update(payload)
    current = load_person(root, person_id)
    after = clone(current)
    if "name" in parsed:
        after["name"] = parsed["name"]
    if "thumbnailItemId" in parsed:
        thumb = parsed["thumbnailItemId"]
        if thumb is None:
            after.pop("thumbnailItemId", None)
        else:
            item = try_load_item(root, thumb)
            if item is None:
                raise fail("not-found")
            faces = item.get("faces") or []
            if not any(face.get("personId") == person_id for face in faces):
                raise fail("invalid-argument")
            after["thumbnailItemId"] = thumb
    before = ordered_person(current)
    next_rec = ordered_person(after)
    if next_rec == before:
        return person_row(root, person_id)
    changes = [{"path": person_rel(person_id), "before": before, "after": next_rec}]
    entry = make_history_entry(root, "person-update", changes)
    transact(root, plan_append(root, entry) + changes)
    return person_row(root, person_id)
