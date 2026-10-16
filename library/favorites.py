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


def read_favorite_flag(value: Any) -> bool:
    if type(value) is not bool:
        raise fail("invalid-argument")
    return value


def parse_favorite_body(body: Any) -> bool:
    if not isinstance(body, dict) or set(body) - {"favorite"}:
        raise fail("invalid-argument")
    return read_favorite_flag(body.get("favorite"))


def read_item_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise fail("invalid-argument")
    ids: list[str] = []
    seen: set[str] = set()
    for item_id in raw:
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        if item_id in seen:
            continue
        seen.add(item_id)
        ids.append(item_id)
    return ids


def read_batch_favorite_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict) or set(body) - {"itemIds", "favorite"}:
        raise fail("invalid-argument")
    return {
        "itemIds": read_item_ids(body.get("itemIds")),
        "favorite": read_favorite_flag(body.get("favorite")),
    }


def set_items_favorite(root: Path, item_ids: list[str], on: bool) -> dict[str, Any]:
    from library.catalog_io import item_read, load_item, try_load_item

    if type(on) is not bool:
        raise fail("invalid-argument")
    ids = read_item_ids(item_ids)
    loaded = [load_item(root, item_id) for item_id in ids]
    before = load_favorites(root)
    after = before
    for item_id in ids:
        after = with_id(after, item_id, on)
    if before == after and favorites_path(root).exists():
        marked = set(after["itemIds"])
        return {
            "ok": True,
            "items": [item_read(item, root, marked) for item in loaded],
        }
    file_change = {
        "path": FAVORITES_REL,
        "before": before if favorites_path(root).exists() else None,
        "after": after,
    }
    entry = make_history_entry(root, "favorite", [file_change])
    transact(root, plan_append(root, entry) + [file_change])
    marked = set(after["itemIds"])
    return {
        "ok": True,
        "items": [
            item_read(try_load_item(root, item["id"]) or item, root, marked)
            for item in loaded
        ],
    }


def _strip_extended_prefix(text: str) -> str:
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[8:]
    if text.startswith("\\\\?\\"):
        return text[4:]
    return text


def existing_folder(path: Path) -> Path | None:
    """Absolute on-disk directory, or None. Never resolve a relative path against CWD."""
    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            return None
        text = _strip_extended_prefix(str(candidate))
        candidate = Path(text)
        if candidate.exists() and candidate.is_dir():
            resolved = candidate.resolve()
            cleaned = Path(_strip_extended_prefix(str(resolved)))
            if cleaned.is_dir():
                return cleaned
            return candidate
    except OSError:
        return None
    return None


def existing_original(path: Path) -> Path | None:
    """Absolute on-disk file, or None. Never resolve a relative path against CWD."""
    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            return None
        text = _strip_extended_prefix(str(candidate))
        candidate = Path(text)
        if candidate.exists() and candidate.is_file():
            resolved = candidate.resolve()
            cleaned = Path(_strip_extended_prefix(str(resolved)))
            if cleaned.is_file():
                return cleaned
            return candidate
    except OSError:
        return None
    return None


def _windows() -> bool:
    return os.name == "nt"


def windows_reveal_select_arg(path: Path) -> str:
    """Single Explorer switch: /select, glued to the path, no extra quotes."""
    text = _strip_extended_prefix(str(path))
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


def open_folder(folder: Path) -> bool:
    target = existing_folder(folder)
    if target is None:
        return False
    try:
        if _windows():
            subprocess.Popen(["explorer.exe", _strip_extended_prefix(str(target))])
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


def open_file(path: Path) -> bool:
    return open_path_with_default(path)


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)
