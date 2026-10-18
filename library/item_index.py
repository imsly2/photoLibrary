"""Stat-validated catalog cache for rendition picking and queue counts.

Item JSON is parsed again only when its directory entry changes
(mtime_ns + size). Writers keep using atomic.transact; this module only
reads. Callers must not mutate the dicts it returns.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from library import item_store
from library.atomic import load_json
from library.catalog_io import items_dir
from library.errors import AppError, fail
from library.records import read_item

SLOTS = ("thumb", "poster", "preview", "proxy", "playback")
_WANTED_MAX = 8

_guard = threading.Lock()
_wanted_lock = threading.Lock()
_batch = threading.local()
_caches: dict[str, "_Cache"] = {}
_wanted: dict[str, list[str]] = {}
_resolved_keys: dict[str, str] = {}

profile_counters = {"resyncs": 0, "parses": 0, "scandirs": 0}


class _Cache:
    def __init__(self) -> None:
        self.sig: dict[str, tuple[int, int]] = {}
        self.items: dict[str, dict[str, Any]] = {}
        self.queued: dict[str, list[str]] = {slot: [] for slot in SLOTS}
        self.since_video = 0
        self.dir_token: tuple[int, int] | None = None
        self.since_full = 0

    def sort_queues(self) -> None:
        for ids in self.queued.values():
            ids.sort()


def root_key(root: Path) -> str:
    """Resolve once per path string. Windows resolve() hits the filesystem."""
    raw = os.path.normcase(os.path.abspath(str(root)))
    hit = _resolved_keys.get(raw)
    if hit is not None:
        return hit
    resolved = os.path.normcase(str(Path(raw).resolve()))
    _resolved_keys[raw] = resolved
    _resolved_keys[resolved] = resolved
    return resolved


def reset_profile_counters() -> None:
    for key in profile_counters:
        profile_counters[key] = 0


def note_wanted(root: Path, item_id: str) -> None:
    """Remember a viewer-opened item. Recent ids are first. Bounded."""
    if type(item_id) is not str or not item_id or "/" in item_id or "\\" in item_id:
        return
    if item_id.startswith("pending-"):
        return
    key = root_key(root)
    with _wanted_lock:
        row = [existing for existing in _wanted.get(key, ()) if existing != item_id]
        row.insert(0, item_id)
        _wanted[key] = row[:_WANTED_MAX]


def wanted_ids(root: Path) -> list[str]:
    with _wanted_lock:
        return list(_wanted.get(root_key(root), ()))


def reading(root: Path):
    """One directory sync, then load_item calls in this thread hit memory."""
    resync(root)

    class _Batch:
        def __enter__(self) -> None:
            depth = int(getattr(_batch, "depth", 0))
            _batch.depth = depth + 1
            _batch.root = root_key(root)

        def __exit__(self, *exc: object) -> None:
            _batch.depth = int(getattr(_batch, "depth", 1)) - 1

    return _Batch()


def _in_batch(root: Path) -> bool:
    return int(getattr(_batch, "depth", 0)) > 0 and getattr(_batch, "root", None) == root_key(root)


def resync(root: Path) -> _Cache:
    """Compare the items directory and parse only new or changed files.

    A matching directory mtime skips the listing. Publication updates that
    token after it refreshes the one item it wrote. Every few calls still
    list the directory so a scan that landed in the same timestamp is noticed.
    """
    with _guard:
        profile_counters["resyncs"] += 1
        cache = _caches.setdefault(root_key(root), _Cache())
        folder = items_dir(root)
        token = _token(root)
        cache.since_full += 1
        if token is not None and cache.dir_token == token and cache.since_full < 8:
            return cache
        profile_counters["scandirs"] += 1
        cache.since_full = 0
        found: dict[str, tuple[int, int]] = {}
        paths: dict[str, Path] = {}
        if folder.is_dir():
            with os.scandir(folder) as scan:
                for entry in scan:
                    name = entry.name
                    if not name.endswith(".json"):
                        continue
                    try:
                        st = entry.stat()
                    except OSError:
                        continue
                    item_id = name[: -len(".json")]
                    if not item_id:
                        continue
                    found[item_id] = (st.st_mtime_ns, st.st_size)
        for item_id, (path, sig) in _folder_record_sigs(root).items():
            found[item_id] = sig
            paths[item_id] = path
        for item_id in list(cache.sig):
            if item_id not in found:
                _forget(cache, item_id)
        for item_id, sig in found.items():
            if cache.sig.get(item_id) == sig and item_id in cache.items:
                continue
            _parse_into(cache, paths.get(item_id) or folder / f"{item_id}.json", item_id, sig)
        cache.sort_queues()
        cache.dir_token = _token(root)
        return cache


def _token(root: Path) -> tuple[int, int] | None:
    """Legacy items directory mtime plus item_store's write count."""
    try:
        return (items_dir(root).stat().st_mtime_ns, item_store.write_count())
    except OSError:
        return None


