"""HTTP server: bind, routes, recovery before serving, lock for life."""

from __future__ import annotations

import errno
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from library.atomic import atomic_write_json
from library.errors import AppError, fail
from library.httpjson import encode, request_json
from library.lock import WriteLock
from library.log import append_error
from library.paths import normalize_root, root_text, roots_equal
from library.service import Library

WEB_DIR = Path(__file__).resolve().parent / "web"
RUNTIME_NAME = "runtime.json"


def _query_map(query: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, values in parse_qs(query, keep_blank_values=True).items():
        if len(values) != 1:
            raise fail("invalid-argument")
        out[key] = values[0]
    return out


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
    print(f"{kind} {rel}", flush=True)


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

    def _yield_scan(self) -> None:
        self.lock.release()
        try:
            time.sleep(0.05)
        finally:
            self.lock.acquire()

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
                with self.lock:
                    self._send_json(200, self.library.settings_get())
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
                with self.lock:
                    self._send_json(200, self.library.sources_list())
                return
            if route == "/api/sources" and method == "POST":
                body = self._read_json()
                with self.lock:
                    self._require_idle()
                    source = self.library.start_http_scan(body)
                lock = self.lock
                library = self.library

                def yield_scan() -> None:
                    lock.release()
                    try:
                        time.sleep(0.05)
                    finally:
                        lock.acquire()

                def scan_worker() -> None:
                    lock.acquire()
                    try:
                        library.finish_http_scan(
                            body,
                            source,
                            on_progress=_scan_progress,
                            between=yield_scan,
                        )
                    except Exception:
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
                self._send_json(200, self.library.update())
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
            if route == "/api/items" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                with self.lock:
                    self._send_json(200, self.library.items_list(query))
                return
            if route == "/api/places" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                with self.lock:
                    self._send_json(200, self.library.places_list(query))
                return
            if route == "/api/globe/tour" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                with self.lock:
                    self._send_json(200, self.library.globe_tour(query))
                return
            if route == "/api/groups" and method in {"GET", "HEAD"}:
                query = _query_map(parsed.query)
                with self.lock:
                    self._send_json(200, self.library.groups_list(query))
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
        with self.lock:
            resolved = self.library.media_resolve(item_id, params)
        path = resolved["path"]
        content_type = resolved["content_type"]
        try:
            data = path.read_bytes()
        except OSError as exc:
            which = params.get("which")
            raise fail("unavailable" if which == "original" else "preview-unavailable") from exc
        if not data:
            which = params.get("which")
            raise fail("unavailable" if which == "original" else "preview-unavailable")
        spec = parse_byte_range(self.headers.get("Range"), len(data))
        if spec is None:
            self._send(200, data, content_type)
            return
        start, end = spec
        self._send_partial(data[start : end + 1], content_type, start, end, len(data))

    def _send_partial(self, body: bytes, content_type: str, start: int, end: int, total: int) -> None:
        self.send_response(206)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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


def serve(root: Path) -> int:
    """Start the server or reopen a matching-root instance. Returns process exit."""
    root = normalize_root(root)
    root.mkdir(parents=True, exist_ok=True)
    host, port = _read_listen_target(root)
    existing = _probe_existing(root, host, port)
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
        port = settings["port"]
        existing = _probe_existing(root, host, port)
        if existing is not None:
            print(existing, flush=True)
            return 0
        handler = LibraryHandler
        handler.library = library
        handler.lock = threading.Lock()
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

        def drain_loop() -> None:
            while not drain_stop.is_set():
                worked = False
                try:
                    with handler.lock:
                        worked = library.drain_step()
                except Exception:
                    worked = False
                drain_stop.wait(0.05 if worked else 0.25)

        drain_thread = threading.Thread(target=drain_loop, name="rendition-drain", daemon=True)
        drain_thread.start()
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
