"""Viewer heart marks and reveal-in-folder. Favorites are not item JSON."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from library.atomic import load_json, transact
from library.errors import fail
from library.history import make_history_entry, plan_append
from library.paths import library_path


FAVORITES_REL = "catalog/favorites.json"


def favorites_path(root: Path) -> Path:
    return library_path(root, FAVORITES_REL)


def empty_favorites() -> dict[str, Any]:
    return {"schemaVersion": 1, "itemIds": []}


def ordered_favorites(data: dict[str, Any]) -> dict[str, Any]:
    ids = data.get("itemIds") or []
    unique = sorted({item_id for item_id in ids if type(item_id) is str and item_id})
    return {"schemaVersion": 1, "itemIds": unique}


def load_favorites(root: Path) -> dict[str, Any]:
    path = favorites_path(root)
    if not path.exists():
        return empty_favorites()
    try:
        data = load_json(path)
    except Exception as exc:
        raise fail("invalid-catalog") from exc
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise fail("invalid-catalog")
    ids = data.get("itemIds")
    if not isinstance(ids, list):
        raise fail("invalid-catalog")
    for item_id in ids:
        if type(item_id) is not str or not item_id:
            raise fail("invalid-catalog")
    return ordered_favorites(data)


def favorite_ids(root: Path) -> set[str]:
    return set(load_favorites(root)["itemIds"])


def apply_favorite(root: Path, item_id: str, favorite: bool) -> dict[str, Any]:
    from library.catalog_io import item_read, load_item

    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    if type(favorite) is not bool:
        raise fail("invalid-argument")
    item = load_item(root, item_id)
    before = load_favorites(root)
    ids = set(before["itemIds"])
    if favorite:
        ids.add(item_id)
    else:
        ids.discard(item_id)
    after = ordered_favorites({"schemaVersion": 1, "itemIds": list(ids)})
    if before == after and favorites_path(root).exists():
        return item_read(item, root)
    change = {
        "path": FAVORITES_REL,
        "before": before if favorites_path(root).exists() else None,
        "after": after,
    }
    entry = make_history_entry(root, "favorite", [change])
    transact(root, plan_append(root, entry) + [change])
    return item_read(load_item(root, item_id), root)


def open_containing_folder(path: Path) -> bool:
    folder = path.parent
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", f"/select,{path}"])
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
            return True
        opener = _which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(folder)])
            return True
    except OSError:
        return False
    return False


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)
