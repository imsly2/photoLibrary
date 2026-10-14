"""Hearted item ids, Reveal in Explorer, and default-app open. One catalog file."""

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
SCHEMA_VERSION = 1


def favorites_path(root: Path) -> Path:
    return library_path(root, FAVORITES_REL)


def default_favorites() -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "itemIds": []}


def empty_favorites() -> dict[str, Any]:
    return default_favorites()


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
    except Exception as exc:
        raise fail("invalid-catalog") from exc
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
    from library.catalog_io import item_read, load_item, try_load_item

    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    if type(on) is not bool:
        raise fail("invalid-argument")
    item = load_item(root, item_id)
    before = load_favorites(root)
    after = with_id(before, item_id, on)
    if before == after and favorites_path(root).exists():
        return item_read(item, root, set(after["itemIds"]))
    file_change = {
        "path": FAVORITES_REL,
        "before": before if favorites_path(root).exists() else None,
        "after": after,
    }
    entry = make_history_entry(root, "favorite", [file_change])
    transact(root, plan_append(root, entry) + [file_change])
    return item_read(try_load_item(root, item_id) or item, root, set(after["itemIds"]))


def apply_favorite(root: Path, item_id: str, favorite: bool) -> dict[str, Any]:
    return set_item_favorite(root, item_id, favorite)


def parse_favorite_body(body: Any) -> bool:
    if not isinstance(body, dict) or set(body) - {"favorite"}:
        raise fail("invalid-argument")
    value = body.get("favorite")
    if type(value) is not bool:
        raise fail("invalid-argument")
    return value


def existing_original(path: Path) -> Path | None:
    """Absolute on-disk file, or None. Directories and missing paths are None."""
    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = candidate.resolve()
        elif candidate.exists():
            candidate = candidate.resolve()
    except OSError:
        return None
    if not candidate.is_absolute() or not candidate.is_file():
        return None
    return candidate


def _windows() -> bool:
    return os.name == "nt"


def windows_reveal_select_arg(path: Path) -> str:
    """Single Explorer switch: /select, glued to the path, no extra quotes."""
    text = str(path)
    if _windows():
        text = os.path.normpath(text)
    return f"/select,{text}"


def windows_reveal_command(path: Path) -> list[str]:
    """Argv Explorer accepts: explorer.exe + /select,path (spaces stay inside the arg)."""
    return ["explorer.exe", windows_reveal_select_arg(path)]


def open_path_with_default(path: Path) -> bool:
    target = existing_original(path)
    if target is None:
        return False
    try:
        if _windows():
            os.startfile(target)  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
            return True
        opener = _which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(target)])
            return True
    except OSError:
        return False
    return False


def open_containing_folder(path: Path) -> bool:
    target = existing_original(path)
    if target is None:
        return False
    folder = target.parent
    try:
        if _windows():
            # List form: /select, glued to the path, no extra quotes in the
            # arg. A quoted string command still opens Documents on spaces.
            subprocess.Popen(windows_reveal_command(target))
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
            return True
        opener = _which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(folder)])
            return True
    except OSError:
        return False
    return False


def open_file(path: Path) -> bool:
    return open_path_with_default(path)


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)
