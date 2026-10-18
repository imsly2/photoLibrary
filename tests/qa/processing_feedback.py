"""Deterministic fixture diagnostics for processing feedback; not a feature grade.

python -m tests.qa.processing_feedback --artifacts <new-folder>
Add --demo to leave a fixture HTTP server busy until <folder>/release exists.
The demo server exits when <folder>/stop exists. No production test seam.
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from library import activity, renditions
from library.catalog_io import iter_item_ids, load_item, try_load_item
from library.server import LibraryHandler, WEB_DIR, unlocked_io
from library.service import Library
from tests.qa.roots import prepare_root

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "media"


def fake_still(source: Path, dest: Path, cap: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / "formats" / "quad.webp", dest)
    return True


def fixture_library(folder: Path) -> tuple[Library, Path]:
    media = folder / "pictures"
    media.mkdir(parents=True)
    for rel in ("a/IMG_1042.jpg", "b/no-exif.jpg", "a/clip.mp4"):
        shutil.copyfile(FIXTURES / rel, media / Path(rel).name)
    library = Library(prepare_root(folder / "catalog"))
    library.ensure_settings()
    return library, media


def scan(library: Library, media: Path, **kwargs):
    body = {"path": str(media), "mode": "serve-from-there", "previewStore": "with-server"}
    source = library.start_http_scan(body)
    return library.finish_http_scan(body, source, **kwargs)


def serve(library: Library):
    handler = type("FixtureHandler", (LibraryHandler,), {
        "library": library, "lock": threading.Lock(), "host": "127.0.0.1",
        "port": 0, "url": "", "static_root": WEB_DIR,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler.port = httpd.server_port
    handler.url = f"http://127.0.0.1:{httpd.server_port}/"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, handler, handler.url.rstrip("/")


def request(base, path, body=None):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    at = time.perf_counter()
    with urllib.request.urlopen(req, timeout=2) as response:
        data = response.read()
        result = json.loads(data) if "json" in response.headers.get("Content-Type", "") else {"bytes": len(data)}
        return {"status": response.status, "seconds": round(time.perf_counter() - at, 4), "body": result}


def run_diagnostics(folder: Path):
    library, media = fixture_library(folder / "priority")
    order = []
    progressive = []

    def writer(source, dest, cap):
        order.append(dest.name.split(".")[0])
        return fake_still(source, dest, cap)

    def between():
        # This is the same boundary where the HTTP scan yields its lock.
        with patch("library.renditions.write_webp", writer):
            if library.drain_step():
                progressive.append({"scanning": library._scanning, "order": list(order)})

    scan(library, media, between=between)
    with patch("library.renditions.write_webp", writer), patch("library.renditions.write_proxy", writer):
        for _ in range(20):
            if renditions.next_rendition_job(library.root) is None:
                break
            library.drain_step()
    assert progressive and all(row["scanning"] for row in progressive), progressive
    assert set(order[:len(progressive)]) <= {"thumb", "poster"}, progressive
    # Jobs already begun during discovery cannot predict files not yet discovered;
    # the whole-catalog priority is tested below after a fully queued scan.
    priority, media2 = fixture_library(folder / "queued")
    scan(priority, media2)
    queued_order = []
    with patch("library.renditions.write_webp", fake_still), patch("library.renditions.write_proxy", fake_still):
        for _ in range(20):
            job = renditions.next_rendition_job(priority.root)
            if job is None:
                break
            queued_order.append(job[1])
            priority.drain_step()
    assert set(queued_order[:3]) <= {"thumb", "poster"}, queued_order
    assert set(queued_order[3:]).isdisjoint({"thumb", "poster"}), queued_order

    httpd, handler, base = serve(priority)
    records = []
    items = [load_item(priority.root, item_id) for item_id in iter_item_ids(priority.root)]
    photos = [item for item in items if item["kind"] == "photo"]
    try:
        for action, photo in zip(("annotate", "remove"), photos):
            # Queue one fresh viewer preview while preserving a ready grid thumb.
            path = priority.root / "catalog" / "items" / f'{photo["id"]}.json'
            current = load_item(priority.root, photo["id"])
            current["renditions"]["status"]["preview"] = "queued"
            old = renditions.rendition_abs(current, "preview", priority.root)
            if old is not None:
                old.unlink(missing_ok=True)
            from library.atomic import atomic_write_json
            atomic_write_json(path, current)
            entered, release = threading.Event(), threading.Event()
            failure = []

            def slow_writer(source, dest, cap):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("diagnostic encoder barrier timed out")
                return fake_still(source, dest, cap)

            def drain():
                try:
                    with handler.lock:
                        priority.drain_step(io_context=lambda: unlocked_io(handler.lock))
                except Exception as exc:
                    failure.append(repr(exc))

            with patch("library.renditions.write_webp", slow_writer):
                worker = threading.Thread(target=drain, daemon=True)
                worker.start()
                try:
                    assert entered.wait(4), "encoder did not start"
                    row = {"case": action, "requests": {}}
                    for key, route, body in (
                        ("items", "/api/items", None),
                        ("thumb", f'/api/media/{photo["id"]}?which=thumb', None),
                        ("jobs", "/api/jobs", None),
                        ("activity", "/api/activity", None),
                        ("pause", "/api/jobs", {"action": "pause"}),
                    ):
                        row["requests"][key] = request(base, route, body)
                    live = row["requests"]["activity"]["body"]
                    assert live["derivative"] == "preview" and live["file"] == photo["filename"], live
                    assert all(req["seconds"] < 2 for req in row["requests"].values()), row
                    if action == "annotate":
                        row["edit"] = request(base, f'/api/items/{photo["id"]}/annotations', {"people": [{"name": "While encoding"}]})
                    else:
                        row["edit"] = request(base, f'/api/items/{photo["id"]}/remove', {})
                    records.append(row)
                finally:
                    release.set()
                    worker.join(4)
                assert not worker.is_alive() and not failure, failure
            after = try_load_item(priority.root, photo["id"])
            if action == "annotate":
                assert after is not None and after["faces"], after
                assert after["renditions"]["status"]["preview"] == "ready", after
            else:
                assert after is None, "removed item resurrected"
                assert old is None or not old.exists(), "stale derivative published for removed item"
            request(base, "/api/jobs", {"action": "resume"})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert activity.snapshot()["phase"] == "idle"
    assert activity.snapshot()["scan"]["phase"] == "idle"
    return {"queuedOrder": queued_order, "progressive": progressive, "responsiveness": records,
            "history": history_diagnostics(folder / "history"),
            "copy": copy_diagnostics(folder / "copy")}


def copy_diagnostics(folder: Path):
    from library.copy import partial_path, write_via_partial
    from library.media import sha256_file

    folder.mkdir()
    original = folder / "readonly.jpg"
    output = folder / "copy.jpg"
    shutil.copyfile(FIXTURES / "a" / "IMG_1042.jpg", original)
    digest = sha256_file(original)
    original.chmod(stat.S_IREAD)
    try:
        write_via_partial(original, output, "src_fixture")
        assert sha256_file(output) == digest == sha256_file(original)
        assert not partial_path(output, "src_fixture").exists()
        # Repeating a durable copy must preserve the existing original bytes.
        write_via_partial(original, output, "src_fixture")
        assert sha256_file(output) == digest
    finally:
        original.chmod(stat.S_IREAD | stat.S_IWRITE)
        if output.exists():
            output.chmod(stat.S_IREAD | stat.S_IWRITE)
    return {"readOnlySourceHash": digest, "copiedHash": sha256_file(output), "partialRemoved": True}


def history_diagnostics(folder: Path):
    from library.atomic import transact
    from library.history import load_entry, load_state, make_history_entry, plan_append, plan_extend_entry

    # Repeated growth of one record keeps two endpoints, never every snapshot.
    folder.mkdir(parents=True)
    root = prepare_root(folder / "synthetic")
    base = {"files": {}}
    initial = {"path": "catalog/source-growth.json", "before": None, "after": base}
    entry = make_history_entry(root, "scan", [initial])
    transact(root, plan_append(root, entry) + [initial])
    current = base
    for index in range(40):
        latest = {"files": {str(n): {"itemId": str(n)} for n in range(index + 1)}}
        transact(root, plan_extend_entry(root, entry["id"], [
            {"path": initial["path"], "before": current, "after": latest},
            {"path": f"catalog/leaf-{index}.json", "before": None, "after": {"index": index}},
        ]))
        current = latest
    compacted = load_entry(root, entry["id"])
    assert len(compacted["changes"]) == 41, compacted
    source_change = compacted["changes"][0]
    assert source_change["before"] is None and source_change["after"] == current
    assert all(change["before"] is None for change in compacted["changes"])

    # Real fixture scan remains one undo operation and restores the same records.
    library, media = fixture_library(folder / "undo-redo")
    scan(library, media)
    state = load_state(library.root)
    assert len(state["entries"]) == 1, state
    scanned_entry = load_entry(library.root, state["entries"][0])
    paths = [change["path"] for change in scanned_entry["changes"]]
    assert len(paths) == len(set(paths)), paths
    before = {item_id: load_item(library.root, item_id) for item_id in iter_item_ids(library.root)}
    library.undo()
    assert not iter_item_ids(library.root)
    library.redo()
    after = {item_id: load_item(library.root, item_id) for item_id in iter_item_ids(library.root)}
    assert after == before, "scan redo changed record snapshots"

    # Annotation between pending publication and content-ID publication is still
    # its own operation, rebased onto the final ID; scan compaction cannot absorb it.
    rebased, pending_media = fixture_library(folder / "pending")
    seen = []

    def annotate_pending():
        if seen:
            return
        pending = [item_id for item_id in iter_item_ids(rebased.root) if item_id.startswith("pending-")]
        if pending:
            seen.append(pending[0])
            rebased.annotate(pending[0], {"people": [{"name": "During scan"}]})

    scan(rebased, pending_media, between=annotate_pending)
    assert seen, "pending publication boundary not exercised"
    marked = [load_item(rebased.root, item_id) for item_id in iter_item_ids(rebased.root)
              if load_item(rebased.root, item_id)["faces"]]
    assert len(marked) == 1 and not marked[0]["id"].startswith("pending-"), marked
    rebased_state = load_state(rebased.root)
    assert len(rebased_state["entries"]) == 2, rebased_state
    annotation = load_entry(rebased.root, rebased_state["entries"][-1])
    assert annotation["operation"] == "annotate", annotation
    assert all(seen[0] not in change["path"] for change in annotation["changes"]), annotation
    rebased.undo()
    assert not load_item(rebased.root, marked[0]["id"])["faces"]
    rebased.redo()
    assert load_item(rebased.root, marked[0]["id"])["faces"] == marked[0]["faces"]
    return {"extensions": 40, "storedPaths": len(compacted["changes"]),
            "scanPathsUnique": len(paths), "undoRedoRecords": len(before),
            "pendingAnnotationRebased": marked[0]["id"]}


def demo(folder: Path):
    library, media = fixture_library(folder)
    scan(library, media)
    with patch("library.renditions.write_webp", fake_still):
        while True:
            job = renditions.next_rendition_job(library.root)
            if job is None or job[1] not in {"thumb", "poster"}:
                break
            library.drain_step()
    httpd, handler, base = serve(library)
    normal_writer = renditions.write_webp

    def held_writer(source, dest, cap):
        (folder / "ready.json").write_text(json.dumps({"url": base, "file": source.name, "derivative": "preview"}), encoding="utf-8")
        while not (folder / "release").exists() and not (folder / "stop").exists():
            time.sleep(0.1)
        return normal_writer(source, dest, cap)

    def drain_loop():
        with patch("library.renditions.write_webp", held_writer):
            while not (folder / "stop").exists():
                with handler.lock:
                    library.drain_step(io_context=lambda: unlocked_io(handler.lock))
                time.sleep(0.1)

    worker = threading.Thread(target=drain_loop, daemon=True)
    worker.start()
    print(json.dumps({"url": base, "release": str(folder / "release"), "stop": str(folder / "stop")}), flush=True)
    try:
        while not (folder / "stop").exists():
            time.sleep(0.2)
    finally:
        (folder / "release").touch()
        httpd.shutdown()
        httpd.server_close()
        worker.join(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    folder = args.artifacts.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    if args.demo:
        demo(folder)
    else:
        result = run_diagnostics(folder)
        (folder / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"diagnostics": "completed", "result": str(folder / "result.json")}))


if __name__ == "__main__":
    main()
