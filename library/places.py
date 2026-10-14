"""GPS place matching. Local geo pack may name an unnamed coordinate place."""

from __future__ import annotations

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
