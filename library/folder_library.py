"""F23 folder library: the one place that decides where a folder's files live.

Every source has one flat folder library. Each picture's generated files are
named after its path inside the source folder, extension kept:

    IMG_0456.JPG.json  IMG_0456.JPG.thumb.webp  2023/IMG_0001.JPG.preview.webp

Folder-level files (``folder.json``, ``people.json``, ``index.html`` ...) never
end in a picture extension plus a suffix, so they cannot clash.

Writers address these files as ``source:<source-id>/<name>`` so atomic.transact,
undo, and recovery handle them like any library-relative path.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DIR_NAME = ".library"
LOGICAL_PREFIX = "source:"
FOLDER_SOURCE = "folder-source"
FOLDER_SERVER = "folder-server"
STORES = frozenset({FOLDER_SOURCE, FOLDER_SERVER})
RECORD = "record"
SUFFIXES: dict[str, str] = {
    RECORD: ".json",
    "thumb": ".thumb.webp",
    "preview": ".preview.webp",
    "poster": ".poster.webp",
    "proxy": ".proxy.mp4",
    "playback": ".playback.mp4",
}
FOLDER_FILES = frozenset({"folder", "people", "places", "things", "favorites", "faces", "objects"})
INDEX_FILES = ("index.html", "index.js")
_SOURCE_ID = re.compile(r"^src_[0-9a-f]{6,}$")


class SourceUnavailable(OSError):
    """The source's folder is not reachable right now (drive absent, folder gone)."""


def _clean_rel(rel: str) -> str:
    parts = [part for part in rel.replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"bad picture path: {rel!r}")
    return "/".join(parts)


def derived_name(rel: str, slot: str) -> str:
    """``2023/IMG_0001.JPG`` + ``thumb`` -> ``2023/IMG_0001.JPG.thumb.webp``."""
    return _clean_rel(rel) + SUFFIXES[slot]


def record_name(rel: str) -> str:
    return derived_name(rel, RECORD)


def parse_name(name: str) -> tuple[str, str] | None:
    """Inverse of derived_name. Folder-level files return None."""
    clean = name.replace("\\", "/")
    for slot, suffix in sorted(SUFFIXES.items(), key=lambda kv: -len(kv[1])):
        if clean.endswith(suffix) and len(clean) > len(suffix):
            rel = clean[: -len(suffix)]
            if Path(rel).suffix:
                return rel, slot
    return None


def folder_file_name(kind: str) -> str:
    if kind not in FOLDER_FILES:
        raise ValueError(f"unknown folder file: {kind}")
    return f"{kind}.json"


@dataclass(frozen=True)
class FolderLibrary:
    source_id: str
    dir: Path

    def path(self, name: str) -> Path:
        clean = _clean_rel(name)
        out = self.dir.joinpath(*clean.split("/"))
        if os.name == "nt" and len(str(out)) >= 248 and not str(out).startswith("\\\\?\\"):
            out = Path("\\\\?\\" + str(out))
        return out

    def logical(self, name: str) -> str:
        return f"{LOGICAL_PREFIX}{self.source_id}/{_clean_rel(name)}"

    def record_path(self, rel: str) -> Path:
        return self.path(record_name(rel))

    def derived_path(self, rel: str, slot: str) -> Path:
        return self.path(derived_name(rel, slot))

    def folder_file(self, kind: str) -> Path:
        return self.path(folder_file_name(kind))


