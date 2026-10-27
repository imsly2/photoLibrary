"""Reuse catalog read results for a short time.

A one-hertz grid poll otherwise stats every original and resolves its path.
The cached view is tied to the item object the catalog cache currently holds,
so a replaced record is read again immediately.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

_TTL_S = 2.0
_views: dict[tuple[str, int, bool], tuple[float, dict[str, Any], dict[str, Any]]] = {}
_files: dict[str, tuple[float, Any, tuple[int, int] | None]] = {}
_dirs: dict[str, tuple[float, Any, tuple[int, int] | None]] = {}


def install_path_checks() -> None:
    """Skip repeated path resolution when the file's stat has not changed."""
    import library.favorites as favorites

    if getattr(favorites, "_read_cache_installed", False):
        return
    favorites.existing_original = _wrap(favorites.existing_original, _files)
    favorites.existing_folder = _wrap(favorites.existing_folder, _dirs)
    favorites._read_cache_installed = True


def _wrap(real, store):
    def cached(path: Path):
        try:
            key = os.path.normcase(os.path.abspath(str(path)))
        except (OSError, ValueError):
            return real(path)
        now = time.monotonic()
        hit = store.get(key)
        if hit is not None and now - hit[0] < _TTL_S:
            return hit[1]
        try:
            st = os.stat(key)
            sig: tuple[int, int] | None = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if hit is not None and hit[2] == sig:
            store[key] = (now, hit[1], sig)
            return hit[1]
        result = real(path)
        store[key] = (now, result, sig)
        return result

    return cached


def cached_item_read(
    item: dict[str, Any],
    root: Path,
    marked: set[str],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    install_path_checks()
    item_id = item.get("id")
    favorite = type(item_id) is str and item_id in marked
    key = (os.path.normcase(os.path.abspath(str(root))), id(item), favorite)
    now = time.monotonic()
    hit = _views.get(key)
    from library.catalog_io import item_entities, item_read
    from library.rating import quality_view

    entities = item_entities(item, root) if metadata is None else metadata["entities"]
    if hit is not None and hit[1] is item and now - hit[0] < _TTL_S:
        base = hit[2]
    else:
        base = item_read(item, root, marked, entities=entities)
        # Retain the raw object as well as its id: Python must not recycle the
        # identity into an unrelated record while this cache entry remains live.
        _views[key] = (now, item, base)
    # A query's stack decoration must never mutate the cached base or leak into
    # another filtered result. Entity records are refreshed independently of TTL.
    view = dict(base)
    view.pop("stack", None)
    view["entities"] = entities
    view["favorite"] = favorite
    view["rating"] = quality_view(item) if metadata is None else metadata["rating"]
    if len(_views) > 8000:
        cutoff = now - _TTL_S
        for old, (seen, _item, _view) in list(_views.items()):
            if seen < cutoff:
                _views.pop(old, None)
    return view
