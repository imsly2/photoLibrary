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
)
from library.groups import LEVELS, groups_from_items
from library.errors import AppError, fail
from library.media import file_suffix
from library.renditions import drain_step as drain_queued_jpegs
from library.renditions import relocate as relocate_renditions
from library.renditions import rendition_abs, restore_relocate_files
from library.volumes import location_file, location_matches_stat
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
from library.scan import scan_copy_here, scan_serve_from_there
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
        self._scanning = False

    def recover(self, *, finish_pending: bool | None = None) -> dict[str, Any]:
        from library.catalog_io import finish_pending_publications

        recovered = recover_transactions(self.root)
        scanning = getattr(self, "_scanning", False)
        if finish_pending is None:
            finish_pending = not scanning
        if finish_pending:
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

    def _assert_idle(self) -> None:
        if self._scanning:
            raise fail("busy")

    def undo(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        self._assert_idle()
        state = load_state(self.root)
        if state["cursor"] == 0:
            return {"ok": True}
        entry_id = state["entries"][state["cursor"] - 1]
        entry = load_entry(self.root, entry_id)
        first_before: dict[str, Any] = {}
        for change in entry["changes"]:
            path = change["path"]
            if path not in first_before:
                first_before[path] = change["before"]
        file_changes = [
            {
                "path": path,
                "before": _read_relative_json(self.root, path),
                "after": before,
            }
            for path, before in first_before.items()
        ]
        transact(
            self.root,
            plan_cursor_move(self.root, state["cursor"] - 1, file_changes),
        )
        if entry.get("operation") == "relocate":
            restore_relocate_files(self.root, entry_id)
        return {"ok": True}

    def redo(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        self._assert_idle()
        state = load_state(self.root)
        if state["cursor"] >= len(state["entries"]):
            return {"ok": True}
        entry_id = state["entries"][state["cursor"]]
        entry = load_entry(self.root, entry_id)
        last_after: dict[str, Any] = {}
        for change in entry["changes"]:
            last_after[change["path"]] = change["after"]
        file_changes = [
            {
                "path": path,
                "before": _read_relative_json(self.root, path),
                "after": after,
            }
            for path, after in last_after.items()
        ]
        transact(
            self.root,
            plan_cursor_move(self.root, state["cursor"] + 1, file_changes),
        )
        return {"ok": True}

    def history_len(self) -> int:
        return len(load_state(self.root)["entries"])

    def scan(self, body: dict[str, Any], on_progress=None, between=None) -> dict[str, Any]:
        self.recover()
        settings = self.ensure_settings()
        self._assert_idle()
        req = read_scan_request(body)
        mode = req["mode"]
        if mode is None:
            mode = settings["addFolderDefault"]
            if mode == "ask":
                raise fail("choice-required")
        self._scanning = True
        try:
            if mode == "copy-here":
                source = scan_copy_here(
                    self.root,
                    Path(req["path"]),
                    preview_store=req["previewStore"],
                    on_progress=on_progress,
                    between=between,
                )
                return source_read(source, self.root)
            source = scan_serve_from_there(
                self.root,
                Path(req["path"]),
                preview_store=req["previewStore"],
                on_progress=on_progress,
                between=between,
            )
            return source_read(source, self.root)
        finally:
            self._scanning = False

    def copy_here(self, source_id: str) -> dict[str, Any]:
        from library.copy import convert_linked_source
        from library.catalog_io import load_source

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        if type(source_id) is not str or not source_id:
            raise fail("invalid-argument")
        source = load_source(self.root, source_id)
        if source["mode"] == "copy-here" and type(source.get("copyRoot")) is str and source["copyRoot"]:
            return source_read(source, self.root)
        source = convert_linked_source(self.root, source_id)
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
        if level not in LEVELS:
            raise fail("invalid-argument")
        items = self.items_list(query)
        return groups_from_items(items, level)

    def rebuild_index(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        self._assert_idle()
        rebuild_sqlite(self.root, use_barrier=True)
        return {"ok": True}

    def annotate(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from library.annotate import apply_annotate

        self.recover(finish_pending=False)
        self.ensure_settings()
        return apply_annotate(self.root, item_id, payload)

    def people_merge(self, keep_id: str, drop_id: str) -> dict[str, Any]:
        from library.annotate import apply_people_merge

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return apply_people_merge(self.root, keep_id, drop_id)

    def drain_step(self) -> bool:
        self.ensure_settings()
        return drain_queued_jpegs(self.root)

    def relocate(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return relocate_renditions(self.root)

    def media_resolve(self, item_id: str, query: dict[str, str]) -> dict[str, Any]:
        extra = set(query) - {"which", "component"}
        if extra:
            raise fail("invalid-argument")
        which = query.get("which")
        if which not in MEDIA_WHICH:
            raise fail("invalid-argument")
        component = query.get("component")
        if component is not None and component not in {"still", "motion"}:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        if which == "original":
            return self._resolve_original(item, component)
        return self._resolve_rendition(item, which)

    def _resolve_original(self, item: dict[str, Any], component: str | None) -> dict[str, Any]:
        if component == "motion":
            has_motion = any(loc.get("component") == "motion" for loc in item.get("locations") or [])
            if not has_motion:
                raise fail("invalid-argument")
            wanted = "motion"
        elif item.get("kind") == "video":
            wanted = "motion"
        else:
            wanted = "still"
        path = _readable_component_file(item, wanted, self.root)
        if path is None:
            raise fail("unavailable")
        return {"path": path, "content_type": original_content_type(path)}

    def _resolve_rendition(self, item: dict[str, Any], which: str) -> dict[str, Any]:
        rend = item.get("renditions") or {}
        status = (rend.get("status") or {}).get(which)
        relative = rend.get(which)
        if relative is None or status != "ready":
            raise fail("preview-unavailable")
        try:
            path = rendition_abs(item, which, self.root)
        except Exception as exc:
            raise fail("preview-unavailable") from exc
        if path is None or not path.is_file() or path.stat().st_size <= 0:
            raise fail("preview-unavailable")
        content_type = "video/mp4" if which == "proxy" else "image/webp"
        return {"path": path, "content_type": content_type}


ITEM_QUERY_KEYS = frozenset(
    {"sort", "dir", "person", "place", "thing", "from", "to", "unavailable", "q", "scope"}
)
MEDIA_WHICH = frozenset({"thumb", "preview", "poster", "proxy", "original"})


def original_content_type(path: Path) -> str:
    suffix = file_suffix(path)
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix in {".mp4", ".m4v"}:
        return "video/mp4"
    if suffix == ".mov":
        return "video/quicktime"
    if suffix == ".webm":
        return "video/webm"
    if suffix == ".avi":
        return "video/x-msvideo"
    if suffix == ".mkv":
        return "video/x-matroska"
    return "application/octet-stream"


def _readable_component_file(item: dict[str, Any], component: str, root: Path) -> Path | None:
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
        path = location_file(loc, root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return path
    return None


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


def _norm_query(value: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFC", value.strip()).casefold()


def _entity_name_match(record: dict[str, Any], token: str) -> bool:
    name = record.get("name")
    if type(name) is str and name and _norm_query(name) == _norm_query(token):
        return True
    return False


def _item_matches(item: dict[str, Any], query: dict[str, str]) -> bool:
    captured = item.get("capturedAt") or ""
    if "from" in query:
        if type(query["from"]) is not str or query["from"] == "":
            raise fail("invalid-argument")
        if captured < query["from"]:
            return False
    if "to" in query:
        if type(query["to"]) is not str or query["to"] == "":
            raise fail("invalid-argument")
        if captured >= query["to"]:
            return False
    entities = item.get("entities") or {}
    people = entities.get("people") or []
    places = entities.get("places") or []
    things = entities.get("things") or []
    if "person" in query:
        token = query["person"]
        if type(token) is not str or token == "":
            raise fail("invalid-argument")
        ids = {rec.get("id") for rec in people}
        if token not in ids and not any(_entity_name_match(rec, token) for rec in people):
            return False
    if "place" in query:
        raw = query["place"]
        if type(raw) is not str or raw == "":
            raise fail("invalid-argument")
        tokens = [part for part in raw.split(",") if part]
        if not tokens:
            raise fail("invalid-argument")
        place_id = item.get("placeId")
        matched = False
        for token in tokens:
            if token == place_id:
                matched = True
                break
            if any(rec.get("id") == token or _entity_name_match(rec, token) for rec in places):
                matched = True
                break
        if not matched:
            return False
    if "thing" in query:
        token = query["thing"]
        if type(token) is not str or token == "":
            raise fail("invalid-argument")
        ids = {rec.get("id") for rec in things}
        if token not in ids and not any(_entity_name_match(rec, token) for rec in things):
            return False
    q = query.get("q")
    if q:
        if type(q) is not str:
            raise fail("invalid-argument")
        if q == "":
            return True
        needle = _norm_query(q)
        scope = query.get("scope")
        if scope is not None and scope not in {"people", "places", "things"}:
            raise fail("invalid-argument")
        matched = False
        if scope in {None, "people"}:
            for rec in people:
                name = rec.get("name")
                if type(name) is str and name and needle in _norm_query(name):
                    matched = True
        if scope in {None, "places"}:
            for rec in places:
                name = rec.get("name")
                if type(name) is str and name and needle in _norm_query(name):
                    matched = True
        if scope in {None, "things"}:
            for rec in things:
                name = rec.get("name")
                if type(name) is str and name and needle in _norm_query(name):
                    matched = True
                for alias in rec.get("aliases") or []:
                    if type(alias) is str and alias and needle in _norm_query(alias):
                        matched = True
        if scope is None:
            filename = item.get("filename") or ""
            if needle in _norm_query(filename):
                matched = True
        if not matched:
            return False
    return True


def _item_place(item: dict[str, Any]) -> dict[str, Any] | None:
    places = (item.get("entities") or {}).get("places") or []
    if places and isinstance(places[0], dict):
        return places[0]
    return None


def _location_category(item: dict[str, Any]) -> int:
    place = _item_place(item)
    if place is not None and place.get("name"):
        return 0
    if place is not None and place.get("latitude") is not None and place.get("longitude") is not None:
        return 1
    metadata = item.get("metadata") or {}
    if metadata.get("latitude") is not None and metadata.get("longitude") is not None:
        return 1
    return 2


def _location_label_key(item: dict[str, Any]) -> tuple:
    place = _item_place(item)
    if place is not None and place.get("name"):
        return (str(place["name"]), 0.0, 0.0)
    if place is not None and place.get("latitude") is not None and place.get("longitude") is not None:
        return ("", float(place["latitude"]), float(place["longitude"]))
    metadata = item.get("metadata") or {}
    if metadata.get("latitude") is not None and metadata.get("longitude") is not None:
        return ("", float(metadata["latitude"]), float(metadata["longitude"]))
    return ("", 0.0, 0.0)


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
        items = sorted(items, key=lambda item: (item.get("capturedAt") or "", item["id"]), reverse=reverse)
        items = sorted(items, key=_location_label_key, reverse=reverse)
        items = sorted(items, key=_location_category)
        return items

    def key(item: dict[str, Any]) -> tuple:
        if sort == "name":
            return (item.get("filename") or "", item.get("capturedAt") or "", item["id"])
        return (item.get("capturedAt") or "", item["id"])

    items = sorted(items, key=key, reverse=reverse)
    return items


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