def _folder_record_sigs(root: Path) -> dict[str, tuple[Path, tuple[int, int]]]:
    """Stat folder-library records one directory listing at a time."""
    by_dir: dict[str, dict[str, str]] = {}
    for item_id, path in item_store.folder_records(root).items():
        by_dir.setdefault(str(path.parent), {})[os.path.normcase(path.name)] = item_id
    out: dict[str, tuple[Path, tuple[int, int]]] = {}
    for parent, wanted in by_dir.items():
        try:
            with os.scandir(parent) as scan:
                for entry in scan:
                    item_id = wanted.get(os.path.normcase(entry.name))
                    if item_id is None:
                        continue
                    try:
                        st = entry.stat()
                    except OSError:
                        continue
                    out[item_id] = (Path(entry.path), (st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    return out


def remember_write(root: Path, item_id: str, item: dict[str, Any]) -> None:
    """Keep a just-written item in memory so the next pick does not reparse it."""
    path = item_store.path_for(root, item_id)
    with _guard:
        cache = _caches.get(root_key(root))
        if cache is None:
            return
        try:
            st = path.stat()
        except OSError:
            cache.dir_token = None
            return
        cache.items[item_id] = item
        cache.sig[item_id] = (st.st_mtime_ns, st.st_size)
        _requeue(cache, item_id, item)
        cache.dir_token = _token(root)


def queued_counts(root: Path) -> dict[str, int]:
    """Waiting work per slot as of the last resync. Never touches the disk."""
    with _guard:
        cache = _caches.get(root_key(root))
        return {slot: len(ids) for slot, ids in cache.queued.items()} if cache else {}


def iter_item_ids(root: Path) -> list[str]:
    if _in_batch(root):
        cache = _caches.get(root_key(root))
        if cache is None:
            cache = resync(root)
        return sorted(cache.items)
    return sorted(resync(root).items)


def iter_items(root: Path) -> list[dict[str, Any]]:
    cache = resync(root)
    return [cache.items[item_id] for item_id in sorted(cache.items)]


def load_item(root: Path, item_id: str) -> dict[str, Any]:
    if _in_batch(root):
        cache = _caches.get(root_key(root))
        item = None if cache is None else cache.items.get(item_id)
        if item is None:
            raise fail("not-found")
        return item
    path = item_store.path_for(root, item_id)
    try:
        st = path.stat()
    except FileNotFoundError as exc:
        with _guard:
            cache = _caches.get(root_key(root))
            if cache is not None:
                _forget(cache, item_id)
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc
    sig = (st.st_mtime_ns, st.st_size)
    with _guard:
        cache = _caches.setdefault(root_key(root), _Cache())
        if cache.sig.get(item_id) == sig and item_id in cache.items:
            return cache.items[item_id]
    try:
        item = read_item(load_json(path))
    except FileNotFoundError as exc:
        raise fail("not-found") from exc
    except OSError as exc:
        raise fail("io-error") from exc
    with _guard:
        cache = _caches.setdefault(root_key(root), _Cache())
        cache.items[item_id] = item
        cache.sig[item_id] = sig
        _requeue(cache, item_id, item)
        cache.sort_queues()
        return item


def _parse_into(cache: _Cache, path: Path, item_id: str, sig: tuple[int, int]) -> None:
    profile_counters["parses"] += 1
    try:
        item = read_item(load_json(path))
    except (OSError, json.JSONDecodeError, AppError, KeyError, TypeError, ValueError):
        _forget(cache, item_id)
        return
    cache.items[item_id] = item
    cache.sig[item_id] = sig
    _requeue(cache, item_id, item)


def _forget(cache: _Cache, item_id: str) -> None:
    cache.sig.pop(item_id, None)
    cache.items.pop(item_id, None)
    for ids in cache.queued.values():
        if item_id in ids:
            ids.remove(item_id)


def _requeue(cache: _Cache, item_id: str, item: dict[str, Any]) -> None:
    status: dict[str, Any] = {}
    rend = item.get("renditions") or {}
    raw = rend.get("status") if isinstance(rend, dict) else None
    if isinstance(raw, dict):
        status = raw
    pending = item_id.startswith("pending-")
    for slot, ids in cache.queued.items():
        want = (not pending) and status.get(slot) == "queued"
        present = item_id in ids
        if want and not present:
            ids.append(item_id)
        elif present and not want:
            ids.remove(item_id)

