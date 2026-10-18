"""Slice S07 / Check F8 / Check F16 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json
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
    run_library,
    start_server,
    stop_owned,
    wait_health,
    write_isolated_port,
)
from tests.qa.s01 import item_file, hash_tree, load_items, load_sources, parse_summary
from tests.qa.s03 import find_item, png_size, request_raw
from tests.qa.s05 import pin_media_from_manifest, start_isolated

VIDEO_REL = "a/clip.mp4"
BANNER = "Original is not on this computer"
PLACEHOLDER = "Preview is not available"
SERIAL_A = "windows:s07-a"
SERIAL_B = "windows:s07-b"
SERIAL_OFF = "windows:fixture-offline"


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


def copy_rels(src: Path, dest: Path, rels: list[str] | tuple[str, ...]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for rel in rels:
        target = dest / Path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / Path(rel), target)
    pin_media_from_manifest(dest)


def settings_port(root: Path) -> int:
    data = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    return int(data["port"])


def start_owned(
    root: Path,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.Popen[str], str, list[int]]:
    port = settings_port(root)
    server = start_server(root, env=env)
    url = f"http://127.0.0.1:{port}/"
    health_status, health_body = wait_health(url, server)
    if health_status != 200 or health_body != {"ok": True}:
        stop_owned(server)
        raise RuntimeError(f"health {health_status} {health_body}")
    owned_pids: list[int] = []
    try:
        status, runtime = request_json(url.rstrip("/") + "/api/runtime", timeout=2)
        if status == 200 and isinstance(runtime, dict):
            pid = runtime.get("pid")
            if type(pid) is int:
                owned_pids.append(pid)
    except Exception:
        pass
    return server, url, owned_pids


def fresh_root(root: Path) -> Path:
    isolated = Path(root)
    if isolated.exists():
        shutil.rmtree(isolated)
    prepare_root(isolated)
    write_isolated_port(isolated, find_free_port())
    return isolated


def original_hashes(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not folder.exists():
        return out
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if ".library" in path.parts:
            continue
        out[path.relative_to(folder).as_posix()] = sha256_file(path)
    return out


def list_files(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return sorted(
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file()
    )


def picture_rel(item: dict[str, Any], folder: Path) -> str:
    """The picture's path inside its folder: the F23 name stem."""
    last = item.get("lastKnownPath")
    if not last:
        locs = [loc for loc in item.get("locations") or [] if loc.get("current", True)]
        locs.sort(key=lambda loc: (loc.get("component") != "still", loc.get("role") != "primary"))
        last = locs[0]["lastKnownPath"] if locs else ""
    return os.path.relpath(str(last), str(folder.resolve())).replace("\\", "/")


def source_file(folder: Path, item: dict[str, Any], suffix: str = ".thumb.webp") -> Path:
    """F23 ``folder-source``: ``<folder>/.library/<picture><suffix>``."""
    return folder / ".library" / Path(picture_rel(item, folder) + suffix)


def server_file(root: Path, folder: Path, item: dict[str, Any], suffix: str = ".thumb.webp") -> Path:
    """F23 ``folder-server``: ``library-data/folders/<name>-<source-id>/<picture><suffix>``."""
    source_id = (item.get("renditions") or {}).get("sourceId")
    return root / "folders" / f"{folder.name}-{source_id}" / Path(picture_rel(item, folder) + suffix)


