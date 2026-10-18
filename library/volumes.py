"""Volume serial lookup and the LIBRARY_TEST_VOLUMES seam."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from library.atomic import load_json
from library.errors import fail
from library.paths import normalize_root

_volume_lookup_context = threading.local()
_process_lock = threading.Lock()
# serial -> (mount or None, monotonic time). Positive hits stay until a
# cheap revalidation fails. Negative hits expire so a newly attached drive
# is noticed without scanning every lookup.
_process_mounts: dict[str, tuple[Path | None, float]] = {}
_NEGATIVE_TTL_S = 2.0
profile_counters = {"drive_scans": 0, "drive_scan_seconds": 0.0}


def reset_profile_counters() -> None:
    for key in profile_counters:
        profile_counters[key] = 0


@contextmanager
def volume_lookup_scope():
    """Cache native Windows serial lookups for one caller-scoped operation."""
    previous = getattr(_volume_lookup_context, "mounts", None)
    _volume_lookup_context.mounts = {}
    try:
        yield
    finally:
        if previous is None:
            del _volume_lookup_context.mounts
        else:
            _volume_lookup_context.mounts = previous


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
    mapping = load_test_volumes()
    if mapping is not None:
        matches: list[tuple[str, Path]] = []
        for serial, mount in mapping.items():
            if mount is None:
                continue
            mount_path = normalize_root(mount)
            try:
                resolved.relative_to(mount_path)
            except ValueError:
                continue
            matches.append((serial, mount_path))
        if matches:
            matches.sort(key=lambda pair: len(str(pair[1])), reverse=True)
            return matches[0]
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
        cache = getattr(_volume_lookup_context, "mounts", None)
        if cache is not None:
            if serial not in cache:
                cache[serial] = _windows_mount_for_serial(serial)
                _remember_process_mount(serial, cache[serial])
            return cache[serial]
        return _process_mount(serial)
    if serial.startswith("linux:") and os.name != "nt":
        mount = Path(serial[len("linux:") :])
        if mount.exists():
            return normalize_root(mount)
        return None
    if serial.startswith("macos:") and sys.platform == "darwin":
        mount = Path(serial[len("macos:") :])
        if mount.exists():
            return normalize_root(mount)
        return None
    return None


def _remember_process_mount(serial: str, mount: Path | None) -> None:
    with _process_lock:
        _process_mounts[serial] = (mount, time.monotonic())


def _process_mount(serial: str) -> Path | None:
    now = time.monotonic()
    with _process_lock:
        row = _process_mounts.get(serial)
    if row is not None:
        mount, seen = row
        if mount is not None or now - seen < _NEGATIVE_TTL_S:
            return mount
    found = _windows_mount_for_serial(serial)
    _remember_process_mount(serial, found)
    return found


def _mount_reports_serial(mount: Path, serial: str) -> bool:
    try:
        found, _mount = windows_volume(mount)
    except Exception:
        return False
    return found == serial


def _refresh_stale_mount(serial: str) -> bool:
    """Full drive scan only when the cached letter no longer has this serial."""
    if load_test_volumes() is not None:
        return False
    if not serial.startswith("windows:") or os.name != "nt":
        return False
    with _process_lock:
        row = _process_mounts.get(serial)
    if row is None or row[0] is None:
        return False
    if _mount_reports_serial(row[0], serial):
        return False
    with _process_lock:
        _process_mounts.pop(serial, None)
    scope = getattr(_volume_lookup_context, "mounts", None)
    if scope is not None:
        scope.pop(serial, None)
    return True


def _windows_mount_for_serial(serial: str) -> Path | None:
    import ctypes
    import string

    started = time.perf_counter()
    profile_counters["drive_scans"] += 1
    try:
        return _windows_mount_for_serial_uncounted(serial)
    finally:
        profile_counters["drive_scan_seconds"] += time.perf_counter() - started


def _windows_mount_for_serial_uncounted(serial: str) -> Path | None:
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
    path = _location_file_once(location, library_root)
    if path is None or location.get("kind") == "library-relative":
        return path
    try:
        present = path.is_file()
    except OSError:
        present = False
    if present:
        return path
    serial = location.get("volumeSerial")
    if type(serial) is not str or not _refresh_stale_mount(serial):
        return path
    return _location_file_once(location, library_root)


def _location_file_once(location: dict[str, Any], library_root: Path) -> Path | None:
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
    if source.get("mode") == "copy-here":
        copy_root = source.get("copyRoot")
        if type(copy_root) is not str or not copy_root:
            return False
        from library.paths import library_path

        try:
            path = library_path(library_root, copy_root)
        except Exception:
            return False
        return path.exists()
    origin = source.get("origin") or {}
    serial = origin.get("volumeSerial")
    rel = origin.get("pathFromVolumeRoot")
    if type(serial) is not str or type(rel) is not str:
        return False
    path = volume_file_path(serial, rel)
    return path is not None and path.exists()


_AVAIL_TTL_S = 2.0
_avail_cache: dict[tuple[Any, ...], tuple[float, bool]] = {}


def _availability_key(item: dict[str, Any], component: str) -> tuple[Any, ...]:
    locs = []
    for loc in item.get("locations") or []:
        if loc.get("current") is not True or loc.get("component") != component:
            continue
        locs.append(
            (
                loc.get("sourceId"),
                loc.get("role"),
                loc.get("pathFromVolumeRoot"),
                loc.get("libraryRelativePath"),
                loc.get("sizeBytes"),
                loc.get("mtimeNs"),
            )
        )
    return (item.get("id"), component, tuple(locs))


def item_component_available(
    item: dict[str, Any],
    component: str,
    library_root: Path,
) -> bool:
    key = _availability_key(item, component)
    now = time.monotonic()
    hit = _avail_cache.get(key)
    if hit is not None and now - hit[0] < _AVAIL_TTL_S:
        return hit[1]
    result = _item_component_available(item, component, library_root)
    _avail_cache[key] = (now, result)
    if len(_avail_cache) > 8000:
        cutoff = now - _AVAIL_TTL_S
        for old, (seen, _value) in list(_avail_cache.items()):
            if seen < cutoff:
                _avail_cache.pop(old, None)
    return result


def _item_component_available(
    item: dict[str, Any],
    component: str,
    library_root: Path,
) -> bool:
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == component
    ]
    candidates.sort(key=lambda loc: (0 if loc.get("role") == "primary" else 1, loc.get("sourceId") or "", loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or ""))
    for loc in candidates:
        path = location_file(loc, library_root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return True
    return False


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
