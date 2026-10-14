"""Group keys from sorted items."""

from __future__ import annotations

from typing import Any

LEVELS = frozenset({"years", "months", "days", "all"})
ARRANGE = frozenset({"date", "people", "places", "tags"})
UNKNOWN_PEOPLE = "Unknown"
NO_PLACE = "No place"
UNTAGGED = "Untagged"


def calendar_date(captured_at: str) -> str:
    """Stored calendar date, independent of browser timezone."""
    if not captured_at:
        return ""
    return captured_at[:10]


def group_key(captured_at: str, level: str) -> str:
    date = calendar_date(captured_at)
    if level == "years":
        return date[:4]
    if level == "months":
        return date[:7]
    return date


def groups_from_items(items: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    """Build {key,itemIds}[] in first-occurrence order; contents keep item order."""
    groups: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for item in items:
        key = group_key(item.get("capturedAt") or "", level)
        idx = seen.get(key)
        if idx is None:
            seen[key] = len(groups)
            groups.append({"key": key, "itemIds": [item["id"]]})
        else:
            groups[idx]["itemIds"].append(item["id"])
    return groups


def _entities(item: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    bucket = (item.get("entities") or {}).get(kind) or []
    if not isinstance(bucket, list):
        return []
    return [rec for rec in bucket if isinstance(rec, dict) and rec.get("id")]


def _first_named(records: list[dict[str, Any]], unnamed: str) -> dict[str, Any] | None:
    if not records:
        return None
    ranked = sorted(
        records,
        key=lambda rec: (
            0 if rec.get("name") else 1,
            str(rec.get("name") or "").casefold(),
            rec.get("id") or "",
        ),
    )
    chosen = ranked[0]
    return {
        "id": chosen["id"],
        "key": chosen["name"] if chosen.get("name") else unnamed,
    }


def _place_choice(item: dict[str, Any]) -> dict[str, Any] | None:
    places = _entities(item, "places")
    if not places:
        return None
    place = places[0]
    name = place.get("name")
    if type(name) is str and name:
        return {"id": place["id"], "key": name}
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is not None and lon is not None:
        return {"id": place["id"], "key": f"{float(lat):.2f}, {float(lon):.2f}"}
    return None


def groups_from_entities(items: list[dict[str, Any]], by: str) -> list[dict[str, Any]]:
    """One group per person/place/tag; leftover bucket last. Ids appear once."""
    buckets: dict[str, dict[str, Any]] = {}
    leftover: list[str] = []
    leftover_key = UNKNOWN_PEOPLE if by == "people" else NO_PLACE if by == "places" else UNTAGGED
    leftover_unnamed = "Unnamed"
    for item in items:
        item_id = item["id"]
        chosen: dict[str, Any] | None
        if by == "people":
            chosen = _first_named(_entities(item, "people"), leftover_unnamed)
        elif by == "places":
            chosen = _place_choice(item)
        else:
            chosen = _first_named(_entities(item, "things"), leftover_unnamed)
        if chosen is None:
            leftover.append(item_id)
            continue
        key = chosen["id"]
        if key not in buckets:
            buckets[key] = {"key": chosen["key"], "id": chosen["id"], "itemIds": [item_id]}
        else:
            buckets[key]["itemIds"].append(item_id)
    groups = sorted(
        buckets.values(),
        key=lambda rec: (str(rec["key"]).casefold(), rec.get("id") or ""),
    )
    if leftover:
        groups.append({"key": leftover_key, "id": None, "itemIds": leftover})
    return groups
