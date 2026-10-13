"""GPS place matching. Names stay null until a person or agent sets them."""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

from library.catalog_io import load_places, new_place_id
from library.records import make_place

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


def resolve_place(
    root: Path,
    latitude: float,
    longitude: float,
    match_meters: float,
) -> tuple[str, dict[str, Any] | None]:
    matched = nearest_place(load_places(root), latitude, longitude, match_meters)
    if matched is not None:
        return matched["id"], None
    place_id = new_place_id(root)
    place = make_place(
        place_id=place_id,
        latitude=latitude,
        longitude=longitude,
        name=None,
    )
    return place_id, place
