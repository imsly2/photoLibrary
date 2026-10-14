"""Group keys from sorted items."""

from __future__ import annotations

from typing import Any

LEVELS = frozenset({"years", "months", "days", "all"})


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
