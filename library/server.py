"""HTTP server: bind, routes, recovery before serving, lock for life."""

from __future__ import annotations

import errno
from contextlib import contextmanager
import json
import os
import socket
import select
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from library.atomic import atomic_write_json
from library.errors import AppError, fail
from library.httpjson import encode, request_json
from library.lock import FairLock, WriteLock
from library.log import append_error
from library.paths import normalize_root, root_text, roots_equal
from library import processing_log
from library.service import Library

WEB_DIR = Path(__file__).resolve().parent / "web"
RUNTIME_NAME = "runtime.json"


@contextmanager
def unlocked_io(lock):
    """Use only around pure original reads or detached derivative computation."""
    lock.release()
    try:
        yield
    finally:
        waited = time.perf_counter()
        lock.acquire()
        processing_log.note_lock_wait(time.perf_counter() - waited)


def _media_cache(which: str | None, mtime_ns: int, size: int) -> tuple[str, str | None]:
    etag = '"%x-%x"' % (mtime_ns, size)
    if which in {"thumb", "camera", "preview", "poster", "face", "proxy", "playback"}:
        return "private, no-cache", etag
    return "no-store", None


def _query_map(query: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, values in parse_qs(query, keep_blank_values=True).items():
        if len(values) != 1:
            raise fail("invalid-argument")
        out[key] = values[0]
    return out


def _face_time_route(route: str) -> tuple[str, str, str | None] | None:
    prefix = "/api/people/"
    if not route.startswith(prefix):
        return None
    parts = [part for part in route[len(prefix) :].split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    if len(parts) == 2 and parts[1] in {"timeline", "film"}:
        return parts[0], parts[1], None
    if len(parts) == 3 and parts[1] == "frame":
        return parts[0], "frame", parts[2]
    return None


def parse_byte_range(header: str | None, length: int) -> tuple[int, int] | None:
    if header is None or header == "":
        return None
    if not header.startswith("bytes="):
        raise fail("invalid-range")
    spec = header[6:]
    if "," in spec or spec == "" or "-" not in spec:
        raise fail("invalid-range")
    start_s, end_s = spec.split("-", 1)
    if start_s == "":
        try:
            suffix = int(end_s)
        except ValueError as exc:
            raise fail("invalid-range") from exc
        if suffix <= 0 or length <= 0:
            raise fail("invalid-range")
        start = max(0, length - suffix)
        return start, length - 1
    try:
        start = int(start_s)
    except ValueError as exc:
        raise fail("invalid-range") from exc
    if start < 0 or start >= length:
        raise fail("invalid-range")
    if end_s == "":
        return start, length - 1
    try:
        end = int(end_s)
    except ValueError as exc:
        raise fail("invalid-range") from exc
    if end < start:
        raise fail("invalid-range")
    if end >= length:
        end = length - 1
    return start, end


def _is_client_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True
    if isinstance(exc, OSError):
        winerror = getattr(exc, "winerror", None)
        if winerror == 10053:
            return True
        if exc.errno in {errno.EPIPE, errno.ECONNRESET, errno.ECONNABORTED}:
            return True
    return False


def _scan_progress(kind: str, rel: str) -> None:
    processing_log.note_read(kind)
    print(f"{kind} {rel}", flush=True)


def start_rescan_worker(lock: threading.Lock, library: Library, source_id: str) -> dict[str, Any]:
    """Start one background rescan. The caller holds ``lock``; returns the source."""
    source, scan_path = library.start_http_rescan(source_id)

    def rescan_worker() -> None:
        lock.acquire()
        try:
            with processing_log.scan(library.root, str(scan_path)):
                library.finish_http_rescan(
                    source,
                    scan_path,
                    on_progress=_scan_progress,
                    between=lambda: _pause_for_readers(lock),
                    io_context=lambda: unlocked_io(lock),
                )
        except Exception as exc:
            traceback.print_exc()
            append_error(library.root, f"/api/sources/{source_id}/rescan", f"rescan-worker:{type(exc).__name__}")
            library._scanning = False
        finally:
            lock.release()

    threading.Thread(target=rescan_worker, name="library-rescan", daemon=True).start()
    return source


def _pause_for_readers(lock: threading.Lock) -> None:
    """Let other requests and the drain thread take the catalog lock."""
    profile = bool(os.environ.get("LIBRARY_PROFILE_SCAN", "").strip())
    started = time.perf_counter() if profile else 0.0
    lock.release()
    try:
        time.sleep(0)
        slept = time.perf_counter()
    finally:
        lock.acquire()
        processing_log.note_lock_wait(time.perf_counter() - slept)
        if profile:
            from library.scan import note_scan_yield

            note_scan_yield(slept - started, time.perf_counter() - slept)


def listen_url(host: str, port: int) -> str:
    display = "127.0.0.1" if host == "0.0.0.0" else host
    return f"http://{display}:{port}/"


def runtime_record(root: Path, pid: int, url: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "pid": pid,
        "root": root_text(root),
        "url": url,
    }


def _connect_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", ""} else host


def tcp_occupied(host: str, port: int) -> bool:
    try:
        with socket.create_connection((_connect_host(host), port), 0.4):
            return True
    except OSError:
        return False


def probe_listener(host: str, port: int) -> tuple[Any, Any] | None:
    display = _connect_host(host)
    base = f"http://{display}:{port}"
    try:
        health_status, health = request_json(base + "/api/health", timeout=0.8)
        runtime_status, runtime = request_json(base + "/api/runtime", timeout=0.8)
    except OSError:
        return None
    return (health_status, health), (runtime_status, runtime)


def matching_root_url(root: Path, host: str, port: int) -> str | None:
    if not tcp_occupied(host, port):
        return None
    probed = probe_listener(host, port)
    if probed is None:
        raise fail("port-in-use")
    (health_status, health), (runtime_status, runtime) = probed
    if (
        health_status == 200
        and health == {"ok": True}
        and runtime_status == 200
        and isinstance(runtime, dict)
        and runtime.get("schemaVersion") == 1
        and roots_equal(runtime.get("root", ""), root)
        and isinstance(runtime.get("url"), str)
    ):
        return runtime["url"]
    raise fail("port-in-use")


class LibraryHandler(BaseHTTPRequestHandler):
    library: Library
    lock: threading.Lock
    host: str
    port: int
    url: str
    static_root: Path

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        allowed = {
            f"http://{self.host}:{self.port}",
            f"http://127.0.0.1:{self.port}",
        }
        if self.host == "0.0.0.0":
            allowed.add(f"http://0.0.0.0:{self.port}")
        return origin.rstrip("/") in {item.rstrip("/") for item in allowed}

    def _require_idle(self) -> None:
        if getattr(self.library, "_scanning", False) or getattr(
            self.library, "_inferring", False
        ):
            raise fail("busy")

    def _catalog_read(self, route: str, snapshot, build) -> None:
        """Take a consistent snapshot under the catalog lock, then build outside it."""
        from library.lock_trace import Hold

        with Hold(self.lock, route):
            snap = snapshot()
        self._send_json(200, build(snap))

    def _items_stream(self, query: dict[str, str]) -> None:
        from library.lock_trace import Hold

        with Hold(self.lock, "/api/items/stream"):
            snap = self.library.snapshot_catalog()
        # Eager metadata validation/order runs before headers; browser projection
        # stays lazy and never holds the catalog lock or waits for later records.
        rows = self.library.items_iter_from_snapshot(snap, query)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        if self.command == "HEAD":
            return

        def frame(body):
            self.wfile.write(encode(body) + b"\n")
            self.wfile.flush()

        try:
            frame({"type": "start"})
            count = 0
            while True:
                if select.select([self.connection], [], [], 0)[0]:
                    if not self.connection.recv(1, socket.MSG_PEEK):
                        return
                try:
                    item = next(rows)
                except StopIteration:
                    break
                frame({"type": "item", "item": item})
                count += 1
            frame({"type": "done", "count": count})
        except Exception as exc:
            if _is_client_disconnect(exc):
                return
            code = exc.code if isinstance(exc, AppError) else "internal-error"
            try:
                append_error(self.library.root, "/api/items/stream", code)
            except Exception:
                pass
            try:
                frame({"type": "error", "error": code})
            except Exception as send_exc:
                if not _is_client_disconnect(send_exc):
                    try:
                        append_error(self.library.root, "/api/items/stream", "stream-write-failed")
                    except Exception:
                        pass

    def _yield_scan(self) -> None:
        _pause_for_readers(self.lock)

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        cache_control: str = "no-store",
        etag: str | None = None,
    ) -> None:
        if etag and (self.headers.get("If-None-Match") or "") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache_control)
            self.end_headers()
            return
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status: int, obj: Any) -> None:
        self._send(status, encode(obj), "application/json")

    def _error(self, code: str, status: int | None = None) -> None:
        from library.errors import HTTP_STATUS

        http_status = status if status is not None else HTTP_STATUS[code]
        parsed = urlparse(self.path)
        logged = parsed.path + (("?" + parsed.query) if parsed.query else "")
        append_error(self.library.root, logged, code)
        self._send_json(http_status, {"error": code})

    def _read_json(self) -> Any:
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype and ctype != "application/json":
            raise fail("invalid-argument")
        length = int(self.headers.get("Content-Length") or "0")
        if length < 0 or length > 1_000_000:
            raise fail("invalid-argument")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise fail("invalid-argument") from exc

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_HEAD(self) -> None:
        self._dispatch("HEAD")

    def _dispatch(self, method: str) -> None:
        from library.volumes import volume_lookup_scope

        with volume_lookup_scope():
            self._dispatch_request(method)

    def _dispatch_request(self, method: str) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            if method in {"PUT", "POST"} and not self._origin_ok():
                raise fail("invalid-argument")
            if route == "/api/health" and method in {"GET", "HEAD"}:
                self._send_json(200, {"ok": True})
                return
            if route == "/api/version" and method in {"GET", "HEAD"}:
                from library.version import version_payload

                self._send_json(200, version_payload())
                return
            if route == "/api/runtime" and method in {"GET", "HEAD"}:
                self._send_json(
                    200,
                    runtime_record(self.library.root, os.getpid(), self.url),
                )
                return
            if route == "/api/settings" and method in {"GET", "HEAD"}:
                self._catalog_read("/api/settings", self.library.settings_get, lambda body: body)
                return
            if route == "/api/settings" and method == "PUT":
                patch = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.settings_set(patch))
                return
            if route == "/api/undo" and method == "POST":
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.undo())
                return
            if route == "/api/redo" and method == "POST":
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.redo())
                return
            if route == "/api/sources" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/sources",
                    self.library.snapshot_sources,
                    self.library.sources_from_snapshot,
                )
                return
            if route == "/api/sources" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._require_idle()
                    source = self.library.start_http_scan(body)
                lock = self.lock
                library = self.library

                def yield_scan() -> None:
                    _pause_for_readers(lock)

                def scan_worker() -> None:
                    lock.acquire()
                    try:
                        with processing_log.scan(library.root, str(body.get("path") or source.get("name") or "")):
                            library.finish_http_scan(
                                body,
                                source,
                                on_progress=_scan_progress,
                                between=yield_scan,
                                io_context=lambda: unlocked_io(lock),
                            )
                    except Exception as exc:
                        traceback.print_exc()
                        append_error(library.root, "/api/sources", f"scan-worker:{type(exc).__name__}")
                        library._scanning = False
                    finally:
                        lock.release()

                threading.Thread(target=scan_worker, name="library-scan", daemon=True).start()
                self._send_json(202, source)
                return
            if route == "/api/pick-folder" and method == "POST":
                self._read_json()
                from library.picker import pick_folder

                chosen = pick_folder()
                self._send_json(200, {"path": chosen})
                return
            if route == "/api/update" and method == "GET":
                from library.app_update import update_status

                self._send_json(200, update_status())
                return
            if route == "/api/update" and method == "POST":
                self._read_json()
                from library.restart import attach_restart_plan

                payload = self.library.update()
                payload = attach_restart_plan(self.library.root, payload)
                self._send_json(200, payload)
                return
            if (
                route.startswith("/api/sources/")
                and route.endswith("/copy-here")
                and method == "POST"
            ):
                source_id = route[len("/api/sources/") : -len("/copy-here")]
                if not source_id or "/" in source_id:
                    raise fail("not-found")
                self._read_json()
                with self.lock:
                    self._send_json(202, self.library.copy_here(source_id))
                return
            if (
                route.startswith("/api/sources/")
                and route.endswith("/rescan")
                and method == "POST"
            ):
                source_id = route[len("/api/sources/") : -len("/rescan")]
                if not source_id or "/" in source_id:
                    raise fail("not-found")
                self._read_json()
                with self.lock:
                    self._require_idle()
                    source = start_rescan_worker(self.lock, self.library, source_id)
                self._send_json(202, source)
                return
            if (
                route.startswith("/api/sources/")
                and route.endswith("/remove")
                and method == "POST"
            ):
                source_id = route[len("/api/sources/") : -len("/remove")]
                if not source_id or "/" in source_id:
                    raise fail("not-found")
                self._read_json()
                with self.lock:
                    self._send_json(200, self.library.remove_source(source_id))
                return
            if route == "/api/items/stream" and method in {"GET", "HEAD"}:
                self._items_stream(_query_map(parsed.query))
                return
            if route == "/api/items" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                self._catalog_read(
                    "/api/items",
                    self.library.snapshot_catalog,
                    lambda snap: self.library.items_from_snapshot(snap, query),
                )
                return
            if route == "/api/duplicates" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/duplicates",
                    self.library.snapshot_catalog,
                    self.library.duplicates_from_snapshot,
                )
                return
            if route == "/api/items/tags" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.tags_apply(body))
                return
            if route == "/api/items/favorite" and method == "POST":
                from library.favorites import read_batch_favorite_body

                body = read_batch_favorite_body(self._read_json())
                with self.lock:
                    self._send_json(
                        200,
                        self.library.set_favorites(body["itemIds"], body["favorite"]),
                    )
                return
            if route == "/api/items/remove" and method == "POST":
                from library.remove import read_batch_remove_body

                ids = read_batch_remove_body(self._read_json())
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.remove_many(ids))
                return
            if route == "/api/items/move" and method == "POST":
                body = self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.move_items(body))
                return
            if route == "/api/tags" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/tags",
                    self.library.read_ready,
                    self.library.tags_built,
                )
                return
            if route == "/api/tags" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.tags_create(body))
                return
            if route == "/api/places/analyze" and method == "POST":
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.analyze_places())
                return
            if route == "/api/places" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                self._catalog_read(
                    "/api/places",
                    self.library.snapshot_catalog,
                    lambda snap: self.library.places_list(query, snap),
                )
                return
            if route == "/api/globe/tour" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                self._catalog_read(
                    "/api/globe/tour",
                    self.library.snapshot_catalog,
                    lambda snap: self.library.globe_tour(query, snap),
                )
                return
            if route == "/api/groups" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                self._catalog_read(
                    "/api/groups",
                    self.library.snapshot_catalog,
                    lambda snap: self.library.groups_from_snapshot(snap, query),
                )
                return
            if route == "/api/rebuild-index" and method == "POST":
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.rebuild_index())
                return
            if route == "/api/renditions/relocate" and method == "POST":
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.relocate())
                return
            if route == "/api/people" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/people",
                    self.library.read_ready,
                    self.library.people_built,
                )
                return
            if route == "/api/people/suggestions" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/people/suggestions",
                    self.library.read_ready,
                    self.library.suggestions_built,
                )
                return
            if route == "/api/people/not-same" and method == "POST":
                from library.people_suggest import read_not_same_payload

                body = read_not_same_payload(self._read_json())
                with self.lock:
                    self._send_json(200, self.library.people_not_same(body["a"], body["b"]))
                return
            if route == "/api/activity" and method in {"GET", "HEAD"}:
                from library.activity import snapshot

                self._send_json(200, snapshot())
                return
            if route == "/api/jobs" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/jobs",
                    self.library.snapshot_catalog,
                    self.library.jobs_from_snapshot,
                )
                return
            if route == "/api/jobs" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.jobs_set(body))
                return
            if route == "/api/analyze" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/analyze",
                    lambda: self.library.read_ready(finish_pending=False),
                    self.library.analyze_built,
                )
                return
            if route == "/api/analyze" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.analyze(body))
                return
            if route == "/api/transcribe" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/transcribe",
                    lambda: self.library.read_ready(finish_pending=False),
                    self.library.transcribe_built,
                )
                return
            if route == "/api/transcribe" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.transcribe(body))
                return
            if route == "/api/rate" and method in {"GET", "HEAD"}:
                self._catalog_read(
                    "/api/rate",
                    lambda: self.library.read_ready(finish_pending=False),
                    self.library.rate_built,
                )
                return
            if route == "/api/rate" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.rate_photos(body))
                return
            if route == "/api/rate/weights" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.reset_rating_weights(body))
                return
            if route == "/api/faces" and method in {"GET", "HEAD"}:
                self._send_json(200, self.library.faces_status())
                return
            if route == "/api/faces/setup" and method == "POST":
                from library.faces import read_setup_payload

                body = self._read_json()
                payload = read_setup_payload(body)
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.setup_faces(payload))
                return
            if route == "/api/faces/infer" and method == "POST":
                from library.faces import read_infer_payload

                body = self._read_json()
                payload = read_infer_payload(body)
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.infer_faces(payload))
                return
            if route == "/api/people/merge" and method == "POST":
                from library.annotate import read_merge_payload

                body = self._read_json()
                payload = read_merge_payload(body)
                self._require_idle()
                with self.lock:
                    self._send_json(
                        200,
                        self.library.people_merge(payload["keepId"], payload["dropId"]),
                    )
                return
            if route == "/api/people/split" and method == "POST":
                from library.annotate import read_split_payload

                body = self._read_json()
                payload = read_split_payload(body)
                self._require_idle()
                with self.lock:
                    self._send_json(
                        200,
                        self.library.people_split(
                            payload["personId"],
                            payload["itemId"],
                            payload.get("box"),
                        ),
                    )
                return
            face_time = _face_time_route(route)
            if face_time is not None:
                person_id, action, item_id = face_time
                from library.face_film import export_film, person_timeline, render_frame

                if action == "timeline" and method in {"GET", "HEAD"}:
                    self._send_json(200, person_timeline(self.library.root, person_id))
                    return
                if action == "frame" and method in {"GET", "HEAD"} and item_id:
                    jpeg = render_frame(self.library.root, person_id, item_id)
                    self._send(200, jpeg, "image/jpeg", cache_control="private, max-age=60")
                    return
                if action == "film" and method == "POST":
                    body = self._read_json()
                    seconds = body.get("seconds") if isinstance(body, dict) else None
                    self._send_json(200, export_film(self.library.root, person_id, seconds))
                    return
                raise fail("not-found")
            if route.startswith("/api/people/") and method == "PUT":
                person_id = route[len("/api/people/") :]
                if not person_id or "/" in person_id:
                    raise fail("not-found")
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.person_update(person_id, body))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/favorite")
                and method == "PUT"
            ):
                from library.favorites import parse_favorite_body

                item_id = route[len("/api/items/") : -len("/favorite")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                body = self._read_json()
                on = parse_favorite_body(body)
                with self.lock:
                    self._send_json(200, self.library.set_favorite(item_id, on))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/annotations")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/annotations")]
                if not item_id or item_id.endswith("/"):
                    raise fail("not-found")
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.annotate(item_id, body))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/favorite")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/favorite")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.favorite(item_id, body))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/rating")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/rating")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                body = self._read_json()
                with self.lock:
                    self._send_json(200, self.library.set_rating(item_id, body))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/reveal")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/reveal")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                self._read_json()
                with self.lock:
                    self._send_json(200, self.library.reveal(item_id))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/locate")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/locate")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                self._read_json()
                with self.lock:
                    self._send_json(200, self.library.locate(item_id))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/open")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/open")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                self._read_json()
                with self.lock:
                    self._send_json(200, self.library.open(item_id))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/remove")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/remove")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.remove(item_id))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/delete-file")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/delete-file")]
                if not item_id or item_id.endswith("/") or "/" in item_id:
                    raise fail("not-found")
                self._read_json()
                self._require_idle()
                with self.lock:
                    self._send_json(200, self.library.delete_file(item_id))
                return
            if (
                route.startswith("/api/items/")
                and route.endswith("/want")
                and method == "POST"
            ):
                item_id = route[len("/api/items/") : -len("/want")]
                if not item_id or "/" in item_id:
                    raise fail("not-found")
                body = self._read_json()
                if not isinstance(body, dict):
                    raise fail("invalid-argument")
                from library.renditions import note_wanted

                note_wanted(self.library.root, item_id)
                self._send_json(200, {"ok": True})
                return
            if route.startswith("/api/media/") and method in {"GET", "HEAD"}:
                self._send_media(route, parsed.query)
                return
            if route == "/" and method in {"GET", "HEAD"}:
                self._send_static(WEB_DIR / "index.html", "text/html; charset=utf-8")
                return
            if route.startswith("/assets/") and method in {"GET", "HEAD"}:
                rel = route[len("/assets/") :]
                if not rel or ".." in Path(rel).parts:
                    raise fail("not-found")
                path = (WEB_DIR / "assets" / rel).resolve()
                try:
                    path.relative_to((WEB_DIR / "assets").resolve())
                except ValueError as exc:
                    raise fail("not-found") from exc
                if not path.is_file():
                    raise fail("not-found")
                if path.suffix == ".css":
                    content_type = "text/css; charset=utf-8"
                elif path.suffix == ".js":
                    content_type = "application/javascript; charset=utf-8"
                elif path.suffix == ".png":
                    content_type = "image/png"
                else:
                    content_type = "application/octet-stream"
                self._send_static(path, content_type)
                return
            raise fail("not-found")
        except AppError as exc:
            try:
                self._error(exc.code, exc.status)
            except Exception as send_exc:
                if not _is_client_disconnect(send_exc):
                    raise
        except Exception as exc:
            if _is_client_disconnect(exc):
                return
            traceback.print_exc()
            append_error(
                self.library.root,
                parsed.path + (("?" + parsed.query) if parsed.query else ""),
                "internal-error",
            )
            try:
                self._send_json(500, {"error": "internal-error"})
            except Exception as send_exc:
                if not _is_client_disconnect(send_exc):
                    raise

    def _send_static(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self._send(200, data, content_type)

    def _send_media(self, route: str, query: str) -> None:
        item_id = route[len("/api/media/") :]
        if not item_id or "/" in item_id:
            raise fail("not-found")
        params = _query_map(query)
        which = params.get("which")
        try:
            resolved = self.library.media_resolve(item_id, params)
        except AppError as exc:
            if exc.code == "preview-unavailable" and which in {
                "preview",
                "poster",
                "proxy",
                "playback",
            }:
                from library.renditions import note_wanted

                note_wanted(self.library.root, item_id)
            raise
        path = resolved["path"]
        content_type = resolved["content_type"]
        try:
            stat = path.stat()
            cache_control, etag = _media_cache(which, stat.st_mtime_ns, stat.st_size)
            if etag and (self.headers.get("If-None-Match") or "") == etag:
                self._send(304, b"", content_type, cache_control=cache_control, etag=etag)
                return
            data = resolved.get("read", Path.read_bytes)(path)
        except OSError as exc:
            if which in {"preview", "poster", "proxy", "playback"}:
                from library.renditions import note_wanted

                note_wanted(self.library.root, item_id)
            raise fail("unavailable" if which == "original" else "preview-unavailable") from exc
        if not data:
            if which in {"preview", "poster", "proxy", "playback"}:
                from library.renditions import note_wanted

                note_wanted(self.library.root, item_id)
            raise fail("unavailable" if which == "original" else "preview-unavailable")
        spec = parse_byte_range(self.headers.get("Range"), len(data))
        if spec is None:
            self._send(200, data, content_type, cache_control=cache_control, etag=etag)
            return
        start, end = spec
        self._send_partial(
            data[start : end + 1],
            content_type,
            start,
            end,
            len(data),
            cache_control=cache_control,
            etag=etag,
        )

    def _send_partial(
        self,
        body: bytes,
        content_type: str,
        start: int,
        end: int,
        total: int,
        cache_control: str = "no-store",
        etag: str | None = None,
    ) -> None:
        self.send_response(206)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def _read_listen_target(root: Path) -> tuple[str, int]:
    from library.settings import defaults, settings_path

    if settings_path(root).exists():
        data = Library(root).ensure_settings()
        return data["listenHost"], data["port"]
    data = defaults()
    return data["listenHost"], data["port"]


def _probe_existing(root: Path, host: str, port: int) -> str | None:
    try:
        return matching_root_url(root, host, port)
    except AppError as exc:
        if exc.code == "port-in-use":
            raise
        return None


def _in_shared_band(port: int) -> bool:
    from library.settings import SHARED_PORT_HI, SHARED_PORT_LO

    return SHARED_PORT_LO <= int(port) <= SHARED_PORT_HI


def _persist_desk_port(root: Path, settings: dict[str, Any]) -> tuple[int, str | None]:
    """Store the reserved Library port when Arena/Command Center hold the band."""
    from library.settings import DESK_PORT, write_settings_file

    host = str(settings.get("listenHost") or "127.0.0.1")
    try:
        existing = matching_root_url(root, host, DESK_PORT)
    except AppError as exc:
        if exc.code == "port-in-use":
            raise fail("port-in-use") from exc
        raise
    if int(settings.get("port") or 0) != DESK_PORT:
        updated = dict(settings)
        updated["port"] = DESK_PORT
        write_settings_file(root, updated)
        settings["port"] = DESK_PORT
    return DESK_PORT, existing


def _resolve_listen(
    root: Path, host: str, port: int, settings: dict[str, Any]
) -> tuple[int, str | None]:
    try:
        existing = matching_root_url(root, host, port)
    except AppError as exc:
        if exc.code != "port-in-use" or not _in_shared_band(port):
            raise
        return _persist_desk_port(root, settings)
    return int(port), existing


def serve(root: Path) -> int:
    """Start the server or reopen a matching-root instance. Returns process exit."""
    root = normalize_root(root)
    root.mkdir(parents=True, exist_ok=True)
    host, port = _read_listen_target(root)
    try:
        existing = _probe_existing(root, host, port)
    except AppError as exc:
        if exc.code != "port-in-use" or not _in_shared_band(port):
            raise
        existing = None
    if existing is not None:
        print(existing, flush=True)
        return 0

    lock = WriteLock(root)
    lock.acquire()
    httpd = None
    drain_stop = threading.Event()
    drain_thread: threading.Thread | None = None
    try:
        library = Library(root)
        library.recover()
        settings = library.ensure_settings()
        host = settings["listenHost"]
        port = int(settings["port"])
        port, existing = _resolve_listen(root, host, port, settings)
        if existing is not None:
            print(existing, flush=True)
            return 0
        handler = LibraryHandler
        handler.library = library
        handler.lock = FairLock()
        handler.host = host
        handler.port = port
        handler.url = listen_url(host, port)
        handler.static_root = WEB_DIR
        try:
            httpd = ThreadingHTTPServer((host, port), handler)
        except OSError as exc:
            raise fail("port-in-use") from exc
        url = listen_url(host, port)
        handler.url = url
        atomic_write_json(
            root / RUNTIME_NAME,
            runtime_record(root, os.getpid(), url),
        )
        print(url, flush=True)

        def io_unlocked():
            return unlocked_io(handler.lock)

        def drain_once() -> bool:
            worked = library.drain_step(io_context=io_unlocked)
            processing_log.tick(library.root)
            reset = None if worked else library.take_folder_reset()
            if reset is not None:
                start_rescan_worker(handler.lock, library, reset)
            return worked

        def work_loop(step) -> None:
            FairLock.mark_background()
            while not drain_stop.is_set():
                worked = False
                try:
                    with handler.lock:
                        worked = step()
                except Exception as exc:
                    traceback.print_exc()
                    append_error(library.root, "/api/jobs", f"processing-drain:outer:{type(exc).__name__}")
                    worked = False
                drain_stop.wait(0.005 if worked else 0.25)

        from library.renditions import encoder_count

        drain_thread = threading.Thread(target=work_loop, args=(drain_once,), name="rendition-drain", daemon=True)
        drain_thread.start()
        for n in range(1, encoder_count()):
            threading.Thread(
                target=work_loop,
                args=(lambda: library.encode_step(io_context=io_unlocked),),
                name=f"rendition-encode-{n}",
                daemon=True,
            ).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    finally:
        drain_stop.set()
        if drain_thread is not None:
            drain_thread.join(timeout=5)
        if httpd is not None:
            httpd.server_close()
        runtime_path = root / RUNTIME_NAME
        if runtime_path.exists():
            try:
                runtime_path.unlink()
            except OSError:
                pass
        lock.release()
