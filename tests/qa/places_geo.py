"""Offline GPS city names. This log is not the grade."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from library.geo import convert_geonames, lookup_name, pack_ready
from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.roots import prepare_root
from tests.qa.s00 import (
    COMMITTED_FIXTURES,
    PRODUCT_ROOT,
    Checks,
    copy_committed_fixtures,
    find_free_port,
    parse_json,
    run_library,
    stop_owned,
    write_isolated_port,
)
from tests.qa.s01 import load_items, load_sources, parse_summary
from tests.qa.s02 import copy_rels, item_for_rel, load_places, items_by_id
from tests.qa.s05 import start_isolated

GEO_FIXTURE = COMMITTED_FIXTURES / "geo"
THREE_JPEG = ("a/IMG_1042.jpg", "a/near.jpg", "b/far.jpg")
NO_GPS = ("b/no-exif.jpg",)
EXPECTED_NAME = "Chicago, Illinois"


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


def _cli_json(proc: subprocess.CompletedProcess[str]) -> Any:
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        return parse_json(text)
    except json.JSONDecodeError:
        start = text.rfind("{")
        if start == -1:
            start = text.rfind("[")
        if start == -1:
            return None
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text, start)
        return obj


def fresh_root(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    prepare_root(path)
    write_isolated_port(path, find_free_port())
    return path


def scan_subset(root: Path, media: Path, rels: tuple[str, ...], dest: Path) -> dict[str, Any]:
    if dest.exists():
        shutil.rmtree(dest)
    copy_rels(media, dest, rels)
    proc = run_library(root, ["scan", str(dest), "--serve-from-there"], timeout=120)
    return {
        "proc": proc,
        "summary": parse_summary(proc.stdout) if proc.stdout.strip() else {},
        "items": load_items(root),
        "places": load_places(root),
        "sources": (load_sources(root) or [{}])[0],
    }


def prove_lookup_and_pack(checks: Checks, artifacts: Path, commands: list[str]) -> None:
    empty = artifacts / "empty-geo-root"
    fresh_root(empty)
    checks.check("lookup-without-pack", lookup_name(empty, 41.88, -87.63) is None)
    checks.check("pack-missing", pack_ready(empty) is False)

    install = run_library(
        empty, ["setup-geo", "--from", str(GEO_FIXTURE)], timeout=30
    )
    commands.append("python -m library setup-geo --from tests/fixtures/geo")
    payload = _cli_json(install)
    checks.check(
        "setup-geo-from-fixture",
        install.returncode == 0 and isinstance(payload, dict) and payload.get("ok") is True,
        f"exit={install.returncode} {payload} err={install.stderr}",
    )
    checks.check("pack-ready-after-from", pack_ready(empty) is True)
    checks.check("lookup-chicago", lookup_name(empty, 41.88, -87.63) == EXPECTED_NAME)
    checks.check("lookup-near", lookup_name(empty, 41.88045, -87.63) == EXPECTED_NAME)
    checks.check(
        "lookup-nyc",
        lookup_name(empty, 40.71427, -74.00597) == "New York City, New York",
    )

    again = run_library(empty, ["setup-geo", "--from", str(GEO_FIXTURE)], timeout=30)
    again_payload = _cli_json(again)
    checks.check(
        "setup-geo-existing-noop",
        again.returncode == 0
        and isinstance(again_payload, dict)
        and again_payload.get("source") == "existing",
        str(again_payload),
    )

    cities_txt = (
        "4887398\tChicago\tChicago\t\t41.85003\t-87.65005\tP\tPPLA2\tUS\t\tIL\t031\t\t\t2695598\t179\t\tAmerica/Chicago\t2024-01-01\n"
    )
    admin = {"US.IL": "Illinois"}
    converted = convert_geonames(cities_txt, admin)
    checks.check("convert-header", converted.splitlines()[0] == "latitude,longitude,name,admin1,cc")
    checks.check("convert-chicago", "Chicago,Illinois,US" in converted.replace(" ", ""))


def prove_scan_named(
    checks: Checks, artifacts: Path, media: Path, commands: list[str]
) -> dict[str, Any]:
    root = fresh_root(artifacts / "named-library-data")
    install = run_library(root, ["setup-geo", "--from", str(GEO_FIXTURE)], timeout=30)
    commands.append("python -m library setup-geo --from tests/fixtures/geo")
    checks.check("named-root-pack", install.returncode == 0, install.stderr)
    dest = artifacts / "named-media"
    scanned = scan_subset(root, media, THREE_JPEG + NO_GPS, dest)
    commands.append("python -m library scan <three-jpeg+no-exif> --serve-from-there")
    checks.check(
        "named-scan-ok",
        scanned["proc"].returncode == 0 and scanned["summary"].get("added") == 4,
        f"exit={scanned['proc'].returncode} {scanned['summary']}",
    )
    places = scanned["places"]
    items = scanned["items"]
    source = scanned["sources"]
    by_id = items_by_id(items)
    img = item_for_rel(source, by_id, "a/IMG_1042.jpg")
    near = item_for_rel(source, by_id, "a/near.jpg")
    far = item_for_rel(source, by_id, "b/far.jpg")
    none = item_for_rel(source, by_id, "b/no-exif.jpg")
    checks.check("named-two-gps-places", len(places) == 2, str(len(places)))
    checks.check("named-img-present", img is not None)
    checks.check("named-near-same", bool(img) and bool(near) and img.get("placeId") == near.get("placeId"))
    checks.check("named-far-other", bool(img) and bool(far) and img.get("placeId") != far.get("placeId"))
    checks.check("named-no-gps", none is not None and none.get("placeId") is None)
    img_place = next((p for p in places if img and p.get("id") == img.get("placeId")), None)
    far_place = next((p for p in places if far and p.get("id") == far.get("placeId")), None)
    checks.check("named-img-chicago", bool(img_place) and img_place.get("name") == EXPECTED_NAME, str(img_place))
    checks.check("named-far-chicago", bool(far_place) and far_place.get("name") == EXPECTED_NAME, str(far_place))
    snapshot = artifacts / "named-places"
    snapshot.mkdir(parents=True, exist_ok=True)
    for place in places:
        (snapshot / f"{place['id']}.json").write_text(
            json.dumps(place, indent=2) + "\n", encoding="utf-8"
        )
    return {"root": root, "img": img, "places": places, "items": items}


def prove_search_and_info(
    checks: Checks, root: Path, commands: list[str]
) -> None:
    listed = run_library(root, ["items", "--q", "Chicago"], timeout=30)
    commands.append("python -m library items --q Chicago")
    rows = _cli_json(listed)
    checks.check("search-chicago-ok", listed.returncode == 0 and isinstance(rows, list), listed.stderr)
    names = [row.get("filename") for row in rows] if isinstance(rows, list) else []
    checks.check("search-chicago-has-img", "IMG_1042.jpg" in names, str(names))
    checks.check("search-chicago-omits-no-exif", "no-exif.jpg" not in names, str(names))
    scoped = run_library(root, ["items", "--q", "chicago", "--scope", "places"], timeout=30)
    commands.append("python -m library items --q chicago --scope places")
    scoped_rows = _cli_json(scoped)
    scoped_names = [row.get("filename") for row in scoped_rows] if isinstance(scoped_rows, list) else []
    checks.check(
        "search-scope-places",
        scoped.returncode == 0 and "IMG_1042.jpg" in scoped_names,
        str(scoped_names),
    )
    if isinstance(rows, list):
        img = next((row for row in rows if row.get("filename") == "IMG_1042.jpg"), None)
        entities = (img or {}).get("entities") or {}
        places = entities.get("places") or []
        checks.check(
            "info-entities-place-name",
            places and places[0].get("name") == EXPECTED_NAME,
            json.dumps(places),
        )


def prove_no_overwrite(
    checks: Checks, artifacts: Path, media: Path, commands: list[str]
) -> None:
    root = fresh_root(artifacts / "keep-name-library-data")
    run_library(root, ["setup-geo", "--from", str(GEO_FIXTURE)], timeout=30)
    dest = artifacts / "keep-name-media"
    scanned = scan_subset(root, media, ("a/IMG_1042.jpg",), dest)
    img = scanned["items"][0] if scanned["items"] else None
    checks.check("keep-scan", img is not None and img.get("placeId"), str(img))
    if not img:
        return
    annotated = run_library(
        root, ["annotate", img["id"], "--place", "Kitchen"], timeout=30
    )
    commands.append("python -m library annotate <id> --place Kitchen")
    checks.check("keep-annotate", annotated.returncode == 0, annotated.stderr)
    after_ann = load_places(root)
    checks.check(
        "keep-kitchen-after-annotate",
        after_ann and after_ann[0].get("name") == "Kitchen",
        json.dumps(after_ann),
    )
    filled = run_library(root, ["analyze-places"], timeout=30)
    commands.append("python -m library analyze-places")
    payload = _cli_json(filled)
    checks.check(
        "keep-analyze-noop",
        filled.returncode == 0 and isinstance(payload, dict) and payload.get("named") == 0,
        str(payload),
    )
    checks.check(
        "keep-kitchen-after-analyze",
        load_places(root)[0].get("name") == "Kitchen",
        json.dumps(load_places(root)),
    )
    rescan = run_library(root, ["scan", str(dest), "--serve-from-there"], timeout=120)
    commands.append("python -m library scan <keep-name-media> --serve-from-there")
    checks.check("keep-rescan-ok", rescan.returncode == 0, rescan.stderr)
    checks.check(
        "keep-kitchen-after-rescan",
        load_places(root)[0].get("name") == "Kitchen",
        json.dumps(load_places(root)),
    )


def prove_analyze_backfill(
    checks: Checks, artifacts: Path, media: Path, commands: list[str]
) -> None:
    root = fresh_root(artifacts / "backfill-library-data")
    dest = artifacts / "backfill-media"
    scanned = scan_subset(root, media, ("a/IMG_1042.jpg",), dest)
    commands.append("python -m library scan <img> --serve-from-there # no pack")
    places = scanned["places"]
    checks.check(
        "backfill-starts-null",
        places and places[0].get("name") is None,
        json.dumps(places),
    )
    missing = run_library(root, ["analyze-places"], timeout=30)
    missing_payload = _cli_json(missing)
    checks.check(
        "analyze-without-pack",
        missing.returncode == 0
        and isinstance(missing_payload, dict)
        and missing_payload.get("packReady") is False
        and missing_payload.get("named") == 0,
        str(missing_payload),
    )
    install = run_library(root, ["setup-geo", "--from", str(GEO_FIXTURE)], timeout=30)
    commands.append("python -m library setup-geo --from tests/fixtures/geo")
    checks.check("backfill-setup", install.returncode == 0, install.stderr)
    filled = run_library(root, ["analyze-places"], timeout=30)
    commands.append("python -m library analyze-places")
    payload = _cli_json(filled)
    checks.check(
        "backfill-named-one",
        filled.returncode == 0 and isinstance(payload, dict) and payload.get("named") == 1,
        str(payload),
    )
    after = load_places(root)
    checks.check(
        "backfill-chicago",
        after and after[0].get("name") == EXPECTED_NAME,
        json.dumps(after),
    )


def prove_http(checks: Checks, artifacts: Path, media: Path, commands: list[str]) -> None:
    isolated = artifacts / "http-library-data"
    server = None
    owned: list[int] = []
    try:
        server, url, _port, owned = start_isolated(isolated)
        install = run_library(isolated, ["setup-geo", "--from", str(GEO_FIXTURE)], timeout=30)
        checks.check("http-setup", install.returncode == 0, install.stderr)
        dest = artifacts / "http-media"
        if dest.exists():
            shutil.rmtree(dest)
        copy_rels(media, dest, ("a/IMG_1042.jpg", "b/no-exif.jpg"))
        # Scan without naming first: wipe pack, scan, restore pack, analyze via HTTP.
        shutil.rmtree(isolated / "geo")
        scan = run_library(isolated, ["scan", str(dest), "--serve-from-there"], timeout=120)
        commands.append("python -m library scan <http-media> --serve-from-there")
        checks.check("http-scan", scan.returncode == 0, scan.stderr)
        checks.check(
            "http-scan-null-name",
            load_places(isolated) and load_places(isolated)[0].get("name") is None,
            json.dumps(load_places(isolated)),
        )
        run_library(isolated, ["setup-geo", "--from", str(GEO_FIXTURE), "--force"], timeout=30)
        status, body = request_json(url.rstrip("/") + "/api/places/analyze", method="POST", body={})
        commands.append("POST /api/places/analyze")
        checks.check("http-analyze-status", status == 200, str(status))
        checks.check(
            "http-analyze-named",
            isinstance(body, dict) and body.get("ok") is True and body.get("named") == 1,
            json.dumps(body),
        )
        status, items = request_json(url.rstrip("/") + "/api/items?q=Chicago")
        checks.check("http-search-status", status == 200 and isinstance(items, list), str(status))
        filenames = [row.get("filename") for row in items] if isinstance(items, list) else []
        checks.check("http-search-img", "IMG_1042.jpg" in filenames, str(filenames))
        checks.check("http-search-no-exif", "no-exif.jpg" not in filenames, str(filenames))
    finally:
        if server is not None:
            stop_owned(server, extra_pids=owned)


def run_session(root: Path, artifacts: Path) -> int:
    checks = Checks()
    commands: list[str] = []
    artifacts.mkdir(parents=True, exist_ok=True)
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media = sandbox / "media"
    prove_lookup_and_pack(checks, artifacts, commands)
    named = prove_scan_named(checks, artifacts, media, commands)
    prove_search_and_info(checks, named["root"], commands)
    prove_no_overwrite(checks, artifacts, media, commands)
    prove_analyze_backfill(checks, artifacts, media, commands)
    prove_http(checks, artifacts, media, commands)
    extra = {
        "named-places": str(artifacts / "named-places"),
    }
    return write_result("GEO", "check", checks, artifacts, commands, extra)


def run_slice(root: Path, artifacts: Path) -> int:
    return run_session(root, artifacts)


def run_check(root: Path, artifacts: Path) -> int:
    return run_session(root, artifacts)