def wait_ready(
    url: str,
    names: tuple[str, ...] | list[str],
    *,
    slots: tuple[str, ...] = ("thumb",),
    timeout: float = 90,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(url.rstrip("/") + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            by_name = {item.get("filename"): item for item in payload}
            if all(name in by_name for name in names):
                ok = True
                for name in names:
                    item = by_name[name]
                    rend = item.get("renditions") or {}
                    status_map = rend.get("status") or {}
                    for slot in slots:
                        if status_map.get(slot) != "ready":
                            ok = False
                            break
                        media_status, _, body = request_raw(
                            f"{url.rstrip('/')}/api/media/{item['id']}?which={slot}"
                        )
                        if media_status != 200 or not body:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    return payload
        time.sleep(0.25)
    raise RuntimeError("ready timeout " + json.dumps([item.get("filename") for item in last]))


def set_setting(url: str, key: str, value: Any) -> None:
    status, body = request_json(
        url.rstrip("/") + "/api/settings",
        method="PUT",
        body={key: value},
        timeout=5,
    )
    if status != 200:
        raise RuntimeError(f"settings {key}={value} {status} {body}")


def post_scan(url: str, path: Path, mode: str, preview_store: str | None = None) -> Any:
    body: dict[str, Any] = {"path": str(path), "mode": mode}
    if preview_store is not None:
        body["previewStore"] = preview_store
    status, payload = request_json(
        url.rstrip("/") + "/api/sources",
        method="POST",
        body=body,
        timeout=300,
    )
    if status not in {200, 202}:
        raise RuntimeError(f"scan {status} {payload}")
    return payload


def json_error(status: int, body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": status, "raw": body[:200].decode("utf-8", "replace")}


def prove_store_and_relocate(
    checks: Checks,
    root: Path,
    media_src: Path,
    artifacts: Path,
    commands: list[str],
) -> dict[str, Any]:
    folder = artifacts / "f8-folder"
    copy_rels(media_src, folder, ("a/IMG_1042.jpg",))
    before_hashes = original_hashes(folder)
    isolated = Path(root)
    server, url, _port, pids = start_isolated(isolated)
    record: dict[str, Any] = {}
    try:
        set_setting(url, "previewStore", "with-source")
        commands.append("settings set previewStore with-source")
        post_scan(url, folder, "serve-from-there")
        commands.append("POST /api/sources serve-from-there")
        items = wait_ready(url, ("IMG_1042.jpg",))
        item = find_item(items, "IMG_1042.jpg")
        checks.check("with-source-item", item is not None)
        if item is None:
            return record
        item_id = item["id"]
        source_thumb = source_file(folder, item)
        server_thumb = server_file(isolated, folder, item)
        source_record = source_file(folder, item, ".json")
        server_record = server_file(isolated, folder, item, ".json")
        checks.check("thumb-under-source", source_thumb.is_file() and source_thumb.stat().st_size > 0, str(source_thumb))
        checks.check("record-under-source", source_record.is_file(), str(source_record))
        checks.check("thumb-not-on-server-yet", not server_thumb.exists(), str(server_thumb))
        checks.check("item-store-with-source", (item.get("renditions") or {}).get("store") == "folder-source")
        record["before"] = {
            "source": list_files(folder / ".library"),
            "server": list_files(isolated / "folders"),
        }

        set_setting(url, "previewStore", "with-server")
        commands.append("settings set previewStore with-server")
        checks.check(
            "setting-without-relocate-keeps-source-bytes",
            source_thumb.is_file() and not server_thumb.exists(),
        )

        relocated = run_library(isolated, ["renditions", "relocate"])
        commands.append("python -m library renditions relocate")
        checks.check("relocate-to-server-exit", relocated.returncode == 0, relocated.stderr)
        try:
            body = json.loads(relocated.stdout)
        except json.JSONDecodeError:
            body = {}
        checks.check("relocate-to-server-ok", body == {"ok": True}, relocated.stdout)
        checks.check("thumb-on-server", server_thumb.is_file() and server_thumb.stat().st_size > 0)
        checks.check("thumb-gone-from-source", not source_thumb.exists())
        checks.check("record-moved-to-server", server_record.is_file() and not source_record.exists())
        disk = json.loads(item_file(isolated, item_id).read_text(encoding="utf-8"))
        checks.check("item-store-with-server", (disk.get("renditions") or {}).get("store") == "folder-server")
        record["after"] = {
            "source": list_files(folder / ".library"),
            "server": list_files(isolated / "folders"),
        }

        set_setting(url, "previewStore", "with-source")
        reverse = run_library(isolated, ["renditions", "relocate"])
        commands.append("renditions relocate reverse")
        checks.check("relocate-to-source-exit", reverse.returncode == 0, reverse.stderr)
        checks.check("reverse-thumb-under-source", source_thumb.is_file() and source_thumb.stat().st_size > 0)
        checks.check("reverse-thumb-gone-from-server", not server_thumb.exists())
        disk = json.loads(item_file(isolated, item_id).read_text(encoding="utf-8"))
        checks.check("reverse-store-with-source", (disk.get("renditions") or {}).get("store") == "folder-source")
        checks.check("reverse-record-under-source", source_record.is_file() and not server_record.exists())
        record["reverse"] = {
            "source": list_files(folder / ".library"),
            "server": list_files(isolated / "folders"),
        }

        undo = run_library(isolated, ["undo"])
        commands.append("undo relocate")
        checks.check("relocate-undo-exit", undo.returncode == 0, undo.stderr)
        disk = json.loads(item_file(isolated, item_id).read_text(encoding="utf-8"))
        checks.check("undo-store-with-server", (disk.get("renditions") or {}).get("store") == "folder-server")
        checks.check("undo-bytes-on-server", server_thumb.is_file() and server_thumb.stat().st_size > 0)
        checks.check("undo-record-on-server", server_record.is_file() and not source_record.exists())
        media_status, _, media_body = request_raw(f"{url.rstrip('/')}/api/media/{item_id}?which=thumb")
        checks.check("undo-media-serves", media_status == 200 and len(media_body) > 0)
        entries = list((isolated / "undo" / "entries").glob("*.json"))
        relocate_ops = []
        for path in entries:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry.get("operation") == "relocate":
                relocate_ops.append(entry)
                files_dir = isolated / "undo" / "files" / entry["id"] / item_id
                checks.check(
                    "undo-files-kept",
                    files_dir.exists() and any(files_dir.iterdir()),
                    str(files_dir),
                )
        checks.check("history-operation-relocate", bool(relocate_ops))
    finally:
        stop_owned(server, extra_pids=pids)
    checks.check("original-hashes-unchanged-f8", original_hashes(folder) == before_hashes)
    return record


def prove_override_and_dedup(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> None:
    folder = artifacts / "override-folder"
    copy_rels(media_src, folder, ("a/IMG_1042.jpg",))
    root = artifacts / "override-library-data"
    fresh_root(root)
    server, url, pids = start_owned(root)
    try:
        set_setting(url, "previewStore", "with-server")
        post_scan(url, folder, "serve-from-there", preview_store="with-source")
        commands.append("scan with per-source previewStore=with-source")
        items = wait_ready(url, ("IMG_1042.jpg",))
        item = find_item(items, "IMG_1042.jpg")
        checks.check("override-item", item is not None)
        if item is None:
            return
        item_id = item["id"]
        checks.check("override-wins-source", source_file(folder, item).is_file())
        checks.check("override-not-server", not server_file(root, folder, item).exists())
        sources = load_sources(root)
        checks.check(
            "override-source-field",
            sources and sources[0].get("previewStore") == "with-source",
            json.dumps(sources[0].get("previewStore") if sources else None),
        )
    finally:
        stop_owned(server, extra_pids=pids)

    other = artifacts / "dedup-other"
    copy_rels(media_src, other, ("a/IMG_1042.jpg",))
    first = artifacts / "dedup-first"
    copy_rels(media_src, first, ("a/IMG_1042.jpg",))
    root = artifacts / "dedup-library-data"
    fresh_root(root)
    server, url, pids = start_owned(root)
    try:
        set_setting(url, "previewStore", "with-source")
        post_scan(url, first, "serve-from-there")
        wait_ready(url, ("IMG_1042.jpg",))
        post_scan(url, other, "serve-from-there")
        commands.append("scan duplicate second location")
        time.sleep(0.5)
        items = load_items(root)
        photos = [item for item in items if item.get("filename") == "IMG_1042.jpg"]
        checks.check("dedup-one-item", len(photos) == 1, str(len(photos)))
        if not photos:
            return
        item = photos[0]
        checks.check("dedup-two-locations", len(item.get("locations") or []) == 2)
        owner = (item.get("renditions") or {}).get("sourceId")
        first_source = load_sources(root)[0]["id"] if load_sources(root) else None
        primaries = [loc for loc in item.get("locations") or [] if loc.get("role") == "primary"]
        checks.check("dedup-one-primary", len(primaries) == 1)
        if primaries:
            checks.check("dedup-owner-is-primary-source", owner == primaries[0].get("sourceId"))
        by_source = {loc.get("sourceId"): loc for loc in item.get("locations") or []}
        first_loc = by_source.get(owner) or {}
        first_item = {**item, "lastKnownPath": first_loc.get("lastKnownPath") or item.get("lastKnownPath")}
        checks.check("dedup-one-rendition-dir", source_file(first, first_item).is_file())
        checks.check("dedup-second-has-no-copy", not list((other / ".library").rglob("*.thumb.webp")))
        checks.check("dedup-owner-first", owner == first_source or owner == primaries[0].get("sourceId") if primaries else False)
    finally:
        stop_owned(server, extra_pids=pids)

    copy_folder = artifacts / "copy-src"
    copy_rels(media_src, copy_folder, ("a/IMG_1042.jpg",))
    root = artifacts / "copy-library-data"
    fresh_root(root)
    server, url, pids = start_owned(root)
    try:
        set_setting(url, "previewStore", "with-source")
        post_scan(url, copy_folder, "copy-here")
        commands.append("scan --copy-here with-source")
        items = wait_ready(url, ("IMG_1042.jpg",))
        item = find_item(items, "IMG_1042.jpg")
        sources = load_sources(root)
        checks.check("copy-here-item", item is not None and sources)
        if item is None or not sources:
            return
        copy_root = sources[0].get("copyRoot")
        checks.check("copy-here-copyRoot", type(copy_root) is str and bool(copy_root), str(copy_root))
        copy_lib = root / Path(*(str(copy_root).split("/"))) / ".library"
        thumbs = [path for path in copy_lib.rglob("*.thumb.webp") if path.stat().st_size > 0]
        checks.check("copy-here-writes-under-copyRoot", len(thumbs) == 1, str(copy_lib))
        checks.check("copy-here-not-old-disk", not list((copy_folder / ".library").rglob("*.thumb.webp")))
    finally:
        stop_owned(server, extra_pids=pids)


def prove_relocate_failures(
    checks: Checks,
    artifacts: Path,
    media_src: Path,
    commands: list[str],
) -> None:
    folder = artifacts / "deny-folder"
    copy_rels(media_src, folder, ("a/IMG_1042.jpg",))
    root = artifacts / "deny-library-data"
    fresh_root(root)
    server, url, pids = start_owned(root)
    item_id = ""
    source_thumb = Path()
    try:
        set_setting(url, "previewStore", "with-source")
        post_scan(url, folder, "serve-from-there")
        items = wait_ready(url, ("IMG_1042.jpg",))
        item = find_item(items, "IMG_1042.jpg")
        checks.check("deny-item", item is not None)
        if item is None:
            return
        item_id = item["id"]
        source_thumb = source_file(folder, item)
        set_setting(url, "previewStore", "with-server")
    finally:
        stop_owned(server, extra_pids=pids)

    renditions = root / "folders"
    renditions.mkdir(parents=True, exist_ok=True)
    os.chmod(renditions, 0o555)
    try:
        denied = run_library(root, ["renditions", "relocate"])
        commands.append("renditions relocate chmod-denied")
        checks.check("denied-exit-1", denied.returncode == 1, f"exit={denied.returncode} {denied.stderr}")
        try:
            err = json.loads(denied.stderr.strip().splitlines()[-1])
        except Exception:
            err = {}
        checks.check(
            "denied-existing-error",
            err.get("error") in {"io-error", "unavailable"},
            denied.stderr,
        )
        disk = json.loads(item_file(root, item_id).read_text(encoding="utf-8"))
        checks.check("denied-old-store", (disk.get("renditions") or {}).get("store") == "folder-source")
        checks.check("denied-old-bytes", source_thumb.is_file() and source_thumb.stat().st_size > 0)
    finally:
        os.chmod(renditions, 0o755)

    fat = artifacts / "interrupt-folder"
    copy_rels(media_src, fat, ("a/IMG_1042.jpg",))
    root = artifacts / "interrupt-library-data"
    fresh_root(root)
    server, url, pids = start_owned(root)
    try:
        set_setting(url, "previewStore", "with-source")
        post_scan(url, fat, "serve-from-there")
        items = wait_ready(url, ("IMG_1042.jpg",))
        item = find_item(items, "IMG_1042.jpg")
        checks.check("interrupt-item", item is not None)
        if item is None:
            return
        item_id = item["id"]
        source_thumb = source_file(fat, item)
        source_preview = source_file(fat, item, ".preview.webp")
        blob = source_thumb.read_bytes() + (os.urandom(48 * 1024 * 1024))
        source_thumb.write_bytes(blob)
        if source_preview.is_file():
            source_preview.write_bytes(blob)
        before_item = json.loads(item_file(root, item_id).read_text(encoding="utf-8"))
        set_setting(url, "previewStore", "with-server")
    finally:
        stop_owned(server, extra_pids=pids)

    env = _env()
    proc = subprocess.Popen(
        [sys.executable, "-m", "library", "--root", str(root), "renditions", "relocate"],
        cwd=str(PRODUCT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    commands.append("kill during renditions relocate")
    dest_tmp = root / "folders"
    deadline = time.time() + 2.0
    while time.time() < deadline and proc.poll() is None:
        tmps = list(dest_tmp.rglob("*.tmp")) if dest_tmp.exists() else []
        if tmps:
            break
        time.sleep(0.01)
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)
    after_item = json.loads(item_file(root, item_id).read_text(encoding="utf-8"))
    checks.check("interrupt-old-refs", after_item.get("renditions") == before_item.get("renditions"))
    checks.check("interrupt-old-bytes", source_thumb.is_file() and source_thumb.stat().st_size > 0)

    off = artifacts / "unavail-folder"
    stay = artifacts / "stay-folder"
    copy_rels(media_src, off, ("a/IMG_1042.jpg",))
    copy_rels(media_src, stay, ("b/no-exif.jpg",))
    volumes_path = artifacts / "unavail-volumes.json"
    atomic_write_json(volumes_path, {SERIAL_A: str(off), SERIAL_B: str(stay)})
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_VOLUMES"] = str(volumes_path)
    root = artifacts / "unavail-relocate-library-data"
    fresh_root(root)
    server, url, pids = start_owned(root, env=env)
    try:
        set_setting(url, "previewStore", "with-source")
        post_scan(url, off, "serve-from-there")
        post_scan(url, stay, "serve-from-there")
        wait_ready(url, ("IMG_1042.jpg", "no-exif.jpg"))
        items = load_items(root)
        gone = find_item(items, "IMG_1042.jpg")
        kept = find_item(items, "no-exif.jpg")
        checks.check("unavail-relocate-items", gone is not None and kept is not None)
        if gone is None or kept is None:
            return
        gone_thumb = source_file(off, gone)
        set_setting(url, "previewStore", "with-server")
        atomic_write_json(volumes_path, {SERIAL_A: None, SERIAL_B: str(stay)})
        relocated = run_library(root, ["renditions", "relocate"], env=env)
        commands.append("relocate with unavailable owning source")
        checks.check("unavail-relocate-exit-1", relocated.returncode == 1, relocated.stderr)
        try:
            err = json.loads(relocated.stderr.strip().splitlines()[-1])
        except Exception:
            err = {}
        checks.check("unavail-relocate-error", err.get("error") == "unavailable", relocated.stderr)
        gone_disk = json.loads(item_file(root, gone['id']).read_text(encoding="utf-8"))
        kept_disk = json.loads(item_file(root, kept['id']).read_text(encoding="utf-8"))
        checks.check("unavail-keeps-old-refs", (gone_disk.get("renditions") or {}).get("store") == "folder-source")
        checks.check("unavail-keeps-old-files", gone_thumb.is_file())
        checks.check(
            "unavail-continues-others",
            (kept_disk.get("renditions") or {}).get("store") == "folder-server"
            and server_file(root, stay, kept).is_file(),
        )
    finally:
        stop_owned(server, extra_pids=pids)


def prove_unavailable(
    checks: Checks,
    root: Path,
    media_src: Path,
    artifacts: Path,
    commands: list[str],
) -> dict[str, Any]:
    resolution: dict[str, Any] = {}
    folder = artifacts / "f16-folder"
    copy_rels(media_src, folder, ("a/IMG_1042.jpg", VIDEO_REL, "b/no-exif.jpg"))
    alt = artifacts / "f16-alt"
    copy_rels(media_src, alt, ("a/IMG_1042.jpg",))
    volumes_path = artifacts / "f16-volumes.json"
    atomic_write_json(volumes_path, {SERIAL_A: str(folder), SERIAL_B: str(alt)})
    env = _env()
    env["LIBRARY_TEST"] = "1"
    env["LIBRARY_TEST_VOLUMES"] = str(volumes_path)
    isolated = fresh_root(root)
    server, url, pids = start_owned(isolated, env=env)
    try:
        set_setting(url, "previewStore", "with-server")
        post_scan(url, folder, "serve-from-there")
        commands.append("scan linked fixture for F16")
        items = wait_ready(url, ("IMG_1042.jpg", "no-exif.jpg"), slots=("thumb", "preview"))
        wait_ready(url, ("clip.mp4",), slots=("poster", "proxy"))
        photo = find_item(items, "IMG_1042.jpg")
        extra = find_item(items, "no-exif.jpg")
        _status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
        video = find_item(listed if isinstance(listed, list) else items, "clip.mp4")
        checks.check("f16-items", photo is not None and extra is not None and video is not None)
        if photo is None or extra is None or video is None:
            return resolution
        photo_id = photo["id"]
        extra_id = extra["id"]
        video_id = video["id"]

        sources_status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=5)
        checks.check("sources-before-unplug", sources_status == 200 and isinstance(sources, list) and sources)
        if isinstance(sources, list) and sources:
            checks.check("source-available-before", sources[0].get("available") is True)

        atomic_write_json(volumes_path, {SERIAL_A: None, SERIAL_B: str(alt)})
        sources_status, sources = request_json(url.rstrip("/") + "/api/sources", timeout=5)
        checks.check("after-launch-unplug-http", sources_status == 200 and isinstance(sources, list))
        if isinstance(sources, list) and sources:
            checks.check("after-launch-source-unavailable", sources[0].get("available") is False, json.dumps(sources[0]))
        items_status, shown = request_json(url.rstrip("/") + "/api/items", timeout=5)
        checks.check("show-includes-unavailable", items_status == 200 and isinstance(shown, list) and any(item.get("id") == extra_id for item in shown))
        orig_status, orig_headers, orig_body = request_raw(f"{url.rstrip('/')}/api/media/{extra_id}?which=original")
        checks.check(
            "original-404-unavailable",
            orig_status == 404 and json_error(orig_status, orig_body) == {"error": "unavailable"},
            json.dumps(json_error(orig_status, orig_body)),
        )
        thumb_status, _, thumb_body = request_raw(f"{url.rstrip('/')}/api/media/{extra_id}?which=thumb")
        checks.check("thumb-still-serves", thumb_status == 200 and len(thumb_body) > 0)

        set_setting(url, "unavailableItems", "hide")
        hide_status, hidden = request_json(url.rstrip("/") + "/api/items", timeout=5)
        checks.check(
            "hide-omits-unavailable",
            hide_status == 200 and isinstance(hidden, list) and not any(item.get("id") == extra_id for item in hidden),
        )
        both_status, both = request_json(url.rstrip("/") + "/api/items?unavailable=1", timeout=5)
        checks.check(
            "unavailable-1-includes",
            both_status == 200 and isinstance(both, list) and any(item.get("id") == extra_id for item in both),
        )
        cli = run_library(isolated, ["items", "--unavailable", "1"], env=env)
        checks.check("cli-unavailable-1-exit", cli.returncode == 0, cli.stderr)
        set_setting(url, "unavailableItems", "show")

        resolution["afterLaunchUnplug"] = {
            "serial": SERIAL_A,
            "sourceAvailable": sources[0].get("available") if isinstance(sources, list) and sources else None,
            "original": json_error(orig_status, orig_body),
            "thumbStatus": thumb_status,
        }

        atomic_write_json(volumes_path, {SERIAL_A: None, SERIAL_B: str(folder)})
        wrong_status, wrong_items = request_json(url.rstrip("/") + "/api/items", timeout=5)
        wrong_extra = find_item(wrong_items if isinstance(wrong_items, list) else [], "no-exif.jpg")
        checks.check(
            "wrong-serial-not-resolve",
            wrong_status == 200 and wrong_extra is not None and wrong_extra.get("available") is False,
            json.dumps(wrong_extra),
        )
        resolution["wrongSerial"] = {
            "mounted": SERIAL_B,
            "stored": SERIAL_A,
            "available": wrong_extra.get("available") if wrong_extra else None,
        }

        atomic_write_json(volumes_path, {SERIAL_A: None, SERIAL_B: str(alt)})
        alt_scan = post_scan(url, alt, "serve-from-there")
        commands.append("scan alternate location")
        time.sleep(0.4)
        alt_status, alt_items = request_json(url.rstrip("/") + "/api/items", timeout=5)
        alt_photo = find_item(alt_items if isinstance(alt_items, list) else [], "IMG_1042.jpg")
        checks.check(
            "available-alternate",
            alt_status == 200 and alt_photo is not None and alt_photo.get("available") is True,
            json.dumps({"locations": (alt_photo or {}).get("locations"), "available": (alt_photo or {}).get("available")}),
        )
        alt_orig, _, alt_body = request_raw(f"{url.rstrip('/')}/api/media/{photo_id}?which=original")
        checks.check("alternate-original-serves", alt_orig == 200 and len(alt_body) > 0)
        resolution["availableAlternate"] = {
            "itemId": photo_id,
            "available": alt_photo.get("available") if alt_photo else None,
            "locationCount": len((alt_photo or {}).get("locations") or []),
            "originalStatus": alt_orig,
            "scan": alt_scan.get("id") if isinstance(alt_scan, dict) else None,
        }

        atomic_write_json(volumes_path, {SERIAL_A: None, SERIAL_B: str(alt)})
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            checks.check("playwright-import", False, str(exc))
            return resolution
        checks.check("playwright-import", True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="no-exif.jpg"]', timeout=30000)
            page.locator('[data-filename="no-exif.jpg"]').click()
            page.wait_for_function(
                """() => {
                  const viewer = document.getElementById('viewer');
                  const banner = document.getElementById('unavailable-banner');
                  const img = document.getElementById('viewer-image');
                  return viewer && !viewer.hidden && banner && !banner.hidden
                    && img && !img.hidden && img.complete && img.naturalWidth > 0;
                }""",
                timeout=15000,
            )
            banner = page.locator("#unavailable-banner").inner_text().strip()
            checks.check("banner-exact", banner == BANNER, banner)
            checks.check("open-original-disabled", page.locator("#open-original").is_disabled())
            checks.check("preview-visible", page.locator("#viewer-image").is_visible())
            shot = artifacts / "unavailable.png"
            page.screenshot(path=str(shot), full_page=False)
            width, height = png_size(shot)
            checks.check("unavailable-png-1280x720", shot.is_file() and width == 1280 and height == 720, f"{width}x{height}")
            page.keyboard.press("Escape")
            page.wait_for_function("() => document.getElementById('viewer') && document.getElementById('viewer').hidden", timeout=5000)

            page.locator('[data-filename="clip.mp4"]').click()
            page.wait_for_function(
                """() => {
                  const viewer = document.getElementById('viewer');
                  const play = document.getElementById('play-preview');
                  return viewer && !viewer.hidden && play && !play.disabled;
                }""",
                timeout=8000,
            )
            checks.check("video-play-preview-enabled", page.locator("#play-preview").is_enabled())
            checks.check("video-open-original-disabled", page.locator("#open-original").is_disabled())
            page.keyboard.press("Escape")

            preview_path = isolated / "renditions" / extra_id / "preview.webp"
            thumb_path = isolated / "renditions" / extra_id / "thumb.webp"
            checks.check("preview-file-before-remove", preview_path.is_file())
            if preview_path.is_file():
                preview_path.unlink()
            if thumb_path.is_file():
                thumb_path.unlink()
            miss_status, _, miss_body = request_raw(f"{url.rstrip('/')}/api/media/{extra_id}?which=preview")
            checks.check(
                "preview-unavailable-404",
                miss_status == 404 and json_error(miss_status, miss_body) == {"error": "preview-unavailable"},
                json.dumps(json_error(miss_status, miss_body)),
            )
            atomic_write_json(volumes_path, {SERIAL_A: str(folder), SERIAL_B: str(alt)})
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="no-exif.jpg"]', timeout=30000)
            page.locator('[data-filename="no-exif.jpg"]').click()
            page.wait_for_function(
                """() => {
                  const viewer = document.getElementById('viewer');
                  const placeholder = document.getElementById('viewer-placeholder');
                  return viewer && !viewer.hidden && placeholder && !placeholder.hidden;
                }""",
                timeout=15000,
            )
            placeholder = page.locator("#viewer-placeholder").inner_text().strip()
            checks.check("placeholder-exact", placeholder == PLACEHOLDER, placeholder)
            checks.check("no-preview-banner-hidden", page.locator("#unavailable-banner").is_hidden())
            no_preview = artifacts / "no-preview.png"
            page.screenshot(path=str(no_preview), full_page=False)
            nw, nh = png_size(no_preview)
            checks.check("no-preview-png-1280x720", no_preview.is_file() and nw == 1280 and nh == 720, f"{nw}x{nh}")
            page.keyboard.press("Escape")

            atomic_write_json(volumes_path, {SERIAL_A: None, SERIAL_B: str(alt)})
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="no-exif.jpg"]', timeout=30000)
            page.locator('[data-filename="no-exif.jpg"]').click()
            page.wait_for_function(
                """() => {
                  const banner = document.getElementById('unavailable-banner');
                  const placeholder = document.getElementById('viewer-placeholder');
                  return banner && !banner.hidden && placeholder && !placeholder.hidden;
                }""",
                timeout=15000,
            )
            checks.check(
                "both-missing-banner",
                page.locator("#unavailable-banner").inner_text().strip() == BANNER,
            )
            checks.check(
                "both-missing-placeholder",
                page.locator("#viewer-placeholder").inner_text().strip() == PLACEHOLDER,
            )
            page.keyboard.press("Escape")

            proxy = isolated / "renditions" / video_id / "proxy.mp4"
            if proxy.is_file():
                proxy.unlink()
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector('[data-filename="clip.mp4"]', timeout=30000)
            page.locator('[data-filename="clip.mp4"]').click()
            page.wait_for_function(
                """() => {
                  const viewer = document.getElementById('viewer');
                  const play = document.getElementById('play-preview');
                  return viewer && !viewer.hidden && play && play.disabled;
                }""",
                timeout=8000,
            )
            checks.check("play-preview-disabled-without-proxy", page.locator("#play-preview").is_disabled())
            browser.close()
    finally:
        stop_owned(server, extra_pids=pids)
    return resolution


def run_check_f8(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {
        "relocation-before-after.json": str(artifacts / "relocation-before-after.json"),
    }
    try:
        media = prepare_media(artifacts)
        record = prove_store_and_relocate(checks, root, media, artifacts, commands)
        (artifacts / "relocation-before-after.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        prove_override_and_dedup(checks, artifacts, media, commands)
        prove_relocate_failures(checks, artifacts, media, commands)
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == hash_tree(COMMITTED_FIXTURES / "media"))
    except Exception as exc:
        checks.check("f8-runner", False, str(exc))
    return write_result("F8", "check", checks, artifacts, commands, extra)


def run_check_f16(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {
        "source-resolution.json": str(artifacts / "source-resolution.json"),
        "unavailable.png": str(artifacts / "unavailable.png"),
        "no-preview.png": str(artifacts / "no-preview.png"),
    }
    try:
        media = prepare_media(artifacts)
        resolution = prove_unavailable(checks, root, media, artifacts, commands)
        (artifacts / "source-resolution.json").write_text(
            json.dumps(resolution, indent=2) + "\n", encoding="utf-8"
        )
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == hash_tree(COMMITTED_FIXTURES / "media"))
    except Exception as exc:
        checks.check("f16-runner", False, str(exc))
    return write_result("F16", "check", checks, artifacts, commands, extra)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    extra = {
        "relocation-before-after.json": str(artifacts / "relocation-before-after.json"),
        "source-resolution.json": str(artifacts / "source-resolution.json"),
        "unavailable.png": str(artifacts / "unavailable.png"),
        "no-preview.png": str(artifacts / "no-preview.png"),
    }
    try:
        media = prepare_media(artifacts)
        record = prove_store_and_relocate(checks, root, media, artifacts, commands)
        (artifacts / "relocation-before-after.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        prove_override_and_dedup(checks, artifacts, media, commands)
        prove_relocate_failures(checks, artifacts, media, commands)
        f16_root = artifacts / "f16-library-data"
        resolution = prove_unavailable(checks, f16_root, media, artifacts, commands)
        (artifacts / "source-resolution.json").write_text(
            json.dumps(resolution, indent=2) + "\n", encoding="utf-8"
        )
        assert_no_pillow_in_server(checks)
        checks.check("original-fixture-bytes", hash_tree(media) == hash_tree(COMMITTED_FIXTURES / "media"))
    except Exception as exc:
        checks.check("s07-runner", False, str(exc))
    return write_result("S07", "slice", checks, artifacts, commands, extra)
