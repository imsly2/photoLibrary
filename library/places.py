"""GPS place matching. Local geo pack may name an unnamed coordinate place."""

from __future__ import annotations

from contextlib import nullcontext
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import load_places, new_place_id, place_rel, try_load_place
from library.history import make_history_entry, plan_append
from library.records import make_place, ordered_place

EARTH_RADIUS_M = 6371000.0


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))


def nearest_place(
    places: list[dict[str, Any]],
    latitude: float,
    longitude: float,
    match_meters: float,
) -> dict[str, Any] | None:
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for place in places:
        plat = place.get("latitude")
        plon = place.get("longitude")
        if plat is None or plon is None:
            continue
        dist = haversine_meters(latitude, longitude, float(plat), float(plon))
        if dist <= match_meters:
            candidates.append((dist, str(place["id"]), place))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def apply_local_name(root: Path, place: dict[str, Any]) -> dict[str, Any] | None:
    """Fill place.name from the local pack when it is null. Never overwrite."""
    if place.get("name") is not None:
        return None
    plat = place.get("latitude")
    plon = place.get("longitude")
    if plat is None or plon is None:
        return None
    from library.geo import lookup_name

    name = lookup_name(root, float(plat), float(plon))
    if not name:
        return None
    updated = make_place(
        place_id=str(place["id"]),
        latitude=float(plat),
        longitude=float(plon),
        name=name,
    )
    if updated == ordered_place(place):
        return None
    return updated


def resolve_place(
    root: Path,
    latitude: float,
    longitude: float,
    match_meters: float,
) -> tuple[str, dict[str, Any] | None]:
    matched = nearest_place(load_places(root), latitude, longitude, match_meters)
    if matched is not None:
        return matched["id"], apply_local_name(root, matched)
    from library.geo import lookup_name

    place_id = new_place_id(root)
    place = make_place(
        place_id=place_id,
        latitude=latitude,
        longitude=longitude,
        name=lookup_name(root, latitude, longitude),
    )
    return place_id, place


def named_place_update(root: Path, place_id: str) -> dict[str, Any] | None:
    current = try_load_place(root, place_id)
    if current is None:
        return None
    return apply_local_name(root, current)


def analyze_places(root: Path) -> dict[str, Any]:
    from library.geo import pack_ready

    ready = pack_ready(root)
    named = 0
    skipped = 0
    changes: list[dict[str, Any]] = []
    for place in load_places(root):
        updated = apply_local_name(root, place) if ready else None
        if updated is None:
            skipped += 1
            continue
        changes.append(
            {"path": place_rel(place["id"]), "before": place, "after": updated}
        )
        named += 1
    if changes:
        entry = make_history_entry(root, "analyze-places", changes)
        transact(root, plan_append(root, entry) + changes)
    return {
        "ok": True,
        "named": named,
        "skipped": skipped,
        "packReady": ready,
    }


def analyze_places_step(root: Path) -> bool:
    from library.geo import pack_ready

    if not pack_ready(root):
        return False
    for place in load_places(root):
        from library.activity import note_item

        note_item("analyze", "Places", place)
        updated = apply_local_name(root, place)
        if updated is None:
            continue
        changes = [{"path": place_rel(place["id"]), "before": place, "after": updated}]
        entry = make_history_entry(root, "analyze-places", changes)
        transact(root, plan_append(root, entry) + changes)
        return True
    return False


_gps_absent: set[str] = set()
_gps_done = False


def _match_meters(root: Path) -> float:
    from library.settings import defaults, load_settings_file

    try:
        return float(load_settings_file(root)["placeMatchMeters"])
    except (OSError, KeyError, TypeError, ValueError):
        return float(defaults()["placeMatchMeters"])


def _media_path(root: Path, item: dict[str, Any]) -> Path | None:
    from library.volumes import location_file

    want = "motion" if item.get("kind") == "video" else "still"
    for loc in item.get("locations") or []:
        if loc.get("current") is not True or loc.get("component") != want:
            continue
        path = location_file(loc, root)
        if path is not None and path.is_file():
            return path
    return None


