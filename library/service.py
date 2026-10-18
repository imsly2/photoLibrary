"""Application service shared by CLI and HTTP."""

from __future__ import annotations

import json
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from library.atomic import load_json, recover_transactions, transact
from library.catalog_io import (
    item_read,
    iter_item_ids,
    iter_source_ids,
    load_item,
    load_places,
    load_source,
    source_read,
)
from library.groups import ARRANGE, LEVELS, groups_from_entities, groups_from_items
from library.errors import AppError, fail
from library.media import file_suffix
from library.renditions import drain_step as drain_queued_jpegs
from library.renditions import encoding as rendition_encoding
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
        self._jobs_paused = False
        self._inferring = False
        self._resets: set[str] = set()
        self._reset_checked = 0.0

    def take_folder_reset(self) -> str | None:
        """One source whose folder library was deleted while its folder is still
        there (F23: that folder starts over), or None. Checked every 2 s."""
        if self._scanning or self._inferring:
            return None
        now = time.monotonic()
        if now - self._reset_checked >= 2.0:
            self._reset_checked = now
            from library.item_store import vanished_sources

            self._resets.update(vanished_sources(self.root))
        return self._resets.pop() if self._resets else None

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
        current = load_settings_file(self.root)
        try:
            on_disk = load_json(path)
        except (OSError, json.JSONDecodeError):
            return current
        if not isinstance(on_disk, dict) or any(key not in on_disk for key in current):
            write_settings_file(self.root, current)
        return current

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
        if self._scanning or getattr(self, "_inferring", False):
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

    def start_http_rescan(self, source_id: str) -> tuple[dict[str, Any], Path]:
        from library.scan import start_rescan_source

        self.recover()
        self.ensure_settings()
        if type(source_id) is not str or not source_id:
            raise fail("invalid-argument")
        self._assert_idle()
        self._scanning = True
        try:
            source, path = start_rescan_source(self.root, source_id)
            return source_read(source, self.root), path
        except Exception:
            self._scanning = False
            raise

    def finish_http_rescan(
        self,
        source: dict[str, Any],
        path: Path,
        on_progress=None,
        between=None,
        io_context=nullcontext,
    ) -> dict[str, Any]:
        from library.catalog_io import try_load_source

        try:
            current = try_load_source(self.root, source["id"]) or source
            mode = current.get("mode") or source.get("mode")
            if mode == "copy-here":
                finished = scan_copy_here(
                    self.root,
                    path,
                    on_progress=on_progress,
                    between=between,
                    io_context=io_context,
                    source=current,
                )
                return source_read(finished, self.root)
            finished = scan_serve_from_there(
                self.root,
                path,
                on_progress=on_progress,
                between=between,
                io_context=io_context,
                source=current,
            )
            return source_read(finished, self.root)
        finally:
            self._scanning = False
            from library.activity import clear
            clear("scan")

    def rescan(self, source_id: str, on_progress=None, between=None) -> dict[str, Any]:
        source, path = self.start_http_rescan(source_id)
        return self.finish_http_rescan(source, path, on_progress=on_progress, between=between)

    def remove_source(self, source_id: str) -> dict[str, Any]:
        from library.sources import remove_source

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return remove_source(self.root, source_id)

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

    def finish_http_scan(self, body: dict[str, Any], source: dict[str, Any], on_progress=None, between=None, io_context=nullcontext) -> dict[str, Any]:
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
                    io_context=io_context,
                    source=current,
                )
                return source_read(finished, self.root)
            finished = scan_serve_from_there(
                self.root,
                Path(req["path"]),
                preview_store=req["previewStore"],
                on_progress=on_progress,
                between=between,
                io_context=io_context,
                source=current,
            )
            return source_read(finished, self.root)
        finally:
            self._scanning = False
            from library.activity import clear
            clear("scan")

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

    def read_ready(self, *, finish_pending: bool = True) -> None:
        """Catalog recovery that writers also need. Call this under the server lock."""
        if finish_pending:
            self.recover()
        else:
            self.recover(finish_pending=False)
        self.ensure_settings()

    def snapshot_catalog(self) -> dict[str, Any]:
        """Cheap consistent view. Call under the server lock, then build outside it."""
        from library.favorites import favorite_ids
        from library.item_index import iter_items
        from library.recent import load_recent_ids
        from library.read_cache import install_path_checks

        install_path_checks()
        self.recover()
        settings = dict(self.ensure_settings())
        return {
            "settings": settings,
            "items": list(iter_items(self.root)),
            "marked": favorite_ids(self.root),
            "recent": list(load_recent_ids(self.root)),
            "paused": bool(getattr(self, "_jobs_paused", False)),
        }

    def snapshot_sources(self) -> list[dict[str, Any]]:
        self.recover()
        self.ensure_settings()
        return [load_source(self.root, source_id) for source_id in iter_source_ids(self.root)]

    def sources_from_snapshot(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [source_read(source, self.root) for source in sources]

    def sources_list(self) -> list[dict[str, Any]]:
        return self.sources_from_snapshot(self.snapshot_sources())

    def items_from_snapshot(
        self,
        snap: dict[str, Any],
        query: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        from library.read_cache import cached_item_read
        from library.stacks import annotate_stacks

        query = query or {}
        extra = set(query) - ITEM_QUERY_KEYS
        if extra:
            raise fail("invalid-argument")
        settings = snap["settings"]
        marked = snap["marked"]
        items = [cached_item_read(item, self.root, marked) for item in snap["items"]]
        items = [item for item in items if _item_visible(item, settings, query)]
        items = [item for item in items if _item_matches(item, query)]
        items = [_attach_search_hint(item, query) for item in items]
        if "recent" in query:
            if query.get("recent") != "1":
                raise fail("invalid-argument")
            allowed = set(snap["recent"])
            items = [item for item in items if item.get("id") in allowed]
        return annotate_stacks(_sort_items(items, query, settings))

    def items_list(self, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        return self.items_from_snapshot(self.snapshot_catalog(), query)

    def duplicates_from_snapshot(self, snap: dict[str, Any]) -> dict[str, Any]:
        from library.duplicates import list_duplicate_groups

        return {"groups": list_duplicate_groups(self.items_from_snapshot(snap, {}))}

    def duplicates_list(self) -> dict[str, Any]:
        return self.duplicates_from_snapshot(self.snapshot_catalog())

    def set_favorite(self, item_id: str, favorite: bool) -> dict[str, Any]:
        from library.favorites import set_item_favorite

        self.recover(finish_pending=False)
        self.ensure_settings()
        return set_item_favorite(self.root, item_id, favorite)

    def set_favorites(self, item_ids: list[str], favorite: bool) -> dict[str, Any]:
        from library.favorites import set_items_favorite

        self.recover(finish_pending=False)
        self.ensure_settings()
        return set_items_favorite(self.root, item_ids, favorite)

    def places_list(
        self,
        query: dict[str, str] | None = None,
        snap: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from library.read_cache import cached_item_read

        if snap is None:
            snap = self.snapshot_catalog()
        settings = snap["settings"]
        query = query or {}
        extra = set(query) - {"unavailable"}
        if extra:
            raise fail("invalid-argument")
        items = [cached_item_read(item, self.root, snap["marked"]) for item in snap["items"]]
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

    def globe_tour(
        self,
        query: dict[str, str] | None = None,
        snap: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from library.read_cache import cached_item_read

        if snap is None:
            snap = self.snapshot_catalog()
        settings = snap["settings"]
        query = query or {}
        extra = set(query) - {"unavailable"}
        if extra:
            raise fail("invalid-argument")
        cap = settings["tourPictures"]
        items = [cached_item_read(item, self.root, snap["marked"]) for item in snap["items"]]
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

    def groups_from_snapshot(
        self,
        snap: dict[str, Any],
        query: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        query = dict(query or {})
        extra = set(query) - ITEM_QUERY_KEYS - {"level", "by"}
        if extra:
            raise fail("invalid-argument")
        by = query.pop("by", "date") or "date"
        if by not in ARRANGE:
            raise fail("invalid-argument")
        if by != "date":
            query.pop("level", None)
            return groups_from_entities(self.items_from_snapshot(snap, query), by)
        level = query.pop("level", None)
        if level not in LEVELS:
            raise fail("invalid-argument")
        return groups_from_items(self.items_from_snapshot(snap, query), level)

    def groups_list(self, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        return self.groups_from_snapshot(self.snapshot_catalog(), query)

    def tags_built(self, _snap: Any = None) -> dict[str, Any]:
        from library.tags import tags_index

        return tags_index(self.root)

    def tags_list(self) -> dict[str, Any]:
        self.read_ready()
        return self.tags_built()

    def tags_create(self, payload: Any) -> dict[str, Any]:
        from library.tags import create_tag

        self.recover(finish_pending=False)
        self.ensure_settings()
        return create_tag(self.root, payload)

    def tags_apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        from library.tags import apply_tags

        self.recover(finish_pending=False)
        self.ensure_settings()
        return apply_tags(self.root, payload)

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
        from library.favorites import existing_original, open_containing_folder

        self.recover()
        self.ensure_settings()
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        path = _reveal_original_path(item, self.root)
        if path is None:
            raise fail("unavailable")
        opened = open_containing_folder(path)
        return {
            "path": str(path),
            "folder": str(path.parent),
            "opened": opened,
        }

    def locate(self, item_id: str) -> dict[str, Any]:
        from library.favorites import open_containing_folder, open_folder

        self.recover()
        self.ensure_settings()
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        path = _reveal_original_path(item, self.root)
        if path is not None:
            opened = open_containing_folder(path)
            return {
                "path": str(path),
                "folder": str(path.parent),
                "opened": opened,
                "mode": "reveal",
            }
        folder = _last_known_folder(item)
        if folder is None:
            raise fail("unavailable")
        opened = open_folder(folder)
        return {
            "path": None,
            "folder": str(folder),
            "opened": opened,
            "mode": "locate",
        }

    def open(self, item_id: str) -> dict[str, Any]:
        from library.favorites import existing_original, open_file

        self.recover()
        self.ensure_settings()
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        path = _reveal_original_path(item, self.root)
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

    def remove_many(self, item_ids: list[str]) -> dict[str, Any]:
        from library.remove import remove_items

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return remove_items(self.root, item_ids)

    def move_items(self, body: dict[str, Any]) -> dict[str, Any]:
        from library.move import move_items, read_move_body

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        spec = read_move_body(body)
        return move_items(self.root, spec["itemIds"], spec)

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

    def people_split(
        self,
        person_id: str,
        item_id: str,
        box: list[float] | None = None,
    ) -> dict[str, Any]:
        from library.annotate import apply_people_split

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return apply_people_split(self.root, person_id, item_id, box)

    def people_built(self, _snap: Any = None) -> dict[str, Any]:
        from library.people_panel import people_index

        return people_index(self.root)

    def people_list(self) -> dict[str, Any]:
        self.read_ready()
        return self.people_built()

    def suggestions_built(self, _snap: Any = None) -> dict[str, Any]:
        from library.people_suggest import people_suggestions

        return people_suggestions(self.root)

    def people_suggestions(self) -> dict[str, Any]:
        self.read_ready()
        return self.suggestions_built()

    def people_not_same(self, a: str, b: str) -> dict[str, Any]:
        from library.people_suggest import remember_not_same

        self.recover()
        self.ensure_settings()
        return remember_not_same(self.root, a, b)

    def person_update(self, person_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from library.people_panel import apply_person_update

        self.recover()
        self.ensure_settings()
        return apply_person_update(self.root, person_id, payload)

    def jobs_from_snapshot(self, snap: dict[str, Any]) -> dict[str, Any]:
        from library.jobs import jobs_status

        return jobs_status(self.root, bool(snap.get("paused")), snap.get("items"))

    def jobs_get(self) -> dict[str, Any]:
        return self.jobs_from_snapshot(self.snapshot_catalog())

    def jobs_set(self, payload: dict[str, Any]) -> dict[str, Any]:
        from library.jobs import jobs_status, read_jobs_action

        action = read_jobs_action(payload)
        if action == "rerun-faces":
            from library.faces import request_faces_rescan

            self.recover()
            self.ensure_settings()
            request_faces_rescan(self.root)
            return jobs_status(self.root, getattr(self, "_jobs_paused", False))
        self._jobs_paused = action == "pause"
        return jobs_status(self.root, self._jobs_paused)

    def analyze_places(self) -> dict[str, Any]:
        from library.places import analyze_places as fill_place_names

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return fill_place_names(self.root)

    def setup_ml(self, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if kind == "objects":
            from library.objects import setup_objects

            self.root.mkdir(parents=True, exist_ok=True)
            self.ensure_settings()
            return setup_objects(self.root)
        if kind == "faces":
            return self.setup_faces(payload)
        if kind == "transcribe":
            from library.transcribe import setup_transcribe

            self.root.mkdir(parents=True, exist_ok=True)
            self.ensure_settings()
            return setup_transcribe(self.root)
        if kind == "aesthetic":
            from library.rating import setup_aesthetic

            self.root.mkdir(parents=True, exist_ok=True)
            self.ensure_settings()
            return setup_aesthetic(self.root, payload)
        raise fail("invalid-argument")

    def setup_faces(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.faces import setup_faces

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return setup_faces(self.root, payload)

    def faces_status(self) -> dict[str, Any]:
        from library.faces import faces_status

        self.recover()
        self.ensure_settings()
        return faces_status(self.root)

    def infer_faces(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.faces import infer_faces

        self.recover()
        self.ensure_settings()
        self._assert_idle()
        self._inferring = True
        try:
            return infer_faces(self.root, payload)
        finally:
            self._inferring = False

    def analyze(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.objects import analyze_objects, read_analyze_payload

        self.recover(finish_pending=False)
        self.ensure_settings()
        parsed = read_analyze_payload(payload)
        item_id = parsed["itemId"] if parsed else None
        return analyze_objects(self.root, item_id)

    def analyze_built(self, snap: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.objects import analyze_status

        items = None if snap is None else snap.get("items")
        return analyze_status(self.root, items)

    def analyze_status(self) -> dict[str, Any]:
        self.read_ready(finish_pending=False)
        return self.analyze_built()

    def transcribe(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.transcribe import read_transcribe_payload, transcribe_videos

        self.recover(finish_pending=False)
        self.ensure_settings()
        parsed = read_transcribe_payload(payload)
        return transcribe_videos(self.root, parsed.get("itemId"), force=bool(parsed.get("force")))

    def transcribe_built(self, _snap: Any = None) -> dict[str, Any]:
        from library.transcribe import transcribe_status

        return transcribe_status(self.root)

    def transcribe_status(self) -> dict[str, Any]:
        self.read_ready(finish_pending=False)
        return self.transcribe_built()

    def rate_photos(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.rating import rate_photos, read_rate_payload

        self.recover(finish_pending=False)
        self.ensure_settings()
        parsed = read_rate_payload(payload)
        return rate_photos(self.root, parsed.get("itemId"), force=bool(parsed.get("force")))

    def rate_built(self, _snap: Any = None) -> dict[str, Any]:
        from library.rating import rate_status

        return rate_status(self.root)

    def rate_status(self) -> dict[str, Any]:
        self.read_ready(finish_pending=False)
        return self.rate_built()

    def set_rating(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from library.rating import apply_user_rating, read_user_rating_body

        self.recover(finish_pending=False)
        self.ensure_settings()
        return apply_user_rating(self.root, item_id, read_user_rating_body(payload))

    def reset_rating_weights(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from library.rating import read_weights_body, reset_rating_weights

        self.recover(finish_pending=False)
        self.ensure_settings()
        read_weights_body(payload)
        return reset_rating_weights(self.root)

    def encode_step(self, *, io_context=nullcontext) -> bool:
        """One thumb/preview/video encode beside drain_step, for the extra
        encoder threads. Never runs faces, objects, rating or transcripts."""
        if self._jobs_paused or self._inferring:
            return False
        return drain_queued_jpegs(self.root, io_context=io_context, sweep=False)

    def drain_step(self, *, io_context=nullcontext) -> bool:
        if getattr(self, "_jobs_paused", False):
            return False
        if getattr(self, "_inferring", False):
            return False
        self.ensure_settings()
        if drain_queued_jpegs(self.root, io_context=io_context):
            return True
        if getattr(self, "_scanning", False) or rendition_encoding(self.root):
            return False
        def log_drain_error(stage: str, exc: Exception) -> None:
            from library.log import append_error

            append_error(self.root, "/api/jobs", f"processing-drain:{stage}:{type(exc).__name__}")

        force_faces = False
        try:
            from library.faces import faces_force_rescan

            force_faces = faces_force_rescan(self.root)
        except Exception as exc:
            log_drain_error("faces-force", exc)
            force_faces = False
        if force_faces:
            try:
                from library.faces import infer_faces_step

                if infer_faces_step(self.root):
                    return True
            except Exception as exc:
                log_drain_error("faces-force-step", exc)
        try:
            from library.places import analyze_places_step

            if analyze_places_step(self.root):
                return True
        except Exception as exc:
            log_drain_error("places", exc)
        if not force_faces:
            try:
                from library.faces import infer_faces_step

                if infer_faces_step(self.root):
                    return True
            except Exception as exc:
                log_drain_error("faces", exc)
        try:
            from library.objects import analyze_step as run_analyze_step

            if run_analyze_step(self.root):
                return True
        except Exception as exc:
            log_drain_error("objects", exc)
        try:
            from library.transcribe import transcribe_step

            if transcribe_step(self.root):
                return True
        except Exception as exc:
            log_drain_error("transcribe", exc)
        try:
            from library.rating import rate_step

            if rate_step(self.root, io_context=io_context):
                return True
        except Exception as exc:
            log_drain_error("rating", exc)
        from library.activity import clear as clear_activity

        clear_activity()
        return False

    def relocate(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        self._assert_idle()
        return relocate_renditions(self.root)

    def media_resolve(self, item_id: str, query: dict[str, str]) -> dict[str, Any]:
        extra = set(query) - {"which", "component", "box", "v"}
        if extra:
            raise fail("invalid-argument")
        which = query.get("which")
        if which not in MEDIA_WHICH:
            raise fail("invalid-argument")
        if "box" in query and which != "face":
            raise fail("invalid-argument")
        component = query.get("component")
        if component is not None and component not in {"still", "motion"}:
            raise fail("invalid-argument")
        item = load_item(self.root, item_id)
        if which == "original":
            return self._resolve_original(item, component)
        if which == "face":
            return self._resolve_face(item, query.get("box"))
        return self._resolve_rendition(item, which)

    def _resolve_face(self, item: dict[str, Any], box_raw: str | None) -> dict[str, Any]:
        from library.face_crop import face_crop_cache_path, parse_face_box, write_face_crop

        box = parse_face_box(box_raw)
        source = _readable_component_file(item, "still", self.root)
        if source is None or not source.is_file():
            source = None
            for which in ("preview", "thumb"):
                try:
                    path = rendition_abs(item, which, self.root)
                except Exception:
                    path = None
                if path is not None and path.is_file() and path.stat().st_size > 0:
                    source = path
                    break
        if source is None:
            raise fail("preview-unavailable")
        dest = face_crop_cache_path(self.root, str(item.get("id") or ""), box, source)
        try:
            fresh = dest.is_file() and dest.stat().st_mtime >= source.stat().st_mtime
        except OSError:
            fresh = False
        if not fresh:
            if not write_face_crop(source, dest, box):
                raise fail("preview-unavailable")
        return {"path": dest, "content_type": "image/webp"}

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
        try:
            path = rendition_abs(item, which, self.root)
        except Exception as exc:
            raise fail("preview-unavailable") from exc
        if path is None or not path.is_file() or path.stat().st_size <= 0:
            if ((item.get("renditions") or {}).get("status") or {}).get(which) == "ready":
                from library.renditions import note_missing

                note_missing(self.root)
            raise fail("preview-unavailable")
        content_type = "video/mp4" if which in {"proxy", "playback"} else "image/webp"
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
        "source",
        "recent",
        "minStars",
        "pick",
        "hideRejects",
        "flag",
    }
)
ITEM_KINDS = frozenset({"photo", "video", "live"})
MEDIA_WHICH = frozenset({"thumb", "preview", "poster", "proxy", "playback", "original", "face"})


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


def _item_component(item: dict[str, Any]) -> str:
    if item.get("kind") == "video":
        return "motion"
    return "still"


def _last_known_folder(item: dict[str, Any]) -> Path | None:
    from library.favorites import existing_folder

    candidates = [loc for loc in item.get("locations") or [] if loc.get("current") is True]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("lastKnownPath") or "",
        )
    )
    for loc in candidates:
        last = loc.get("lastKnownPath")
        if type(last) is not str or not last:
            continue
        folder = existing_folder(Path(last).parent)
        if folder is not None:
            return folder
    return None


def _last_known_original(item: dict[str, Any], component: str) -> Path | None:
    from library.favorites import existing_original

    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == component
    ]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("lastKnownPath") or "",
        )
    )
    for loc in candidates:
        last = loc.get("lastKnownPath")
        if type(last) is not str or not last:
            continue
        found = existing_original(Path(last))
        if found is not None:
            return found
    return None


def _reveal_original_path(item: dict[str, Any], root: Path) -> Path | None:
    from library.favorites import existing_original

    component = _item_component(item)
    raw = _readable_component_file(item, component, root)
    path = existing_original(raw) if raw is not None else None
    if path is not None:
        return path
    return _last_known_original(item, component)


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
    for alias in record.get("aliases") or []:
        if type(alias) is str and alias and _norm_query(alias) == _norm_query(token):
            return True
    return False


def _entity_token_match(records: list[dict[str, Any]], token: str) -> bool:
    ids = {rec.get("id") for rec in records}
    if token in ids:
        return True
    return any(_entity_name_match(rec, token) for rec in records)


def _all_tokens_match(records: list[dict[str, Any]], token: str) -> bool:
    if type(token) is not str or token == "":
        raise fail("invalid-argument")
    if "," in token:
        tokens = [part for part in token.split(",") if part]
        if not tokens:
            raise fail("invalid-argument")
        return all(_entity_token_match(records, part) for part in tokens)
    return _entity_token_match(records, token)


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
        if not _all_tokens_match(people, query["person"]):
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
        if not _all_tokens_match(things, query["thing"]):
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
            if needle in _UNNAMED_LABELS and any(
                isinstance(rec, dict) and not rec.get("name") for rec in people
            ):
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
            if _label_query_match(item, needle):
                matched = True
            if _transcript_query_match(item, q):
                matched = True
        if not matched:
            return False
    source = query.get("source")
    if source is not None:
        if type(source) is not str or source == "":
            raise fail("invalid-argument")
        locs = item.get("locations") or []
        if not any(isinstance(loc, dict) and loc.get("sourceId") == source for loc in locs):
            return False
    from library.rating import quality_view

    rating = item.get("rating") if isinstance(item.get("rating"), dict) else quality_view(item)
    raw_min = query.get("minStars")
    if raw_min is not None:
        if type(raw_min) is not str or not raw_min.isdigit():
            raise fail("invalid-argument")
        minimum = int(raw_min, 10)
        if minimum < 1 or minimum > 5:
            raise fail("invalid-argument")
        stars = rating.get("stars")
        if type(stars) is not int or stars < minimum:
            return False
    raw_pick = query.get("pick")
    if raw_pick is not None:
        if raw_pick != "1":
            raise fail("invalid-argument")
        if rating.get("pick") is not True:
            return False
    raw_hide = query.get("hideRejects")
    if raw_hide is not None:
        if raw_hide not in {"0", "1"}:
            raise fail("invalid-argument")
        if raw_hide == "1" and rating.get("reject") is True:
            return False
    raw_flag = query.get("flag")
    if raw_flag is not None:
        if raw_flag not in {"blurry", "too-dark", "too-bright"}:
            raise fail("invalid-argument")
        flags = rating.get("flags") or []
        if raw_flag not in flags:
            return False
    return True


_UNNAMED_LABELS = frozenset({"unnamed", "未命名", "unknown", "未知"})
_NO_PLACE_LABELS = frozenset({"no place", "无地点", "no location", "无位置"})
_UNTAGGED_LABELS = frozenset({"untagged", "无标签"})


def _label_query_match(item: dict[str, Any], needle: str) -> bool:
    if needle in _UNNAMED_LABELS:
        people = (item.get("entities") or {}).get("people") or []
        return any(not rec.get("name") for rec in people if isinstance(rec, dict))
    if needle in _NO_PLACE_LABELS:
        places = (item.get("entities") or {}).get("places") or []
        return not places
    if needle in _UNTAGGED_LABELS:
        things = (item.get("entities") or {}).get("things") or []
        return not things
    return False


def _transcript_query_match(item: dict[str, Any], needle: str) -> bool:
    from library.transcribe import transcript_search_hit

    return transcript_search_hit(item, needle) is not None


def _attach_search_hint(item: dict[str, Any], query: dict[str, str]) -> dict[str, Any]:
    q = query.get("q")
    if type(q) is not str or q == "":
        return item
    from library.transcribe import transcript_search_hit

    hit = transcript_search_hit(item, q)
    if hit is None:
        return item
    out = dict(item)
    out["saidInVideo"] = hit
    return out


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
    if sort not in {"date", "location", "name", "rating"} or direction not in {"asc", "desc"}:
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
        if sort == "rating":
            rating = item.get("rating") if isinstance(item.get("rating"), dict) else {}
            stars = rating.get("stars")
            pick = 1 if rating.get("pick") is True else 0
            suggested = rating.get("suggested")
            return (
                stars if type(stars) is int else 0,
                pick,
                suggested if type(suggested) is int else 0,
                item.get("capturedAt") or "",
                item["id"],
            )
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
