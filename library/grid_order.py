"""The order the grid shows pictures in.

Reading a new folder and making thumbnails and previews follow the same
order, so the top of the grid fills first and new tiles land below the ones
already showing.
"""

from __future__ import annotations

from typing import Any, Callable

ItemKey = Callable[[dict[str, Any]], tuple]


def _date_key(item: dict[str, Any]) -> tuple:
    return (item.get("capturedAt") or "", item["id"])


def _name_key(item: dict[str, Any]) -> tuple:
    return (item.get("filename") or "", item.get("capturedAt") or "", item["id"])


def _rating_key(item: dict[str, Any]) -> tuple:
    rating = item.get("rating") if isinstance(item.get("rating"), dict) else {}
    stars = rating.get("stars")
    pick = 1 if rating.get("pick") is True else 0
    suggested = rating.get("suggested")
    return (
        stars if type(stars) is int else 0,
        pick,
        suggested if type(suggested) is int else 0,
        item.get("capturedAt") or "",
        item["id"],
    )


def item_key(sort: str) -> ItemKey:
    """Location groups by place first; within work queues it falls back to date."""
    if sort == "name":
        return _name_key
    if sort == "rating":
        return _rating_key
    return _date_key


def descending(settings: dict[str, Any]) -> bool:
    return settings.get("dir") != "asc"
