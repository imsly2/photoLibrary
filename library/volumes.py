"""Volume serial lookup and the LIBRARY_TEST_VOLUMES seam."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from library.atomic import load_json
from library.errors import fail
from library.paths import normalize_root


def load_test_volumes() -> dict[str, str | None] | None:
    if os.environ.get("LIBRARY_TEST") != "1":
        return None
    raw = os.environ.get("LIBRARY_TEST_VOLUMES")
    if not raw:
        return None
    path = Path(raw)
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise fail("invalid-argument") from exc
    if not isinstance(data, dict):
        raise fail("invalid-argument")
    out: dict[str, str | None] = {}
    for key, value in data.items():
        if type(key) is not str:
            raise fail("invalid-argument")
        if value is None:
            out[key] = None
        elif type(value) is str:
            out[key] = value
        else:
            raise fail("invalid-argument")
    return out


def windows_volume(path: Path) -> tuple[str, Path]:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    volume = ctypes.create_unicode_buffer(520)
    if not kernel32.GetVolumePathNameW(str(path), volume, 520):
        raise fail("volume-identity-unavailable")
    serial = ctypes.c_uint()
    if not kernel32.GetVolumeInformationW(
        volume.value, None, 0, ctypes.byref(serial), None, None, None, 0
    ):
        raise fail("volume-identity-unavailable")
    return f"windows:{serial.value:08X}", Path(volume.value)


def posix_volume(path: Path) -> tuple[str, Path]:
    resolved = normalize_root(path)
    mount = resolved
    while mount.parent != mount and not os.path.ismount(str(mount)):
        mount = mount.parent
    if sys.platform == "darwin":
        return f"macos:{mount}", mount
    return f"linux:{mount}", mount


def volume_of_path(path: Path) -> tuple[str, Path]:
    resolved = normalize_root(path)
    if not resolved.exists():
        raise fail("invalid-argument")
    if os.name == "nt":
        return windows_volume(resolved)
    return posix_volume(resolved)


def path_from_volume_root(path: Path, volume_root: Path) -> str:
    resolved = normalize_root(path)
    root = normalize_root(volume_root)
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise fail("volume-identity-unavailable") from exc
    text = rel.as_posix()
    if text == ".":
        return ""
    return text


def resolve_volume_mount(serial: str) -> Path | None:
    mapping = load_test_volumes()
    if mapping is not None and serial in mapping:
        mount = mapping[serial]
        if mount is None:
            return None
        return normalize_root(mount)
    if serial.startswith("windows:") and os.name == "nt":
        return _windows_mount_for_serial(serial)
    return None


def _windows_mount_for_serial(serial: str) -> Path | None:
    import ctypes
    import string

    kernel32 = ctypes.windll.kernel32
    bitmask = kernel32.GetLogicalDrives()
    for index, letter in enumerate(string.ascii_uppercase):
        if not bitmask & (1 << index):
            continue
        root = Path(f"{letter}:\\")
        try:
            found, mount = windows_volume(root)
        except Exception:
            continue
        if found == serial:
            return mount
    return None


def volume_file_path(serial: str, path_from_volume_root: str) -> Path | None:
    mount = resolve_volume_mount(serial)
    if mount is None:
        return None
    rel = path_from_volume_root.replace("\\", "/").strip("/")
    if not rel:
        return mount
    if ".." in Path(rel).parts:
        return None
    return mount / Path(*rel.split("/"))


def location_file(location: dict[str, Any], library_root: Path) -> Path | None:
    if location.get("kind") == "library-relative":
        rel = location.get("libraryRelativePath")
        if type(rel) is not str:
            return None
        from library.paths import library_path

        try:
            return library_path(library_root, rel)
        except Exception:
            return None
    serial = location.get("volumeSerial")
    rel = location.get("pathFromVolumeRoot")
    if type(serial) is not str or type(rel) is not str:
        return None
    return volume_file_path(serial, rel)


def location_matches_stat(location: dict[str, Any], path: Path) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    if location.get("sizeBytes") != stat.st_size:
        return False
    from library.media import mtime_iso

    return location.get("modifiedAt") == mtime_iso(path)


def source_available(source: dict[str, Any], library_root: Path) -> bool:
    origin = source.get("origin") or {}
    serial = origin.get("volumeSerial")
    rel = origin.get("pathFromVolumeRoot")
    if type(serial) is not str or type(rel) is not str:
        return False
    path = volume_file_path(serial, rel)
    return path is not None and path.exists()


def has_component_location(item: dict[str, Any], component: str) -> bool:
    return any(loc.get("component") == component for loc in item.get("locations") or [])


def resolve_component_path(
    item: dict[str, Any],
    component: str,
    library_root: Path,
) -> Path | None:
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == component
    ]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or "",
        )
    )
    for loc in candidates:
        path = location_file(loc, library_root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return path
    return None


def item_component_available(
    item: dict[str, Any],
    component: str,
    library_root: Path,
) -> bool:
    return resolve_component_path(item, component, library_root) is not None


def item_available(item: dict[str, Any], library_root: Path) -> bool:
    kind = item.get("kind")
    if kind == "video":
        return item_component_available(item, "motion", library_root)
    return item_component_available(item, "still", library_root)


def item_motion_available(item: dict[str, Any], library_root: Path) -> bool:
    return item_component_available(item, "motion", library_root)


def last_known_text(path: Path) -> str:
    return str(normalize_root(path))


def same_origin(source: dict[str, Any], serial: str, path_from_root: str) -> bool:
    origin = source.get("origin") or {}
    return origin.get("volumeSerial") == serial and origin.get(
        "pathFromVolumeRoot"
    ) == path_from_root