def _label_from_item(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    from library.catalog_io import place_beside_item, try_load_place

    place_id = item.get("placeId")
    place = None
    if type(place_id) is str and place_id:
        place = try_load_place(root, place_id)
        if place is None:
            place = place_beside_item(root, item, place_id)
    if place is not None and place.get("latitude") is not None and place.get("longitude") is not None:
        return {
            "write": False,
            "placeId": place_id if type(place_id) is str else None,
            "name": place.get("name"),
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
        }
    meta = item.get("metadata") or {}
    if meta.get("latitude") is not None and meta.get("longitude") is not None:
        return {
            "write": False,
            "placeId": place_id if type(place_id) is str else None,
            "name": None,
            "latitude": meta.get("latitude"),
            "longitude": meta.get("longitude"),
        }
    return {"write": False, "placeId": None, "name": None, "latitude": None, "longitude": None}


def _gps_from_file(root: Path, item: dict[str, Any]) -> tuple[float, float] | None:
    from library.media import VIDEO_SUFFIXES, file_suffix
    from library.metadata import _apply_tiff_fields, _heif_tiff, _video_from_ffprobe, read_capture
    from library.records import empty_metadata

    path = _media_path(root, item)
    if path is None:
        return None
    suffix = file_suffix(path)
    # A video's location is a short header tag. Reading the whole movie
    # into memory made opening one take as long as playing it.
    if suffix in VIDEO_SUFFIXES:
        try:
            metadata = _video_from_ffprobe(path)["metadata"]
        except OSError:
            return None
    else:
        try:
            data = path.read_bytes()
        except OSError:
            return None
        if suffix in {".heic", ".heif"}:
            tiff = _heif_tiff(data)
            metadata = empty_metadata()
            if tiff is not None:
                _apply_tiff_fields(metadata, tiff)
        else:
            try:
                _captured, _source, metadata = read_capture(path, data)
            except OSError:
                return None
    latitude = metadata.get("latitude")
    longitude = metadata.get("longitude")
    if latitude is None or longitude is None:
        return None
    return float(latitude), float(longitude)


def _place_label(prepared: dict[str, Any]) -> dict[str, Any]:
    return {
        "placeId": prepared.get("placeId"),
        "name": prepared.get("name"),
        "latitude": prepared.get("latitude"),
        "longitude": prepared.get("longitude"),
    }


def prepare_file_place(root: Path, item_id: str) -> dict[str, Any]:
    """Read coordinates for one picture. Does not write the catalog."""
    from library.catalog_io import load_item

    item = load_item(root, item_id)
    label = _label_from_item(root, item)
    if label["latitude"] is not None:
        return label
    if item_id in _gps_absent:
        return label
    found = _gps_from_file(root, item)
    if found is None:
        _gps_absent.add(item_id)
        return label
    latitude, longitude = found
    place_id, new_place = resolve_place(root, latitude, longitude, _match_meters(root))
    name = new_place.get("name") if new_place else None
    if not name:
        existing = try_load_place(root, place_id)
        if existing is not None:
            name = existing.get("name")
    return {
        "write": True,
        "placeId": place_id,
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "place": new_place,
    }


def store_file_place(root: Path, item_id: str, prepared: dict[str, Any]) -> dict[str, Any]:
    """Save a place prepared outside the catalog lock."""
    from library.catalog_io import item_rel, load_item
    from library.item_index import remember_write
    from library.records import clone, empty_metadata, ordered_item

    if not prepared.get("write"):
        return _place_label(prepared)
    item = load_item(root, item_id)
    current = _label_from_item(root, item)
    if current["latitude"] is not None and item.get("placeId"):
        return _place_label(current)
    after = clone(item)
    metadata = dict(after.get("metadata") or empty_metadata())
    metadata["latitude"] = prepared["latitude"]
    metadata["longitude"] = prepared["longitude"]
    after["metadata"] = metadata
    after["placeId"] = prepared["placeId"]
    after = ordered_item(after)
    changes: list[dict[str, Any]] = [{"path": item_rel(item_id), "before": item, "after": after}]
    place = prepared.get("place")
    if isinstance(place, dict) and place.get("id"):
        existing = try_load_place(root, place["id"])
        if existing != place:
            changes.append({"path": place_rel(place["id"]), "before": existing, "after": place})
    transact(root, changes)
    remember_write(root, item_id, after)
    return _place_label(prepared)


def _needs_file_gps(item: dict[str, Any]) -> bool:
    item_id = item.get("id")
    if type(item_id) is not str or item_id in _gps_absent:
        return False
    name = str(item.get("filename") or "")
    if not name.lower().endswith((".heic", ".heif")):
        return False
    if item.get("placeId"):
        return False
    meta = item.get("metadata") or {}
    return meta.get("latitude") is None or meta.get("longitude") is None


def capture_gps_step(root: Path, *, io_context=nullcontext) -> bool:
    """One HEIC whose coordinates were never stored. File read stays outside the lock."""
    global _gps_done
    from library.item_index import iter_items

    if _gps_done:
        return False
    for item in iter_items(root):
        if not _needs_file_gps(item):
            continue
        with io_context():
            prepared = prepare_file_place(root, item["id"])
        if prepared.get("write"):
            store_file_place(root, item["id"], prepared)
        return True
    _gps_done = True
    return False


def unnamed_gps_counts(root: Path) -> tuple[int, int, int]:
    pending = 0
    done = 0
    for place in load_places(root):
        if place.get("latitude") is None or place.get("longitude") is None:
            continue
        if place.get("name"):
            done += 1
        else:
            pending += 1
    return pending, done, 0