def _safe_component(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "folder"


def store_for(preview_store: str | None) -> str:
    """F8 ``previewStore`` value -> the folder-library store new files use."""
    return FOLDER_SOURCE if preview_store == "with-source" else FOLDER_SERVER


def current_store(root: Path, source: dict[str, Any]) -> str:
    from library.renditions import _current_settings, effective_preview_store

    return store_for(effective_preview_store(source, _current_settings(root)))


def library_dir(root: Path, source: dict[str, Any], store: str | None = None) -> Path | None:
    """Where this source's folder library for ``store`` lives (default: the
    one the settings choose now). None when that folder is unreachable."""
    from library.paths import library_path

    source_id = str(source.get("id") or "")
    if source.get("mode") == "copy-here":
        copy_root = source.get("copyRoot")
        if type(copy_root) is not str or not copy_root:
            return None
        return library_path(root, copy_root) / DIR_NAME
    if (store or current_store(root, source)) == FOLDER_SOURCE:
        from library.portable import folder_for_source

        folder = folder_for_source(root, source)
        return None if folder is None else folder / DIR_NAME
    name = _safe_component(str(source.get("name") or "folder"))
    return library_path(root, f"folders/{name}-{source_id}")


def candidate_dirs(root: Path, source: dict[str, Any]) -> list[Path]:
    """Every place this source's records may be, whatever its mode now: the
    copy's ``.library/``, the original folder's ``.library/``, and
    ``library-data/folders/``. A setting change without relocate, or turning a
    served folder into a copy, leaves earlier records in one of the others."""
    served = {**source, "mode": "serve-from-there"}
    found = [
        library_dir(root, source, FOLDER_SOURCE),
        library_dir(root, served, FOLDER_SOURCE),
        library_dir(root, served, FOLDER_SERVER),
    ]
    out: list[Path] = []
    for path in found:
        if path is not None and path not in out:
            out.append(path)
    return out


def for_source(root: Path, source: dict[str, Any] | None, store: str | None = None) -> FolderLibrary | None:
    if not isinstance(source, dict) or type(source.get("id")) is not str:
        return None
    found = library_dir(root, source, store)
    return None if found is None else FolderLibrary(source["id"], found)


def for_source_id(root: Path, source_id: str, store: str | None = None) -> FolderLibrary | None:
    from library.catalog_io import try_load_source_head

    return for_source(root, try_load_source_head(root, source_id), store)


def for_item(root: Path, item: dict[str, Any]) -> FolderLibrary | None:
    """The folder library an F23 item's files are in (its recorded store)."""
    rend = item.get("renditions") or {}
    store = rend.get("store")
    if store not in STORES:
        return None
    return for_source_id(root, str(rend.get("sourceId") or ""), store)


def is_logical(relative: str) -> bool:
    return relative.startswith(LOGICAL_PREFIX)


def resolve_logical(root: Path, relative: str) -> Path:
    """``source:<id>/<name>`` -> absolute path. Raises SourceUnavailable."""
    body = relative[len(LOGICAL_PREFIX):]
    source_id, _, name = body.partition("/")
    if not _SOURCE_ID.match(source_id) or not name:
        from library.paths import PathError

        raise PathError("path-outside-root")
    library = for_source_id(root, source_id)
    if library is None:
        raise SourceUnavailable(f"source {source_id} is not reachable")
    return library.path(name)


def _rel_from_location(source: dict[str, Any], location: dict[str, Any]) -> str | None:
    if location.get("kind") == "library-relative":
        dest = location.get("libraryRelativePath")
        base = source.get("copyRoot")
    else:
        dest = location.get("pathFromVolumeRoot")
        base = (source.get("origin") or {}).get("pathFromVolumeRoot")
    if type(dest) is not str or not dest or type(base) is not str:
        return None
    if base == "":
        return dest
    prefix = base.rstrip("/") + "/"
    return dest[len(prefix):] if dest.startswith(prefix) else None


def picture_rel(source: dict[str, Any], item: dict[str, Any], location: dict[str, Any]) -> str | None:
    """The picture's path inside the folder its library sits in.

    Read straight from the location (no walk over ``source.files``); the
    files map is only a fallback for locations outside the folder.
    """
    key = _rel_from_location(source, location)
    if key is None:
        from library.catalog_io import file_key_for_location

        item_id = str(item.get("id") or "")
        key = next(
            (k for k, entry in (source.get("files") or {}).items()
             if entry.get("itemId") == item_id and entry.get("component") == location.get("component")),
            None,
        ) or file_key_for_location(source, item_id, location)
    if type(key) is not str or not key:
        return None
    try:
        return _clean_rel(key)
    except ValueError:
        return None


def item_rel(source: dict[str, Any], item: dict[str, Any]) -> str | None:
    """Name an item's files after its primary still, else its primary motion file."""
    source_id = source.get("id")
    locations = [
        loc for loc in item.get("locations") or []
        if loc.get("sourceId") == source_id and loc.get("current") is True
    ]
    locations.sort(key=lambda loc: (
        0 if loc.get("component") == "still" else 1,
        0 if loc.get("role") == "primary" else 1,
        str(loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or ""),
    ))
    for loc in locations:
        rel = picture_rel(source, item, loc)
        if rel is not None:
            return rel
    return None
