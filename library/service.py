"""Application service shared by CLI and HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from library.atomic import recover_transactions, transact
from library.catalog_io import (
    item_read,
    iter_item_ids,
    iter_source_ids,
    load_item,
    load_source,
    source_read,
    try_load_item,
)
from library.errors import AppError, fail
from library.history import (
    load_entry,
    load_state,
    make_settings_entry,
    plan_append,
    plan_cursor_move,
)
from library.index import maybe_rebuild_missing, rebuild_sqlite
from library.lock import WriteLock
from library.records import read_scan_request
from library.scan import scan_serve_from_there
from library.settings import (
    defaults,
    dumps_settings,
    load_settings_file,
    merge_patch,
    ordered,
    parse_cli_value,
    settings_path,
    write_settings_file,
)


class Library:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def recover(self) -> dict[str, Any]:
        from library.catalog_io import finish_pending_publications

        recovered = recover_transactions(self.root)
        finish_pending_publications(self.root)
        maybe_rebuild_missing(self.root)
        return recovered

    def ensure_settings(self) -> dict[str, Any]:
        path = settings_path(self.root)
        if not path.exists():
            write_settings_file(self.root, defaults())
            return defaults()
        return load_settings_file(self.root)

    def settings_get(self) -> dict[str, Any]:
        self.recover()
        return ordered(self.ensure_settings())

    def settings_set(self, patch: dict[str, Any]) -> dict[str, Any]:
        self.recover()
        before = self.ensure_settings()
        after = merge_patch(before, patch)
        if dumps_settings(before) == dumps_settings(after):
            return after
        entry = make_settings_entry(self.root, before, after)
        changes = [
            {
                "path": "settings.json",
                "before": ordered(before),
                "after": ordered(after),
            }
        ]
        changes.extend(plan_append(self.root, entry))
        transact(self.root, changes, use_settings_barriers=True)
        return after

    def settings_set_cli(self, key: str, raw: str) -> dict[str, Any]:
        return self.settings_set({key: parse_cli_value(key, raw)})

    def undo(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        state = load_state(self.root)
        if state["cursor"] == 0:
            return {"ok": True}
        entry_id = state["entries"][state["cursor"] - 1]
        entry = load_entry(self.root, entry_id)
        file_changes = [
            {
                "path": change["path"],
                "before": _read_relative_json(self.root, change["path"]),
                "after": change["before"],
            }
            for change in entry["changes"]
        ]
        transact(
            self.root,
            plan_cursor_move(self.root, state["cursor"] - 1, file_changes),
        )
        return {"ok": True}

    def redo(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        state = load_state(self.root)
        if state["cursor"] >= len(state["entries"]):
            return {"ok": True}
        entry_id = state["entries"][state["cursor"]]
        entry = load_entry(self.root, entry_id)
        file_changes = [
            {
                "path": change["path"],
                "before": _read_relative_json(self.root, change["path"]),
                "after": change["after"],
            }
            for change in entry["changes"]
        ]
        transact(
            self.root,
            plan_cursor_move(self.root, state["cursor"] + 1, file_changes),
        )
        return {"ok": True}

    def history_len(self) -> int:
        return len(load_state(self.root)["entries"])

    def scan(self, body: dict[str, Any], on_progress=None) -> dict[str, Any]:
        self.recover()
        settings = self.ensure_settings()
        req = read_scan_request(body)
        mode = req["mode"]
        if mode is None:
            mode = settings["addFolderDefault"]
            if mode == "ask":
                raise fail("choice-required")
        if mode == "copy-here":
            raise fail("not-found")
        source = scan_serve_from_there(
            self.root,
            Path(req["path"]),
            preview_store=req["previewStore"],
            on_progress=on_progress,
        )
        return source_read(source, self.root)

    def sources_list(self) -> list[dict[str, Any]]:
        self.recover()
        self.ensure_settings()
        return [source_read(load_source(self.root, source_id), self.root) for source_id in iter_source_ids(self.root)]

    def items_list(self, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        self.recover()
        settings = self.ensure_settings()
        query = query or {}
        extra = set(query) - ITEM_QUERY_KEYS
        if extra:
            raise fail("invalid-argument")
        items = [item_read(load_item(self.root, item_id), self.root) for item_id in iter_item_ids(self.root)]
        items = [item for item in items if _item_visible(item, settings, query)]
        items = [item for item in items if _item_matches(item, query)]
        return _sort_items(items, query, settings)

    def groups_list(self, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        query = dict(query or {})
        extra = set(query) - ITEM_QUERY_KEYS - {"level"}
        if extra:
            raise fail("invalid-argument")
        level = query.pop("level", None)
        if level not in GROUP_LEVELS:
            raise fail("invalid-argument")
        items = self.items_list(query)
        groups: list[dict[str, Any]] = []
        buckets: dict[str, list[str]] = {}
        for item in items:
            key = calendar_group_key(item.get("capturedAt") or "", level)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = []
                buckets[key] = bucket
                groups.append({"key": key, "itemIds": bucket})
            bucket.append(item["id"])
        return groups

    def rebuild_index(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        rebuild_sqlite(self.root, use_barrier=True)
        return {"ok": True}

    def media(
        self,
        item_id: str,
        query: dict[str, str],
        range_header: str | None,
    ) -> tuple[int, bytes, str, list[tuple[str, str]]]:
        extra = set(query) - {"which", "component"}
        if extra:
            raise fail("invalid-argument")
        which = query.get("which")
        if which not in MEDIA_WHICH:
            raise fail("invalid-argument")
        component = query.get("component")
        if component is not None and component not in COMPONENTS:
            raise fail("invalid-argument")
        if not item_id:
            raise fail("not-found")
        item = try_load_item(self.root, item_id)
        if item is None:
            raise fail("not-found")
        if which == "original":
            data, content_type = self._original_bytes(item, component)
        else:
            data, content_type = self._rendition_bytes(item, which)
        return apply_range(data, content_type, range_header)

    def _original_bytes(
        self, item: dict[str, Any], component: str | None
    ) -> tuple[bytes, str]:
        from library.volumes import has_component_location, resolve_component_path

        if component is None:
            component = "motion" if item.get("kind") == "video" else "still"
        if not has_component_location(item, component):
            raise fail("invalid-argument")
        path = resolve_component_path(item, component, self.root)
        if path is None:
            raise fail("unavailable")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise fail("unavailable") from exc
        if not data:
            raise fail("unavailable")
        return data, original_content_type(path)

    def _rendition_bytes(self, item: dict[str, Any], which: str) -> tuple[bytes, str]:
        from library.paths import PathError, library_path

        rend = item.get("renditions") or {}
        status = (rend.get("status") or {}).get(which)
        relative = rend.get(which)
        if relative is None or status != "ready":
            raise fail("preview-unavailable")
        try:
            path = library_path(self.root, relative)
        except PathError as exc:
            raise fail("preview-unavailable") from exc
        if not path.is_file():
            raise fail("preview-unavailable")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise fail("preview-unavailable") from exc
        if not data:
            raise fail("preview-unavailable")
        if which in {"thumb", "preview", "poster"}:
            content_type = "image/webp"
        else:
            content_type = "video/mp4"
        return data, content_type


ITEM_QUERY_KEYS = frozenset(
    {"sort", "dir", "person", "place", "thing", "from", "to", "unavailable", "q", "scope"}
)
GROUP_LEVELS = frozenset({"years", "months", "days", "all"})
MEDIA_WHICH = frozenset({"thumb", "preview", "poster", "proxy", "original"})
COMPONENTS = frozenset({"still", "motion"})


def original_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    if suffix == ".bmp":
        return "image/bmp"
    if suffix == ".mp4":
        return "video/mp4"
    if suffix in {".mov", ".m4v"}:
        return "video/quicktime"
    if suffix == ".avi":
        return "video/x-msvideo"
    if suffix == ".mkv":
        return "video/x-matroska"
    if suffix == ".webm":
        return "video/webm"
    return "application/octet-stream"


def apply_range(
    data: bytes,
    content_type: str,
    range_header: str | None,
) -> tuple[int, bytes, str, list[tuple[str, str]]]:
    if not range_header or not range_header.strip():
        return 200, data, content_type, []
    start, end = parse_byte_range(range_header, len(data))
    sliced = data[start : end + 1]
    extra = [("Content-Range", f"bytes {start}-{end}/{len(data)}")]
    return 206, sliced, content_type, extra


def parse_byte_range(header: str, size: int) -> tuple[int, int]:
    text = header.strip()
    if "," in text or not text.startswith("bytes="):
        raise fail("invalid-range")
    spec = text[len("bytes=") :]
    if "-" not in spec:
        raise fail("invalid-range")
    left, right = spec.split("-", 1)
    if left == "" or right == "" or not left.isdigit() or not right.isdigit():
        raise fail("invalid-range")
    start = int(left)
    end = int(right)
    if end < start or start >= size:
        raise fail("invalid-range")
    if end >= size:
        end = size - 1
    return start, end


def _item_visible(item: dict[str, Any], settings: dict[str, Any], query: dict[str, str]) -> bool:
    raw = query.get("unavailable")
    if raw is None:
        include = settings["unavailableItems"] == "show"
    elif raw == "1":
        include = True
    elif raw == "0":
        include = False
    else:
        raise fail("invalid-argument")
    if include:
        return True
    return item["available"] is True


def _item_matches(item: dict[str, Any], query: dict[str, str]) -> bool:
    q = query.get("q")
    if q:
        needle = q.casefold()
        hay = item.get("filename") or ""
        if needle not in hay.casefold():
            return False
    return True


def calendar_group_key(captured_at: str, level: str) -> str:
    date = captured_at.split("T", 1)[0]
    if level == "years":
        return date[:4]
    if level == "months":
        return date[:7]
    return date


def _place_record(item: dict[str, Any]) -> dict[str, Any] | None:
    places = ((item.get("entities") or {}).get("places")) or []
    if places and isinstance(places[0], dict):
        return places[0]
    return None


def _sort_location(items: list[dict[str, Any]], reverse: bool) -> list[dict[str, Any]]:
    named: list[dict[str, Any]] = []
    unnamed: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for item in items:
        place = _place_record(item)
        name = place.get("name") if place else None
        lat = place.get("latitude") if place else None
        lon = place.get("longitude") if place else None
        if place is not None and type(name) is str and name:
            named.append(item)
        elif place is not None and lat is not None and lon is not None:
            unnamed.append(item)
        else:
            missing.append(item)

    def named_key(item: dict[str, Any]) -> tuple:
        place = _place_record(item) or {}
        return ((place.get("name") or "").casefold(), item.get("capturedAt") or "", item["id"])

    def unnamed_key(item: dict[str, Any]) -> tuple:
        place = _place_record(item) or {}
        return (
            float(place.get("latitude")),
            float(place.get("longitude")),
            item.get("capturedAt") or "",
            item["id"],
        )

    def missing_key(item: dict[str, Any]) -> tuple:
        return (item.get("capturedAt") or "", item["id"])

    named = sorted(named, key=named_key, reverse=reverse)
    unnamed = sorted(unnamed, key=unnamed_key, reverse=reverse)
    missing = sorted(missing, key=missing_key, reverse=reverse)
    return named + unnamed + missing


def _sort_items(
    items: list[dict[str, Any]],
    query: dict[str, str],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    sort = query.get("sort") or settings["sort"]
    direction = query.get("dir") or settings["dir"]
    if sort not in {"date", "location", "name"} or direction not in {"asc", "desc"}:
        raise fail("invalid-argument")
    reverse = direction == "desc"
    if sort == "location":
        return _sort_location(items, reverse)

    def key(item: dict[str, Any]) -> tuple:
        if sort == "name":
            return ((item.get("filename") or "").casefold(), item.get("capturedAt") or "", item["id"])
        return (item.get("capturedAt") or "", item["id"])

    return sorted(items, key=key, reverse=reverse)


def _read_relative_json(root: Path, relative: str) -> Any:
    from library.paths import library_path

    path = library_path(root, relative)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def with_write_lock(root: Path) -> WriteLock:
    return WriteLock(root)


def error_payload(code: str) -> bytes:
    return json.dumps({"error": code}, separators=(",", ":")).encode("utf-8")
