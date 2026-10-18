"""F23: where each item record is stored.

The app addresses item records as ``catalog/items/<id>.json``; history, undo,
catalog overlays and transactions all keep that address. Its file is:

- ``<folder library>/<name>.json`` when ``renditions.store`` is
  ``folder-source`` or ``folder-server`` (``IMG_0456.JPG.json`` beside
  ``IMG_0456.JPG.thumb.webp`` in that store's folder library);
- ``library-data/catalog/items/<id>.json`` for pending items, old-layout
  items (until migration moves their previews and record together), and
  items whose folder is unreachable.

The id -> folder record map is built once from every reachable folder
library and kept current by ``write``.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from library import folder_library

ITEM_PREFIX = "catalog/items/"

profile_counters = {"builds": 0, "record_reads": 0}

_guard = threading.RLock()
_states: dict[str, "_State"] = {}
_writes = 0


@dataclass
class _State:
    ids: dict[str, Path] = field(default_factory=dict)
    paths: dict[str, str] = field(default_factory=dict)
    # folder library dirs that held records: pkey -> (source id, dir)
    bases: dict[str, tuple[str, Path]] = field(default_factory=dict)

    def put(self, item_id: str, path: Path) -> None:
        self.forget(item_id)
        self.ids[item_id] = path
        self.paths[_pkey(path)] = item_id

    def forget(self, item_id: str) -> None:
        old = self.ids.pop(item_id, None)
        if old is not None and self.paths.get(_pkey(old)) == item_id:
            self.paths.pop(_pkey(old), None)


def write_count() -> int:
    """Bumped by every write; caches compare it to notice folder-record changes."""
    return _writes


def _key(root: Path) -> str:
    return os.path.normcase(os.path.abspath(str(root)))


def _pkey(path: Path) -> str:
    return os.path.normcase(str(path))


def item_id_of(relative: str) -> str | None:
    """``catalog/items/<id>.json`` -> ``<id>``; anything else -> None."""
    if not relative.startswith(ITEM_PREFIX) or not relative.endswith(".json"):
        return None
    item_id = relative[len(ITEM_PREFIX) : -len(".json")]
    if not item_id or "/" in item_id or "\\" in item_id or item_id in {".", ".."}:
        return None
    return item_id


def legacy_path(root: Path, item_id: str) -> Path:
    return Path(root) / "catalog" / "items" / f"{item_id}.json"


def invalidate(root: Path) -> None:
    """Forget the map; the next lookup re-reads every folder library."""
    global _writes
    with _guard:
        _writes += 1
        _states.pop(_key(root), None)


def _state(root: Path) -> _State:
    key = _key(root)
    with _guard:
        state = _states.get(key)
        if state is None:
            state = _states[key] = _build(root)
        return state


def _build(root: Path) -> _State:
    """Read every folder record. A record found twice (a copy, or a relocate
    cut short) resolves to the one in its owner's folder, in the store it names."""
    profile_counters["builds"] += 1
    state = _State()
    ranks: dict[str, int] = {}
    for source, base in _library_dirs(root):
        for path in _record_files(base):
            found = _read_owner(path)
            if found is None:
                continue
            state.bases[_pkey(base)] = (source["id"], base)
            item_id, owner, store = found
            rank = 0
            if owner == source["id"]:
                rank = 1
                if store in folder_library.STORES and folder_library.library_dir(root, source, store) == base:
                    rank = 2
            if item_id in ranks and ranks[item_id] >= rank:
                continue
            state.put(item_id, path)
            ranks[item_id] = rank
    return state


def _library_dirs(root: Path):
    """Every existing folder library of every source (a setting change without
    relocate, or a copy, can leave older records in another one)."""
    from library.catalog_io import iter_source_ids, try_load_source_head
    from library.errors import AppError

    seen: set[str] = set()
    for source_id in iter_source_ids(root):
        try:
            source = try_load_source_head(root, source_id)
            dirs = folder_library.candidate_dirs(root, source) if source else []
        except (AppError, OSError, ValueError):
            continue
        for base in dirs:
            if _pkey(base) in seen or not base.is_dir():
                continue
            seen.add(_pkey(base))
            yield source, base


def _record_files(base: Path):
    for top, dirs, files in os.walk(base):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        rel_top = os.path.relpath(top, base).replace("\\", "/")
        for name in files:
            if not name.endswith(".json"):
                continue
            rel = name if rel_top == "." else f"{rel_top}/{name}"
            parsed = folder_library.parse_name(rel)
            if parsed is not None and parsed[1] == folder_library.RECORD:
                yield Path(top) / name


