"""Session Recently added ids. Written after a scan that added items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json, load_json
from library.paths import library_path


RECENT_REL = "recent.json"


def recent_path(root: Path) -> Path:
    return library_path(root, RECENT_REL)


def load_recent_ids(root: Path) -> list[str]:
    path = recent_path(root)
    if not path.is_file():
        return []
    try:
        data = load_json(path)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    ids = data.get("itemIds")
    if not isinstance(ids, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item_id in ids:
        if type(item_id) is not str or not item_id or item_id in seen:
            continue
        seen.add(item_id)
        out.append(item_id)
    return out


def remember_recent(root: Path, item_ids: list[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for item_id in item_ids:
        if type(item_id) is not str or not item_id or item_id in seen:
            continue
        seen.add(item_id)
        clean.append(item_id)
    if not clean:
        return load_recent_ids(root)
    payload: dict[str, Any] = {"itemIds": clean}
    atomic_write_json(recent_path(root), payload)
    return clean
