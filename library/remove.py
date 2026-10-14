"""Remove from library (catalog only) vs delete-file (trash then catalog)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.atomic import transact
from library.catalog_io import (
    item_rel,
    iter_source_ids,
    load_item,
    load_source,
    source_rel,
)
from library.errors import fail
from library.favorites import FAVORITES_REL, favorites_path, load_favorites, with_id
from library.history import make_history_entry, plan_append
from library.index import rebuild_sqlite
from library.records import clone, ordered_item, ordered_source
from library.trash import trash_file
from library.volumes import location_file, location_matches_stat


def current_original_paths(item: dict[str, Any], root: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for loc in item.get("locations") or []:
        if loc.get("current") is not True:
            continue
        path = location_file(loc, root)
        if path is None or not path.is_file():
            continue
        if not location_matches_stat(loc, path):
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        found.append(path)
    return found


def plan_drop_item(root: Path, item_id: str) -> list[dict[str, Any]]:
    item = load_item(root, item_id)
    changes: list[dict[str, Any]] = [
        {"path": item_rel(item_id), "before": ordered_item(item), "after": None}
    ]
    fav_path = favorites_path(root)
    if fav_path.exists():
        before_fav = load_favorites(root)
        after_fav = with_id(before_fav, item_id, False)
        if before_fav != after_fav:
            changes.append(
                {
                    "path": FAVORITES_REL,
                    "before": before_fav,
                    "after": after_fav,
                }
            )
    for source_id in iter_source_ids(root):
        source = load_source(root, source_id)
        files = dict(source.get("files") or {})
        dropped = {
            rel: entry
            for rel, entry in files.items()
            if isinstance(entry, dict) and entry.get("itemId") == item_id
        }
        if not dropped:
            continue
        after_source = clone(source)
        kept = {
            rel: entry
            for rel, entry in files.items()
            if rel not in dropped
        }
        after_source["files"] = kept
        changes.append(
            {
                "path": source_rel(source_id),
                "before": ordered_source(source),
                "after": ordered_source(after_source),
            }
        )
    return changes


def remove_item(root: Path, item_id: str) -> dict[str, Any]:
    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    changes = plan_drop_item(root, item_id)
    entry = make_history_entry(root, "remove", changes)
    transact(root, plan_append(root, entry) + changes)
    rebuild_sqlite(root, use_barrier=False)
    return {"ok": True, "id": item_id}


def delete_file(root: Path, item_id: str) -> dict[str, Any]:
    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    item = load_item(root, item_id)
    paths = current_original_paths(item, root)
    if not paths:
        raise fail("unavailable")
    changes = plan_drop_item(root, item_id)
    entry = make_history_entry(root, "delete-file", changes)
    transact(root, plan_append(root, entry) + changes)
    rebuild_sqlite(root, use_barrier=False)
    trashed = True
    for path in paths:
        if not trash_file(path):
            trashed = False
    return {"ok": True, "id": item_id, "trashed": trashed}
