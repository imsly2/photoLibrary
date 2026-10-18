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
_views: dict[tuple[int, bool], tuple[float, dict[str, Any]]] = {}
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
) -> dict[str, Any]:
    install_path_checks()
    item_id = item.get("id")
    favorite = type(item_id) is str and item_id in marked
    key = (id(item), favorite)
    now = time.monotonic()
    hit = _views.get(key)
    if hit is not None and now - hit[0] < _TTL_S:
        return hit[1]
    from library.catalog_io import item_read

    view = item_read(item, root, marked)
    _views[key] = (now, view)
    if len(_views) > 8000:
        cutoff = now - _TTL_S
        for old, (seen, _view) in list(_views.items()):
            if seen < cutoff:
                _views.pop(old, None)
    return view
