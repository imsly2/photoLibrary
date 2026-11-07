"""People sidebar index and person profile updates."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from library.annotate import clone
from library.atomic import transact
from library.catalog_io import (
    load_people,
    load_person,
    people_dir,
    person_rel,
    try_load_item,
)
from library.errors import fail
from library.history import make_history_entry, plan_append
from library.records import ordered_person

PERSON_OF_INTEREST_MIN = 3

_guard = threading.Lock()
_index_cache: dict[str, tuple[Any, dict[str, Any]]] = {}
_people_cache: dict[str, tuple[Any, list[dict[str, Any]]]] = {}
_people_bump: dict[str, int] = {}


def _root_key(root: Path) -> str:
    from library.item_index import root_key

    return root_key(root)


def people_generation(root: Path) -> tuple[Any, ...]:
    """Token that changes when item faces or person records change."""
    from library import item_store

    key = _root_key(root)
    try:
        st = people_dir(root).stat()
        people_token = (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        people_token = (0, 0)
    return (item_store.write_count(), people_token, _people_bump.get(key, 0))


def _people_sig(root: Path) -> tuple[Any, ...]:
    return people_generation(root)


def invalidate_people(root: Path) -> None:
    """Drop people list and panel caches after a person write/merge/split."""
    key = _root_key(root)
    with _guard:
        _people_bump[key] = _people_bump.get(key, 0) + 1
        _index_cache.pop(key, None)
        _people_cache.pop(key, None)
    try:
        from library.catalog_index import bump

        bump(root)
    except Exception:
        pass
    try:
        from library.people_suggest import invalidate_suggestions

        invalidate_suggestions(root)
    except Exception:
        pass


def cached_load_people(root: Path) -> list[dict[str, Any]]:
    key = _root_key(root)
    sig = _people_sig(root)
    with _guard:
        hit = _people_cache.get(key)
        if hit is not None and hit[0] == sig:
            return hit[1]
    rows = load_people(root)
    with _guard:
        _people_cache[key] = (sig, rows)
    return rows


def _face_box(face: dict[str, Any]) -> list[float] | None:
    box = face.get("box")
    if isinstance(box, list) and len(box) == 4:
        return [float(box[0]), float(box[1]), float(box[2]), float(box[3])]
    return None


def _face_score(face: dict[str, Any]) -> float:
    for key in ("detScore", "matchScore"):
        value = face.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _face_area(face: dict[str, Any]) -> float:
    box = _face_box(face)
    if box is None:
        return 0.0
    return max(0.0, box[2]) * max(0.0, box[3])


def _best_face(faces: list[dict[str, Any]]) -> dict[str, Any] | None:
    boxed = [face for face in faces if _face_box(face) is not None]
    if not boxed:
        return faces[0] if faces else None
    boxed.sort(key=lambda face: (_face_score(face), _face_area(face)), reverse=True)
    return boxed[0]


def _thumbnail_for(
    person: dict[str, Any],
    faces: list[dict[str, Any]],
) -> dict[str, Any] | None:
    chosen = person.get("thumbnailItemId")
    if chosen:
        matches = [face for face in faces if face.get("itemId") == chosen]
        face = _best_face(matches) if matches else None
        if face is not None:
            out: dict[str, Any] = {"itemId": chosen}
            box = _face_box(face)
            if box is not None:
                out["box"] = box
            return out
    face = _best_face(faces)
    if face is None:
        return None
    out = {"itemId": face["itemId"]}
    box = _face_box(face)
    if box is not None:
        out["box"] = box
    return out


def _better_face(left: dict[str, Any] | None, right: dict[str, Any]) -> dict[str, Any]:
    if left is None:
        return right
    return _best_face([left, right]) or right


def people_index(root: Path) -> dict[str, Any]:
    from library.item_index import iter_items

    key = _root_key(root)
    sig = _people_sig(root)
    with _guard:
        hit = _index_cache.get(key)
        if hit is not None and hit[0] == sig:
            return hit[1]

    people = cached_load_people(root)
    preferred = {
        person["id"]: person.get("thumbnailItemId")
        for person in people
        if type(person.get("thumbnailItemId")) is str and person.get("thumbnailItemId")
    }
    best_overall: dict[str, dict[str, Any]] = {}
    best_preferred: dict[str, dict[str, Any]] = {}
    item_ids_by_person: dict[str, set[str]] = {}
    # Keep only the best thumbnail candidate per person (and the preferred
    # thumbnailItemId candidate when set). Do not retain every face.
    for item in iter_items(root):
        item_id = item["id"]
        seen: set[str] = set()
        for face in item.get("faces") or []:
            person_id = face.get("personId")
            if type(person_id) is not str or not person_id:
                continue
            rec: dict[str, Any] = {"itemId": item_id, "box": face.get("box")}
            if "detScore" in face:
                rec["detScore"] = face.get("detScore")
            if "matchScore" in face:
                rec["matchScore"] = face.get("matchScore")
            best_overall[person_id] = _better_face(best_overall.get(person_id), rec)
            if preferred.get(person_id) == item_id:
                best_preferred[person_id] = _better_face(best_preferred.get(person_id), rec)
            if person_id not in seen:
                item_ids_by_person.setdefault(person_id, set()).add(item_id)
                seen.add(person_id)
    rows: list[dict[str, Any]] = []
    for person in people:
        person_id = person["id"]
        count = len(item_ids_by_person.get(person_id) or [])
        named = type(person.get("name")) is str and bool(person.get("name"))
        visible = named or count >= PERSON_OF_INTEREST_MIN
        face = best_preferred.get(person_id) or best_overall.get(person_id)
        thumb = None
        if face is not None:
            thumb = {"itemId": face["itemId"]}
            box = _face_box(face)
            if box is not None:
                thumb["box"] = box
        rows.append(
            {
                "id": person_id,
                "name": person.get("name"),
                "itemCount": count,
                "visible": visible,
                "named": named,
                "thumbnail": thumb,
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
    payload = {
        "personOfInterestMin": PERSON_OF_INTEREST_MIN,
        "people": rows,
    }
    with _guard:
        _index_cache[key] = (sig, payload)
    return payload


def warm(root: Path) -> dict[str, Any]:
    """Build and cache the people panel payload."""
    return people_index(root)


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
    invalidate_people(root)
    return person_row(root, person_id)
