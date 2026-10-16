"""Settings defaults, validation, and canonical dump."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json, dumps_canonical, load_json
from library.errors import fail

SCHEMA_VERSION = 1

KEY_ORDER = (
    "schemaVersion",
    "previewStore",
    "unavailableItems",
    "addFolderDefault",
    "playProxies",
    "listenHost",
    "port",
    "thumbPx",
    "previewPx",
    "proxyWidth",
    "placeMatchMeters",
    "tourOrbitSec",
    "tourPictures",
    "tourPictureSec",
    "sort",
    "dir",
    "zoomLevel",
    "language",
    "faceMatchThreshold",
    "faceMinSidePx",
    "transcribeVideos",
)

ENUMS: dict[str, frozenset[str]] = {
    "previewStore": frozenset({"with-server", "with-source"}),
    "unavailableItems": frozenset({"show", "hide"}),
    "addFolderDefault": frozenset({"ask", "copy-here", "serve-from-there"}),
    "playProxies": frozenset({"days-and-all", "always", "off"}),
    "listenHost": frozenset({"127.0.0.1", "0.0.0.0"}),
    "sort": frozenset({"date", "location", "name"}),
    "dir": frozenset({"asc", "desc"}),
    "zoomLevel": frozenset({"years", "months", "days", "all"}),
    "language": frozenset({"en", "zh-Hans"}),
}

INT_KEYS = frozenset({"port", "thumbPx", "previewPx", "proxyWidth", "tourPictures", "faceMinSidePx"})
NUMBER_KEYS = frozenset({"placeMatchMeters", "tourOrbitSec", "tourPictureSec", "faceMatchThreshold"})
BOOL_KEYS = frozenset({"transcribeVideos"})
SETTING_KEYS = frozenset(KEY_ORDER[1:])

DEFAULTS: dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "previewStore": "with-server",
    "unavailableItems": "show",
    "addFolderDefault": "ask",
    "playProxies": "days-and-all",
    "listenHost": "127.0.0.1",
    "port": 8765,
    "thumbPx": 320,
    "previewPx": 1600,
    "proxyWidth": 480,
    "placeMatchMeters": 100,
    "tourOrbitSec": 8,
    "tourPictures": 5,
    "tourPictureSec": 3,
    "sort": "date",
    "dir": "desc",
    "zoomLevel": "years",
    "language": "en",
    "faceMatchThreshold": 0.8,
    "faceMinSidePx": 80,
    "transcribeVideos": True,
}


def _is_int(value: Any) -> bool:
    return type(value) is int


def _is_number(value: Any) -> bool:
    return type(value) is int or type(value) is float


def validate_value(key: str, value: Any) -> Any:
    if key == "schemaVersion":
        if value != SCHEMA_VERSION:
            raise fail("invalid-argument")
        return SCHEMA_VERSION
    if key not in SETTING_KEYS:
        raise fail("invalid-argument")
    if key in ENUMS:
        if type(value) is not str or value not in ENUMS[key]:
            raise fail("invalid-argument")
        return value
    if key in BOOL_KEYS:
        if type(value) is not bool:
            raise fail("invalid-argument")
        return value
    if key == "port":
        if not _is_int(value) or not (1 <= value <= 65535):
            raise fail("invalid-argument")
        return value
    if key in INT_KEYS:
        if not _is_int(value) or value <= 0:
            raise fail("invalid-argument")
        return value
    if key == "faceMatchThreshold":
        if not _is_number(value) or isinstance(value, bool):
            raise fail("invalid-argument")
        number = float(value)
        if not math.isfinite(number) or number <= 0 or number > 1:
            raise fail("invalid-argument")
        return number
    if key in NUMBER_KEYS:
        if not _is_number(value) or isinstance(value, bool):
            raise fail("invalid-argument")
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise fail("invalid-argument")
        return value
    raise fail("invalid-argument")


def ordered(settings: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in KEY_ORDER if key not in settings]
    extra = [key for key in settings if key not in KEY_ORDER]
    if missing or extra:
        raise fail("invalid-catalog")
    return {key: settings[key] for key in KEY_ORDER}


def validate_complete(settings: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, dict):
        raise fail("invalid-catalog")
    out: dict[str, Any] = {}
    for key in KEY_ORDER:
        if key not in settings:
            raise fail("invalid-catalog")
        out[key] = validate_value(key, settings[key])
    extra = [key for key in settings if key not in KEY_ORDER]
    if extra:
        raise fail("invalid-catalog")
    return ordered(out)


def merge_patch(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise fail("invalid-argument")
    merged = dict(current)
    for key, value in patch.items():
        if key == "schemaVersion":
            if value != SCHEMA_VERSION:
                raise fail("invalid-argument")
            continue
        merged[key] = validate_value(key, value)
    return validate_complete(merged)


def parse_cli_value(key: str, raw: str) -> Any:
    if key not in SETTING_KEYS:
        raise fail("invalid-argument")
    lowered = raw.lower()
    if key in BOOL_KEYS:
        if lowered == "true":
            return validate_value(key, True)
        if lowered == "false":
            return validate_value(key, False)
        raise fail("invalid-argument")
    if lowered in ("true", "false"):
        raise fail("invalid-argument")
    if key in ENUMS:
        return validate_value(key, raw)
    if key in INT_KEYS:
        if raw.startswith(("+",)) or not _digits(raw):
            raise fail("invalid-argument")
        try:
            number = int(raw, 10)
        except ValueError as exc:
            raise fail("invalid-argument") from exc
        return validate_value(key, number)
    if key in NUMBER_KEYS:
        try:
            if "." in raw or "e" in lowered:
                number: Any = float(raw)
            else:
                number = int(raw, 10)
        except ValueError as exc:
            raise fail("invalid-argument") from exc
        return validate_value(key, number)
    raise fail("invalid-argument")


def _digits(raw: str) -> bool:
    if not raw:
        return False
    return raw.isdigit()


def dumps_settings(settings: dict[str, Any]) -> str:
    return dumps_canonical(ordered(settings))


def settings_path(root: Path) -> Path:
    return root / "settings.json"


def fill_missing_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Accept a pre-language, pre-face-quality, or pre-transcribe file by filling new keys from defaults."""
    if not isinstance(data, dict):
        raise fail("invalid-catalog")
    extra = [key for key in data if key not in KEY_ORDER]
    if extra:
        raise fail("invalid-catalog")
    out = dict(data)
    for key in KEY_ORDER:
        if key not in out:
            out[key] = DEFAULTS[key]
    return out


def load_settings_file(root: Path) -> dict[str, Any]:
    path = settings_path(root)
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        raise fail("invalid-catalog") from exc
    except OSError as exc:
        raise fail("io-error") from exc
    try:
        return validate_complete(fill_missing_defaults(data))
    except Exception as exc:
        if getattr(exc, "code", None) == "invalid-argument":
            raise fail("invalid-catalog") from exc
        raise


def write_settings_file(root: Path, settings: dict[str, Any]) -> None:
    atomic_write_json(settings_path(root), ordered(settings))


def defaults() -> dict[str, Any]:
    return dict(DEFAULTS)
