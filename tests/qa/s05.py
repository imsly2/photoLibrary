"""Slice S05 / Check F1 / Check F4 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json
from library.copy import copy_root_rel, is_partial_name, safe_name
from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    _env,
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


def pin_mtime(path: Path, iso: str) -> None:
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def start_isolated(root: Path) -> tuple[subprocess.Popen[str], str, int, list[int]]:
    isolated = Path(root)
    last_exc: Exception | None = None
    for _ in range(5):
        if isolated.exists():
            shutil.rmtree(isolated)
        prepare_root(isolated)
        port = find_free_port()
        write_isolated_port(isolated, port)
        server = start_server(isolated)
        url = f"http://127.0.0.1:{port}/"
        try:
            health_status, health_body = wait_health(url, server)
        except RuntimeError as exc:
            last_exc = exc
            stop_owned(server)
            if "port-in-use" not in str(exc):
                raise
            time.sleep(0.2)
            continue
        if health_status != 200 or health_body != {"ok": True}:
            stop_owned(server)
            raise RuntimeError(f"health {health_status} {health_body}")
        owned_pids: list[int] = []
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/runtime", timeout=2) as resp:
                runtime_body = json.loads(resp.read().decode("utf-8"))
            server_pid = runtime_body.get("pid")
            if type(server_pid) is int:
                owned_pids.append(server_pid)
        except Exception:
            pass
        return server, url, port, owned_pids
    raise RuntimeError(last_exc or "could not start isolated server")

PERSON_ID = "person_aaaaaaaaaaaa"
THING_ID = "thing_bbbbbbbbbbbb"
LINKED_SERIAL = "windows:s05-linked"
OTHER_SERIAL = "windows:s05-other"


def load_manifest() -> dict[str, Any]:
    return json.loads((COMMITTED_FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def pin_media_from_manifest(media: Path) -> None:
    files = {rec["path"]: rec for rec in load_manifest().get("files", [])}
    for rel, rec in files.items():
        path = media / Path(rel)
        if path.is_file():
            pin_mtime(path, rec["mtime"])


def pin_tree(folder: Path, iso: str = "2022-01-01T00:00:00Z") -> None:
    files = {rec["path"]: rec for rec in load_manifest().get("files", [])}
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(folder).as_posix()
        if rel in files:
            pin_mtime(path, files[rel]["mtime"])
        else:
            pin_mtime(path, iso)


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


def originals_files(root: Path) -> list[Path]:
    folder = root / "originals"
    if not folder.exists():
        return []
    out: list[Path] = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and not is_partial_name(path.name):
            out.append(path)
    return out


def partials(root: Path) -> list[Path]:
    folder = root / "originals"
    if not folder.exists():
        return []
    return [path for path in folder.rglob("*") if path.is_file() and is_partial_name(path.name)]


def copy_root_of(root: Path, source: dict[str, Any]) -> Path:
    rel = source.get("copyRoot") or copy_root_rel(source.get("name") or "folder", source["id"])
    return root / Path(*rel.split("/"))


def seed_entities(root: Path, item_path: Path) -> dict[str, Any]:
    people = root / "catalog" / "people"
    things = root / "catalog" / "things"
    people.mkdir(parents=True, exist_ok=True)
    things.mkdir(parents=True, exist_ok=True)
    person = {"schemaVersion": 1, "id": PERSON_ID, "name": "Ada"}
    thing = {"schemaVersion": 1, "id": THING_ID, "name": "mug", "aliases": []}
    atomic_write_json(people / f"{PERSON_ID}.json", person)
    atomic_write_json(things / f"{THING_ID}.json", thing)
    item = json.loads(item_path.read_text(encoding="utf-8"))
    item["faces"] = [{"personId": PERSON_ID}]
    item["things"] = [{"thingId": THING_ID}]
    item_path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return item


def item_has_ada_mug(item: dict[str, Any]) -> bool:
    faces = item.get("faces") or []
    things = item.get("things") or []
    return any(face.get("personId") == PERSON_ID for face in faces) and any(
        thing.get("thingId") == THING_ID for thing in things
    )


def primary_kind(item: dict[str, Any]) -> str | None:
    primaries = [loc for loc in item.get("locations") or [] if loc.get("role") == "primary"]
    if not primaries:
        return None
    return primaries[0].get("kind")


def no_pillow(checks: Checks) -> None:
    hits = []
    for path in (PRODUCT_ROOT / "library").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PIL" in text or "pillow" in text.lower():
            hits.append(str(path.relative_to(PRODUCT_ROOT)))
    checks.check("library-no-pillow", hits == [], ", ".join(hits))


def prepare_media(artifacts: Path) -> Path:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    pin_media_from_manifest(media)
    return media


def make_two_file_folder(src_media: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    photo = dest / "a" / "photo.jpg"
    clip = dest / "a" / "clip.mp4"
    photo.parent.mkdir(parents=True)
    shutil.copy2(src_media / "a" / "IMG_1042.jpg", photo)
    shutil.copy2(src_media / "a" / "clip.mp4", clip)
    pin_media_from_manifest(src_media)
    files = {rec["path"]: rec for rec in load_manifest().get("files", [])}
    pin_mtime(photo, files["a/IMG_1042.jpg"]["mtime"])
    pin_mtime(clip, files["a/clip.mp4"]["mtime"])
    return dest


def dump_copied_items(root: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    items = root / "catalog" / "items"
    if items.exists():
        shutil.copytree(items, dest, dirs_exist_ok=True)


def prove_choice_and_override(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
) -> None:
    ask_root = artifacts / "choice-root"
    if ask_root.exists():
        shutil.rmtree(ask_root)
    prepare_root(ask_root)
    folder = artifacts / "choice-media"
    make_two_file_folder(src_media, folder)
    no_flag = run_library(ask_root, ["scan", str(folder)])
    commands.append("scan <path> # ask default")
    checks.check("choice-required-exit", no_flag.returncode == 2, no_flag.stderr)
    try:
        err = parse_json(no_flag.stderr.strip().splitlines()[-1])
    except Exception:
        err = {}
    checks.check("choice-required-code", err.get("error") == "choice-required", no_flag.stderr)

    default_copy = artifacts / "default-copy-root"
    if default_copy.exists():
        shutil.rmtree(default_copy)
    prepare_root(default_copy)
    run_library(default_copy, ["settings", "set", "addFolderDefault", "copy-here"])
    flag_link = run_library(
        default_copy,
        ["scan", str(folder), "--serve-from-there"],
        timeout=180,
    )
    commands.append("addFolderDefault=copy-here scan --serve-from-there")
    checks.check("cli-flag-wins-link-exit", flag_link.returncode == 0, flag_link.stderr)
    sources = load_sources(default_copy)
    checks.check("cli-flag-wins-link-mode", sources and sources[0].get("mode") == "serve-from-there")
    checks.check("cli-flag-wins-no-originals", originals_files(default_copy) == [])

    default_link = artifacts / "default-link-root"
    if default_link.exists():
        shutil.rmtree(default_link)
    prepare_root(default_link)
    run_library(default_link, ["settings", "set", "addFolderDefault", "serve-from-there"])
    flag_copy = run_library(
        default_link,
        ["scan", str(folder), "--copy-here"],
        timeout=180,
    )
    commands.append("addFolderDefault=serve-from-there scan --copy-here")
    checks.check("cli-flag-wins-copy-exit", flag_copy.returncode == 0, flag_copy.stderr)
    sources = load_sources(default_link)
    checks.check("cli-flag-wins-copy-mode", sources and sources[0].get("mode") == "copy-here")
    checks.check("cli-flag-wins-has-originals", len(originals_files(default_link)) == 2)

    implicit = artifacts / "implicit-copy-root"
    if implicit.exists():
        shutil.rmtree(implicit)
    prepare_root(implicit)
    run_library(implicit, ["settings", "set", "addFolderDefault", "copy-here"])
    implicit_scan = run_library(implicit, ["scan", str(folder)], timeout=180)
    commands.append("addFolderDefault=copy-here scan <path>")
    checks.check("implicit-copy-exit", implicit_scan.returncode == 0, implicit_scan.stderr)
    sources = load_sources(implicit)
    checks.check("implicit-copy-mode", sources and sources[0].get("mode") == "copy-here")


def prove_f4_two_file(
    root: Path,
    src_media: Path,
    artifacts: Path,
    checks: Checks,
    commands: list[str],
) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    prepare_root(root)
    copy_folder = artifacts / "f4-copy-media"
    link_folder = artifacts / "f4-link-media"
    make_two_file_folder(src_media, copy_folder)
    if link_folder.exists():
        shutil.rmtree(link_folder)
    link_folder.mkdir(parents=True)
    (link_folder / "b").mkdir()
    shutil.copy2(src_media / "b" / "far.jpg", link_folder / "b" / "far.jpg")
    shutil.copy2(src_media / "b" / "no-exif.jpg", link_folder / "b" / "no-exif.jpg")
    files = {rec["path"]: rec for rec in load_manifest().get("files", [])}
    pin_mtime(link_folder / "b" / "far.jpg", files["b/far.jpg"]["mtime"])
    pin_mtime(link_folder / "b" / "no-exif.jpg", files["b/no-exif.jpg"]["mtime"])
    before = hash_tree(copy_folder)
    copied = run_library(root, ["scan", str(copy_folder), "--copy-here"], timeout=180)
    commands.append("scan <a/> --copy-here")
    checks.check("f4-copy-exit", copied.returncode == 0, copied.stderr)
    summary = parse_summary(copied.stdout) if copied.stdout.strip() else {}
    checks.check("f4-copy-added-2", summary.get("added") == 2, json.dumps(summary))
    sources = load_sources(root)
    checks.check("f4-one-copied-source", len(sources) == 1, str(len(sources)))
    source = sources[0] if sources else {}
    checks.check("f4-copy-mode", source.get("mode") == "copy-here")
    copy_root = source.get("copyRoot")
    checks.check(
        "f4-copy-root-shape",
        type(copy_root) is str
        and copy_root.startswith("originals/")
        and copy_root.endswith("-" + str(source.get("id"))),
        str(copy_root),
    )
    dest_photo = root / Path(*str(copy_root).split("/")) / "a" / "photo.jpg"
    dest_clip = root / Path(*str(copy_root).split("/")) / "a" / "clip.mp4"
    checks.check("f4-copied-photo", dest_photo.is_file(), str(dest_photo))
    checks.check("f4-copied-clip", dest_clip.is_file(), str(dest_clip))
    checks.check("f4-structure-kept", dest_photo.parent.name == "a")
    checks.check("f4-source-bytes-unchanged", hash_tree(copy_folder) == before)
    items = load_items(root)
    checks.check("f4-two-items", len(items) == 2, str([item.get("filename") for item in items]))
    names = {item.get("filename") for item in items}
    checks.check("f4-filenames", names == {"photo.jpg", "clip.mp4"}, str(names))
    for item in items:
        locs = item.get("locations") or []
        checks.check(f"f4-loc0-library-relative:{item.get('filename')}", locs and locs[0].get("kind") == "library-relative")
        checks.check(f"f4-no-partial-path:{item.get('filename')}", ".partial-" not in str(locs[0].get("libraryRelativePath")))
    dump_copied_items(root, artifacts / "copied-items")
    checks.check("copied-items-artifact", any((artifacts / "copied-items").glob("*.json")))

    linked = run_library(root, ["scan", str(link_folder), "--serve-from-there"], timeout=180)
    commands.append("scan <second/> --serve-from-there")
    checks.check("f4-link-exit", linked.returncode == 0, linked.stderr)
    after_originals = originals_files(root)
    checks.check("f4-link-no-extra-originals", len(after_originals) == 2, str(len(after_originals)))
    sources = load_sources(root)
    checks.check("f4-two-sources", len(sources) == 2, str(len(sources)))
    linked_source = next((src for src in sources if src.get("mode") == "serve-from-there"), None)
    checks.check("f4-linked-source", linked_source is not None)
    link_items = [
        item
        for item in load_items(root)
        if any(loc.get("sourceId") == (linked_source or {}).get("id") for loc in item.get("locations") or [])
    ]
    for item in link_items:
        primaries = [loc for loc in item.get("locations") or [] if loc.get("role") == "primary"]
        checks.check(
            f"f4-linked-kind-volume:{item.get('filename')}",
            primaries and primaries[0].get("kind") == "volume",
            json.dumps(primaries),
        )
    return source


def prove_collision(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
) -> None:
    root = artifacts / "collision-root"
    if root.exists():
        shutil.rmtree(root)
    prepare_root(root)
    folder = artifacts / "collision-media"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    shutil.copy2(src_media / "a" / "near.jpg", folder / "keep.jpg")
    pin_mtime(folder / "keep.jpg", "2022-01-01T00:00:00Z")
    first = run_library(root, ["scan", str(folder), "--copy-here"], timeout=120)
    commands.append("scan keep.jpg --copy-here")
    checks.check("collision-seed-scan", first.returncode == 0, first.stderr)
    source = load_sources(root)[0]
    dest_dir = copy_root_of(root, source)
    dest_dir.mkdir(parents=True, exist_ok=True)
    seed_a = dest_dir / "photo.jpg"
    seed_b = dest_dir / "photo_2.jpg"
    shutil.copy2(src_media / "b" / "far.jpg", seed_a)
    shutil.copy2(src_media / "b" / "no-exif.jpg", seed_b)
    hash_a = sha256_file(seed_a)
    hash_b = sha256_file(seed_b)
    shutil.copy2(src_media / "a" / "IMG_1042.jpg", folder / "photo.jpg")
    pin_mtime(folder / "photo.jpg", "2022-01-01T00:00:00Z")
    second = run_library(root, ["scan", str(folder), "--copy-here"], timeout=120)
    commands.append("scan photo.jpg --copy-here after seeded dest")
    checks.check("collision-rescan-exit", second.returncode == 0, second.stderr)
    written = dest_dir / "photo_3.jpg"
    checks.check("collision-wrote-photo-3", written.is_file(), str(list(dest_dir.iterdir())))
    checks.check("collision-seed-a-unchanged", sha256_file(seed_a) == hash_a)
    checks.check("collision-seed-b-unchanged", sha256_file(seed_b) == hash_b)
    checks.check("collision-not-overwrite-photo", sha256_file(seed_a) != sha256_file(written))
    items = [item for item in load_items(root) if item.get("filename") == "photo.jpg"]
    checks.check("collision-item-filename", len(items) == 1)
    if items:
        loc = items[0]["locations"][0]
        checks.check(
            "collision-record-points-photo-3",
            str(loc.get("libraryRelativePath") or "").endswith("photo_3.jpg"),
            str(loc.get("libraryRelativePath")),
        )
        checks.check("collision-display-name", items[0].get("filename") == "photo.jpg")
    payload = {
        "seeded": {"photo.jpg": hash_a, "photo_2.jpg": hash_b},
        "written": "photo_3.jpg",
        "writtenHash": sha256_file(written) if written.is_file() else None,
        "seededUnchanged": sha256_file(seed_a) == hash_a and sha256_file(seed_b) == hash_b,
    }
    (artifacts / "collision.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def prove_interrupt(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
) -> None:
    root = artifacts / "interrupt-root"
    if root.exists():
        shutil.rmtree(root)
    prepare_root(root)
    folder = artifacts / "interrupt-media"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    shutil.copy2(src_media / "a" / "IMG_1042.jpg", folder / "photo.jpg")
    pin_mtime(folder / "photo.jpg", "2022-01-01T00:00:00Z")
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_BARRIER"] = "copy-partial"
    crashed = run_library(root, ["scan", str(folder), "--copy-here"], env=env, timeout=60)
    commands.append("scan --copy-here LIBRARY_TEST_BARRIER=copy-partial")
    checks.check("interrupt-exit-86", crashed.returncode == 86, crashed.stderr)
    try:
        barrier = parse_json(crashed.stderr.strip().splitlines()[-1])
    except Exception:
        barrier = {}
    checks.check(
        "interrupt-barrier",
        barrier.get("error") == "test-barrier" and barrier.get("barrier") == "copy-partial",
        crashed.stderr,
    )
    dests = originals_files(root)
    parts = partials(root)
    checks.check("interrupt-no-published-original", dests == [], str(dests))
    checks.check("interrupt-partial-present", len(parts) == 1, str(parts))
    checks.check(
        "interrupt-partial-not-item",
        all(".partial-" not in str((item.get("locations") or [{}])[0].get("libraryRelativePath") or "") for item in load_items(root)),
    )
    sources = load_sources(root)
    checks.check("interrupt-mapping-persisted", bool(sources and sources[0].get("files")), json.dumps(sources))
    mapped_dest = None
    if sources:
        for entry in (sources[0].get("files") or {}).values():
            mapped_dest = entry.get("destination")
    resume = run_library(root, ["scan", str(folder), "--copy-here"], timeout=120)
    commands.append("scan --copy-here # resume")
    checks.check("interrupt-resume-exit", resume.returncode == 0, resume.stderr)
    dests_after = originals_files(root)
    parts_after = partials(root)
    checks.check("interrupt-resume-one-original", len(dests_after) == 1, str(dests_after))
    checks.check("interrupt-no-extra-copy", len(dests_after) == 1)
    checks.check("interrupt-partial-cleared", parts_after == [], str(parts_after))
    items = load_items(root)
    checks.check("interrupt-one-item", len(items) == 1, str([item.get("id") for item in items]))
    if items and mapped_dest:
        loc = items[0]["locations"][0]
        checks.check("interrupt-item-not-partial", loc.get("libraryRelativePath") == mapped_dest, str(loc))
        checks.check("interrupt-kind", loc.get("kind") == "library-relative")


def prove_convert(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
) -> None:
    root = artifacts / "convert-root"
    if root.exists():
        shutil.rmtree(root)
    prepare_root(root)
    folder = artifacts / "convert-media"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    shutil.copy2(src_media / "a" / "IMG_1042.jpg", folder / "photo.jpg")
    pin_mtime(folder / "photo.jpg", "2022-01-01T00:00:00Z")
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_BARRIER"] = "hash-publication"
    crashed = run_library(root, ["scan", str(folder), "--serve-from-there"], env=env, timeout=60)
    checks.check("convert-barrier-exit", crashed.returncode == 86, crashed.stderr)
    pending_files = list((root / "catalog" / "items").glob("pending-*.json"))
    checks.check("convert-pending-present", len(pending_files) == 1, str(pending_files))
    if pending_files:
        seed_entities(root, pending_files[0])
        pending = json.loads(pending_files[0].read_text(encoding="utf-8"))
        checks.check("convert-pending-seeded", item_has_ada_mug(pending))
    recovered = run_library(root, ["settings", "get"])
    checks.check("convert-recover", recovered.returncode == 0, recovered.stderr)
    items = load_items(root)
    checks.check("convert-one-final", len(items) == 1 and not str(items[0].get("id", "")).startswith("pending-"))
    before_id = items[0]["id"] if items else None
    if items:
        if not item_has_ada_mug(items[0]):
            seed_entities(root, root / "catalog" / "items" / f"{items[0]['id']}.json")
            items = load_items(root)
        checks.check("convert-final-seeded", item_has_ada_mug(items[0]))
    source = load_sources(root)[0]
    source_id = source["id"]
    converted = run_library(root, ["copy-here", source_id], timeout=180)
    commands.append(f"copy-here {source_id}")
    checks.check("convert-exit", converted.returncode == 0, converted.stderr)
    after_sources = load_sources(root)
    checks.check("convert-same-source-id", after_sources and after_sources[0]["id"] == source_id)
    checks.check("convert-mode", after_sources and after_sources[0].get("mode") == "copy-here")
    after_items = load_items(root)
    checks.check("convert-same-item-id", after_items and after_items[0]["id"] == before_id, str(before_id))
    if after_items:
        item = after_items[0]
        checks.check("convert-annotations", item_has_ada_mug(item), json.dumps(item.get("faces")))
        primaries = [loc for loc in item["locations"] if loc.get("role") == "primary"]
        alts = [loc for loc in item["locations"] if loc.get("role") == "alternate"]
        checks.check("convert-copied-primary", primaries and primaries[0].get("kind") == "library-relative")
        checks.check("convert-old-volume-alternate", alts and alts[0].get("kind") == "volume")
        checks.check("convert-same-source-on-locs", all(loc.get("sourceId") == source_id for loc in item["locations"]))
    again = run_library(root, ["copy-here", source_id], timeout=60)
    checks.check("convert-noop-exit", again.returncode == 0, again.stderr)
    checks.check("convert-noop-no-extra", len(originals_files(root)) == 1, str(originals_files(root)))


def prove_undo(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
) -> None:
    root = artifacts / "undo-root"
    if root.exists():
        shutil.rmtree(root)
    prepare_root(root)
    folder = artifacts / "undo-media"
    make_two_file_folder(src_media, folder)
    source_hashes = hash_tree(folder)
    scanned = run_library(root, ["scan", str(folder), "--copy-here"], timeout=180)
    commands.append("scan --copy-here then undo")
    checks.check("undo-scan-exit", scanned.returncode == 0, scanned.stderr)
    copied_hashes = {path.relative_to(root).as_posix(): sha256_file(path) for path in originals_files(root)}
    checks.check("undo-has-originals", len(copied_hashes) == 2, str(copied_hashes))
    checks.check("undo-has-catalog", load_sources(root) and load_items(root))
    undone = run_library(root, ["undo"])
    checks.check("undo-exit", undone.returncode == 0, undone.stderr)
    checks.check("undo-source-gone", load_sources(root) == [])
    checks.check("undo-items-gone", load_items(root) == [])
    after_copied = {path.relative_to(root).as_posix(): sha256_file(path) for path in originals_files(root)}
    checks.check("undo-bytes-remain", after_copied == copied_hashes, json.dumps(after_copied))
    checks.check("undo-source-folder-untouched", hash_tree(folder) == source_hashes)


def prove_move_and_remap(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
    *,
    serve: bool,
) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    copy_root = artifacts / "move-library-data"
    if copy_root.exists():
        shutil.rmtree(copy_root)
    prepare_root(copy_root)
    folder = artifacts / "move-copy-media"
    make_two_file_folder(src_media, folder)
    source_before = hash_tree(folder)
    scanned = run_library(copy_root, ["scan", str(folder), "--copy-here"], timeout=180)
    commands.append("scan --copy-here then move library-data")
    checks.check("move-copy-exit", scanned.returncode == 0, scanned.stderr)
    items_before = load_items(copy_root)
    checks.check("move-two-items", len(items_before) == 2)
    before_ids = sorted(item["id"] for item in items_before)
    before_hashes = {path.relative_to(copy_root).as_posix(): sha256_file(path) for path in originals_files(copy_root)}
    paths["beforeRoot"] = str(copy_root)
    paths["beforeOriginals"] = before_hashes

    moved = artifacts / "moved-library-data"
    if moved.exists():
        shutil.rmtree(moved)
    shutil.copytree(copy_root, moved)
    hidden = artifacts / "old-library-data-hidden"
    if hidden.exists():
        shutil.rmtree(hidden)
    copy_root.rename(hidden)
    paths["afterRoot"] = str(moved)
    after_hashes = {path.relative_to(moved).as_posix(): sha256_file(path) for path in originals_files(moved)}
    paths["afterOriginals"] = after_hashes
    checks.check("move-original-bytes", before_hashes == after_hashes)
    items_after = load_items(moved)
    checks.check("move-catalog-ids", sorted(item["id"] for item in items_after) == before_ids)
    for item in items_after:
        loc = next((entry for entry in item["locations"] if entry.get("role") == "primary"), None)
        rel = (loc or {}).get("libraryRelativePath")
        checks.check(f"move-rel-resolves:{item.get('filename')}", type(rel) is str and (moved / Path(*rel.split("/"))).is_file())

    if serve:
        port = find_free_port()
        write_isolated_port(moved, port)
        server = start_server(moved)
        url = f"http://127.0.0.1:{port}/"
        try:
            wait_health(url, server)
            status, payload = request_json(url.rstrip("/") + "/api/items", timeout=5)
            checks.check("move-http-items", status == 200 and isinstance(payload, list) and len(payload) == 2)
            if isinstance(payload, list):
                for item in payload:
                    checks.check(f"move-item-available:{item.get('filename')}", item.get("available") is True)
                    raw = urllib.request.urlopen(
                        f"{url.rstrip('/')}/api/media/{item['id']}?which=original",
                        timeout=5,
                    )
                    body = raw.read()
                    checks.check(
                        f"move-original-bytes:{item.get('filename')}",
                        raw.status == 200 and hashlib_match(item["id"], body),
                        f"status={raw.status} len={len(body)}",
                    )
        finally:
            stop_owned(server)

    checks.check("move-source-untouched", hash_tree(folder) == source_before)
    checks.check("no-catalog-in-source", not (folder / "catalog").exists() and not (folder / ".library").exists())

    vol_a = artifacts / "vol-a"
    vol_b = artifacts / "vol-b"
    if vol_a.exists():
        shutil.rmtree(vol_a)
    if vol_b.exists():
        shutil.rmtree(vol_b)
    make_two_file_folder(src_media, vol_a)
    volumes_path = artifacts / "test-volumes.json"
    atomic_write_json(volumes_path, {LINKED_SERIAL: str(vol_a)})
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_VOLUMES"] = str(volumes_path)
    link_root = artifacts / "remap-library-data"
    if link_root.exists():
        shutil.rmtree(link_root)
    prepare_root(link_root)
    linked = run_library(
        link_root,
        ["scan", str(vol_a), "--serve-from-there"],
        env=env,
        timeout=180,
    )
    commands.append("scan linked volume then remount")
    checks.check("remap-scan-exit", linked.returncode == 0, linked.stderr)
    link_source = load_sources(link_root)[0]
    checks.check("remap-serial", link_source["origin"]["volumeSerial"] == LINKED_SERIAL, json.dumps(link_source["origin"]))
    shutil.copytree(vol_a, vol_b)
    pin_tree(vol_b)
    atomic_write_json(volumes_path, {LINKED_SERIAL: str(vol_b)})
    items_status = run_library(link_root, ["items"], env=env)
    checks.check("remap-items-exit", items_status.returncode == 0, items_status.stderr)
    remounted = parse_json_list(items_status.stdout)
    checks.check("remap-still-available", remounted and all(item.get("available") is True for item in remounted), items_status.stdout)
    atomic_write_json(volumes_path, {LINKED_SERIAL: str(vol_b), OTHER_SERIAL: str(vol_a)})
    other = run_library(link_root, ["items"], env=env)
    other_items = parse_json_list(other.stdout)
    checks.check("remap-other-serial-ignored", other_items and all(item.get("available") is True for item in other_items))
    atomic_write_json(volumes_path, {LINKED_SERIAL: None, OTHER_SERIAL: str(vol_a)})
    missing = run_library(link_root, ["items"], env=env)
    missing_items = parse_json_list(missing.stdout)
    checks.check(
        "remap-old-path-wrong-serial-unavailable",
        missing_items and all(item.get("available") is False for item in missing_items),
        missing.stdout,
    )
    paths["linked"] = {
        "serial": LINKED_SERIAL,
        "before": str(vol_a),
        "after": str(vol_b),
        "otherSerial": OTHER_SERIAL,
    }
    (artifacts / "paths-before-after.json").write_text(json.dumps(paths, indent=2) + "\n", encoding="utf-8")
    return paths


def hashlib_match(digest: str, data: bytes) -> bool:
    import hashlib

    return hashlib.sha256(data).hexdigest() == digest


def parse_json_list(stdout: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    index = stdout.find("[")
    while index != -1:
        try:
            obj, _end = decoder.raw_decode(stdout, index)
        except json.JSONDecodeError:
            index = stdout.find("[", index + 1)
            continue
        if isinstance(obj, list):
            return obj
        index = stdout.find("[", index + 1)
    return []


def prove_http_and_dialog(
    artifacts: Path,
    src_media: Path,
    checks: Checks,
    commands: list[str],
) -> None:
    folder = artifacts / "dialog-media"
    make_two_file_folder(src_media, folder)
    root = artifacts / "dialog-library-data"
    server, url, _port, pids = start_isolated(root)
    commands.append("serve + dialog copy-here")
    try:
        base = url.rstrip("/")
        status, empty = request_json(base + "/api/sources", timeout=5)
        checks.check("http-empty-sources", status == 200 and empty == [])
        ask_status, ask_body = request_json(
            base + "/api/sources",
            method="POST",
            body={"path": str(folder)},
            timeout=10,
        )
        checks.check(
            "http-ask-choice-required",
            ask_status == 400 and ask_body == {"error": "choice-required"},
            str(ask_body),
        )
        copy_status, copy_body = request_json(
            base + "/api/sources",
            method="POST",
            body={"path": str(folder), "mode": "copy-here"},
            timeout=180,
        )
        checks.check("http-copy-202", copy_status == 202, str(copy_status))
        checks.check("http-copy-mode", isinstance(copy_body, dict) and copy_body.get("mode") == "copy-here")
        source_id = copy_body.get("id") if isinstance(copy_body, dict) else None
        noop_status, noop_body = request_json(
            base + f"/api/sources/{source_id}/copy-here",
            method="POST",
            body={},
            timeout=60,
        )
        checks.check("http-copy-here-noop", noop_status == 202, str(noop_status))
        checks.check("http-copy-here-same-id", isinstance(noop_body, dict) and noop_body.get("id") == source_id)

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return
        checks.check("playwright-import", True)
        dialog_root = artifacts / "dialog-page-library-data"
        dialog_server, dialog_url, _dport, dialog_pids = start_isolated(dialog_root)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(dialog_url, wait_until="domcontentloaded")
                page.get_by_role("button", name="Add folder").click()
                page.wait_for_selector("dialog#add-folder[open]", timeout=5000)
                checks.check(
                    "dialog-ask-neither",
                    page.locator('input[name="add-mode"]:checked').count() == 0,
                )
                checks.check("dialog-copy-choice-present", page.locator('input[name="add-mode"][value="copy-here"]').count() == 1)
                page.keyboard.press("Escape")
                request_json(dialog_url.rstrip("/") + "/api/settings", method="PUT", body={"addFolderDefault": "copy-here"})
                page.reload(wait_until="domcontentloaded")
                page.get_by_role("button", name="Add folder").click()
                page.wait_for_selector("dialog#add-folder[open]", timeout=5000)
                checks.check(
                    "dialog-preselect-copy-here",
                    page.locator('input[name="add-mode"][value="copy-here"]').is_checked(),
                )
                page.locator("#add-path").fill(str(folder))
                checks.check("dialog-add-enabled", page.locator("#add-submit").is_enabled())
                page.locator("#add-submit").click()
                page.wait_for_function("() => !document.getElementById('add-folder').open", timeout=60000)
                page.wait_for_selector('[data-filename="photo.jpg"]', timeout=60000)
                browser.close()
        except Exception as exc:
            checks.check("dialog-copy-here", False, str(exc))
        else:
            sources = load_sources(dialog_root)
            checks.check("dialog-wrote-copy-source", sources and sources[0].get("mode") == "copy-here", str(sources))
            checks.check("dialog-copied-files", len(originals_files(dialog_root)) == 2)
        finally:
            stop_owned(dialog_server, extra_pids=dialog_pids)

        request_json(base + "/api/settings", method="PUT", body={"addFolderDefault": "serve-from-there"})
        link_folder = artifacts / "dialog-link-media"
        make_two_file_folder(src_media, link_folder)
        pre_status, pre_body = request_json(
            base + "/api/sources",
            method="POST",
            body={"path": str(link_folder)},
            timeout=180,
        )
        checks.check("http-default-serve", pre_status == 202 and isinstance(pre_body, dict) and pre_body.get("mode") == "serve-from-there")
    finally:
        stop_owned(server, extra_pids=pids)


def record_hashes(artifacts: Path, before: dict[str, str], after: dict[str, str]) -> None:
    (artifacts / "original-hashes.json").write_text(
        json.dumps({"before": before, "after": after}, indent=2) + "\n",
        encoding="utf-8",
    )


def extra_artifact_paths(artifacts: Path) -> dict[str, str]:
    return {
        "paths-before-after.json": str(artifacts / "paths-before-after.json"),
        "copied-items": str(artifacts / "copied-items"),
        "collision.json": str(artifacts / "collision.json"),
        "original-hashes.json": str(artifacts / "original-hashes.json"),
    }


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    try:
        no_pillow(checks)
        src_media = prepare_media(artifacts)
        before = hash_tree(src_media)
        prove_choice_and_override(artifacts, src_media, checks, commands)
        prove_f4_two_file(Path(root), src_media, artifacts, checks, commands)
        prove_collision(artifacts, src_media, checks, commands)
        prove_interrupt(artifacts, src_media, checks, commands)
        prove_convert(artifacts, src_media, checks, commands)
        prove_undo(artifacts, src_media, checks, commands)
        prove_move_and_remap(artifacts, src_media, checks, commands, serve=True)
        prove_http_and_dialog(artifacts, src_media, checks, commands)
        after = hash_tree(src_media)
        record_hashes(artifacts, before, after)
        checks.check("fixture-bytes-unchanged", before == after)
        checks.check("no-catalog-in-fixtures", not (src_media / "catalog").exists() and not (src_media / ".library").exists())
    except Exception as exc:
        checks.check("s05-uncaught", False, str(exc))
    return write_result("S05", "slice", checks, artifacts, commands, extra_artifact_paths(artifacts))


def run_check_f1(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    try:
        no_pillow(checks)
        src_media = prepare_media(artifacts)
        before = hash_tree(src_media)
        prove_move_and_remap(artifacts, src_media, checks, commands, serve=True)
        after = hash_tree(src_media)
        record_hashes(artifacts, before, after)
        checks.check("f1-fixture-bytes", before == after)
        checks.check("f1-no-catalog-in-source", not (src_media / "catalog").exists())
        if Path(root).exists():
            shutil.rmtree(root)
        shutil.copytree(artifacts / "moved-library-data", root)
    except Exception as exc:
        checks.check("f1-uncaught", False, str(exc))
    return write_result("F1", "check", checks, artifacts, commands, extra_artifact_paths(artifacts))


def run_check_f4(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    try:
        no_pillow(checks)
        src_media = prepare_media(artifacts)
        before = hash_tree(src_media)
        prove_choice_and_override(artifacts, src_media, checks, commands)
        prove_f4_two_file(Path(root), src_media, artifacts, checks, commands)
        prove_collision(artifacts, src_media, checks, commands)
        prove_interrupt(artifacts, src_media, checks, commands)
        prove_convert(artifacts, src_media, checks, commands)
        prove_undo(artifacts, src_media, checks, commands)
        prove_http_and_dialog(artifacts, src_media, checks, commands)
        after = hash_tree(src_media)
        record_hashes(artifacts, before, after)
        checks.check("f4-fixture-bytes", before == after)
    except Exception as exc:
        checks.check("f4-uncaught", False, str(exc))
    return write_result("F4", "check", checks, artifacts, commands, extra_artifact_paths(artifacts))
