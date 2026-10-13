"""Canonical source and item records. Unknown fields are rejected."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from library.errors import fail

ITEM_KEYS = (
    "schemaVersion",
    "id",
    "kind",
    "filename",
    "capturedAt",
    "capturedAtSource",
    "placeId",
    "metadata",
    "contentIdentifier",
    "locations",
    "renditions",
    "faces",
    "things",
)
METADATA_KEYS = (
    "width",
    "height",
    "orientation",
    "camera",
    "lens",
    "durationSec",
    "latitude",
    "longitude",
)
LOCATION_KEYS = (
    "sourceId",
    "role",
    "component",
    "kind",
    "current",
    "libraryRelativePath",
    "volumeSerial",
    "pathFromVolumeRoot",
    "lastKnownPath",
    "sizeBytes",
    "modifiedAt",
    "sha256",
)
RENDITION_KEYS = ("store", "sourceId", "thumb", "preview", "poster", "proxy", "status")
RENDITION_STATUS_KEYS = ("thumb", "preview", "poster", "proxy")
SOURCE_KEYS = (
    "schemaVersion",
    "id",
    "name",
    "mode",
    "origin",
    "copyRoot",
    "previewStore",
    "files",
    "scan",
)
ORIGIN_KEYS = ("volumeSerial", "pathFromVolumeRoot", "lastKnownPath")
FILE_ENTRY_KEYS = (
    "destination",
    "itemId",
    "component",
    "sizeBytes",
    "modifiedAt",
    "sha256",
    "state",
)
SCAN_KEYS = ("state", "added", "skipped", "errors")
SCAN_ERROR_KEYS = ("path", "error")
PLACE_KEYS = ("schemaVersion", "id", "name", "latitude", "longitude")
PERSON_KEYS = ("schemaVersion", "id", "name")
THING_KEYS = ("schemaVersion", "id", "name", "aliases")
SOURCE_MODES = frozenset({"copy-here", "serve-from-there"})
ITEM_KINDS = frozenset({"photo", "video", "live"})
CAPTURE_SOURCES = frozenset({"exif", "filename", "mtime"})
ROLES = frozenset({"primary", "alternate"})
COMPONENTS = frozenset({"still", "motion"})
LOCATION_KINDS = frozenset({"library-relative", "volume"})
FILE_STATES = frozenset({"pending", "copied", "indexed", "error"})
SCAN_STATES = frozenset({"idle", "running", "complete", "interrupted", "error"})
PREVIEW_STORES = frozenset({"with-server", "with-source"})
RENDITION_STATUSES = frozenset({"not-applicable", "queued", "ready", "error"})
SCAN_FILE_ERRORS = frozenset({"io-error", "decode-error", "invalid-argument"})


def _require_dict(value: Any, code: str = "invalid-catalog") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise fail(code)
    return value


def _exact_keys(data: dict[str, Any], keys: tuple[str, ...], code: str = "invalid-catalog") -> None:
    if set(data.keys()) != set(keys):
        raise fail(code)


def _str(value: Any, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise fail("invalid-catalog")
    if not allow_empty and value == "":
        raise fail("invalid-catalog")
    return value


def _null_or_str(value: Any) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise fail("invalid-catalog")
    return value


def _bool(value: Any) -> bool:
    if type(value) is not bool:
        raise fail("invalid-catalog")
    return value


def _int(value: Any) -> int:
    if type(value) is not int:
        raise fail("invalid-catalog")
    return value


def _null_or_int(value: Any) -> int | None:
    if value is None:
        return None
    return _int(value)


def _null_or_number(value: Any) -> int | float | None:
    if value is None:
        return None
    if type(value) is bool or not isinstance(value, (int, float)):
        raise fail("invalid-catalog")
    return value


def read_metadata(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, METADATA_KEYS)
    width = _null_or_int(data["width"])
    height = _null_or_int(data["height"])
    if width is not None and width <= 0:
        raise fail("invalid-catalog")
    if height is not None and height <= 0:
        raise fail("invalid-catalog")
    orientation = _null_or_int(data["orientation"])
    if orientation is not None and orientation not in range(1, 9):
        raise fail("invalid-catalog")
    duration = _null_or_number(data["durationSec"])
    if duration is not None and duration < 0:
        raise fail("invalid-catalog")
    latitude = _null_or_number(data["latitude"])
    longitude = _null_or_number(data["longitude"])
    if latitude is not None and not (-90 <= float(latitude) <= 90):
        raise fail("invalid-catalog")
    if longitude is not None and not (-180 <= float(longitude) <= 180):
        raise fail("invalid-catalog")
    camera = _null_or_str(data["camera"])
    lens = _null_or_str(data["lens"])
    return {
        "width": width,
        "height": height,
        "orientation": orientation,
        "camera": camera,
        "lens": lens,
        "durationSec": duration,
        "latitude": latitude,
        "longitude": longitude,
    }


def read_location(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, LOCATION_KEYS)
    kind = _str(data["kind"])
    if kind not in LOCATION_KINDS:
        raise fail("invalid-catalog")
    role = _str(data["role"])
    if role not in ROLES:
        raise fail("invalid-catalog")
    component = _str(data["component"])
    if component not in COMPONENTS:
        raise fail("invalid-catalog")
    library_rel = _null_or_str(data["libraryRelativePath"])
    volume_serial = _null_or_str(data["volumeSerial"])
    path_from_root = _null_or_str(data["pathFromVolumeRoot"])
    if kind == "library-relative":
        if library_rel is None or volume_serial is not None or path_from_root is not None:
            raise fail("invalid-catalog")
    else:
        if library_rel is not None or volume_serial is None or path_from_root is None:
            raise fail("invalid-catalog")
    size = _int(data["sizeBytes"])
    if size < 0:
        raise fail("invalid-catalog")
    return {
        "sourceId": _str(data["sourceId"]),
        "role": role,
        "component": component,
        "kind": kind,
        "current": _bool(data["current"]),
        "libraryRelativePath": library_rel,
        "volumeSerial": volume_serial,
        "pathFromVolumeRoot": path_from_root,
        "lastKnownPath": _str(data["lastKnownPath"]),
        "sizeBytes": size,
        "modifiedAt": _str(data["modifiedAt"]),
        "sha256": _null_or_str(data["sha256"]),
    }


def read_rendition_status(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, RENDITION_STATUS_KEYS)
    out: dict[str, Any] = {}
    for key in RENDITION_STATUS_KEYS:
        status = _str(data[key])
        if status not in RENDITION_STATUSES:
            raise fail("invalid-catalog")
        out[key] = status
    return out


def read_renditions(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, RENDITION_KEYS)
    store = _str(data["store"])
    if store not in PREVIEW_STORES:
        raise fail("invalid-catalog")
    return {
        "store": store,
        "sourceId": _str(data["sourceId"]),
        "thumb": _null_or_str(data["thumb"]),
        "preview": _null_or_str(data["preview"]),
        "poster": _null_or_str(data["poster"]),
        "proxy": _null_or_str(data["proxy"]),
        "status": read_rendition_status(data["status"]),
    }


def _read_box(value: Any) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise fail("invalid-catalog")
    nums = []
    for item in value:
        if type(item) is bool or not isinstance(item, (int, float)):
            raise fail("invalid-catalog")
        nums.append(float(item))
    x, y, width, height = nums
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise fail("invalid-catalog")
    if x + width > 1 or y + height > 1:
        raise fail("invalid-catalog")
    return nums


def read_face(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"personId", "box"}
    if extra or "personId" not in data:
        raise fail("invalid-catalog")
    out: dict[str, Any] = {"personId": _str(data["personId"])}
    if "box" in data:
        box = _read_box(data["box"])
        if box is not None:
            out["box"] = box
    return out


def read_thing_ref(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    extra = set(data.keys()) - {"thingId", "box"}
    if extra or "thingId" not in data:
        raise fail("invalid-catalog")
    out: dict[str, Any] = {"thingId": _str(data["thingId"])}
    if "box" in data:
        box = _read_box(data["box"])
        if box is not None:
            out["box"] = box
    return out


def read_item(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, ITEM_KEYS)
    if data["schemaVersion"] != 1:
        raise fail("invalid-catalog")
    kind = _str(data["kind"])
    if kind not in ITEM_KINDS:
        raise fail("invalid-catalog")
    captured_source = _str(data["capturedAtSource"])
    if captured_source not in CAPTURE_SOURCES:
        raise fail("invalid-catalog")
    locations = data["locations"]
    if not isinstance(locations, list):
        raise fail("invalid-catalog")
    faces = data["faces"]
    things = data["things"]
    if not isinstance(faces, list) or not isinstance(things, list):
        raise fail("invalid-catalog")
    return {
        "schemaVersion": 1,
        "id": _str(data["id"]),
        "kind": kind,
        "filename": _str(data["filename"], allow_empty=True),
        "capturedAt": _str(data["capturedAt"]),
        "capturedAtSource": captured_source,
        "placeId": _null_or_str(data["placeId"]),
        "metadata": read_metadata(data["metadata"]),
        "contentIdentifier": _null_or_str(data["contentIdentifier"]),
        "locations": [read_location(item) for item in locations],
        "renditions": read_renditions(data["renditions"]),
        "faces": [read_face(item) for item in faces],
        "things": [read_thing_ref(item) for item in things],
    }


def ordered_item(item: dict[str, Any]) -> dict[str, Any]:
    item = read_item(item)
    return {key: item[key] for key in ITEM_KEYS}


def read_origin(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, ORIGIN_KEYS)
    return {
        "volumeSerial": _str(data["volumeSerial"]),
        "pathFromVolumeRoot": _str(data["pathFromVolumeRoot"], allow_empty=True),
        "lastKnownPath": _str(data["lastKnownPath"]),
    }


def read_file_entry(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, FILE_ENTRY_KEYS)
    state = _str(data["state"])
    if state not in FILE_STATES:
        raise fail("invalid-catalog")
    component = _str(data["component"])
    if component not in COMPONENTS:
        raise fail("invalid-catalog")
    size = _int(data["sizeBytes"])
    if size < 0:
        raise fail("invalid-catalog")
    return {
        "destination": _null_or_str(data["destination"]),
        "itemId": _str(data["itemId"]),
        "component": component,
        "sizeBytes": size,
        "modifiedAt": _str(data["modifiedAt"]),
        "sha256": _null_or_str(data["sha256"]),
        "state": state,
    }


def read_scan_error(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, SCAN_ERROR_KEYS)
    error = _str(data["error"])
    if error not in SCAN_FILE_ERRORS:
        raise fail("invalid-catalog")
    return {"path": _str(data["path"], allow_empty=True), "error": error}


def read_scan(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, SCAN_KEYS)
    state = _str(data["state"])
    if state not in SCAN_STATES:
        raise fail("invalid-catalog")
    added = _int(data["added"])
    skipped = _int(data["skipped"])
    if added < 0 or skipped < 0:
        raise fail("invalid-catalog")
    errors = data["errors"]
    if not isinstance(errors, list):
        raise fail("invalid-catalog")
    return {
        "state": state,
        "added": added,
        "skipped": skipped,
        "errors": [read_scan_error(item) for item in errors],
    }


def read_source(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, SOURCE_KEYS)
    if data["schemaVersion"] != 1:
        raise fail("invalid-catalog")
    mode = _str(data["mode"])
    if mode not in SOURCE_MODES:
        raise fail("invalid-catalog")
    preview = data["previewStore"]
    if preview is not None:
        if type(preview) is not str or preview not in PREVIEW_STORES:
            raise fail("invalid-catalog")
    files = data["files"]
    if not isinstance(files, dict):
        raise fail("invalid-catalog")
    file_map: dict[str, Any] = {}
    for key, entry in files.items():
        if type(key) is not str:
            raise fail("invalid-catalog")
        file_map[key] = read_file_entry(entry)
    return {
        "schemaVersion": 1,
        "id": _str(data["id"]),
        "name": _str(data["name"], allow_empty=True),
        "mode": mode,
        "origin": read_origin(data["origin"]),
        "copyRoot": _null_or_str(data["copyRoot"]),
        "previewStore": preview,
        "files": file_map,
        "scan": read_scan(data["scan"]),
    }


def ordered_source(source: dict[str, Any]) -> dict[str, Any]:
    source = read_source(source)
    return {key: source[key] for key in SOURCE_KEYS}


def read_place(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, PLACE_KEYS)
    if data["schemaVersion"] != 1:
        raise fail("invalid-catalog")
    name = _null_or_str(data["name"])
    if name is not None and name == "":
        raise fail("invalid-catalog")
    latitude = _null_or_number(data["latitude"])
    longitude = _null_or_number(data["longitude"])
    if (latitude is None) != (longitude is None):
        raise fail("invalid-catalog")
    if latitude is not None and not (-90 <= float(latitude) <= 90):
        raise fail("invalid-catalog")
    if longitude is not None and not (-180 <= float(longitude) <= 180):
        raise fail("invalid-catalog")
    return {
        "schemaVersion": 1,
        "id": _str(data["id"]),
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
    }


def ordered_place(place: dict[str, Any]) -> dict[str, Any]:
    place = read_place(place)
    return {key: place[key] for key in PLACE_KEYS}


def read_person(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, PERSON_KEYS)
    if data["schemaVersion"] != 1:
        raise fail("invalid-catalog")
    name = _null_or_str(data["name"])
    if name is not None and name == "":
        raise fail("invalid-catalog")
    return {
        "schemaVersion": 1,
        "id": _str(data["id"]),
        "name": name,
    }


def ordered_person(person: dict[str, Any]) -> dict[str, Any]:
    person = read_person(person)
    return {key: person[key] for key in PERSON_KEYS}


def read_thing(value: Any) -> dict[str, Any]:
    data = _require_dict(value)
    _exact_keys(data, THING_KEYS)
    if data["schemaVersion"] != 1:
        raise fail("invalid-catalog")
    name = _str(data["name"])
    aliases = data["aliases"]
    if not isinstance(aliases, list):
        raise fail("invalid-catalog")
    seen: set[str] = set()
    out_aliases: list[str] = []
    for alias in aliases:
        text = _str(alias)
        folded = text.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        out_aliases.append(text)
    return {
        "schemaVersion": 1,
        "id": _str(data["id"]),
        "name": name,
        "aliases": out_aliases,
    }


def ordered_thing(thing: dict[str, Any]) -> dict[str, Any]:
    thing = read_thing(thing)
    return {key: thing[key] for key in THING_KEYS}


def make_place(
    *,
    place_id: str,
    latitude: int | float,
    longitude: int | float,
    name: str | None = None,
) -> dict[str, Any]:
    return ordered_place(
        {
            "schemaVersion": 1,
            "id": place_id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
        }
    )


def empty_metadata() -> dict[str, Any]:
    return {key: None for key in METADATA_KEYS}


def renditions_for(kind: str, source_id: str, *, decode_error: bool = False) -> dict[str, Any]:
    if kind == "photo":
        status = {
            "thumb": "error" if decode_error else "queued",
            "preview": "error" if decode_error else "queued",
            "poster": "not-applicable",
            "proxy": "not-applicable",
        }
    elif kind == "video":
        status = {
            "thumb": "not-applicable",
            "preview": "not-applicable",
            "poster": "error" if decode_error else "queued",
            "proxy": "error" if decode_error else "queued",
        }
    else:
        status = {
            "thumb": "error" if decode_error else "queued",
            "preview": "error" if decode_error else "queued",
            "poster": "error" if decode_error else "queued",
            "proxy": "error" if decode_error else "queued",
        }
    return {
        "store": "with-server",
        "sourceId": source_id,
        "thumb": None,
        "preview": None,
        "poster": None,
        "proxy": None,
        "status": status,
    }


def make_location(
    *,
    source_id: str,
    role: str,
    component: str,
    volume_serial: str,
    path_from_volume_root: str,
    last_known_path: str,
    size_bytes: int,
    modified_at: str,
    sha256: str | None,
) -> dict[str, Any]:
    return {
        "sourceId": source_id,
        "role": role,
        "component": component,
        "kind": "volume",
        "current": True,
        "libraryRelativePath": None,
        "volumeSerial": volume_serial,
        "pathFromVolumeRoot": path_from_volume_root,
        "lastKnownPath": last_known_path,
        "sizeBytes": size_bytes,
        "modifiedAt": modified_at,
        "sha256": sha256,
    }


def make_item(
    *,
    item_id: str,
    kind: str,
    filename: str,
    captured_at: str,
    captured_at_source: str,
    content_identifier: str | None,
    locations: list[dict[str, Any]],
    renditions: dict[str, Any],
    place_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    faces: list[dict[str, Any]] | None = None,
    things: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return ordered_item(
        {
            "schemaVersion": 1,
            "id": item_id,
            "kind": kind,
            "filename": filename,
            "capturedAt": captured_at,
            "capturedAtSource": captured_at_source,
            "placeId": place_id,
            "metadata": metadata if metadata is not None else empty_metadata(),
            "contentIdentifier": content_identifier,
            "locations": locations,
            "renditions": renditions,
            "faces": faces or [],
            "things": things or [],
        }
    )


def make_source(
    *,
    source_id: str,
    name: str,
    mode: str,
    origin: dict[str, Any],
    copy_root: str | None = None,
    preview_store: str | None = None,
    files: dict[str, Any] | None = None,
    scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ordered_source(
        {
            "schemaVersion": 1,
            "id": source_id,
            "name": name,
            "mode": mode,
            "origin": origin,
            "copyRoot": copy_root,
            "previewStore": preview_store,
            "files": files or {},
            "scan": scan
            or {"state": "idle", "added": 0, "skipped": 0, "errors": []},
        }
    )


def make_file_entry(
    *,
    item_id: str,
    component: str,
    size_bytes: int,
    modified_at: str,
    sha256: str | None,
    state: str,
    destination: str | None = None,
) -> dict[str, Any]:
    return read_file_entry(
        {
            "destination": destination,
            "itemId": item_id,
            "component": component,
            "sizeBytes": size_bytes,
            "modifiedAt": modified_at,
            "sha256": sha256,
            "state": state,
        }
    )


def clone(obj: Any) -> Any:
    return copy.deepcopy(obj)


def read_scan_request(value: Any) -> dict[str, Any]:
    data = _require_dict(value, "invalid-argument")
    extra = set(data.keys()) - {"path", "mode", "previewStore"}
    if extra:
        raise fail("invalid-argument")
    path = data.get("path")
    if type(path) is not str or not path.strip():
        raise fail("invalid-argument")
    mode = data.get("mode")
    if mode is not None and (type(mode) is not str or mode not in SOURCE_MODES):
        raise fail("invalid-argument")
    preview = data.get("previewStore")
    if preview is not None and (type(preview) is not str or preview not in PREVIEW_STORES):
        raise fail("invalid-argument")
    return {"path": path, "mode": mode, "previewStore": preview}


def location_key(location: dict[str, Any]) -> tuple[str, str, str]:
    path = location.get("pathFromVolumeRoot") or location.get("libraryRelativePath") or ""
    return (location["sourceId"], path, location["component"])
