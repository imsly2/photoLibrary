"""Slice S01 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json
from library.catalog_io import relative_from_origin
from library.httpjson import request_json
from library.media import sha256_file
from library.records import (
    make_file_entry,
    make_item,
    make_location,
    make_source,
    renditions_for,
)
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    FORMAT_FILES,
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

LIVE_STILL = "live/LIVE_0001.jpg"
LIVE_MOTION = "live/LIVE_0001.mov"
DUPLICATE_REL = "second/source/same.jpg"
ALLOWED_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".heic",
    ".heif",
    ".tif",
    ".tiff",
    ".bmp",
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}


def parse_summary(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    index = stdout.find("{")
    last: dict[str, Any] | None = None
    while index != -1:
        try:
            obj, end = decoder.raw_decode(stdout, index)
        except json.JSONDecodeError:
            index = stdout.find("{", index + 1)
            continue
        if isinstance(obj, dict):
            last = obj
        index = stdout.find("{", end)
    if last is None:
        raise ValueError(stdout)
    return last


def hash_tree(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not folder.exists():
        return out
    for path in folder.rglob("*"):
        if path.is_file() and not path.is_symlink():
            rel = path.relative_to(folder).as_posix()
            out[rel] = sha256_file(path)
    return out


def primary_byte_path(media: Path, source: dict[str, Any], item: dict[str, Any]) -> Path | None:
    locations = item.get("locations") or []
    if item.get("kind") == "live":
        primaries = [
            loc
            for loc in locations
            if loc.get("component") == "still" and loc.get("role") == "primary"
        ]
    else:
        primaries = [loc for loc in locations if loc.get("role") == "primary"]
    if len(primaries) != 1:
        return None
    rel = relative_from_origin(source, primaries[0].get("pathFromVolumeRoot") or "")
    if not rel:
        return None
    path = media / Path(rel.replace("\\", "/"))
    return path if path.is_file() else None


def id_matches_primary_file_bytes(media: Path, source: dict[str, Any], item: dict[str, Any]) -> bool:
    item_id = item.get("id")
    if type(item_id) is not str or len(item_id) != 64 or item_id.startswith("pending-"):
        return False
    path = primary_byte_path(media, source, item)
    if path is None:
        return False
    return item_id == sha256_file(path)


def load_items(root: Path) -> list[dict[str, Any]]:
    folder = root / "catalog" / "items"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.json")):
        items.append(json.loads(path.read_text(encoding="utf-8")))
    return items


def load_sources(root: Path) -> list[dict[str, Any]]:
    folder = root / "catalog" / "sources"
    if not folder.exists():
        return []
    sources = []
    for path in sorted(folder.glob("*.json")):
        sources.append(json.loads(path.read_text(encoding="utf-8")))
    return sources


def scan_history_count(root: Path) -> int:
    state_path = root / "undo" / "state.json"
    if not state_path.exists():
        return 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    count = 0
    for entry_id in state.get("entries") or []:
        path = root / "undo" / "entries" / f"{entry_id}.json"
        if not path.exists():
            continue
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("operation") == "scan":
            count += 1
    return count


def make_junction(link: Path, target: Path) -> subprocess.CompletedProcess[str]:
    target.mkdir(parents=True, exist_ok=True)
    if link.exists():
        link.rmdir()
    return subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )


def snapshot_catalog(root: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    catalog = root / "catalog"
    if catalog.exists():
        shutil.copytree(catalog, dest / "catalog", dirs_exist_ok=True)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    commands: list[str] = []
    interruption: dict[str, Any] = {}
    try:
        sandbox = artifacts / "fixture-sandbox"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        copy_committed_fixtures(sandbox)
        media = sandbox / "media"
        dup = media / Path(*DUPLICATE_REL.split("/"))
        dup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media / "a" / "IMG_1042.jpg", dup)
        (media / "ignored.txt").write_text("not media\n", encoding="utf-8")
        before_hashes = hash_tree(media)
        (artifacts / "original-hashes.json").write_text(
            json.dumps({"before": before_hashes}, indent=2) + "\n",
            encoding="utf-8",
        )

        isolated = Path(root)
        if isolated.exists():
            shutil.rmtree(isolated)
        prepare_root(isolated)
        isolated_port = find_free_port()
        write_isolated_port(isolated, isolated_port)

        first = run_library(
            isolated,
            ["scan", str(media), "--serve-from-there"],
            timeout=300,
        )
        commands.append("python -m library scan <media> --serve-from-there")
        (artifacts / "scan-first.log").write_text(
            first.stdout + "\n--- stderr ---\n" + first.stderr, encoding="utf-8"
        )
        summary1: dict[str, Any] = {}
        try:
            summary1 = parse_summary(first.stdout)
        except Exception as exc:
            checks.check("scan-first-json", False, f"{exc} stdout={first.stdout!r}")
        else:
            checks.check("scan-first-json", True)
        errors = summary1.get("errors") if summary1 else None
        checks.check(
            "scan-first-exit",
            first.returncode == 1 if errors else first.returncode == 0,
            f"exit={first.returncode} stderr={first.stderr!r}",
        )
        checks.check("scan-first-added", isinstance(summary1.get("added"), int) and summary1.get("added", 0) > 0)
        source_id = summary1.get("sourceId")
        checks.check("scan-first-source-id", type(source_id) is str and str(source_id).startswith("src_"))

        after_hashes = hash_tree(media)
        (artifacts / "original-hashes.json").write_text(
            json.dumps({"before": before_hashes, "after": after_hashes}, indent=2) + "\n",
            encoding="utf-8",
        )
        checks.check("originals-byte-identical", before_hashes == after_hashes)
        checks.check("no-library-dir-in-media", not (media / ".library").exists())
        checks.check("ignored-txt-untouched", (media / "ignored.txt").read_text(encoding="utf-8") == "not media\n")

        sources = load_sources(isolated)
        checks.check("one-source", len(sources) == 1, str(len(sources)))
        source = sources[0] if sources else {}
        checks.check("source-mode", source.get("mode") == "serve-from-there")
        checks.check("source-id-reused-field", source.get("id") == source_id)
        files = source.get("files") or {}
        dest_null = all(entry.get("destination") is None for entry in files.values())
        checks.check("linked-destination-null", dest_null)
        checks.check("ignored-not-indexed", "ignored.txt" not in files)
        checks.check("duplicate-path-indexed", DUPLICATE_REL in files)
        checks.check("broken-heic-indexed", "formats/broken.heic" in files)

        items = load_items(isolated)
        pending = [item for item in items if str(item.get("id", "")).startswith("pending-")]
        checks.check("no-pending-after-scan", pending == [], str([item.get("id") for item in pending]))
        snapshot_catalog(isolated, artifacts / "catalog-first")

        still_hash = sha256_file(media / "live" / "LIVE_0001.jpg")
        live_items = [item for item in items if item.get("kind") == "live"]
        checks.check("one-live-item", len(live_items) == 1, str(len(live_items)))
        if live_items:
            live = live_items[0]
            checks.check("live-id-is-still-hash", live.get("id") == still_hash, live.get("id"))
            live_locs = live.get("locations") or []
            comps = sorted(loc.get("component") for loc in live_locs)
            checks.check("live-components", comps == ["motion", "still"], str(comps))
            still_primary = sum(
                1 for loc in live_locs if loc.get("component") == "still" and loc.get("role") == "primary"
            )
            motion_primary = sum(
                1 for loc in live_locs if loc.get("component") == "motion" and loc.get("role") == "primary"
            )
            checks.check(
                "live-has-primaries",
                len(live_locs) == 2
                and comps == ["motion", "still"]
                and still_primary == 1
                and motion_primary == 1,
                f"locations={len(live_locs)} still_primary={still_primary} motion_primary={motion_primary}",
            )

        img_hash = sha256_file(media / "a" / "IMG_1042.jpg")
        dup_items = [item for item in items if item.get("id") == img_hash]
        checks.check("duplicate-one-item", len(dup_items) == 1)
        if dup_items:
            locs = dup_items[0].get("locations") or []
            checks.check("duplicate-two-locations", len(locs) == 2, str(len(locs)))
            primaries = [loc for loc in locs if loc.get("role") == "primary"]
            checks.check("duplicate-one-primary", len(primaries) == 1, str(len(primaries)))
            kinds = {loc.get("kind") for loc in locs}
            checks.check("duplicate-kind-volume", kinds == {"volume"}, str(kinds))

        broken = [item for item in items if item.get("filename") == "broken.heic"]
        checks.check("broken-heic-item", len(broken) == 1)
        if broken:
            status = ((broken[0].get("renditions") or {}).get("status") or {})
            checks.check(
                "broken-heic-rendition-error",
                status.get("thumb") == "error" and status.get("preview") == "error",
                str(status),
            )
            checks.check(
                "broken-heic-no-rendition-path",
                broken[0].get("renditions", {}).get("thumb") is None,
            )
        error_paths = [err.get("path") for err in (errors or [])]
        checks.check("broken-heic-source-error", "formats/broken.heic" in error_paths, str(errors))

        filenames = {item.get("filename") for item in items}
        for rel in FORMAT_FILES:
            name = Path(rel).name
            checks.check(f"format-indexed:{name}", name in filenames)
        checks.check("unicode-indexed", "旅行 photo.jpg" in filenames)
        long_name = "raw_relative_path_would_make_a_bad_pending_json_filename.jpg"
        checks.check("long-path-indexed", long_name in filenames)
        for item in items:
            item_id = item.get("id")
            byte_path = primary_byte_path(media, source, item)
            expected_id = sha256_file(byte_path) if byte_path is not None else None
            checks.check(
                f"item-id-hash:{item_id}",
                id_matches_primary_file_bytes(media, source, item),
                f"id={item_id!r} expected={expected_id!r} path={byte_path!r}",
            )
            rend = item.get("renditions") or {}
            checks.check(
                f"rendition-paths-null:{item.get('id')}",
                rend.get("thumb") is None and rend.get("preview") is None and rend.get("poster") is None and rend.get("proxy") is None,
            )
            for loc in item.get("locations") or []:
                checks.check(f"location-kind-volume:{item.get('id')}", loc.get("kind") == "volume")

        checks.check("scan-history-one", scan_history_count(isolated) == 1, str(scan_history_count(isolated)))

        second = run_library(
            isolated,
            ["scan", str(media), "--serve-from-there"],
            timeout=300,
        )
        commands.append("python -m library scan <media> --serve-from-there #2")
        (artifacts / "scan-second.log").write_text(
            second.stdout + "\n--- stderr ---\n" + second.stderr, encoding="utf-8"
        )
        summary2 = parse_summary(second.stdout) if second.stdout.strip() else {}
        checks.check("scan-second-json", "added" in summary2, second.stdout)
        checks.check("scan-second-added-0", summary2.get("added") == 0, str(summary2.get("added")))
        checks.check("scan-second-skipped", isinstance(summary2.get("skipped"), int) and summary2.get("skipped", 0) > 0)
        checks.check("scan-second-same-source", summary2.get("sourceId") == source_id)
        checks.check("scan-second-stdout-skipped", "skipped" in second.stdout)
        items_after = load_items(isolated)
        checks.check("rescan-same-item-count", len(items_after) == len(items), f"{len(items_after)} vs {len(items)}")
        checks.check("scan-history-two", scan_history_count(isolated) == 2, str(scan_history_count(isolated)))
        snapshot_catalog(isolated, artifacts / "catalog-second")

        copy_here = run_library(isolated, ["copy-here", str(source_id)])
        checks.check("copy-here-cli-not-found-exit", copy_here.returncode == 1, copy_here.stderr)
        try:
            copy_err = parse_json(copy_here.stderr.strip().splitlines()[-1])
        except Exception:
            copy_err = {}
        checks.check("copy-here-cli-not-found", copy_err.get("error") == "not-found", copy_here.stderr)

        no_flag = run_library(isolated, ["scan", str(media)])
        checks.check("choice-required-exit", no_flag.returncode == 2, no_flag.stderr)
        try:
            choice_err = parse_json(no_flag.stderr.strip().splitlines()[-1])
        except Exception:
            choice_err = {}
        checks.check("choice-required-code", choice_err.get("error") == "choice-required")

        copy_flag = run_library(isolated, ["scan", str(media), "--copy-here"])
        checks.check("copy-here-scan-not-found-exit", copy_flag.returncode == 1)
        try:
            copy_scan_err = parse_json(copy_flag.stderr.strip().splitlines()[-1])
        except Exception:
            copy_scan_err = {}
        checks.check("copy-here-scan-not-found", copy_scan_err.get("error") == "not-found")

        ids_before = sorted(item["id"] for item in load_items(isolated))
        sqlite_path = isolated / "catalog" / "catalog.sqlite"
        checks.check("sqlite-exists-after-scan", sqlite_path.is_file())
        sqlite_path.unlink()
        rebuild = run_library(isolated, ["rebuild-index"])
        checks.check("rebuild-cli-exit", rebuild.returncode == 0, rebuild.stderr)
        checks.check("sqlite-exists-after-rebuild", sqlite_path.is_file())
        ids_after = sorted(item["id"] for item in load_items(isolated))
        checks.check("rebuild-same-item-ids", ids_before == ids_after)

        server = start_server(isolated)
        owned.append(server)
        url = f"http://127.0.0.1:{isolated_port}/"
        health_status, health_body = wait_health(url, server)
        checks.check("s01-health", health_status == 200 and health_body == {"ok": True})
        rt_status, runtime = request_json(url.rstrip("/") + "/api/runtime")
        server_pid = runtime.get("pid")
        if type(server_pid) is int:
            owned_pids.append(server_pid)
        src_status, src_body = request_json(url.rstrip("/") + "/api/sources")
        checks.check("http-sources", src_status == 200 and isinstance(src_body, list) and src_body)
        if isinstance(src_body, list) and src_body:
            checks.check("http-source-available", src_body[0].get("available") is True)
            checks.check("http-source-id", src_body[0].get("id") == source_id)
        item_status, item_body = request_json(url.rstrip("/") + "/api/items")
        checks.check("http-items", item_status == 200 and isinstance(item_body, list))
        if isinstance(item_body, list):
            checks.check("http-item-count", len(item_body) == len(ids_before), str(len(item_body)))
            live_http = [item for item in item_body if item.get("kind") == "live"]
            checks.check("http-one-live", len(live_http) == 1)
            if item_body:
                checks.check("http-item-available-field", "available" in item_body[0])
                checks.check("http-item-entities", "entities" in item_body[0])
        post_status, post_body = request_json(
            url.rstrip("/") + "/api/sources",
            method="POST",
            body={"path": str(media), "mode": "serve-from-there"},
            timeout=300.0,
        )
        checks.check("http-rescan-202", post_status == 202, str(post_status))
        if isinstance(post_body, dict):
            checks.check("http-rescan-added-0", (post_body.get("scan") or {}).get("added") == 0)
            checks.check("http-rescan-same-source", post_body.get("id") == source_id)
        copy_http_status, copy_http = request_json(
            url.rstrip("/") + f"/api/sources/{source_id}/copy-here",
            method="POST",
            body={},
        )
        checks.check(
            "http-copy-here-not-found",
            copy_http_status == 404 and copy_http == {"error": "not-found"},
            str(copy_http),
        )
        rebuild_status, rebuild_body = request_json(
            url.rstrip("/") + "/api/rebuild-index",
            method="POST",
            body={},
        )
        checks.check("http-rebuild", rebuild_status == 200 and rebuild_body == {"ok": True})
        from library.index import item_ids_from_sqlite

        sqlite_ids = item_ids_from_sqlite(isolated)
        checks.check("sqlite-ids-match", sqlite_ids == ids_before, str(sqlite_ids))
        stop_owned(server, extra_pids=[server_pid] if type(server_pid) is int else None)
        if server in owned:
            owned.remove(server)

        skip_root = artifacts / "skip-root"
        if skip_root.exists():
            shutil.rmtree(skip_root)
        prepare_root(skip_root)
        skip_media = artifacts / "skip-media"
        if skip_media.exists():
            shutil.rmtree(skip_media)
        skip_media.mkdir()
        shutil.copy2(media / "a" / "IMG_1042.jpg", skip_media / "keep.jpg")
        (skip_media / "notes.txt").write_text("nope", encoding="utf-8")
        hidden = skip_media / ".library" / "hidden.jpg"
        hidden.parent.mkdir()
        shutil.copy2(media / "a" / "near.jpg", hidden)
        extra = artifacts / "skip-extra"
        if extra.exists():
            shutil.rmtree(extra)
        extra.mkdir()
        shutil.copy2(media / "b" / "far.jpg", extra / "sneaky.jpg")
        junction = skip_media / "junction-dir"
        link_proc = make_junction(junction, extra)
        checks.check(
            "junction-created",
            link_proc.returncode == 0 and junction.exists(),
            f"exit={link_proc.returncode} stdout={link_proc.stdout!r} stderr={link_proc.stderr!r}",
        )
        skip_scan = run_library(
            skip_root,
            ["scan", str(skip_media), "--serve-from-there"],
            timeout=120,
        )
        skip_summary = parse_summary(skip_scan.stdout) if skip_scan.stdout.strip() else {}
        skip_items = load_items(skip_root)
        skip_names = {item.get("filename") for item in skip_items}
        checks.check("skip-keep-indexed", "keep.jpg" in skip_names, str(skip_names))
        checks.check("skip-hidden-library", "hidden.jpg" not in skip_names)
        checks.check("skip-notes", "notes.txt" not in skip_names)
        checks.check("skip-junction-file", "sneaky.jpg" not in skip_names)
        checks.check("skip-added-one", skip_summary.get("added") == 1, str(skip_summary))

        self_scan = run_library(skip_root, ["scan", str(skip_root), "--serve-from-there"])
        checks.check("scan-library-data-rejected-exit", self_scan.returncode == 2, self_scan.stderr)
        try:
            self_err = parse_json(self_scan.stderr.strip().splitlines()[-1])
        except Exception:
            self_err = {}
        checks.check("scan-library-data-invalid", self_err.get("error") == "invalid-argument", self_scan.stderr)

        iroot = artifacts / "interrupt-root"
        if iroot.exists():
            shutil.rmtree(iroot)
        prepare_root(iroot)
        imedia = artifacts / "interrupt-media"
        if imedia.exists():
            shutil.rmtree(imedia)
        imedia.mkdir()
        shutil.copy2(media / "b" / "no-exif.jpg", imedia / "one.jpg")
        env = _env()
        env["LIBRARY_TEST"] = "1"
        env["LIBRARY_TEST_BARRIER"] = "hash-publication"
        crashed = run_library(
            iroot,
            ["scan", str(imedia), "--serve-from-there"],
            env=env,
            timeout=60,
        )
        pending_files = list((iroot / "catalog" / "items").glob("pending-*.json")) if (iroot / "catalog" / "items").exists() else []
        barrier_pending_id: str | None = None
        if pending_files:
            barrier_pending_id = json.loads(pending_files[0].read_text(encoding="utf-8")).get("id")
        hash_files = [
            path
            for path in (iroot / "catalog" / "items").glob("*.json")
            if not path.name.startswith("pending-")
        ] if (iroot / "catalog" / "items").exists() else []
        interruption["exit"] = crashed.returncode
        interruption["stderr"] = crashed.stderr.strip()
        interruption["pendingCount"] = len(pending_files)
        interruption["hashCountBeforeRecover"] = len(hash_files)
        checks.check("barrier-hash-exit-86", crashed.returncode == 86, crashed.stderr)
        try:
            barrier_err = parse_json(crashed.stderr.strip().splitlines()[-1])
        except Exception:
            barrier_err = {}
        checks.check(
            "barrier-hash-payload",
            barrier_err.get("error") == "test-barrier" and barrier_err.get("barrier") == "hash-publication",
            crashed.stderr,
        )
        checks.check("barrier-pending-present", len(pending_files) == 1, str(len(pending_files)))
        checks.check("barrier-hash-not-only-published", len(hash_files) == 0, str(len(hash_files)))
        recovered = run_library(iroot, ["settings", "get"])
        checks.check("barrier-recover-exit", recovered.returncode == 0, recovered.stderr)
        after_pending = list((iroot / "catalog" / "items").glob("pending-*.json")) if (iroot / "catalog" / "items").exists() else []
        after_items = load_items(iroot)
        interruption["pendingAfterRecover"] = len(after_pending)
        interruption["itemIdsAfterRecover"] = [item.get("id") for item in after_items]
        checks.check("barrier-pending-cleared", after_pending == [])
        checks.check("barrier-one-item", len(after_items) == 1, str([item.get("id") for item in after_items]))
        interrupt_sources = load_sources(iroot)
        interrupt_source = interrupt_sources[0] if interrupt_sources else {}
        if after_items:
            published_id = after_items[0]["id"]
            checks.check(
                "barrier-pending-not-published-id",
                type(barrier_pending_id) is str and barrier_pending_id != published_id,
                f"pending={barrier_pending_id!r} published={published_id!r}",
            )
            checks.check(
                "barrier-item-is-hash",
                id_matches_primary_file_bytes(imedia, interrupt_source, after_items[0]),
                f"id={published_id!r} expected={sha256_file(imedia / 'one.jpg')!r}",
            )
        rescan = run_library(iroot, ["scan", str(imedia), "--serve-from-there"], timeout=60)
        rescan_summary = parse_summary(rescan.stdout) if rescan.stdout.strip() else {}
        rescan_items = load_items(iroot)
        interruption["rescan"] = rescan_summary
        interruption["itemIdsAfterRescan"] = [item.get("id") for item in rescan_items]
        checks.check("barrier-rescan-one-item", len(rescan_items) == 1)
        checks.check("barrier-rescan-same-id", [item["id"] for item in rescan_items] == [item["id"] for item in after_items])

        volumes_path = artifacts / "test-volumes.json"
        volumes_path.write_text(
            json.dumps({"windows:fixture-offline": None}, indent=2) + "\n",
            encoding="utf-8",
        )
        uroot = artifacts / "unavailable-root"
        if uroot.exists():
            shutil.rmtree(uroot)
        prepare_root(uroot)
        run_library(uroot, ["settings", "get"])
        source_id_off = "src_bbbbbbbbbbbb"
        item_id_off = "b" * 64
        origin = {
            "volumeSerial": "windows:fixture-offline",
            "pathFromVolumeRoot": "pictures",
            "lastKnownPath": r"Z:\pictures",
        }
        off_source = make_source(
            source_id=source_id_off,
            name="pictures",
            mode="serve-from-there",
            origin=origin,
            files={
                "offline.jpg": make_file_entry(
                    item_id=item_id_off,
                    component="still",
                    size_bytes=12,
                    modified_at="2022-01-01T00:00:00Z",
                    sha256=item_id_off,
                    state="indexed",
                    destination=None,
                )
            },
            scan={"state": "complete", "added": 1, "skipped": 0, "errors": []},
        )
        off_item = make_item(
            item_id=item_id_off,
            kind="photo",
            filename="offline.jpg",
            captured_at="2022-01-01T00:00:00Z",
            captured_at_source="mtime",
            content_identifier=None,
            locations=[
                make_location(
                    source_id=source_id_off,
                    role="primary",
                    component="still",
                    volume_serial="windows:fixture-offline",
                    path_from_volume_root="pictures/offline.jpg",
                    last_known_path=r"Z:\pictures\offline.jpg",
                    size_bytes=12,
                    modified_at="2022-01-01T00:00:00Z",
                    sha256=item_id_off,
                )
            ],
            renditions=renditions_for("photo", source_id_off),
        )
        (uroot / "catalog" / "sources").mkdir(parents=True, exist_ok=True)
        (uroot / "catalog" / "items").mkdir(parents=True, exist_ok=True)
        atomic_write_json(uroot / "catalog" / "sources" / f"{source_id_off}.json", off_source)
        atomic_write_json(uroot / "catalog" / "items" / f"{item_id_off}.json", off_item)
        uenv = _env()
        uenv["LIBRARY_TEST"] = "1"
        uenv["LIBRARY_TEST_VOLUMES"] = str(volumes_path)
        listed = run_library(uroot, ["sources"], env=uenv)
        checks.check("unavailable-sources-exit", listed.returncode == 0, listed.stderr)
        listed_body = parse_json(listed.stdout) if listed.returncode == 0 else []
        checks.check("unavailable-source-present", isinstance(listed_body, list) and len(listed_body) == 1)
        if isinstance(listed_body, list) and listed_body:
            checks.check("unavailable-source-flag", listed_body[0].get("available") is False)
        items_cli = run_library(uroot, ["items"], env=uenv)
        checks.check("unavailable-items-exit", items_cli.returncode == 0, items_cli.stderr)
        items_body = parse_json(items_cli.stdout) if items_cli.returncode == 0 else []
        checks.check("unavailable-item-listed", isinstance(items_body, list) and len(items_body) == 1)
        if isinstance(items_body, list) and items_body:
            checks.check("unavailable-item-flag", items_body[0].get("available") is False)
            checks.check("unavailable-item-id", items_body[0].get("id") == item_id_off)
        disk_item = json.loads(
            (uroot / "catalog" / "items" / f"{item_id_off}.json").read_text(encoding="utf-8")
        )
        checks.check("unavailable-location-retained", len(disk_item.get("locations") or []) == 1)
        interruption["unavailable"] = {
            "sourceAvailable": listed_body[0].get("available") if listed_body else None,
            "itemAvailable": items_body[0].get("available") if items_body else None,
        }
        (artifacts / "interruption.json").write_text(
            json.dumps(interruption, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest_hash = sha256_file(COMMITTED_FIXTURES / "manifest.json") if (COMMITTED_FIXTURES / "manifest.json").is_file() else ""
    result = {
        "slice": "S01",
        "pass": checks.ok(),
        "assertions": checks.assertions,
        "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version},
        "fixtureManifestHash": manifest_hash,
        "revision": revision,
        "commands": commands,
        "artifactPaths": {
            "result.json": str(artifacts / "result.json"),
            "stdout.log": str(artifacts / "stdout.log"),
            "scan-first.log": str(artifacts / "scan-first.log"),
            "scan-second.log": str(artifacts / "scan-second.log"),
            "original-hashes.json": str(artifacts / "original-hashes.json"),
            "interruption.json": str(artifacts / "interruption.json"),
        },
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1
