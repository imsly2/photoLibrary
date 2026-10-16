"""Optional local face inference. Fixture proof; this log is not the grade."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.media import sha256_file
from tests.qa.s00 import (
    Checks,
    _env,
    parse_json,
    run_library,
    stop_owned,
)
from tests.qa.s01 import load_items
from tests.qa.s08 import fresh_root, load_people, start_owned, write_result

FACE_A = (16, 200, 48)
FACE_B = (32, 48, 220)
BEACON = (255, 0, 170)
WHITE = (255, 255, 255)
BG = (30, 30, 36)


def write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _fill(buf: bytearray, width: int, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    r, g, b = color
    for y in range(y0, y1):
        row = y * width * 3
        for x in range(x0, x1):
            p = row + x * 3
            buf[p] = r
            buf[p + 1] = g
            buf[p + 2] = b


def paint_face(
    buf: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    fw: int,
    fh: int,
    identity: tuple[int, int, int],
) -> None:
    x1 = min(width, x + fw)
    y1 = min(height, y + fh)
    _fill(buf, width, x, y, x1, y1, identity)
    border = 8
    _fill(buf, width, x, y, x1, y + border, BEACON)
    _fill(buf, width, x, y1 - border, x1, y1, BEACON)
    _fill(buf, width, x, y, x + border, y1, BEACON)
    _fill(buf, width, x1 - border, y, x1, y1, BEACON)
    eye_w = max(8, fw // 8)
    eye_h = max(8, fh // 10)
    left = x + fw // 4
    right = x + (fw * 3) // 5
    eye_y = y + fh // 3
    _fill(buf, width, left, eye_y, left + eye_w, eye_y + eye_h, WHITE)
    _fill(buf, width, right, eye_y, right + eye_w, eye_y + eye_h, WHITE)


def make_face_media(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    width, height = 640, 480
    specs = {
        "a1.png": [("A", 80, 80, 140, 180)],
        "a2.png": [("A", 220, 110, 140, 180)],
        "b1.png": [("B", 360, 90, 140, 180)],
        "b2.png": [("B", 120, 170, 140, 180)],
        "both.png": [("A", 60, 90, 140, 180), ("B", 400, 100, 140, 180)],
        "empty.png": [],
    }
    colors = {"A": FACE_A, "B": FACE_B}
    for name, faces in specs.items():
        buf = bytearray(width * height * 3)
        _fill(buf, width, 0, 0, width, height, BG)
        for who, x, y, fw, fh in faces:
            paint_face(buf, width, height, x, y, fw, fh, colors[who])
        write_png(dest / name, width, height, bytes(buf))
    return dest


def test_env() -> dict[str, str]:
    env = _env()
    env["LIBRARY_TEST"] = "1"
    return env


def last_error(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        return parse_json(proc.stderr.strip().splitlines()[-1])
    except Exception:
        return {}


def item_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("filename") == name:
            return item
    return None


def box_ok(box: Any) -> bool:
    if not isinstance(box, list) or len(box) != 4:
        return False
    x, y, w, h = (float(v) for v in box)
    return x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= 1.0001 and y + h <= 1.0001


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    commands = [
        "setup-ml faces --backend fixture",
        "GET /api/faces",
        "scan <faces> --serve-from-there",
        "infer-faces",
        "POST /api/items/<id>/annotations {id,name}",
        "GET /api/items?person=Ada",
        "people merge",
        "people split",
        "infer-faces without models",
    ]
    artifacts.mkdir(parents=True, exist_ok=True)
    fresh_root(root)
    media = make_face_media(artifacts / "faces-media")
    originals = {path.name: sha256_file(path) for path in sorted(media.glob("*.png"))}

    missing = run_library(root, ["infer-faces"], env=test_env())
    missing_err = last_error(missing)
    checks.check("infer-without-models-exit", missing.returncode != 0, missing.stderr)
    checks.check(
        "infer-without-models",
        missing_err.get("error") == "models-missing",
        json.dumps(missing_err),
    )

    prod_fixture = run_library(root, ["setup-ml", "faces", "--backend", "fixture"], env=_env())
    prod_err = last_error(prod_fixture)
    checks.check(
        "fixture-backend-prod-rejected",
        prod_fixture.returncode != 0 and prod_err.get("error") == "invalid-argument",
        prod_fixture.stderr,
    )

    setup = run_library(root, ["setup-ml", "faces", "--backend", "fixture"], env=test_env())
    checks.check("setup-exit", setup.returncode == 0, setup.stderr)
    setup_body = parse_json(setup.stdout) if setup.returncode == 0 else {}
    checks.check("setup-ready", setup_body.get("ready") is True, setup.stdout)
    checks.check("setup-backend", setup_body.get("backend") == "fixture", setup.stdout)
    checks.check(
        "manifest-exists",
        (root / "models" / "faces" / "manifest.json").is_file(),
        str(root / "models" / "faces" / "manifest.json"),
    )

    scan = run_library(
        root,
        ["scan", str(media), "--serve-from-there"],
        env=test_env(),
        timeout=120,
    )
    checks.check("scan-exit", scan.returncode == 0, scan.stderr)

    infer = run_library(root, ["infer-faces"], env=test_env(), timeout=120)
    checks.check("infer-exit", infer.returncode == 0, infer.stderr)
    infer_body = parse_json(infer.stdout) if infer.returncode == 0 else {}
    checks.check("infer-ok", infer_body.get("ok") is True, infer.stdout)
    checks.check("infer-backend", infer_body.get("backend") == "fixture", infer.stdout)
    checks.check("infer-faces-6", infer_body.get("faces") == 6, infer.stdout)
    checks.check("infer-people-created-2", infer_body.get("peopleCreated") == 2, infer.stdout)
    write_json = artifacts / "infer.json"
    write_json.write_text(json.dumps(infer_body, indent=2) + "\n", encoding="utf-8")

    people = load_people(root)
    checks.check("people-count-2", len(people) == 2, json.dumps(people))
    checks.check(
        "people-unnamed",
        all(rec.get("name") is None for rec in people),
        json.dumps(people),
    )
    guessed = [
        rec
        for rec in people
        if type(rec.get("name")) is str and rec["name"].strip() != ""
    ]
    checks.check("no-guessed-name", guessed == [], json.dumps(guessed))

    items = load_items(root)
    by_name = {item["filename"]: item for item in items}
    a1 = by_name.get("a1.png") or {}
    a2 = by_name.get("a2.png") or {}
    b1 = by_name.get("b1.png") or {}
    b2 = by_name.get("b2.png") or {}
    both = by_name.get("both.png") or {}
    empty = by_name.get("empty.png") or {}
    checks.check("a1-one-face", len(a1.get("faces") or []) == 1, json.dumps(a1.get("faces")))
    checks.check("empty-no-faces", empty.get("faces") == [], json.dumps(empty.get("faces")))
    checks.check("both-two-faces", len(both.get("faces") or []) == 2, json.dumps(both.get("faces")))

    def person_of(item: dict[str, Any]) -> str | None:
        faces = item.get("faces") or []
        if not faces:
            return None
        return faces[0].get("personId")

    person_a = person_of(a1)
    person_b = person_of(b1)
    checks.check("a-cluster", person_a is not None and person_of(a2) == person_a, json.dumps([a1.get("faces"), a2.get("faces")]))
    checks.check("b-cluster", person_b is not None and person_of(b2) == person_b, json.dumps([b1.get("faces"), b2.get("faces")]))
    checks.check("a-ne-b", person_a != person_b, f"{person_a} {person_b}")
    both_ids = sorted(pid for pid in {face.get("personId") for face in both.get("faces") or []} if pid)
    expected = sorted(pid for pid in (person_a, person_b) if pid)
    checks.check("both-has-a-and-b", both_ids == expected and len(expected) == 2, json.dumps(both_ids))
    all_boxes = [
        face.get("box")
        for item in items
        for face in item.get("faces") or []
    ]
    checks.check("boxes-in-range", all(box_ok(box) for box in all_boxes), json.dumps(all_boxes))

    people_dir = artifacts / "people"
    if people_dir.exists():
        shutil.rmtree(people_dir)
    shutil.copytree(root / "catalog" / "people", people_dir)

    server = None
    owned: list[int] = []
    try:
        server, url, owned = start_owned(root)
        status, face_status = request_json(url + "api/faces", timeout=5)
        checks.check("http-faces-status", status == 200 and face_status.get("ready") is True, json.dumps(face_status))
        status, http_infer = request_json(
            url + "api/faces/infer", method="POST", body={"force": False}, timeout=60
        )
        checks.check("http-infer-skip", status == 200 and http_infer.get("faces") == 0, json.dumps(http_infer))
        a1_id = a1.get("id")
        status, named = request_json(
            url + f"api/items/{a1_id}/annotations",
            method="POST",
            body={"people": [{"id": person_a, "name": "Ada"}]},
            timeout=10,
        )
        checks.check("name-ada-http", status == 200, json.dumps(named))
        ada = json.loads((root / "catalog" / "people" / f"{person_a}.json").read_text(encoding="utf-8"))
        checks.check("ada-name", ada.get("name") == "Ada", json.dumps(ada))
        still_b = json.loads((root / "catalog" / "people" / f"{person_b}.json").read_text(encoding="utf-8"))
        checks.check("b-still-unnamed", still_b.get("name") is None, json.dumps(still_b))
        status, by_person = request_json(url + "api/items?person=Ada", timeout=5)
        names = sorted(item.get("filename") for item in (by_person or []) if isinstance(item, dict))
        checks.check("search-person-ada", status == 200 and set(names) == {"a1.png", "a2.png", "both.png"}, json.dumps(names))
        status, by_q = request_json(url + "api/items?q=Ada&scope=people", timeout=5)
        q_names = sorted(item.get("filename") for item in (by_q or []) if isinstance(item, dict))
        checks.check("search-q-ada", status == 200 and set(q_names) == {"a1.png", "a2.png", "both.png"}, json.dumps(q_names))
        (artifacts / "search.json").write_text(
            json.dumps({"person": by_person, "q": by_q}, indent=2) + "\n",
            encoding="utf-8",
        )
        status, merged = request_json(
            url + "api/people/merge",
            method="POST",
            body={"keepId": person_a, "dropId": person_b},
            timeout=10,
        )
        checks.check("merge-http", status == 200 and merged.get("id") == person_a, json.dumps(merged))
    finally:
        stop_owned(server, owned)

    after_people = load_people(root)
    checks.check("merge-one-person", len(after_people) == 1, json.dumps(after_people))
    checks.check("merge-keep-ada", after_people[0].get("name") == "Ada", json.dumps(after_people))
    checks.check(
        "drop-gone",
        not (root / "catalog" / "people" / f"{person_b}.json").exists(),
        person_b or "",
    )
    after_items = load_items(root)
    face_ids = {
        face.get("personId")
        for item in after_items
        for face in item.get("faces") or []
    }
    checks.check("all-faces-keep", face_ids == {person_a}, json.dumps(sorted(face_ids)))
    index = json.loads((root / "models" / "faces" / "index.json").read_text(encoding="utf-8"))
    checks.check("index-keep-only", set((index.get("people") or {}).keys()) == {person_a}, json.dumps(index))
    (artifacts / "merge.json").write_text(json.dumps({"keep": person_a, "drop": person_b, "index": index}, indent=2) + "\n", encoding="utf-8")

    prove_split(checks, artifacts, media)

    after_hashes = {path.name: sha256_file(path) for path in sorted(media.glob("*.png"))}
    checks.check("original-hashes", after_hashes == originals, json.dumps({"before": originals, "after": after_hashes}))

    history = []
    state_path = root / "undo" / "state.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for entry_id in state.get("entries") or []:
            path = root / "undo" / "entries" / f"{entry_id}.json"
            if path.is_file():
                history.append(json.loads(path.read_text(encoding="utf-8")))
    ops = [entry.get("operation") for entry in history]
    checks.check("history-faces-infer", "faces-infer" in ops, json.dumps(ops))

    genderage = root / "models" / "faces" / "buffalo_s" / "genderage.onnx"
    checks.check("no-genderage", not genderage.exists(), str(genderage))

    prove_quality_gates(checks, artifacts)

    return write_result(
        "FACES",
        "slice",
        checks,
        artifacts,
        commands,
        {
            "infer.json": str(artifacts / "infer.json"),
            "search.json": str(artifacts / "search.json"),
            "merge.json": str(artifacts / "merge.json"),
            "split.json": str(artifacts / "split.json"),
            "people": str(artifacts / "people"),
        },
    )


def prove_split(checks: Checks, artifacts: Path, media: Path) -> None:
    root = fresh_root(artifacts / "split-root")
    setup = run_library(root, ["setup-ml", "faces", "--backend", "fixture"], env=test_env())
    checks.check("split-setup", setup.returncode == 0, setup.stderr)
    scan = run_library(root, ["scan", str(media), "--serve-from-there"], env=test_env(), timeout=120)
    checks.check("split-scan", scan.returncode == 0, scan.stderr)
    infer = run_library(root, ["infer-faces"], env=test_env(), timeout=120)
    checks.check("split-infer", infer.returncode == 0, infer.stderr)
    items = {item["filename"]: item for item in load_items(root)}
    a1 = items.get("a1.png") or {}
    b1 = items.get("b1.png") or {}
    person_a = ((a1.get("faces") or [{}])[0] or {}).get("personId")
    person_b = ((b1.get("faces") or [{}])[0] or {}).get("personId")
    checks.check("split-two-people", bool(person_a) and bool(person_b) and person_a != person_b, f"{person_a} {person_b}")
    name_json = artifacts / "split-name-ada.json"
    name_json.write_text(json.dumps({"people": [{"id": person_a, "name": "Ada"}]}), encoding="utf-8")
    named = run_library(root, ["annotate", a1["id"], "--json", str(name_json)], env=test_env())
    checks.check("split-name-ada", named.returncode == 0, named.stderr)
    merged = run_library(root, ["people", "merge", person_a, person_b], env=test_env())
    checks.check("split-wrong-join", merged.returncode == 0, merged.stderr)
    after_join = {item["filename"]: item for item in load_items(root)}
    b1_face = (after_join.get("b1.png", {}).get("faces") or [{}])[0]
    checks.check("split-b1-on-ada", b1_face.get("personId") == person_a, json.dumps(b1_face))
    split = run_library(
        root,
        ["people", "split", person_a, "--item", after_join["b1.png"]["id"]],
        env=test_env(),
    )
    checks.check("split-cli", split.returncode == 0, split.stderr)
    split_body = parse_json(split.stdout) if split.returncode == 0 else {}
    new_id = split_body.get("id")
    checks.check("split-new-id", type(new_id) is str and new_id.startswith("person_") and new_id != person_a, json.dumps(split_body))
    ada = json.loads((root / "catalog" / "people" / f"{person_a}.json").read_text(encoding="utf-8"))
    checks.check("split-ada-remains", ada.get("name") == "Ada", json.dumps(ada))
    created = json.loads((root / "catalog" / "people" / f"{new_id}.json").read_text(encoding="utf-8"))
    checks.check("split-unnamed", created.get("name") is None, json.dumps(created))
    after_split = {item["filename"]: item for item in load_items(root)}
    a1_ids = {face.get("personId") for face in after_split.get("a1.png", {}).get("faces") or []}
    b1_ids = {face.get("personId") for face in after_split.get("b1.png", {}).get("faces") or []}
    checks.check("split-a1-still-ada", a1_ids == {person_a}, json.dumps(sorted(a1_ids)))
    checks.check("split-b1-left", b1_ids == {new_id}, json.dumps(sorted(b1_ids)))
    people = load_people(root)
    names = {rec.get("id"): rec.get("name") for rec in people}
    checks.check("split-ada-file", names.get(person_a) == "Ada", json.dumps(names))
    checks.check("split-bob-person-gone", person_b not in names, json.dumps(names))
    index = json.loads((root / "models" / "faces" / "index.json").read_text(encoding="utf-8"))
    index_people = set((index.get("people") or {}).keys())
    checks.check("split-index-both", {person_a, new_id} <= index_people, json.dumps(sorted(index_people)))
    src_faces = (index.get("people") or {}).get(person_a, {}).get("faces") or []
    new_faces = (index.get("people") or {}).get(new_id, {}).get("faces") or []
    checks.check(
        "split-index-moved",
        any(ref.get("itemId") == after_join["b1.png"]["id"] for ref in new_faces)
        and not any(ref.get("itemId") == after_join["b1.png"]["id"] for ref in src_faces),
        json.dumps({"src": src_faces, "new": new_faces}),
    )
    missing = run_library(root, ["people", "split", "person_missing", "--item", after_join["b1.png"]["id"]], env=test_env())
    missing_err = last_error(missing)
    checks.check(
        "split-missing-person",
        missing.returncode != 0 and missing_err.get("error") in {"not-found", "invalid-argument"},
        json.dumps(missing_err),
    )
    http_split: dict[str, Any] | None = None
    server = None
    owned: list[int] = []
    try:
        server, url, owned = start_owned(root)
        status, http_split = request_json(
            url + "api/people/split",
            method="POST",
            body={
                "personId": person_a,
                "itemId": after_split["b2.png"]["id"],
                "box": (after_split.get("b2.png", {}).get("faces") or [{}])[0].get("box"),
            },
            timeout=10,
        )
        checks.check("split-http", status == 200 and (http_split or {}).get("id") != person_a, json.dumps(http_split))
        ada_http = json.loads((root / "catalog" / "people" / f"{person_a}.json").read_text(encoding="utf-8"))
        checks.check("split-http-ada-stays", ada_http.get("name") == "Ada", json.dumps(ada_http))
    finally:
        stop_owned(server, owned)
    (artifacts / "split.json").write_text(
        json.dumps({"from": person_a, "cli": split_body, "http": http_split}, indent=2) + "\n",
        encoding="utf-8",
    )


def prove_quality_gates(checks: Checks, artifacts: Path) -> None:
    from library.faces import (
        DEFAULT_MIN_SIDE_PX,
        INSIGHT_THRESHOLD,
        _nearest_person,
        detect_fixture,
        face_passes_stored_gates,
        passes_min_side,
    )
    from library.settings import DEFAULTS, KEY_ORDER
    from tests.qa.s08 import fresh_root

    checks.check("insight-threshold-family", abs(INSIGHT_THRESHOLD - 0.80) < 1e-9, str(INSIGHT_THRESHOLD))
    checks.check("min-side-default", DEFAULT_MIN_SIDE_PX >= 64, str(DEFAULT_MIN_SIDE_PX))
    checks.check(
        "settings-have-face-keys",
        "faceMatchThreshold" in KEY_ORDER and "faceMinSidePx" in KEY_ORDER,
        json.dumps(list(KEY_ORDER)),
    )
    checks.check(
        "settings-face-threshold",
        abs(float(DEFAULTS.get("faceMatchThreshold")) - 0.8) < 1e-9,
        json.dumps(DEFAULTS),
    )
    checks.check("settings-face-min-side", DEFAULTS.get("faceMinSidePx") == 80, json.dumps(DEFAULTS))
    from library.settings import fill_missing_defaults, validate_complete

    legacy = {key: DEFAULTS[key] for key in KEY_ORDER if key not in {"faceMatchThreshold", "faceMinSidePx"}}
    migrated = validate_complete(fill_missing_defaults(legacy))
    checks.check(
        "legacy-settings-migrate",
        abs(float(migrated.get("faceMatchThreshold")) - 0.8) < 1e-9 and migrated.get("faceMinSidePx") == 80,
        json.dumps(migrated),
    )
    prove_tile_detect(checks)
    prove_named_threshold(checks, artifacts)

    tiny = [0.01, 0.02, 20 / 640, 20 / 480]
    large = [0.125, 0.167, 140 / 640, 180 / 480]
    checks.check("reject-tiny-side", passes_min_side(tiny, 640, 480, 80) is False, str(tiny))
    checks.check("keep-large-side", passes_min_side(large, 640, 480, 80) is True, str(large))
    checks.check(
        "cleanup-drops-tiny",
        face_passes_stored_gates(
            {"personId": "person_x", "box": tiny},
            {"metadata": {"width": 640, "height": 480}},
            min_side_px=80,
            match_threshold=0.5,
            min_det=0.65,
        )
        is False,
        str(tiny),
    )
    checks.check(
        "cleanup-keeps-large",
        face_passes_stored_gates(
            {"personId": "person_x", "box": large, "detScore": 0.9, "matchScore": 0.72},
            {"metadata": {"width": 640, "height": 480}},
            min_side_px=80,
            match_threshold=0.5,
            min_det=0.65,
        )
        is True,
        str(large),
    )
    near_miss = _nearest_person([1.0, 0.0], {"person_a": [0.4, 0.916515]}, 0.5)
    checks.check("near-miss-unmatched", near_miss == (None, None), json.dumps(near_miss))
    solid = _nearest_person([1.0, 0.0], {"person_a": [1.0, 0.0]}, 0.5)
    checks.check("solid-match-assigned", solid[0] == "person_a" and solid[1] is not None and solid[1] > 0.5, json.dumps(solid))

    width, height = 640, 480
    buf = bytearray(width * height * 3)
    _fill(buf, width, 0, 0, width, height, BG)
    paint_face(buf, width, height, 40, 40, 24, 24, FACE_A)
    paint_face(buf, width, height, 200, 80, 140, 180, FACE_A)
    detected = detect_fixture(width, height, bytes(buf), min_side_px=80)
    checks.check("detect-skips-tiny", len(detected) == 1, json.dumps([face.get("box") for face in detected]))
    if detected:
        checks.check(
            "detect-kept-large",
            passes_min_side(detected[0]["box"], width, height, 80) is True,
            json.dumps(detected[0].get("box")),
        )

    css = Path("library/web/assets/style.css").read_text(encoding="utf-8")
    img_rule = css.split(".person-face img")[1].split("}")[0] if ".person-face img" in css else ""
    checks.check("css-face-img-cover", "object-fit: cover" in img_rule and "width:" in img_rule and "height:" in img_rule, img_rule)
    checks.check("css-picker-tile-large", ".person-face-choice" in css and "3.6rem" in css, "picker tile size")
    js = Path("library/web/assets/library.js").read_text(encoding="utf-8")
    checks.check("js-face-crop-url", "which=face&box=" in js, "dedicated face crop URL")
    checks.check("js-paint-cover", 'img.style.objectFit = "cover"' in js, "picker object-fit cover")
    checks.check("js-choice-stop", "stopPropagation" in js and "person-face-choice" in js, "picker isolation")
    checks.check("js-choice-pointerdown", "pointerdown" in js and "choosePersonThumb" in js, "picker pointerdown")
    html = Path("library/web/index.html").read_text(encoding="utf-8")
    checks.check("html-merge-dialog", 'id="confirm-merge"' in html and 'id="people-merge"' in html, "merge confirm")
    checks.check("html-split-info-crops", 'id="viewer-face-crops"' in html, "info face crops")
    checks.check("js-split-route", "/api/people/split" in js, "split HTTP")
    checks.check("js-photos-together", 'id="photos-together"' in js or "photos-together" in js, "photos together")
    i18n = Path("library/web/assets/i18n.js").read_text(encoding="utf-8")
    checks.check(
        "i18n-split-merge-together",
        "notThisPerson" in i18n and "mergeInto" in i18n and "photosTogether" in i18n and "不是这个人" in i18n and "共同的照片" in i18n,
        "zh split/merge/together",
    )
    checks.check(
        "html-threshold-slider",
        'id="set-faceMatchThreshold"' in html
        and 'type="range"' in html
        and 'min="0.35"' in html
        and 'max="0.95"' in html
        and 'id="settings-faces-rerun"' in html,
        "settings slider + rerun note",
    )
    faces_src = Path("library/faces.py").read_text(encoding="utf-8")
    checks.check(
        "step-skips-already-when-force",
        "if item_id in already:" in faces_src and "if not force and item_id in already" not in faces_src,
        "skip already-scanned during force rescan",
    )
    checks.check("step-marks-failed-scanned", "_mark_faces_scanned" in faces_src, "failed item advances")

    quality_root = fresh_root(artifacts / "quality-root")
    media = artifacts / "quality-media"
    if media.exists():
        shutil.rmtree(media)
    media.mkdir(parents=True)
    write_png(media / "mixed.png", width, height, bytes(buf))
    setup = run_library(quality_root, ["setup-ml", "faces", "--backend", "fixture"], env=test_env())
    checks.check("quality-setup", setup.returncode == 0, setup.stderr)
    scan = run_library(quality_root, ["scan", str(media), "--serve-from-there"], env=test_env(), timeout=120)
    checks.check("quality-scan", scan.returncode == 0, scan.stderr)
    infer = run_library(quality_root, ["infer-faces"], env=test_env(), timeout=120)
    checks.check("quality-infer", infer.returncode == 0, infer.stderr)
    infer_body = parse_json(infer.stdout) if infer.returncode == 0 else {}
    checks.check("quality-one-face", infer_body.get("faces") == 1, infer.stdout)
    items = load_items(quality_root)
    mixed = item_by_name(items, "mixed.png") or {}
    faces = mixed.get("faces") or []
    checks.check("quality-item-one-face", len(faces) == 1, json.dumps(faces))
    if faces:
        checks.check(
            "quality-item-large-box",
            passes_min_side(faces[0].get("box") or [], 640, 480, 80) is True,
            json.dumps(faces[0]),
        )
        checks.check("quality-has-scores", "detScore" in faces[0] or "matchScore" in faces[0], json.dumps(faces[0]))

    planted = clone_item_with_tiny_face(quality_root, mixed)
    checks.check("quality-planted-tiny", planted is True, "plant tiny face")
    cleanup = run_library(quality_root, ["infer-faces", "--cleanup"], env=test_env(), timeout=60)
    checks.check("quality-cleanup-exit", cleanup.returncode == 0, cleanup.stderr)
    cleaned = item_by_name(load_items(quality_root), "mixed.png") or {}
    cleaned_faces = cleaned.get("faces") or []
    checks.check("quality-cleanup-dropped-tiny", len(cleaned_faces) == 1, json.dumps(cleaned_faces))
    named = run_library(
        quality_root,
        ["annotate", mixed.get("id") or "", "--person", "Ada"],
        env=test_env(),
    )
    checks.check("quality-name-ada", named.returncode == 0, named.stderr)
    people_before = load_people(quality_root)
    named_ids = {rec["id"] for rec in people_before if rec.get("name") == "Ada"}
    force = run_library(quality_root, ["infer-faces", "--force"], env=test_env(), timeout=120)
    checks.check("quality-force-exit", force.returncode == 0, force.stderr)
    people_after = load_people(quality_root)
    named_after = {rec["id"] for rec in people_after if rec.get("name") == "Ada"}
    checks.check("quality-force-keeps-ada", named_ids <= named_after and bool(named_ids), json.dumps(people_after))
    prove_face_crop(checks, artifacts)


def prove_tile_detect(checks: Checks) -> None:
    from library.faces import TILE_SRC, TILE_TRIGGER, detect_px_on_canvas, iter_detect_windows

    phone_w, phone_h = 4032, 3024
    face_side = 200.0
    full = detect_px_on_canvas(face_side, phone_w, phone_h)
    tiled = detect_px_on_canvas(face_side, phone_w, phone_h, TILE_SRC, TILE_SRC)
    checks.check(
        "tile-full-frame-crushes-small-face",
        full < 40,
        json.dumps({"full": full, "face": face_side, "canvas": [phone_w, phone_h]}),
    )
    checks.check(
        "tile-1280-window-keeps-face-usable",
        tiled >= 80 and tiled > full * 2,
        json.dumps({"tiled": tiled, "full": full, "tile": TILE_SRC}),
    )
    small = iter_detect_windows(800, 600)
    checks.check("tile-skips-small-stills", small == [(0, 0, 800, 600)], json.dumps(small))
    windows = iter_detect_windows(phone_w, phone_h)
    extras = [win for win in windows if win != (0, 0, phone_w, phone_h)]
    checks.check("tile-keeps-full-frame-first", windows[0] == (0, 0, phone_w, phone_h), json.dumps(windows[:2]))
    checks.check("tile-adds-overlapping-windows", len(extras) >= 1, json.dumps({"count": len(windows), "extras": extras[:4]}))
    checks.check("tile-trigger-is-large", TILE_TRIGGER >= 1600, str(TILE_TRIGGER))
    faces_src = Path("library/faces.py").read_text(encoding="utf-8")
    checks.check(
        "tile-used-by-detect",
        "for window in iter_detect_windows" in faces_src and "def detect_insightface" in faces_src,
        "detect_insightface walks tiles then original 112 embed",
    )
    checks.check(
        "tile-aligns-from-original",
        "_affine_112" in faces_src and "_crop_112" in faces_src and "letterbox_size" in faces_src,
        "112 crop still from original pixels",
    )


def prove_face_crop(checks: Checks, artifacts: Path) -> None:
    from library.errors import AppError
    from library.face_crop import parse_face_box, square_crop_px, write_face_crop

    dest_dir = artifacts / "face-crop"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    width, height = 200, 160
    buf = bytearray(width * height * 3)
    _fill(buf, width, 0, 0, width, height, BG)
    paint_face(buf, width, height, 20, 20, 80, 100, FACE_A)
    src = dest_dir / "face.png"
    write_png(src, width, height, bytes(buf))
    box = parse_face_box("0.10,0.125,0.40,0.625")
    dest = dest_dir / "crop.webp"
    ok = write_face_crop(src, dest, box)
    checks.check("face-crop-writes-webp", ok is True and dest.is_file() and dest.stat().st_size > 0, str(dest))
    x, y, side, same = square_crop_px(box, width, height)
    checks.check("face-crop-square", side == same and side >= 2, json.dumps([x, y, side, same]))
    invalid = None
    try:
        parse_face_box("1,2")
    except AppError as exc:
        invalid = exc.code
    checks.check("face-crop-box-invalid", invalid == "invalid-argument", str(invalid))


def prove_named_threshold(checks: Checks, artifacts: Path) -> None:
    from library.faces import NAMED_WEAK_BUMP, named_assignment_threshold

    base = 0.80
    strong = named_assignment_threshold(base, {"shortSidePx": 200, "detScore": 0.90})
    small = named_assignment_threshold(base, {"shortSidePx": 90, "detScore": 0.90})
    weak = named_assignment_threshold(base, {"shortSidePx": 200, "detScore": 0.70})
    checks.check("named-strong-keeps-base", abs(strong - base) < 1e-9, str(strong))
    checks.check("named-small-raises", abs(small - (base + NAMED_WEAK_BUMP)) < 1e-9, str(small))
    checks.check("named-weak-det-raises", abs(weak - (base + NAMED_WEAK_BUMP)) < 1e-9, str(weak))
    from library.faces import _nearest_person, cluster_detections
    from library.atomic import atomic_write_json
    from library.records import ordered_person
    from tests.qa.s08 import fresh_root

    root = fresh_root(artifacts / "named-threshold-root")
    people_dir = root / "catalog" / "people"
    people_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        people_dir / "person_namedada12.json",
        ordered_person({"schemaVersion": 1, "id": "person_namedada12", "name": "Ada"}),
    )
    index = {
        "schemaVersion": 1,
        "backend": "fixture",
        "matchThreshold": 0.80,
        "people": {
            "person_namedada12": {"centroid": [1.0, 0.0], "faces": []},
        },
    }
    weak_det = {
        "itemId": "item_weak",
        "box": [0.1, 0.1, 0.05, 0.05],
        "embedding": [0.86, 0.5107],
        "detScore": 0.70,
        "shortSidePx": 90,
    }
    assigned, _, created, reused = cluster_detections(root, [weak_det], index)
    checks.check(
        "named-weak-not-merged",
        created == 1 and reused == 0 and assigned and assigned[0]["personId"] != "person_namedada12",
        json.dumps({"created": created, "reused": reused, "assigned": assigned}),
    )
    strong_det = {
        "itemId": "item_strong",
        "box": [0.2, 0.2, 0.2, 0.25],
        "embedding": [1.0, 0.0],
        "detScore": 0.92,
        "shortSidePx": 220,
    }
    assigned_s, _, created_s, reused_s = cluster_detections(root, [strong_det], index)
    checks.check(
        "named-strong-reused",
        created_s == 0 and reused_s == 1 and assigned_s and assigned_s[0]["personId"] == "person_namedada12",
        json.dumps({"created": created_s, "reused": reused_s, "assigned": assigned_s}),
    )
    near = _nearest_person([0.86, 0.5107], {"person_namedada12": [1.0, 0.0]}, 0.80)
    checks.check("named-near-above-base", near[0] == "person_namedada12" and near[1] is not None and near[1] > 0.80, json.dumps(near))


def clone_item_with_tiny_face(root: Path, item: dict[str, Any]) -> bool:
    if not item or not item.get("id"):
        return False
    path = root / "catalog" / "items" / (item["id"] + ".json")
    if not path.is_file():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    faces = list(data.get("faces") or [])
    if not faces:
        return False
    tiny = dict(faces[0])
    tiny["box"] = [0.01, 0.02, 20 / 640, 20 / 480]
    tiny.pop("detScore", None)
    tiny.pop("matchScore", None)
    faces.append(tiny)
    data["faces"] = faces
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True
