"""Hearted item ids. One catalog file; computed on item reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.atomic import load_json, transact
from library.catalog_io import item_read, load_item, try_load_item
from library.errors import fail
from library.history import make_history_entry, plan_append

FAVORITES_REL = "catalog/favorites.json"
SCHEMA_VERSION = 1


def favorites_path(root: Path) -> Path:
    return root / "catalog" / "favorites.json"


def default_favorites() -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "itemIds": []}


def ordered_favorites(data: dict[str, Any]) -> dict[str, Any]:
    ids = data.get("itemIds")
    if data.get("schemaVersion") != SCHEMA_VERSION or not isinstance(ids, list):
        raise fail("invalid-catalog")
    seen: set[str] = set()
    clean: list[str] = []
    for item_id in ids:
        if type(item_id) is not str or not item_id or item_id in seen:
            raise fail("invalid-catalog")
        seen.add(item_id)
        clean.append(item_id)
    clean.sort()
    return {"schemaVersion": SCHEMA_VERSION, "itemIds": clean}


def load_favorites(root: Path) -> dict[str, Any]:
    path = favorites_path(root)
    if not path.exists():
        return default_favorites()
    try:
        data = load_json(path)
    except OSError as exc:
        raise fail("io-error") from exc
    if not isinstance(data, dict):
        raise fail("invalid-catalog")
    return ordered_favorites(data)


def favorite_ids(root: Path) -> set[str]:
    return set(load_favorites(root)["itemIds"])


def with_id(current: dict[str, Any], item_id: str, on: bool) -> dict[str, Any]:
    ids = set(current["itemIds"])
    if on:
        ids.add(item_id)
    else:
        ids.discard(item_id)
    return ordered_favorites({"schemaVersion": SCHEMA_VERSION, "itemIds": sorted(ids)})


def plan_remap_favorite(root: Path, old_id: str, new_id: str) -> list[dict[str, Any]]:
    if old_id == new_id:
        return []
    before = load_favorites(root)
    if old_id not in before["itemIds"]:
        return []
    ids = {item_id for item_id in before["itemIds"] if item_id != old_id}
    ids.add(new_id)
    after = ordered_favorites({"schemaVersion": SCHEMA_VERSION, "itemIds": sorted(ids)})
    if before == after:
        return []
    return [{"path": FAVORITES_REL, "before": before, "after": after}]


def set_item_favorite(root: Path, item_id: str, on: bool) -> dict[str, Any]:
    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    if type(on) is not bool:
        raise fail("invalid-argument")
    item = load_item(root, item_id)
    before = load_favorites(root)
    after = with_id(before, item_id, on)
    if before == after:
        return item_read(item, root, set(after["itemIds"]))
    file_change = {
        "path": FAVORITES_REL,
        "before": before if favorites_path(root).exists() else None,
        "after": after,
    }
    entry = make_history_entry(root, "favorite", [file_change])
    changes = [file_change]
    changes.extend(plan_append(root, entry))
    transact(root, changes)
    return item_read(try_load_item(root, item_id) or item, root, set(after["itemIds"]))


def parse_favorite_body(body: Any) -> bool:
    if not isinstance(body, dict) or set(body) - {"favorite"}:
        raise fail("invalid-argument")
    value = body.get("favorite")
    if type(value) is not bool:
        raise fail("invalid-argument")
    return value