def _read_owner(path: Path) -> tuple[str, str, str] | None:
    """(item id, owning source id, store) from one record file."""
    profile_counters["record_reads"] += 1
    try:
        with open(path, encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(body, dict) or type(body.get("id")) is not str or not body["id"]:
        return None
    rend = body.get("renditions") if isinstance(body.get("renditions"), dict) else {}
    owner, store = rend.get("sourceId"), rend.get("store")
    return body["id"], owner if type(owner) is str else "", store if type(store) is str else ""


def stored_path(root: Path, item_id: str) -> Path | None:
    """The folder record for this item, or None when it is stored in library-data."""
    if item_id.startswith("pending-"):
        return None
    return _state(root).ids.get(item_id)


def path_for(root: Path, item_id: str) -> Path:
    """The file that holds this item's record now (it may not exist)."""
    return stored_path(root, item_id) or legacy_path(root, item_id)


def folder_records(root: Path) -> dict[str, Path]:
    """Items stored in folder libraries: id -> record file."""
    return dict(_state(root).ids)


def iter_ids(root: Path) -> list[str]:
    ids = {item_id for item_id, path in folder_records(root).items() if path.is_file()}
    legacy = Path(root) / "catalog" / "items"
    if legacy.is_dir():
        ids.update(path.stem for path in legacy.glob("*.json"))
    return sorted(ids)


def vanished_sources(root: Path) -> set[str]:
    """Sources whose folder library was deleted while its folder is still there.

    Their records are forgotten here; the caller rescans them as new (F23
    "delete ``.library/`` and that folder starts over"). An unplugged drive
    (parent folder gone too) is not a reset.
    """
    global _writes
    out: set[str] = set()
    with _guard:
        state = _state(root)
        for pkey, (source_id, base) in list(state.bases.items()):
            if base.exists() or not base.parent.is_dir():
                continue
            del state.bases[pkey]
            prefix = pkey.rstrip("\\/") + os.sep
            for item_id, path in list(state.ids.items()):
                if _pkey(path).startswith(prefix):
                    state.forget(item_id)
            _writes += 1
            out.add(source_id)
    return out


def _folder_target(root: Path, item: dict[str, Any]) -> tuple[Path, folder_library.FolderLibrary] | None:
    rend = item.get("renditions")
    if not isinstance(rend, dict) or rend.get("store") not in folder_library.STORES:
        return None
    source_id = rend.get("sourceId")
    if type(source_id) is not str:
        return None
    from library.catalog_io import try_load_source_head

    source = try_load_source_head(root, source_id)
    library = folder_library.for_source(root, source, rend["store"])
    rel = folder_library.item_rel(source, item) if source is not None else None
    if library is None or rel is None:
        return None
    return library.record_path(rel), library


def target_for(root: Path, item_id: str, payload: Any) -> Path:
    """Where a write of ``payload`` lands."""
    if item_id.startswith("pending-") or not isinstance(payload, dict):
        return path_for(root, item_id)
    found = _folder_target(root, payload)
    return found[0] if found else legacy_path(root, item_id)


def write(root: Path, item_id: str, payload: Any, *, sync: bool = True) -> Path:
    """Write or delete one item record; returns the file written or removed.

    A folder write that takes another item's name moves that item's record
    back to ``library-data`` first, so no record is ever overwritten by a
    different item. Moving a record to a new file removes the old one.
    """
    global _writes
    from library.atomic import atomic_write_json

    legacy = legacy_path(root, item_id)
    with _guard:
        _writes += 1
        state = _state(root)
        old = state.ids.get(item_id)
        if payload is None:
            for path in (old, legacy):
                if path is not None and path.exists():
                    path.unlink()
            state.forget(item_id)
            return old or legacy
        found = None if item_id.startswith("pending-") else _folder_target(root, payload)
        dest = found[0] if found else legacy
        if found:
            other = state.paths.get(_pkey(dest))
            if other is not None and other != item_id:
                _evict(root, state, other, dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(dest, payload, sync=sync)
        if old is not None and old != dest and old.exists():
            old.unlink()
        if not found:
            state.forget(item_id)
            return dest
        state.put(item_id, dest)
        state.bases[_pkey(found[1].dir)] = (found[1].source_id, found[1].dir)
        if legacy.exists():
            legacy.unlink()
        return dest


def _evict(root: Path, state: _State, item_id: str, path: Path) -> None:
    from library.atomic import atomic_write_bytes

    try:
        data = path.read_bytes()
    except OSError:
        data = None
    if data is not None:
        legacy = legacy_path(root, item_id)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(legacy, data, sync=True)
    state.forget(item_id)
