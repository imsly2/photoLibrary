"""Source reads (stats), rescan, and catalog-only remove."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import (
    item_rel,
    iter_item_ids,
    load_item,
    load_source,
    source_rel,
    try_load_item,
)
from library.copy import origin_dir
from library.errors import fail
from library.favorites import FAVORITES_REL, favorites_path, load_favorites, with_id
from library.history import make_history_entry, plan_append
from library.index import rebuild_sqlite
from library.records import clone, ordered_item, ordered_source


CORE_SLOTS = {
    "photo": ("thumb", "preview"),
    "live": ("thumb", "preview"),
    "video": ("poster", "proxy"),
}


def resolve_source_folder(source: dict[str, Any], root: Path) -> Path | None:
    """Folder to walk again: lastKnown if it is still a directory, else the volume path."""
    origin = source.get("origin") or {}
    last = origin.get("lastKnownPath")
    if type(last) is str and last.strip():
        known = Path(last)
        try:
            if known.is_dir():
                return known
        except OSError:
            pass
    if source.get("mode") == "copy-here":
        return None
    mounted = origin_dir(source)
    if mounted is not None:
        try:
            if mounted.is_dir():
                return mounted
        except OSError:
            return None
    return None


def source_stats(source: dict[str, Any], root: Path) -> dict[str, int]:
    """Honest per-source counts from catalog files + item rendition status."""
    item_ids: set[str] = set()
    for entry in (source.get("files") or {}).values():
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("itemId")
        if type(item_id) is str and item_id:
            item_ids.add(item_id)
    photos = 0
    videos = 0
    live = 0
    done = 0
    queued = 0
    error = 0
    for item_id in item_ids:
        item = try_load_item(root, item_id)
        if item is None:
            continue
        kind = item.get("kind")
        if kind == "video":
            videos += 1
        elif kind == "live":
            live += 1
        else:
            photos += 1
        slots = CORE_SLOTS.get(kind if type(kind) is str else "", CORE_SLOTS["photo"])
        status = ((item.get("renditions") or {}).get("status") or {})
        states = [status.get(slot) for slot in slots]
        if any(state == "error" for state in states):
            error += 1
        elif any(state not in {"ready", "not-applicable"} for state in states):
            queued += 1
        else:
            done += 1
    return {
        "photos": photos,
        "videos": videos,
        "live": live,
        "total": photos + videos + live,
        "renditionsDone": done,
        "renditionsQueued": queued,
        "renditionsError": error,
    }


def plan_remove_source(root: Path, source_id: str) -> list[dict[str, Any]]:
    source = load_source(root, source_id)
    changes: list[dict[str, Any]] = [
        {
            "path": source_rel(source_id),
            "before": ordered_source(source),
            "after": None,
        }
    ]
    for item_id in list(iter_item_ids(root)):
        item = load_item(root, item_id)
        locations = item.get("locations") or []
        if not any(loc.get("sourceId") == source_id for loc in locations):
            continue
        remaining = [clone(loc) for loc in locations if loc.get("sourceId") != source_id]
        if not remaining:
            changes.append(
                {
                    "path": item_rel(item_id),
                    "before": ordered_item(item),
                    "after": None,
                }
            )
            fav_path = favorites_path(root)
            already = next((row for row in changes if row["path"] == FAVORITES_REL), None)
            current_fav = already["after"] if already is not None else (
                load_favorites(root) if fav_path.exists() else None
            )
            if current_fav is not None:
                after_fav = with_id(current_fav, item_id, False)
                if already is not None:
                    already["after"] = after_fav
                elif after_fav != current_fav:
                    changes.append(
                        {
                            "path": FAVORITES_REL,
                            "before": current_fav,
                            "after": after_fav,
                        }
                    )
            continue
        if not any(loc.get("role") == "primary" for loc in remaining):
            remaining[0]["role"] = "primary"
        after = clone(item)
        after["locations"] = remaining
        changes.append(
            {
                "path": item_rel(item_id),
                "before": ordered_item(item),
                "after": ordered_item(after),
            }
        )
    return changes


def remove_source(root: Path, source_id: str) -> dict[str, Any]:
    if type(source_id) is not str or not source_id:
        raise fail("invalid-argument")
    load_source(root, source_id)
    changes = plan_remove_source(root, source_id)
    entry = make_history_entry(root, "remove-source", changes)
    transact(root, plan_append(root, entry) + changes)
    rebuild_sqlite(root, use_barrier=False)
    return {"ok": True, "id": source_id}
