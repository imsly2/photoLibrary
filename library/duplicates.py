"""Read-only duplicate groups from existing catalog signals.

Same-hash files are already one item with several locations (F5). Same
filename across different items is the other signal. This module never
deletes files or catalog records.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def location_path(loc: dict[str, Any] | None) -> str:
    if not isinstance(loc, dict):
        return ""
    for key in ("lastKnownPath", "libraryRelativePath", "pathFromVolumeRoot"):
        value = loc.get(key)
        if type(value) is str and value.strip():
            return value
    return ""


def location_folder(path: str) -> str:
    if not path:
        return ""
    return str(Path(path).parent)


def wanted_component(item: dict[str, Any]) -> str:
    return "motion" if item.get("kind") == "video" else "still"


def current_component_locations(item: dict[str, Any]) -> list[dict[str, Any]]:
    want = wanted_component(item)
    current: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for loc in item.get("locations") or []:
        if not isinstance(loc, dict) or loc.get("current") is not True:
            continue
        fallback.append(loc)
        if loc.get("component") == want:
            current.append(loc)
    return current or fallback


def side_from(item: dict[str, Any], loc: dict[str, Any] | None, index: int) -> dict[str, Any]:
    meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    loc = loc if isinstance(loc, dict) else {}
    path = location_path(loc)
    sha = loc.get("sha256")
    item_id = item.get("id")
    if not sha and type(item_id) is str and not item_id.startswith("pending-"):
        sha = item_id
    return {
        "itemId": item_id,
        "filename": item.get("filename"),
        "kind": item.get("kind"),
        "capturedAt": item.get("capturedAt"),
        "width": meta.get("width"),
        "height": meta.get("height"),
        "sizeBytes": loc.get("sizeBytes"),
        "path": path,
        "folder": location_folder(path),
        "sha256": sha,
        "role": loc.get("role"),
        "available": item.get("available"),
        "locationIndex": index,
    }


def _unique_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in rows:
        item_id = item.get("id")
        if type(item_id) is not str or item_id in seen:
            continue
        seen.add(item_id)
        out.append(item)
    return out


def list_duplicate_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group visible item reads. Read-only; never mutates the catalog."""
    groups: list[dict[str, Any]] = []
    by_hash: dict[str, list[tuple[dict[str, Any], dict[str, Any], int]]] = {}
    for item in items:
        for index, loc in enumerate(current_component_locations(item)):
            sha = loc.get("sha256")
            if type(sha) is not str or not sha:
                continue
            by_hash.setdefault(sha, []).append((item, loc, index))
    for sha, members in sorted(by_hash.items()):
        if len(members) < 2:
            continue
        item_ids: list[str] = []
        sides: list[dict[str, Any]] = []
        for item, loc, index in members:
            item_id = item.get("id")
            if type(item_id) is str and item_id not in item_ids:
                item_ids.append(item_id)
            sides.append(side_from(item, loc, index))
        groups.append(
            {
                "key": "hash:" + sha,
                "reason": "hash",
                "itemIds": item_ids,
                "sides": sides,
            }
        )

    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        name = item.get("filename")
        if type(name) is not str or not name.strip():
            continue
        by_name.setdefault(name.strip().lower(), []).append(item)
    for name, rows in sorted(by_name.items()):
        uniq = _unique_items(rows)
        if len(uniq) < 2:
            continue
        sides = []
        item_ids = []
        for item in uniq:
            locs = current_component_locations(item)
            loc = locs[0] if locs else {}
            sides.append(side_from(item, loc, 0))
            item_ids.append(item["id"])
        groups.append(
            {
                "key": "name:" + name,
                "reason": "filename",
                "itemIds": item_ids,
                "sides": sides,
            }
        )
    return groups
