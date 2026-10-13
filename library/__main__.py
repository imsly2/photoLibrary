"""CLI: running server is the sole writer; offline CLI takes the lock."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from library.atomic import load_json
from library.errors import AppError, HTTP_STATUS, fail
from library.httpjson import request_json
from library.lock import WriteLock
from library.paths import default_root, normalize_root, roots_equal
from library.server import serve
from library.service import Library, error_payload
from library.settings import parse_cli_value

def _print_error(code: str) -> None:
    sys.stderr.buffer.write(error_payload(code) + b"\n")
    sys.stderr.buffer.flush()


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    sys.stdout.flush()


def _print_scan_summary(source: Any) -> None:
    scan = source.get("scan") if isinstance(source, dict) else None
    if not isinstance(source, dict) or not isinstance(scan, dict):
        raise fail("internal-error")
    _print_json(
        {
            "sourceId": source.get("id"),
            "added": scan.get("added"),
            "skipped": scan.get("skipped"),
            "errors": scan.get("errors"),
        }
    )


def _scan_exit(source: Any) -> int:
    scan = source.get("scan") if isinstance(source, dict) else None
    errors = scan.get("errors") if isinstance(scan, dict) else None
    if errors:
        return 1
    return 0


def _exit_for(code: str) -> int:
    if HTTP_STATUS.get(code) == 400:
        return 2
    if code in {"invalid-argument", "choice-required"}:
        return 2
    return 1


def _pid_alive(pid: int) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _running_server_url(root: Path) -> str | None:
    runtime_path = root / "runtime.json"
    if not runtime_path.exists():
        return None
    try:
        runtime = load_json(runtime_path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(runtime, dict):
        return None
    if not _pid_alive(runtime.get("pid", 0)):
        return None
    url = runtime.get("url")
    if not isinstance(url, str) or not url:
        return None
    try:
        status, body = request_json(url.rstrip("/") + "/api/runtime", timeout=1.0)
    except OSError:
        return None
    if status != 200 or not isinstance(body, dict):
        return None
    if not roots_equal(body.get("root", ""), root):
        return None
    return url.rstrip("/")


def _forward(
    url: str,
    method: str,
    route: str,
    body: Any | None,
    timeout: float = 5.0,
) -> tuple[int, Any]:
    return request_json(url + route, method=method, body=body, timeout=timeout)


def _with_lock(root: Path, fn):
    lock = WriteLock(root)
    lock.acquire()
    try:
        return fn()
    finally:
        lock.release()


def _mutation(
    root: Path,
    local_fn,
    method: str,
    route: str,
    body: Any | None,
    timeout: float = 5.0,
) -> Any:
    url = _running_server_url(root)
    if url is not None:
        status, payload = _forward(url, method, route, body, timeout=timeout)
        if status in {200, 202}:
            return payload
        if isinstance(payload, dict) and "error" in payload:
            raise AppError(payload["error"], status)
        raise fail_from_status(status)
    return _with_lock(root, local_fn)


def fail_from_status(status: int) -> AppError:
    if status == 409:
        return AppError("busy", 409)
    if status == 400:
        return AppError("invalid-argument", 400)
    if status == 404:
        return AppError("not-found", 404)
    return AppError("internal-error", 500)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m library")
    parser.add_argument("--root", default=None, help="library-data directory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve")

    settings = sub.add_parser("settings")
    settings_sub = settings.add_subparsers(dest="settings_cmd")
    settings_sub.add_parser("get")
    set_p = settings_sub.add_parser("set")
    set_p.add_argument("key")
    set_p.add_argument("value")

    sub.add_parser("undo")
    sub.add_parser("redo")

    scan = sub.add_parser("scan")
    scan.add_argument("path")
    scan.add_argument("--copy-here", action="store_true")
    scan.add_argument("--serve-from-there", action="store_true")

    sub.add_parser("sources")

    copy_here = sub.add_parser("copy-here")
    copy_here.add_argument("source_id")

    items = sub.add_parser("items")
    items.add_argument("--sort")
    items.add_argument("--dir")
    items.add_argument("--q")
    items.add_argument("--unavailable")
    items.add_argument("--person")
    items.add_argument("--place")
    items.add_argument("--thing")
    items.add_argument("--from", dest="from_")
    items.add_argument("--to")
    items.add_argument("--scope")

    annotate = sub.add_parser("annotate")
    annotate.add_argument("id")
    annotate.add_argument("--json")
    annotate.add_argument("--person")
    annotate.add_argument("--thing")
    annotate.add_argument("--place")

    people = sub.add_parser("people")
    people_sub = people.add_subparsers(dest="people_cmd")
    merge = people_sub.add_parser("merge")
    merge.add_argument("keep")
    merge.add_argument("drop")

    sub.add_parser("rebuild-index")
    renditions = sub.add_parser("renditions")
    renditions.add_argument("action", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    root = normalize_root(args.root) if args.root else default_root()
    try:
        if args.command == "serve":
            return serve(root)
        if args.command == "settings":
            if args.settings_cmd == "get":
                url = _running_server_url(root)
                if url is not None:
                    status, payload = _forward(url, "GET", "/api/settings", None)
                    if status != 200:
                        if isinstance(payload, dict) and "error" in payload:
                            raise AppError(payload["error"], status)
                        raise fail_from_status(status)
                    _print_json(payload)
                    return 0
                data = _with_lock(root, lambda: Library(root).settings_get())
                _print_json(data)
                return 0
            if args.settings_cmd == "set":
                patch = {args.key: parse_cli_value(args.key, args.value)}
                result = _mutation(
                    root,
                    lambda: Library(root).settings_set(patch),
                    "PUT",
                    "/api/settings",
                    patch,
                )
                _print_json(result)
                return 0
            _print_error("invalid-argument")
            return 2
        if args.command == "scan":
            if args.copy_here and args.serve_from_there:
                raise fail("invalid-argument")
            body: dict[str, Any] = {"path": args.path}
            if args.copy_here:
                body["mode"] = "copy-here"
            if args.serve_from_there:
                body["mode"] = "serve-from-there"
            url = _running_server_url(root)
            if url is not None:
                status, payload = _forward(url, "POST", "/api/sources", body, timeout=300.0)
                if status not in {200, 202}:
                    if isinstance(payload, dict) and "error" in payload:
                        raise AppError(payload["error"], status)
                    raise fail_from_status(status)
                _print_scan_summary(payload)
                return _scan_exit(payload)
            source = _with_lock(
                root,
                lambda: Library(root).scan(
                    body,
                    on_progress=lambda kind, rel: print(f"{kind} {rel}", flush=True),
                ),
            )
            _print_scan_summary(source)
            return _scan_exit(source)
        if args.command == "sources":
            url = _running_server_url(root)
            if url is not None:
                status, payload = _forward(url, "GET", "/api/sources", None)
                if status != 200:
                    if isinstance(payload, dict) and "error" in payload:
                        raise AppError(payload["error"], status)
                    raise fail_from_status(status)
                _print_json(payload)
                return 0
            payload = _with_lock(root, lambda: Library(root).sources_list())
            _print_json(payload)
            return 0
        if args.command == "copy-here":
            result = _mutation(
                root,
                lambda: Library(root).copy_here(args.source_id),
                "POST",
                f"/api/sources/{args.source_id}/copy-here",
                {},
                timeout=300.0,
            )
            _print_json(result)
            return 0
        if args.command == "items":
            query = {}
            if args.sort:
                query["sort"] = args.sort
            if getattr(args, "dir", None):
                query["dir"] = args.dir
            if args.q:
                query["q"] = args.q
            if args.unavailable is not None:
                query["unavailable"] = args.unavailable
            if args.person:
                query["person"] = args.person
            if args.place:
                query["place"] = args.place
            if args.thing:
                query["thing"] = args.thing
            if getattr(args, "from_", None):
                query["from"] = args.from_
            if getattr(args, "to", None):
                query["to"] = args.to
            if args.scope:
                query["scope"] = args.scope
            url = _running_server_url(root)
            if url is not None:
                qs = "&".join(f"{key}={value}" for key, value in query.items())
                route = "/api/items" + (("?" + qs) if qs else "")
                status, payload = _forward(url, "GET", route, None)
                if status != 200:
                    if isinstance(payload, dict) and "error" in payload:
                        raise AppError(payload["error"], status)
                    raise fail_from_status(status)
                _print_json(payload)
                return 0
            payload = _with_lock(root, lambda: Library(root).items_list(query))
            _print_json(payload)
            return 0
        if args.command == "annotate":
            from library.annotate import cli_payload_from_flags

            payload = cli_payload_from_flags(
                json_path=args.json,
                person=args.person,
                thing=args.thing,
                place=args.place,
            )
            result = _mutation(
                root,
                lambda: Library(root).annotate(args.id, payload),
                "POST",
                f"/api/items/{args.id}/annotations",
                payload,
            )
            _print_json(result)
            return 0
        if args.command == "people":
            if args.people_cmd != "merge":
                _print_error("invalid-argument")
                return 2
            body = {"keepId": args.keep, "dropId": args.drop}
            result = _mutation(
                root,
                lambda: Library(root).people_merge(args.keep, args.drop),
                "POST",
                "/api/people/merge",
                body,
            )
            _print_json(result)
            return 0
        if args.command == "renditions":
            if getattr(args, "action", None) != "relocate":
                _print_error("invalid-argument")
                return 2
            result = _mutation(
                root,
                lambda: Library(root).relocate(),
                "POST",
                "/api/renditions/relocate",
                {},
                timeout=300.0,
            )
            _print_json(result)
            return 0
        if args.command == "rebuild-index":
            result = _mutation(
                root,
                lambda: Library(root).rebuild_index(),
                "POST",
                "/api/rebuild-index",
                {},
            )
            _print_json(result)
            return 0
        if args.command == "undo":
            result = _mutation(
                root,
                lambda: Library(root).undo(),
                "POST",
                "/api/undo",
                {},
            )
            _print_json(result)
            return 0
        if args.command == "redo":
            result = _mutation(
                root,
                lambda: Library(root).redo(),
                "POST",
                "/api/redo",
                {},
            )
            _print_json(result)
            return 0
        parser.print_help()
        return 2
    except AppError as exc:
        _print_error(exc.code)
        return _exit_for(exc.code)
    except SystemExit as exc:
        raise exc
    except Exception:
        _print_error("internal-error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
