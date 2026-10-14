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
    load_places,
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

    def start_http_scan(self, body: dict[str, Any]) -> dict[str, Any]:
        from library.scan import start_scan_source

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
            source = start_scan_source(
                self.root,
                Path(req["path"]),
                mode,
                req["previewStore"],
            )
            return source_read(source, self.root)
        except Exception:
            self._scanning = False
            raise

    def finish_http_scan(self, body: dict[str, Any], source: dict[str, Any], on_progress=None, between=None) -> dict[str, Any]:
        from library.catalog_io import try_load_source

        try:
            req = read_scan_request(body)
            mode = source.get("mode") or req["mode"]
            current = try_load_source(self.root, source["id"]) or source
            if mode == "copy-here":
                finished = scan_copy_here(
                    self.root,
                    Path(req["path"]),
                    preview_store=req["previewStore"],
                    on_progress=on_progress,
                    between=between,
                    source=current,
                )
                return source_read(finished, self.root)
            finished = scan_serve_from_there(
                self.root,
                Path(req["path"]),
                preview_store=req["previewStore"],
                on_progress=on_progress,
                between=between,
                source=current,
            )
            return source_read(finished, self.root)
        finally:
            self._scanning = False

    def copy_here(self, source_id: str) -> dict[str, Any]:
        from library.copy import convert_linked_source
        from library.catalog_io import load_source

        self.recover()
        self.ensure_settings()
        if type(source_id) is not str or not source_id:
            raise fail("invalid-argument")
        source = load_source(self.root, source_id)
        if source["mode"] == "copy-here" and type(source.get("copyRoot")) is str and source["copyRoot"]:
            return source_read(source, self.root)
        self._assert_idle()
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
        from library.favorites import favorite_ids

        marked = favorite_ids(self.root)
        items = [
            item_read(load_item(self.root, item_id), self.root, marked)
            for item_id in iter_item_ids(self.root)
        ]
        items = [item for item in items if _item_visible(item, settings, query)]
        items = [item for item in items if _item_matches(item, query)]
        return _sort_items(items, query, settings)

    def set_favorite(self, item_id: str, favorite: bool) -> dict[str, Any]:
        from library.favorites import set_item_favorite

        self.recover(finish_pending=False)
        self.ensure_settings()
        return set_item_favorite(self.root, item_id, favorite)

    def places_list(self, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        self.recover()
        settings = self.ensure_settings()
        query = query or {}
        extra = set(query) - {"unavailable"}
        if extra:
            raise fail("invalid-argument")
        items = [item_read(load_item(self.root, item_id), self.root) for item_id in iter_item_ids(self.root)]
        items = [item for item in items if _item_visible(item, settings, query)]
        by_place: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            place_id = item.get("placeId")
            if type(place_id) is str and place_id:
                by_place.setdefault(place_id, []).append(item)
        out: list[dict[str, Any]] = []
        for place in load_places(self.root):
            latitude = place.get("latitude")
            longitude = place.get("longitude")
            if latitude is None or longitude is None:
                continue
            members = by_place.get(place["id"]) or []
            if not members:
                continue
            newest = sorted(
                members,
                key=lambda item: (item.get("capturedAt") or "", item["id"]),
                reverse=True,
            )[0]
            out.append(
                {
                    "id": place["id"],
                    "latitude": latitude,
                    "longitude": longitude,
                    "name": place.get("name"),
                    "itemCount": len(members),
                    "newestItemId": newest["id"],
                }
            )
        out.sort(key=lambda rec: rec["id"])
        return out

    def globe_tour(self, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        self.recover()
        settings = self.ensure_settings()
        query = query or {}
        extra = set(query) - {"unavailable"}
        if extra:
            raise fail("invalid-argument")
        cap = settings["tourPictures"]
        items = [item_read(load_item(self.root, item_id), self.root) for item_id in iter_item_ids(self.root)]
        items = [item for item in items if _item_visible(item, settings, query)]
        places_by_id = {place["id"]: place for place in load_places(self.root)}
        by_place: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            place_id = item.get("placeId")
            if type(place_id) is not str or not place_id:
                continue
            place = places_by_id.get(place_id)
            if place is None:
                continue
            if place.get("latitude") is None or place.get("longitude") is None:
                continue
            if not _item_tour_eligible(item, self.root):
                continue
            by_place.setdefault(place_id, []).append(item)
        decorated: list[tuple[str, str, dict[str, Any]]] = []
        for place_id, members in by_place.items():
            members_sorted = sorted(
                members,
                key=lambda item: (item.get("capturedAt") or "", item["id"]),
                reverse=True,
            )
            newest = members_sorted[0]
            decorated.append(
                (
                    newest.get("capturedAt") or "",
                    place_id,
                    {
                        "placeId": place_id,
                        "itemIds": [item["id"] for item in members_sorted[:cap]],
                    },
                )
            )
        decorated.sort(key=lambda row: row[1])
        decorated.sort(key=lambda row: row[0], reverse=True)
        return [row[2] for row in decorated]

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

    def favorite(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from library.favorites import parse_favorite_body

        return self.set_favorite(item_id, parse_favorite_body(payload))

    def reveal(self, item_id: str) -> dict[str, Any]:
        from library.favorites import open_containing_folder

        self.recover()
        self.ensure_settings()
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        if item.get("kind") == "video":
            component = "motion"
        else:
            component = "still"
        path = _readable_component_file(item, component, self.root)
        if path is None:
            raise fail("unavailable")
        opened = open_containing_folder(path)
        return {
            "path": str(path),
            "folder": str(path.parent),
            "opened": opened,
        }

    def open(self, item_id: str) -> dict[str, Any]:
        from library.favorites import open_file

        self.recover()
        self.ensure_settings()
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        if item.get("kind") == "video":
            component = "motion"
        else:
            component = "still"
        path = _readable_component_file(item, component, self.root)
        if path is None:
            raise fail("unavailable")
        opened = open_file(path)
        return {
            "path": str(path),
            "opened": opened,
        }

    def remove(self, item_id: str) -> dict[str, Any]:
        from library.remove import remove_item

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return remove_item(self.root, item_id)

    def delete_file(self, item_id: str) -> dict[str, Any]:
        from library.remove import delete_file

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return delete_file(self.root, item_id)

    def update(self) -> dict[str, Any]:
        from library.update import pull_latest

        return pull_latest()

    def people_merge(self, keep_id: str, drop_id: str) -> dict[str, Any]:
        from library.annotate import apply_people_merge

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return apply_people_merge(self.root, keep_id, drop_id)

    def setup_ml(self, kind: str) -> dict[str, Any]:
        from library.objects import setup_objects

        if kind != "objects":
            raise fail("invalid-argument")
        self.root.mkdir(parents=True, exist_ok=True)
        self.ensure_settings()
        return setup_objects(self.root)

    def analyze(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.objects import analyze_objects, read_analyze_payload

        self.recover(finish_pending=False)
        self.ensure_settings()
        parsed = read_analyze_payload(payload)
        item_id = parsed["itemId"] if parsed else None
        return analyze_objects(self.root, item_id)

    def analyze_status(self) -> dict[str, Any]:
        from library.objects import analyze_status

        self.recover(finish_pending=False)
        self.ensure_settings()
        return analyze_status(self.root)

    def analyze_step(self) -> bool:
        from library.objects import analyze_step as run_analyze_step

        if self._scanning:
            return False
        self.ensure_settings()
        return run_analyze_step(self.root)

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
    {
        "sort",
        "dir",
        "person",
        "place",
        "thing",
        "kind",
        "favorite",
        "from",
        "to",
        "unavailable",
        "q",
        "scope",
    }
)
ITEM_KINDS = frozenset({"photo", "video", "live"})
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


def _tour_slot(item: dict[str, Any]) -> str | None:
    kind = item.get("kind")
    if kind == "video":
        return "proxy"
    if kind in {"photo", "live"}:
        return "preview"
    return None


def _item_tour_eligible(item: dict[str, Any], root: Path) -> bool:
    which = _tour_slot(item)
    if which is None:
        return False
    rend = item.get("renditions") or {}
    status = (rend.get("status") or {}).get(which)
    relative = rend.get(which)
    if relative is None or status != "ready":
        return False
    try:
        path = rendition_abs(item, which, root)
    except Exception:
        return False
    return path is not None and path.is_file() and path.stat().st_size > 0


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
    kind = query.get("kind")
    if kind is not None:
        if type(kind) is not str or kind == "":
            raise fail("invalid-argument")
        kinds = {part.strip() for part in kind.split(",") if part.strip()}
        if not kinds or not kinds.issubset(ITEM_KINDS):
            raise fail("invalid-argument")
        if item.get("kind") not in kinds:
            return False
    raw_favorite = query.get("favorite")
    if raw_favorite is not None:
        if raw_favorite != "1":
            raise fail("invalid-argument")
        if item.get("favorite") is not True:
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
            if _date_query_match(captured, needle):
                matched = True
        if not matched:
            return False
    return True


def _date_query_match(captured: str, needle: str) -> bool:
    if type(captured) is not str or not captured or not needle:
        return False
    calendar = _norm_query(captured[:10])
    if len(needle) not in {4, 7, 10}:
        return False
    if len(needle) == 4 and needle.isdigit():
        return calendar.startswith(needle)
    if len(needle) == 7 and needle[4] == "-":
        return calendar.startswith(needle)
    if len(needle) == 10 and needle[4] == "-" and needle[7] == "-":
        return calendar == needle or calendar.startswith(needle)
    return False


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
