"""F7 missing previews: delete a folder's .library/ and Library must notice.

python -m tests.qa.missing_previews [--count 12] [--keep]

Scratch server + scratch copy of Steve's photos under .qa/bench/. Never
touches library-data/ or the real picture folders.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.perf.bench import (
    FIXTURE_SOURCE,
    REPO_ROOT,
    HarnessError,
    _collect_source_media,
    _http_json,
    _inside,
    _new_scratch_root,
    _port_is_occupied,
    _prepare_library_root,
    _start_server,
    _stop_server,
    _wait_health,
)

ARTIFACT_DIR = REPO_ROOT / "docs" / "features" / "processing-feedback" / "Rev1.0" / "assets" / "missing-previews"
REQUEUE_WITHIN_SEC = 10.0
RESTORE_WITHIN_SEC = 60.0
FILE_SLOTS = ("thumb", "preview", "poster", "proxy", "playback")


def _media(base: str, item_id: str, which: str, etag: str | None = None) -> dict[str, Any]:
    req = urllib.request.Request(f"{base}/api/media/{item_id}?which={which}")
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return {"status": resp.status, "bytes": len(body), "cacheControl": resp.headers.get("Cache-Control"), "etag": resp.headers.get("ETag")}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "bytes": 0, "cacheControl": exc.headers.get("Cache-Control"), "etag": exc.headers.get("ETag")}


def _queue(base: str) -> dict[str, Any]:
    _, status, body = _http_json(base, "/api/jobs", timeout=30)
    if status != 200 or not isinstance(body, dict):
        return {}
    return next((q for q in body.get("queues") or [] if q.get("id") == "renditions"), {})


def _items(lib_root: Path) -> list[dict[str, Any]]:
    from tests.qa.s01 import item_records

    out = []
    for path in item_records(lib_root).values():
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not str(item.get("id", "")).startswith("pending-"):
            out.append(item)
    return out


def _slot_file(rend: dict[str, Any], rel: Any, folder: Path, lib_root: Path) -> Path | None:
    if not isinstance(rel, str) or not rel:
        return None
    store = rend.get("store")
    if store == "folder-source":
        return folder / ".library" / rel
    if store == "folder-server":
        found = sorted((lib_root / "folders").glob(f"*-{rend.get('sourceId')}"))
        return found[0] / rel if found else None
    if store == "with-server":
        return lib_root / rel
    return folder / rel


def _ready_slots(items: list[dict[str, Any]], folder: Path, lib_root: Path) -> list[dict[str, Any]]:
    """Every slot the catalog calls ready, and whether its file is really there."""
    rows = []
    for item in items:
        rend = item.get("renditions") or {}
        for slot, status in (rend.get("status") or {}).items():
            if slot not in FILE_SLOTS or status != "ready":
                continue
            path = _slot_file(rend, rend.get(slot), folder, lib_root)
            present = path is not None and path.is_file() and path.stat().st_size > 0
            rows.append({"id": item["id"], "slot": slot, "present": present})
    return rows


def _free_port(start: int = 8810) -> int:
    for port in range(start, start + 50):
        if not _port_is_occupied(port):
            return port
    raise HarnessError("no free port")


def _wait(predicate, timeout: float, step: float = 0.5) -> float | None:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if predicate():
            return round(time.monotonic() - started, 2)
        time.sleep(step)
    return None


def run(count: int, keep: bool) -> int:
    scratch = _new_scratch_root()
    folder = scratch / "pictures"
    folder.mkdir()
    jpgs, mov = _collect_source_media(FIXTURE_SOURCE)
    for src in jpgs[:count] + ([mov] if mov else []):
        shutil.copy2(src, folder / src.name)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    lib_root = _prepare_library_root(port, scratch)
    checks: list[dict[str, Any]] = []
    record: dict[str, Any] = {"scratch": str(scratch), "count": count, "video": bool(mov), "checks": checks}

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "pass": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail is not None else ""), flush=True)

    proc = _start_server(REPO_ROOT, lib_root, scratch / "server.out.log", scratch / "server.err.log")
    try:
        _wait_health(base)
        _, status, _ = _http_json(base, "/api/sources", method="POST", timeout=120,
                                  body={"path": str(folder), "mode": "serve-from-there", "previewStore": "with-source"})
        check("add-folder", status in (200, 202), status)
        expected = count + (1 if mov else 0)
        idle = _wait(lambda: len(_items(lib_root)) >= expected and (_queue(base).get("pending") == 0)
                     and all(r["present"] for r in _ready_slots(_items(lib_root), folder, lib_root))
                     and len(_ready_slots(_items(lib_root), folder, lib_root)) >= 2 * count, 240)
        check("first-pass-idle", idle is not None, idle)
        before = _ready_slots(_items(lib_root), folder, lib_root)
        record["readyBefore"] = len(before)
        photo = next(r["id"] for r in before if r["slot"] == "thumb")
        first = _media(base, photo, "thumb")
        record["thumbBefore"] = first
        check("thumb-served", first["status"] == 200 and first["bytes"] > 0, first)
        cache = (first.get("cacheControl") or "").replace(" ", "")
        check("media-revalidates", "no-cache" in cache or "max-age=0" in cache, first.get("cacheControl"))
        again = _media(base, photo, "thumb", first.get("etag"))
        check("unchanged-is-304", again["status"] == 304, again["status"])

        library_dir = folder / ".library"
        if not _inside(scratch, library_dir):
            raise HarnessError(f"refusing to delete outside scratch: {library_dir}")
        shutil.rmtree(library_dir)
        deleted_at = time.monotonic()
        stale = _media(base, photo, "thumb", first.get("etag"))
        record["thumbRightAfterDelete"] = stale
        check("deleted-not-304", stale["status"] != 304, stale["status"])

        def noticed() -> bool:
            rows = _ready_slots(_items(lib_root), folder, lib_root)
            regenerated = len(rows) >= len(before) and all(r["present"] for r in rows)
            return int(_queue(base).get("pending") or 0) > 0 or len(rows) < len(before) or regenerated

        requeued = _wait(noticed, REQUEUE_WITHIN_SEC, 0.25)
        check("processing-shows-waiting", requeued is not None, {"sec": requeued, "queue": _queue(base)})

        def restored() -> bool:
            rows = _ready_slots(_items(lib_root), folder, lib_root)
            return len(rows) >= len(before) and all(r["present"] for r in rows) and _queue(base).get("pending") == 0

        back = _wait(restored, RESTORE_WITHIN_SEC)
        after = _ready_slots(_items(lib_root), folder, lib_root)
        missing = [r for r in after if not r["present"]]
        record["restoreSec"] = None if back is None else round(time.monotonic() - deleted_at, 2)
        check("every-ready-slot-has-file", back is not None and not missing,
              {"sec": record["restoreSec"], "ready": len(after), "missingFiles": len(missing), "queue": _queue(base)})
        served = [_media(base, r["id"], r["slot"])["status"] for r in after if r["slot"] in {"thumb", "preview"}]
        check("ready-serves-200", bool(served) and all(s == 200 for s in served),
              {"200": served.count(200), "other": [s for s in served if s != 200][:5]})
    except HarnessError as exc:
        check("harness", False, str(exc))
    finally:
        _stop_server(proc)

    ok = all(c["pass"] for c in checks)
    record["result"] = "PASS" if ok else "FAIL"
    out = ARTIFACT_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{record['result']}  artifact: {out / 'result.json'}")
    if not keep:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    return run(args.count, args.keep)


if __name__ == "__main__":
    sys.exit(main())
