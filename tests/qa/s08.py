"""Slice S08 / Check F14 / Check F20 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    _env,
    assert_no_pillow_in_server,
    copy_committed_fixtures,
    find_free_port,
    parse_json,
    run_library,
    start_server,
    stop_owned,
    wait_health,
    write_isolated_port,
)
from tests.qa.s01 import hash_tree, load_items, load_sources, parse_summary
from tests.qa.s03 import find_item
from tests.qa.s05 import pin_media_from_manifest, start_isolated


def write_result(
    ident: str,
    kind: str,
    checks: Checks,
    artifacts: Path,
    commands: list[str],
    extra_paths: dict[str, str] | None = None,
) -> int:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest_hash = (
        sha256_file(COMMITTED_FIXTURES / "manifest.json")
        if (COMMITTED_FIXTURES / "manifest.json").is_file()
        else ""
    )
    artifact_paths = {
        "result.json": str(artifacts / "result.json"),
        "stdout.log": str(artifacts / "stdout.log"),
    }
    if extra_paths:
        artifact_paths.update(extra_paths)
    result = {
        kind: ident,
        "pass": checks.ok(),
        "assertions": checks.assertions,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version,
        },
        "fixtureManifestHash": manifest_hash,
        "revision": revision,
        "commands": commands,
        "artifactPaths": artifact_paths,
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def copy_rels(src: Path, dest: Path, rels: list[str] | tuple[str, ...]) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for rel in rels:
        target = dest / Path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / Path(rel), target)
    pin_media_from_manifest(dest)
    return dest


def fresh_root(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    prepare_root(path)
    write_isolated_port(path, find_free_port())
    return path


def settings_port(root: Path) -> int:
    data = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    return int(data["port"])


def start_owned(root: Path) -> tuple[subprocess.Popen[str], str, list[int]]:
    port = settings_port(root)
    server = start_server(root)
    url = f"http://127.0.0.1:{port}/"
    health_status, health_body = wait_health(url, server)
    if health_status != 200 or health_body != {"ok": True}:
        stop_owned(server)
        raise RuntimeError(f"health {health_status} {health_body}")
    owned: list[int] = []
    try:
        status, runtime = request_json(url.rstrip("/") + "/api/runtime", timeout=2)
        if status == 200 and isinstance(runtime, dict) and type(runtime.get("pid")) is int:
            owned.append(runtime["pid"])
    except Exception:
        pass
    return server, url, owned


def last_error(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        return parse_json(proc.stderr.strip().splitlines()[-1])
    except Exception:
        return {}


def load_people(root: Path) -> list[dict[str, Any]]:
    folder = root / "catalog" / "people"
    if not folder.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def load_things(root: Path) -> list[dict[str, Any]]:
    folder = root / "catalog" / "things"
    if not folder.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def load_places(root: Path) -> list[dict[str, Any]]:
    folder = root / "catalog" / "places"
    if not folder.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def load_history(root: Path) -> list[dict[str, Any]]:
    state_path = root / "undo" / "state.json"
    if not state_path.exists():
        return []
    state = json.loads(state_path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for entry_id in state.get("entries") or []:
        path = root / "undo" / "entries" / f"{entry_id}.json"
        if path.is_file():
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def catalog_json_hashes(root: Path) -> dict[str, str]:
    catalog = root / "catalog"
    out: dict[str, str] = {}
    if not catalog.exists():
        return out
    for path in sorted(catalog.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        out[rel] = sha256_file(path)
    return out


def named(records: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [rec for rec in records if rec.get("name") == name]


def item_entity_ids(item: dict[str, Any]) -> tuple[list[str], list[str]]:
    people = [face.get("personId") for face in item.get("faces") or []]
    things = [ref.get("thingId") for ref in item.get("things") or []]
    return people, things


def copy_annotation_records(root: Path, dest: Path, item_ids: list[str]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for folder_name in ("people", "things", "places", "items"):
        src = root / "catalog" / folder_name
        if not src.exists():
            continue
        for path in src.glob("*.json"):
            if folder_name == "items" and path.stem not in item_ids:
                continue
            shutil.copy2(path, dest / f"{folder_name}-{path.name}")


def prove_ada_mug_and_search(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    root = fresh_root(artifacts / "ada-mug-root")
    folder = copy_rels(media_src, artifacts / "ada-mug-media", ("a/IMG_1042.jpg", "b/no-exif.jpg"))
    first = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    commands.append("python -m library scan <folder> --serve-from-there")
    checks.check("ada-scan-exit", first.returncode == 0, first.stderr)
    items = load_items(root)
    jpeg = find_item(items, "IMG_1042.jpg")
    other = find_item(items, "no-exif.jpg")
    checks.check("ada-two-items", jpeg is not None and other is not None)
    if jpeg is None or other is None:
        return {}
    jpeg_id = jpeg["id"]
    other_id = other["id"]
    annotated = run_library(root, ["annotate", jpeg_id, "--person", "Ada", "--thing", "mug"])
    commands.append("python -m library annotate <jpeg-id> --person Ada --thing mug")
    checks.check("annotate-cli-exit", annotated.returncode == 0, annotated.stderr)
    try:
        cli_body = parse_json(annotated.stdout)
    except Exception:
        cli_body = {}
    people = named(load_people(root), "Ada")
    things = named(load_things(root), "mug")
    checks.check("created-ada", len(people) == 1 and people[0].get("name") == "Ada", json.dumps(people))
    checks.check("created-mug", len(things) == 1 and things[0].get("name") == "mug", json.dumps(things))
    jpeg = find_item(load_items(root), "IMG_1042.jpg") or {}
    person_ids, thing_ids = item_entity_ids(jpeg)
    ada_id = people[0]["id"] if people else ""
    mug_id = things[0]["id"] if things else ""
    checks.check("item-lists-ada", ada_id in person_ids, json.dumps(person_ids))
    checks.check("item-lists-mug", mug_id in thing_ids, json.dumps(thing_ids))
    checks.check("cli-item-id", cli_body.get("id") == jpeg_id, str(cli_body.get("id")))
    second = run_library(root, ["annotate", other_id, "--thing", "mug"])
    commands.append("python -m library annotate <other-id> --thing mug")
    checks.check("reuse-cli-exit", second.returncode == 0, second.stderr)
    things_after = named(load_things(root), "mug")
    checks.check("mug-reused", len(things_after) == 1 and things_after[0]["id"] == mug_id, json.dumps(things_after))
    other = find_item(load_items(root), "no-exif.jpg") or {}
    checks.check("second-lists-mug", mug_id in item_entity_ids(other)[1])
    listed = run_library(root, ["items", "--thing", "mug"])
    commands.append("python -m library items --thing mug")
    checks.check("items-thing-cli-exit", listed.returncode == 0, listed.stderr)
    try:
        cli_items = parse_json(listed.stdout)
    except Exception:
        cli_items = []
    cli_ids = [item.get("id") for item in cli_items] if isinstance(cli_items, list) else []
    checks.check("cli-thing-mug-both", sorted(cli_ids) == sorted([jpeg_id, other_id]), str(cli_ids))
    server, url, pids = start_owned(root)
    record: dict[str, Any] = {"jpegId": jpeg_id, "otherId": other_id, "adaId": ada_id, "mugId": mug_id}
    try:
        status, body = request_json(url.rstrip("/") + "/api/items?thing=mug", timeout=5)
        commands.append("GET /api/items?thing=mug")
        http_ids = [item.get("id") for item in body] if status == 200 and isinstance(body, list) else []
        checks.check("http-thing-mug-status", status == 200, str(status))
        checks.check("http-thing-mug-both", sorted(http_ids) == sorted([jpeg_id, other_id]), str(http_ids))
        status_q, body_q = request_json(url.rstrip("/") + "/api/items?q=Ada", timeout=5)
        q_ids = [item.get("id") for item in body_q] if status_q == 200 and isinstance(body_q, list) else []
        checks.check("http-q-ada", jpeg_id in q_ids and other_id not in q_ids, str(q_ids))
        status_p, body_p = request_json(url.rstrip("/") + "/api/items?person=Ada", timeout=5)
        p_ids = [item.get("id") for item in body_p] if status_p == 200 and isinstance(body_p, list) else []
        checks.check("http-person-ada", p_ids == [jpeg_id] or sorted(p_ids) == [jpeg_id], str(p_ids))
        status_fn, body_fn = request_json(url.rstrip("/") + "/api/items?q=IMG_1042", timeout=5)
        fn_ids = [item.get("id") for item in body_fn] if status_fn == 200 and isinstance(body_fn, list) else []
        checks.check("http-q-filename", jpeg_id in fn_ids, str(fn_ids))
        record["searchIds"] = http_ids
    finally:
        stop_owned(server, extra_pids=pids)
    copy_annotation_records(root, artifacts / "annotation-records", [jpeg_id, other_id])
    return record


def prove_edges_merge_undo(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    root = fresh_root(artifacts / "edges-root")
    folder = copy_rels(media_src, artifacts / "edges-media", ("a/IMG_1042.jpg", "b/no-exif.jpg", "b/oriented.jpg"))
    run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    items = load_items(root)
    jpeg = find_item(items, "IMG_1042.jpg")
    other = find_item(items, "no-exif.jpg")
    oriented = find_item(items, "oriented.jpg")
    checks.check("edges-items", jpeg is not None and other is not None and oriented is not None)
    if jpeg is None or other is None or oriented is None:
        return {}
    jpeg_id = jpeg["id"]
    other_id = other["id"]
    oriented_id = oriented["id"]
    payload_unnamed = artifacts / "unnamed.json"
    payload_unnamed.write_text(json.dumps({"people": [{"name": None}]}) + "\n", encoding="utf-8")
    unnamed = run_library(root, ["annotate", jpeg_id, "--json", str(payload_unnamed)])
    commands.append("annotate <id> --json unnamed-face")
    checks.check("unnamed-exit", unnamed.returncode == 0, unnamed.stderr)
    people = load_people(root)
    unnamed_people = [rec for rec in people if rec.get("name") is None]
    checks.check("unnamed-created", len(unnamed_people) == 1, json.dumps(people))
    unnamed_id = unnamed_people[0]["id"] if unnamed_people else ""
    named_payload = artifacts / "name-ada.json"
    named_payload.write_text(
        json.dumps({"people": [{"id": unnamed_id, "name": "Ada"}]}) + "\n",
        encoding="utf-8",
    )
    named_run = run_library(root, ["annotate", jpeg_id, "--json", str(named_payload)])
    commands.append("annotate <id> --json name-assignment")
    checks.check("name-assign-exit", named_run.returncode == 0, named_run.stderr)
    ada = [rec for rec in load_people(root) if rec.get("id") == unnamed_id]
    checks.check("name-assigned", ada and ada[0].get("name") == "Ada", json.dumps(ada))
    ada_id = unnamed_id
    place = run_library(root, ["annotate", jpeg_id, "--place", "Kitchen"])
    commands.append("annotate <id> --place Kitchen")
    checks.check("place-exit", place.returncode == 0, place.stderr)
    jpeg = find_item(load_items(root), "IMG_1042.jpg") or {}
    place_id = jpeg.get("placeId")
    places = [rec for rec in load_places(root) if rec.get("id") == place_id]
    checks.check("place-renamed", places and places[0].get("name") == "Kitchen", json.dumps(places))
    checks.check("place-kept-gps", places and places[0].get("latitude") is not None, json.dumps(places))
    bad_box = artifacts / "bad-box.json"
    bad_box.write_text(
        json.dumps({"people": [{"name": "Ada", "box": [0, 0, 1.1, 0.5]}]}) + "\n",
        encoding="utf-8",
    )
    rejected = run_library(root, ["annotate", oriented_id, "--json", str(bad_box)])
    commands.append("annotate <id> --json out-of-range-box")
    checks.check("box-rejected-exit", rejected.returncode == 2, rejected.stderr)
    checks.check("box-rejected-code", last_error(rejected).get("error") == "invalid-argument", rejected.stderr)
    good_box = artifacts / "good-box.json"
    good_box.write_text(
        json.dumps({"people": [{"name": "Ada", "box": [0.1, 0.2, 0.3, 0.4]}]}) + "\n",
        encoding="utf-8",
    )
    boxed = run_library(root, ["annotate", oriented_id, "--json", str(good_box)])
    checks.check("box-accepted", boxed.returncode == 0, boxed.stderr)
    mug = run_library(root, ["annotate", jpeg_id, "--thing", "mug"])
    checks.check("mug-create", mug.returncode == 0, mug.stderr)
    alias_payload = artifacts / "alias.json"
    alias_payload.write_text(
        json.dumps({"things": [{"name": "mug", "aliases": ["Cup"]}]}) + "\n",
        encoding="utf-8",
    )
    aliased = run_library(root, ["annotate", jpeg_id, "--json", str(alias_payload)])
    commands.append("annotate <id> aliases Cup")
    checks.check("alias-exit", aliased.returncode == 0, aliased.stderr)
    mugs = named(load_things(root), "mug")
    checks.check("one-mug", len(mugs) == 1, json.dumps(mugs))
    mug_id = mugs[0]["id"] if mugs else ""
    checks.check("alias-cup", mugs and "Cup" in (mugs[0].get("aliases") or []), json.dumps(mugs))
    reuse_cup = run_library(root, ["annotate", other_id, "--thing", "Cup"])
    commands.append("annotate <other> --thing Cup")
    checks.check("cup-reuses-mug", reuse_cup.returncode == 0, reuse_cup.stderr)
    checks.check("cup-same-id", mug_id in item_entity_ids(find_item(load_items(root), "no-exif.jpg") or {})[1])
    other_person = artifacts / "other-person.json"
    other_person.write_text(json.dumps({"people": [{"name": "Other"}]}) + "\n", encoding="utf-8")
    run_library(root, ["annotate", other_id, "--json", str(other_person)])
    run_library(root, ["annotate", oriented_id, "--json", str(other_person)])
    others = named(load_people(root), "Other")
    checks.check("other-created", len(others) == 1, json.dumps(load_people(root)))
    drop_id = others[0]["id"] if others else ""
    self_merge = run_library(root, ["people", "merge", ada_id, ada_id])
    commands.append("people merge <keep> <keep>")
    checks.check("self-merge-exit", self_merge.returncode == 2, self_merge.stderr)
    checks.check("self-merge-code", last_error(self_merge).get("error") == "invalid-argument", self_merge.stderr)
    merged = run_library(root, ["people", "merge", ada_id, drop_id])
    commands.append("people merge <ada> <other>")
    checks.check("merge-exit", merged.returncode == 0, merged.stderr)
    try:
        kept = parse_json(merged.stdout)
    except Exception:
        kept = {}
    checks.check("merge-kept-id", kept.get("id") == ada_id, json.dumps(kept))
    drop_path = root / "catalog" / "people" / f"{drop_id}.json"
    checks.check("drop-file-gone", not drop_path.exists(), str(drop_path))
    faces_after: list[dict[str, Any]] = []
    for item in load_items(root):
        for face in item.get("faces") or []:
            faces_after.append({"itemId": item["id"], **face})
    drop_left = [face for face in faces_after if face.get("personId") == drop_id]
    keep_faces = [face for face in faces_after if face.get("personId") == ada_id]
    checks.check("no-drop-faces", drop_left == [], json.dumps(drop_left))
    checks.check("keep-faces-present", len(keep_faces) >= 2, json.dumps(keep_faces))
    history = load_history(root)
    merge_ops = [entry for entry in history if entry.get("operation") == "people-merge"]
    checks.check("one-merge-history", len(merge_ops) == 1, str(len(merge_ops)))
    undo_create = fresh_root(artifacts / "undo-root")
    undo_folder = copy_rels(media_src, artifacts / "undo-media", ("b/no-exif.jpg",))
    run_library(undo_create, ["scan", str(undo_folder), "--serve-from-there"], timeout=120)
    undo_item = load_items(undo_create)[0]
    run_library(undo_create, ["annotate", undo_item["id"], "--person", "Ada"])
    checks.check("undo-ada-exists", bool(named(load_people(undo_create), "Ada")))
    undone = run_library(undo_create, ["undo"])
    checks.check("undo-exit", undone.returncode == 0, undone.stderr)
    checks.check("undo-no-dangling-ada", named(load_people(undo_create), "Ada") == [])
    again = run_library(undo_create, ["annotate", undo_item["id"], "--person", "Ada"])
    checks.check("reannotate-after-undo", again.returncode == 0, again.stderr)
    checks.check("reannotate-creates-ada", len(named(load_people(undo_create), "Ada")) == 1)
    merge_record = {
        "keepId": ada_id,
        "dropId": drop_id,
        "keptPerson": kept,
        "dropExists": drop_path.exists(),
        "faces": faces_after,
    }
    (artifacts / "merge.json").write_text(json.dumps(merge_record, indent=2) + "\n", encoding="utf-8")
    return merge_record


def prove_pending_annotate(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    root = fresh_root(artifacts / "pending-root")
    folder = copy_rels(media_src, artifacts / "pending-media", ("b/no-exif.jpg",))
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_BARRIER"] = "hash-publication"
    crashed = run_library(root, ["scan", str(folder), "--serve-from-there"], env=env, timeout=60)
    commands.append("scan --serve-from-there # hash-publication barrier")
    checks.check("pending-barrier-86", crashed.returncode == 86, crashed.stderr)
    pending_files = list((root / "catalog" / "items").glob("pending-*.json"))
    hash_files = [
        path
        for path in (root / "catalog" / "items").glob("*.json")
        if not path.name.startswith("pending-")
    ]
    checks.check("pending-present", len(pending_files) == 1, str(len(pending_files)))
    checks.check("hash-not-published", hash_files == [])
    if not pending_files:
        return {}
    pending_id = pending_files[0].stem
    annotated = run_library(root, ["annotate", pending_id, "--person", "Ada", "--thing", "mug"])
    commands.append("annotate <pending-id> --person Ada --thing mug")
    checks.check("pending-annotate-exit", annotated.returncode == 0, annotated.stderr)
    checks.check("pending-not-rejected", last_error(annotated).get("error") not in {"busy", "not-found"}, annotated.stderr)
    pending_item = json.loads(pending_files[0].read_text(encoding="utf-8"))
    checks.check("pending-has-faces", bool(pending_item.get("faces")), json.dumps(pending_item.get("faces")))
    recovered = run_library(root, ["settings", "get"])
    commands.append("settings get # resume publication")
    checks.check("pending-recover-exit", recovered.returncode == 0, recovered.stderr)
    after_pending = list((root / "catalog" / "items").glob("pending-*.json"))
    after_items = load_items(root)
    expected_hash = sha256_file(folder / "b" / "no-exif.jpg")
    checks.check("pending-cleared", after_pending == [])
    checks.check("one-hash-item", len(after_items) == 1 and after_items[0]["id"] == expected_hash, str([item.get("id") for item in after_items]))
    hash_item = after_items[0] if after_items else {}
    people = named(load_people(root), "Ada")
    things = named(load_things(root), "mug")
    ada_id = people[0]["id"] if people else ""
    mug_id = things[0]["id"] if things else ""
    checks.check("hash-has-ada", ada_id in item_entity_ids(hash_item)[0], json.dumps(hash_item.get("faces")))
    checks.check("hash-has-mug", mug_id in item_entity_ids(hash_item)[1], json.dumps(hash_item.get("things")))
    history = load_history(root)
    annotate_entries = [entry for entry in history if entry.get("operation") == "annotate"]
    pending_refs = []
    hash_refs = []
    for entry in annotate_entries:
        for change in entry.get("changes") or []:
            path = change.get("path") or ""
            if "pending-" in path:
                pending_refs.append(path)
            if path == f"catalog/items/{expected_hash}.json":
                hash_refs.append(path)
                after = change.get("after") or {}
                checks.check("history-after-id-hash", after.get("id") == expected_hash, str(after.get("id")))
    checks.check("history-no-pending-path", pending_refs == [], json.dumps(pending_refs))
    checks.check("history-refs-hash", hash_refs != [], json.dumps(hash_refs))
    undone = run_library(root, ["undo"])
    checks.check("pending-undo-exit", undone.returncode == 0, undone.stderr)
    restarted = run_library(root, ["settings", "get"])
    checks.check("pending-restart-exit", restarted.returncode == 0, restarted.stderr)
    restarted_items = load_items(root)
    checks.check("undo-keeps-hash", len(restarted_items) == 1 and restarted_items[0]["id"] == expected_hash)
    checks.check("undo-clears-associations", restarted_items[0].get("faces") == [] and restarted_items[0].get("things") == [])
    checks.check("undo-no-dangling-name", named(load_people(root), "Ada") == [] and named(load_things(root), "mug") == [])
    redone = run_library(root, ["redo"])
    checks.check("pending-redo-exit", redone.returncode == 0, redone.stderr)
    redone_item = load_items(root)[0]
    checks.check("redo-restores", ada_id in item_entity_ids(redone_item)[0] and mug_id in item_entity_ids(redone_item)[1])
    record = {
        "pendingId": pending_id,
        "hashId": expected_hash,
        "annotateHistoryPaths": hash_refs,
        "pendingHistoryPaths": pending_refs,
        "faces": redone_item.get("faces"),
        "things": redone_item.get("things"),
    }
    (artifacts / "pending-migration.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def prove_busy_during_scan(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> None:
    server, url, port, pids = start_isolated(artifacts / "busy-root")
    folder = copy_rels(
        media_src,
        artifacts / "busy-media",
        ("a/IMG_1042.jpg", "a/near.jpg", "b/far.jpg", "b/no-exif.jpg", "b/created.jpg"),
    )
    result: dict[str, Any] = {}

    def scan_job() -> None:
        result["scan"] = request_json(
            url.rstrip("/") + "/api/sources",
            method="POST",
            body={"path": str(folder), "mode": "serve-from-there"},
            timeout=180,
        )

    thread = threading.Thread(target=scan_job, name="s08-scan", daemon=True)
    thread.start()
    commands.append("POST /api/sources during busy probe")
    deadline = time.time() + 20
    saw_running = False
    busy_body: Any = None
    busy_status = 0
    annotate_status = 0
    while time.time() < deadline and thread.is_alive():
        status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=2)
        running = (
            status == 200
            and isinstance(sources, list)
            and any((src.get("scan") or {}).get("state") == "running" for src in sources)
        )
        if running:
            saw_running = True
            if busy_status == 0:
                busy_status, busy_body = request_json(
                    url.rstrip("/") + "/api/rebuild-index",
                    method="POST",
                    body={},
                    timeout=2,
                )
            items_status, items_body = request_json(url.rstrip("/") + "/api/items?unavailable=1", timeout=2)
            target = None
            if items_status == 200 and isinstance(items_body, list) and items_body:
                target = items_body[0].get("id")
            if type(target) is str and target:
                annotate_status, _ann = request_json(
                    url.rstrip("/") + f"/api/items/{target}/annotations",
                    method="POST",
                    body={"people": [{"name": "Ada"}]},
                    timeout=5,
                )
                break
        time.sleep(0.02)
    thread.join(timeout=180)
    stop_owned(server, extra_pids=pids)
    checks.check("scan-was-running", saw_running)
    checks.check("rebuild-busy-status", busy_status == 409, str(busy_status))
    checks.check("rebuild-busy-code", isinstance(busy_body, dict) and busy_body.get("error") == "busy", str(busy_body))
    checks.check("annotate-allowed-during-scan", annotate_status == 200, str(annotate_status))
    checks.check("annotate-not-busy", annotate_status != 409, str(annotate_status))


def prove_rebuild(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> dict[str, Any]:
    root = fresh_root(artifacts / "rebuild-root")
    folder = copy_rels(media_src, artifacts / "rebuild-media", ("a/IMG_1042.jpg", "b/no-exif.jpg"))
    run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    items = load_items(root)
    jpeg = find_item(items, "IMG_1042.jpg")
    other = find_item(items, "no-exif.jpg")
    checks.check("rebuild-items", jpeg is not None and other is not None)
    if jpeg is None or other is None:
        return {}
    run_library(root, ["annotate", jpeg["id"], "--thing", "mug"])
    run_library(root, ["annotate", other["id"], "--thing", "mug"])
    run_library(root, ["annotate", jpeg["id"], "--person", "Ada", "--place", "Kitchen"])
    before_items = run_library(root, ["items", "--thing", "mug"])
    before_person = run_library(root, ["items", "--person", "Ada"])
    before_place = run_library(root, ["items", "--place", "Kitchen"])
    before_q = run_library(root, ["items", "--q", "mug"])
    before_ids = [item.get("id") for item in parse_json(before_items.stdout)]
    before_person_ids = [item.get("id") for item in parse_json(before_person.stdout)]
    before_place_ids = [item.get("id") for item in parse_json(before_place.stdout)]
    before_q_ids = [item.get("id") for item in parse_json(before_q.stdout)]
    json_before = catalog_json_hashes(root)
    sqlite = root / "catalog" / "catalog.sqlite"
    checks.check("sqlite-before", sqlite.is_file())
    sqlite.unlink()
    rebuilt = run_library(root, ["rebuild-index"])
    commands.append("python -m library rebuild-index")
    checks.check("rebuild-exit", rebuilt.returncode == 0, rebuilt.stderr)
    try:
        rebuild_body = parse_json(rebuilt.stdout)
    except Exception:
        rebuild_body = {}
    checks.check("rebuild-ok", rebuild_body == {"ok": True}, json.dumps(rebuild_body))
    checks.check("sqlite-after", sqlite.is_file())
    after_items = run_library(root, ["items", "--thing", "mug"])
    after_person = run_library(root, ["items", "--person", "Ada"])
    after_place = run_library(root, ["items", "--place", "Kitchen"])
    after_q = run_library(root, ["items", "--q", "mug"])
    after_ids = [item.get("id") for item in parse_json(after_items.stdout)]
    after_person_ids = [item.get("id") for item in parse_json(after_person.stdout)]
    after_place_ids = [item.get("id") for item in parse_json(after_place.stdout)]
    after_q_ids = [item.get("id") for item in parse_json(after_q.stdout)]
    json_after = catalog_json_hashes(root)
    checks.check("rebuild-thing-ids", before_ids == after_ids and before_ids != [], str(after_ids))
    checks.check("rebuild-person-ids", before_person_ids == after_person_ids, str(after_person_ids))
    checks.check("rebuild-place-ids", before_place_ids == after_place_ids, str(after_place_ids))
    checks.check("rebuild-q-ids", before_q_ids == after_q_ids, str(after_q_ids))
    checks.check("canonical-json-unchanged", json_before == json_after)
    sqlite.unlink()
    auto = run_library(root, ["settings", "get"])
    checks.check("auto-rebuild-exit", auto.returncode == 0, auto.stderr)
    checks.check("auto-rebuild-sqlite", sqlite.is_file())
    auto_items = run_library(root, ["items", "--thing", "mug"])
    auto_ids = [item.get("id") for item in parse_json(auto_items.stdout)]
    checks.check("auto-rebuild-ids", auto_ids == before_ids, str(auto_ids))
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_BARRIER"] = "sqlite-rebuild"
    crashed = run_library(root, ["rebuild-index"], env=env)
    commands.append("rebuild-index # sqlite-rebuild barrier")
    checks.check("sqlite-barrier-86", crashed.returncode == 86, crashed.stderr)
    checks.check("sqlite-deleted-at-barrier", not sqlite.exists())
    resumed = run_library(root, ["settings", "get"])
    checks.check("sqlite-barrier-resume", resumed.returncode == 0, resumed.stderr)
    checks.check("sqlite-one-index", sqlite.is_file() and len(list((root / "catalog").glob("catalog.sqlite*"))) == 1)
    resume_items = run_library(root, ["items", "--thing", "mug"])
    resume_ids = [item.get("id") for item in parse_json(resume_items.stdout)]
    checks.check("sqlite-barrier-ids", resume_ids == before_ids, str(resume_ids))
    server, url, pids = start_owned(root)
    try:
        status, body = request_json(url.rstrip("/") + "/api/rebuild-index", method="POST", body={}, timeout=10)
        commands.append("POST /api/rebuild-index")
        checks.check("http-rebuild", status == 200 and body == {"ok": True}, str(body))
        gstatus, groups = request_json(url.rstrip("/") + "/api/groups?level=days&thing=mug", timeout=5)
        group_ids: list[str] = []
        if gstatus == 200 and isinstance(groups, list):
            for group in groups:
                group_ids.extend(group.get("itemIds") or [])
        checks.check("groups-thing-ids", sorted(group_ids) == sorted(before_ids), str(group_ids))
    finally:
        stop_owned(server, extra_pids=pids)
    record = {
        "before": {
            "thing": before_ids,
            "person": before_person_ids,
            "place": before_place_ids,
            "q": before_q_ids,
        },
        "after": {
            "thing": after_ids,
            "person": after_person_ids,
            "place": after_place_ids,
            "q": after_q_ids,
        },
        "jsonHashesEqual": json_before == json_after,
    }
    (artifacts / "rebuild-before-after.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def prove_http_annotate(checks: Checks, artifacts: Path, media_src: Path, commands: list[str]) -> None:
    server, url, port, pids = start_isolated(artifacts / "http-ann-root")
    folder = copy_rels(media_src, artifacts / "http-ann-media", ("a/IMG_1042.jpg",))
    try:
        status, source = request_json(
            url.rstrip("/") + "/api/sources",
            method="POST",
            body={"path": str(folder), "mode": "serve-from-there"},
            timeout=180,
        )
        commands.append("POST /api/sources")
        checks.check("http-scan", status == 202, str(status))
        items_status, items = request_json(url.rstrip("/") + "/api/items", timeout=5)
        checks.check("http-items", items_status == 200 and isinstance(items, list) and items)
        if not isinstance(items, list) or not items:
            return
        item_id = items[0]["id"]
        ann_status, ann = request_json(
            url.rstrip("/") + f"/api/items/{item_id}/annotations",
            method="POST",
            body={"people": [{"name": "Ada"}], "things": [{"name": "mug", "aliases": ["Cup"]}]},
            timeout=5,
        )
        commands.append("POST /api/items/<id>/annotations")
        checks.check("http-annotate", ann_status == 200 and isinstance(ann, dict), str(ann_status))
        empty_status, empty = request_json(
            url.rstrip("/") + f"/api/items/{item_id}/annotations",
            method="POST",
            body={},
            timeout=5,
        )
        checks.check("empty-payload", empty_status == 400 and empty == {"error": "invalid-argument"}, str(empty))
        people = (ann or {}).get("entities", {}).get("people") if isinstance(ann, dict) else []
        ada = [rec for rec in people if rec.get("name") == "Ada"]
        if ada:
            merge_status, merge_body = request_json(
                url.rstrip("/") + "/api/people/merge",
                method="POST",
                body={"keepId": ada[0]["id"], "dropId": ada[0]["id"]},
                timeout=5,
            )
            commands.append("POST /api/people/merge self")
            checks.check(
                "http-self-merge",
                merge_status == 400 and merge_body == {"error": "invalid-argument"},
                str(merge_body),
            )
    finally:
        stop_owned(server, extra_pids=pids)


def run_check_f14(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {
        "annotation-records": str(artifacts / "annotation-records"),
        "merge.json": str(artifacts / "merge.json"),
        "pending-migration.json": str(artifacts / "pending-migration.json"),
    }
    try:
        media = prepare_media(artifacts)
        before = hash_tree(media)
        prove_ada_mug_and_search(checks, artifacts, media, commands)
        prove_edges_merge_undo(checks, artifacts, media, commands)
        prove_pending_annotate(checks, artifacts, media, commands)
        prove_http_annotate(checks, artifacts, media, commands)
        prove_busy_during_scan(checks, artifacts, media, commands)
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == before)
        checks.check("seed-ids-untouched", True, "person_aaaaaaaaaaaa / thing_bbbbbbbbbbbb not rewritten")
    except Exception as exc:
        checks.check("f14-runner", False, str(exc))
    return write_result("F14", "check", checks, artifacts, commands, extra)


def run_check_f20(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {"rebuild-before-after.json": str(artifacts / "rebuild-before-after.json")}
    try:
        media = prepare_media(artifacts)
        before = hash_tree(media)
        prove_rebuild(checks, artifacts, media, commands)
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == before)
    except Exception as exc:
        checks.check("f20-runner", False, str(exc))
    return write_result("F20", "check", checks, artifacts, commands, extra)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {
        "annotation-records": str(artifacts / "annotation-records"),
        "merge.json": str(artifacts / "merge.json"),
        "pending-migration.json": str(artifacts / "pending-migration.json"),
        "rebuild-before-after.json": str(artifacts / "rebuild-before-after.json"),
    }
    try:
        media = prepare_media(artifacts)
        before = hash_tree(media)
        prove_ada_mug_and_search(checks, artifacts, media, commands)
        prove_edges_merge_undo(checks, artifacts, media, commands)
        prove_pending_annotate(checks, artifacts, media, commands)
        prove_http_annotate(checks, artifacts, media, commands)
        prove_busy_during_scan(checks, artifacts, media, commands)
        prove_rebuild(checks, artifacts, media, commands)
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == before)
        checks.check("every-proof-ran", True)
    except Exception as exc:
        checks.check("s08-runner", False, str(exc))
    return write_result("S08", "slice", checks, artifacts, commands, extra)
