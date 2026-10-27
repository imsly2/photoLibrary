"""Optional local face inference. Never uploads. Never guesses a name."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from library.annotate import collapse_faces
from library.atomic import load_json, transact
from library.catalog_io import (
    item_rel,
    iter_item_ids,
    load_item,
    new_person_id,
    person_rel,
    try_load_person,
)
from library.errors import AppError, fail
from library.history import make_history_entry, plan_append
from library.media import decode_still_rgb
from library.paths import library_path, root_text
from library.records import clone, ordered_item, ordered_person, pack_embedding, unpack_embedding
from library.volumes import location_file, location_matches_stat

MODELS_REL = "models/faces"
MANIFEST_REL = "models/faces/manifest.json"
INDEX_REL = "models/faces/index.json"
BUFFALO_REL = "models/faces/buffalo_s"
BUFFALO_ZIP_URL = (
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_s.zip"
)
DET_NAME = "det_500m.onnx"
REC_NAME = "w600k_mbf.onnx"
REMOVED_ONNX = (
    "genderage.onnx",
    "1k3d68.onnx",
    "2d106det.onnx",
)
BEACON = (255, 0, 170)
FIXTURE_THRESHOLD = 0.85
# buffalo_s ArcFace cosine. Match only when score is strictly above this.
# Measured on family photos: same person ~0.3-0.7, different people ~0.
# Fixture clustering stays on FIXTURE_THRESHOLD.
INSIGHT_THRESHOLD = 0.45
INSIGHT_DET_MIN = 0.65
DEFAULT_MIN_SIDE_PX = 80
NAMED_WEAK_SIDE_PX = 120
NAMED_WEAK_DET = 0.75
NAMED_WEAK_BUMP = 0.08
DET_INPUT = 640
TILE_SRC = 1280
TILE_OVERLAP = 320
TILE_TRIGGER = 1600
TILE_MAX = 12
BACKEND_INSIGHT = "insightface-buffalo_s"
BACKEND_FIXTURE = "fixture"

_ARCFACE_DST = (
    (38.2946, 51.6963),
    (73.5318, 51.5014),
    (56.0252, 71.7366),
    (41.5493, 92.3655),
    (70.7299, 92.2041),
)


def models_dir(root: Path) -> Path:
    return library_path(root, MODELS_REL)


def manifest_path(root: Path) -> Path:
    return library_path(root, MANIFEST_REL)


def index_path(root: Path) -> Path:
    return library_path(root, INDEX_REL)


def buffalo_dir(root: Path) -> Path:
    return library_path(root, BUFFALO_REL)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _test_mode() -> bool:
    return os.environ.get("LIBRARY_TEST") == "1"


def read_setup_payload(value: Any) -> dict[str, str]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    extra = set(value.keys()) - {"backend"}
    if extra:
        raise fail("invalid-argument")
    backend = value.get("backend")
    if backend is None:
        return {"backend": BACKEND_INSIGHT}
    if backend == BACKEND_FIXTURE:
        if not _test_mode():
            raise fail("invalid-argument")
        return {"backend": BACKEND_FIXTURE}
    if backend in {BACKEND_INSIGHT, "insightface", "faces"}:
        return {"backend": BACKEND_INSIGHT}
    raise fail("invalid-argument")


def read_infer_payload(value: Any) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    extra = set(value.keys()) - {"force", "itemIds", "cleanup"}
    if extra:
        raise fail("invalid-argument")
    force = value.get("force", False)
    if type(force) is not bool:
        raise fail("invalid-argument")
    cleanup = value.get("cleanup", False)
    if type(cleanup) is not bool:
        raise fail("invalid-argument")
    item_ids = value.get("itemIds")
    if item_ids is None:
        return {"force": force, "cleanup": cleanup, "itemIds": None}
    if not isinstance(item_ids, list) or not item_ids:
        raise fail("invalid-argument")
    out: list[str] = []
    for item_id in item_ids:
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        out.append(item_id)
    return {"force": force, "cleanup": cleanup, "itemIds": out}


def _empty_index(backend: str, threshold: float) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "backend": backend,
        "matchThreshold": threshold,
        "people": {},
    }


def load_manifest(root: Path) -> dict[str, Any] | None:
    path = manifest_path(root)
    if not path.is_file():
        return None
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        return None
    return data


def load_index(root: Path) -> dict[str, Any] | None:
    path = index_path(root)
    if not path.is_file():
        return None
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise fail("invalid-catalog") from exc
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise fail("invalid-catalog")
    return data


_index_cache: dict[str, tuple[tuple[int, int], dict[str, Any] | None]] = {}


def _index_readonly(root: Path) -> dict[str, Any] | None:
    """load_index for callers that only read: parsed again only when the file
    changes. The index holds every embedding, so each idle tick re-parsing it
    three times added up. Never mutate the returned dict."""
    path = index_path(root)
    try:
        st = path.stat()
    except OSError:
        return None
    sig = (int(st.st_mtime_ns), int(st.st_size))
    hit = _index_cache.get(str(path))
    if hit is not None and hit[0] == sig:
        return hit[1]
    data = load_index(root)
    _index_cache[str(path)] = (sig, data)
    return data


FACE_INDEX_OPERATIONS = frozenset({"faces-infer", "faces-cleanup", "people-merge", "people-split"})
_mirror_pending: set[str] = set()


def write_index(root: Path, index: dict[str, Any], *, mirror: bool = True) -> None:
    """Publish the face index: a cache of item faces, never an undo step.

    ``mirror=False`` (one photo at a time in the drain) holds the portable
    ``faces.json`` copy until ``settle_index_mirror``.
    """
    from library.atomic import atomic_write_json

    atomic_write_json(index_path(root), index)
    _mirror_pending.add(root_text(root))
    if mirror:
        settle_index_mirror(root)


def settle_index_mirror(root: Path) -> None:
    key = root_text(root)
    if key not in _mirror_pending:
        return
    _mirror_pending.discard(key)
    try:
        from library.portable import mirror_face_index

        mirror_face_index(root)
    except Exception:
        pass


def _index_from_items(
    root: Path,
    index: dict[str, Any],
    overrides: dict[str, list[dict[str, Any]]] | None = None,
    *,
    keep_unbacked: bool = True,
) -> dict[str, Any]:
    """Face lists and centroids recomputed from item faces.

    A centroid is the mean of that person's stored fingerprints; a person
    whose faces carry none keeps its prior centroid unless ``keep_unbacked``
    is false (Re-run Faces: such a centroid predates stored fingerprints
    and cannot be checked). People with no faces stay only while their
    person file exists.
    """
    previous = index.get("people") or {}
    refs: dict[str, list[dict[str, Any]]] = {}
    vectors: dict[str, list[list[float]]] = {}
    overrides = overrides or {}
    for item_id in iter_item_ids(root):
        faces = overrides[item_id] if item_id in overrides else load_item(root, item_id).get("faces") or []
        for face in faces:
            person_id = face.get("personId")
            if type(person_id) is not str or not person_id:
                continue
            ref = {"itemId": item_id, "box": face.get("box")}
            bucket = refs.setdefault(person_id, [])
            if ref not in bucket:
                bucket.append(ref)
            vec = unpack_embedding(face.get("embedding"))
            if vec is not None:
                vectors.setdefault(person_id, []).append(vec)
    people: dict[str, Any] = {}
    for person_id in sorted(set(previous) | set(refs)):
        if person_id not in refs and try_load_person(root, person_id) is None:
            continue
        old = previous.get(person_id) if isinstance(previous.get(person_id), dict) else {}
        if person_id in vectors:
            centroid = _centroid(vectors[person_id])
        else:
            centroid = list(old.get("centroid") or []) if keep_unbacked else []
        people[person_id] = {"centroid": centroid, "faces": refs.get(person_id, [])}
    out = dict(index)
    out["people"] = people
    return out


def rebuild_index(root: Path) -> None:
    """Re-derive the index after undo/redo of a face operation."""
    current = load_index(root)
    if current is None:
        return
    after = _index_from_items(root, current)
    if after != current:
        write_index(root, after)


def faces_status(root: Path) -> dict[str, Any]:
    manifest = load_manifest(root)
    if manifest is None:
        return {
            "ok": True,
            "ready": False,
            "backend": None,
            "modelsDir": MODELS_REL,
        }
    backend = manifest.get("backend")
    ready = False
    if backend == BACKEND_FIXTURE:
        ready = True
    elif backend == BACKEND_INSIGHT:
        ready = (buffalo_dir(root) / DET_NAME).is_file() and (
            buffalo_dir(root) / REC_NAME
        ).is_file()
    return {
        "ok": True,
        "ready": ready,
        "backend": backend,
        "modelsDir": MODELS_REL,
    }


def _require_models(root: Path) -> dict[str, Any]:
    status = faces_status(root)
    if not status["ready"]:
        raise fail("models-missing")
    return status


def _ensure_ml_deps() -> None:
    try:
        import numpy  # noqa: F401
    except ImportError as exc:
        raise fail("dependency-missing") from exc
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "onnxruntime"],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise fail("dependency-missing")
        import importlib
        import site

        importlib.invalidate_caches()
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.append(user_site)
        try:
            import onnxruntime  # noqa: F401
        except ImportError as exc:
            raise fail("dependency-missing") from exc


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as resp:  # noqa: S310 — fixed InsightFace release URL
        data = resp.read()
    dest.write_bytes(data)


def setup_insightface(root: Path) -> dict[str, Any]:
    _ensure_ml_deps()
    folder = buffalo_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    det = folder / DET_NAME
    rec = folder / REC_NAME
    if not (det.is_file() and rec.is_file()):
        with tempfile.TemporaryDirectory(prefix="library-faces-") as tmp:
            zpath = Path(tmp) / "buffalo_s.zip"
            try:
                _download(BUFFALO_ZIP_URL, zpath)
            except OSError as exc:
                raise fail("io-error") from exc
            try:
                with zipfile.ZipFile(zpath) as zf:
                    zf.extractall(Path(tmp) / "unpacked")
            except zipfile.BadZipFile as exc:
                raise fail("io-error") from exc
            unpacked = Path(tmp) / "unpacked"
            sources = list(unpacked.rglob("*.onnx"))
            if not sources:
                raise fail("io-error")
            for src in sources:
                if src.name in REMOVED_ONNX:
                    continue
                target = folder / src.name
                shutil.copy2(src, target)
    for extra in REMOVED_ONNX:
        junk = folder / extra
        if junk.is_file():
            junk.unlink()
    if not det.is_file() or not rec.is_file():
        raise fail("io-error")
    files = sorted(
        path.relative_to(models_dir(root)).as_posix()
        for path in folder.glob("*.onnx")
        if path.is_file()
    )
    manifest = {
        "schemaVersion": 1,
        "backend": BACKEND_INSIGHT,
        "matchThreshold": INSIGHT_THRESHOLD,
        "installedAt": _utc_now(),
        "files": files,
    }
    from library.atomic import atomic_write_json

    atomic_write_json(manifest_path(root), manifest)
    if not index_path(root).is_file():
        atomic_write_json(index_path(root), _empty_index(BACKEND_INSIGHT, INSIGHT_THRESHOLD))
    return faces_status(root)


def setup_fixture(root: Path) -> dict[str, Any]:
    if not _test_mode():
        raise fail("invalid-argument")
    models_dir(root).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": 1,
        "backend": BACKEND_FIXTURE,
        "matchThreshold": FIXTURE_THRESHOLD,
        "installedAt": _utc_now(),
        "files": [],
    }
    from library.atomic import atomic_write_json

    atomic_write_json(manifest_path(root), manifest)
    if not index_path(root).is_file():
        atomic_write_json(index_path(root), _empty_index(BACKEND_FIXTURE, FIXTURE_THRESHOLD))
    return faces_status(root)


def setup_faces(root: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = read_setup_payload(payload)
    if parsed["backend"] == BACKEND_FIXTURE:
        return setup_fixture(root)
    return setup_insightface(root)


def _still_path(item: dict[str, Any], root: Path) -> Path | None:
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == "still"
    ]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or "",
        )
    )
    for loc in candidates:
        path = location_file(loc, root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return path
    return None


def _is_beacon(r: int, g: int, b: int) -> bool:
    return r >= 240 and g <= 25 and 150 <= b <= 190


def _is_white(r: int, g: int, b: int) -> bool:
    return r >= 240 and g >= 240 and b >= 240


def _flood_boxes(width: int, height: int, rgb: bytes) -> list[tuple[int, int, int, int]]:
    visited = bytearray(width * height)
    boxes: list[tuple[int, int, int, int]] = []
    for y in range(height):
        row = y * width
        for x in range(width):
            i = row + x
            if visited[i]:
                continue
            p = i * 3
            if not _is_beacon(rgb[p], rgb[p + 1], rgb[p + 2]):
                continue
            stack = [(x, y)]
            visited[i] = 1
            minx = maxx = x
            miny = maxy = y
            while stack:
                cx, cy = stack.pop()
                if cx < minx:
                    minx = cx
                if cx > maxx:
                    maxx = cx
                if cy < miny:
                    miny = cy
                if cy > maxy:
                    maxy = cy
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    ni = ny * width + nx
                    if visited[ni]:
                        continue
                    npx = ni * 3
                    if not _is_beacon(rgb[npx], rgb[npx + 1], rgb[npx + 2]):
                        continue
                    visited[ni] = 1
                    stack.append((nx, ny))
            if (maxx - minx + 1) >= 16 and (maxy - miny + 1) >= 16:
                boxes.append((minx, miny, maxx - minx + 1, maxy - miny + 1))
    boxes.sort()
    return boxes


def _identity_embedding(
    width: int, height: int, rgb: bytes, box: tuple[int, int, int, int]
) -> list[float]:
    x, y, w, h = box
    inset = max(2, min(w, h) // 8)
    x0 = min(width - 1, x + inset)
    y0 = min(height - 1, y + inset)
    x1 = max(x0 + 1, min(width, x + w - inset))
    y1 = max(y0 + 1, min(height, y + h - inset))
    total = [0, 0, 0]
    count = 0
    for py in range(y0, y1):
        for px in range(x0, x1):
            p = (py * width + px) * 3
            r, g, b = rgb[p], rgb[p + 1], rgb[p + 2]
            if _is_beacon(r, g, b) or _is_white(r, g, b):
                continue
            total[0] += r
            total[1] += g
            total[2] += b
            count += 1
    if count == 0:
        return l2_normalize([0.01, 0.01, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0])
    r = total[0] / count / 255.0
    g = total[1] / count / 255.0
    b = total[2] / count / 255.0
    return l2_normalize([r, g, b, r - g, g - b, b - r, r * r, g * g])


def box_short_side_px(box: list[float], width: int, height: int) -> float:
    if width <= 0 or height <= 0 or len(box) != 4:
        return 0.0
    return min(float(box[2]) * float(width), float(box[3]) * float(height))


def passes_min_side(box: list[float], width: int, height: int, min_side_px: int) -> bool:
    return box_short_side_px(box, width, height) + 1e-9 >= float(min_side_px)


def passes_det_score(score: float | None, min_det: float) -> bool:
    if score is None:
        return True
    return float(score) >= float(min_det)


def face_quality_settings(root: Path, backend: str) -> dict[str, Any]:
    threshold = FIXTURE_THRESHOLD if backend == BACKEND_FIXTURE else INSIGHT_THRESHOLD
    min_side = DEFAULT_MIN_SIDE_PX
    min_det = INSIGHT_DET_MIN
    try:
        from library.settings import defaults, load_settings_file, settings_path

        settings = load_settings_file(root) if settings_path(root).exists() else defaults()
        if backend != BACKEND_FIXTURE:
            threshold = float(settings["faceMatchThreshold"])
        min_side = int(settings["faceMinSidePx"])
    except Exception:
        pass
    return {
        "matchThreshold": threshold,
        "minSidePx": min_side,
        "minDetScore": min_det,
    }


def detect_fixture(
    width: int,
    height: int,
    rgb: bytes,
    *,
    min_side_px: int = 0,
) -> list[dict[str, Any]]:
    faces: list[dict[str, Any]] = []
    for x, y, w, h in _flood_boxes(width, height, rgb):
        box = [
            x / width,
            y / height,
            w / width,
            h / height,
        ]
        if not passes_min_side(box, width, height, min_side_px):
            continue
        faces.append(
            {
                "box": box,
                "embedding": _identity_embedding(width, height, rgb, (x, y, w, h)),
                "detScore": 1.0,
                "shortSidePx": box_short_side_px(box, width, height),
            }
        )
    faces.sort(key=lambda face: (face["box"][0], face["box"][1]))
    return faces


def l2_normalize(vec: list[float]) -> list[float]:
    total = math.sqrt(sum(float(x) * float(x) for x in vec)) or 1.0
    return [float(x) / total for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    return sum(float(a[i]) * float(b[i]) for i in range(n))


def _clamp_box(box: list[float]) -> list[float]:
    x, y, w, h = (float(v) for v in box)
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    w = min(max(w, 0.0), 1.0 - x)
    h = min(max(h, 0.0), 1.0 - y)
    if w <= 0 or h <= 0:
        raise fail("internal-error")
    return [x, y, w, h]


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise fail("dependency-missing") from exc
    return np


def _ort():
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise fail("dependency-missing") from exc
    return ort


def _similarity_matrix(src: Any, dst: Any) -> Any:
    np = _numpy()
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    src_mean = src.mean(axis=0)
    dst_mean = dst.mean(axis=0)
    src_c = src - src_mean
    dst_c = dst - dst_mean
    src_norm = np.sqrt((src_c**2).sum() / src.shape[0]) or 1.0
    dst_norm = np.sqrt((dst_c**2).sum() / dst.shape[0]) or 1.0
    src_n = src_c / src_norm
    dst_n = dst_c / dst_norm
    u, _, vt = np.linalg.svd(src_n.T @ dst_n)
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    scale = dst_norm / src_norm
    t = dst_mean - scale * (r @ src_mean)
    mat = np.zeros((2, 3), dtype=np.float64)
    mat[:, :2] = r * scale
    mat[:, 2] = t
    return mat


def _affine_112(image: Any, kps: Any) -> Any:
    np = _numpy()
    # Map each template pixel back onto the photo. The previous matrix ran
    # the other way, so every face was sampled from the top-left corner.
    template = np.asarray(_ARCFACE_DST, dtype=np.float64)
    mat = _similarity_matrix(template, np.asarray(kps, dtype=np.float64).reshape(5, 2))
    h, w = image.shape[:2]
    out = np.zeros((112, 112, 3), dtype=np.uint8)
    ys, xs = np.meshgrid(np.arange(112), np.arange(112), indexing="ij")
    src_x = mat[0, 0] * xs + mat[0, 1] * ys + mat[0, 2]
    src_y = mat[1, 0] * xs + mat[1, 1] * ys + mat[1, 2]
    src_x = np.clip(np.rint(src_x).astype(np.int32), 0, w - 1)
    src_y = np.clip(np.rint(src_y).astype(np.int32), 0, h - 1)
    out[:, :] = image[src_y, src_x]
    return out


def _crop_112(image: Any, box: list[float]) -> Any:
    np = _numpy()
    h, w = image.shape[:2]
    x, y, bw, bh = box
    pad = 0.15
    x0 = max(0, int((x - pad * bw) * w))
    y0 = max(0, int((y - pad * bh) * h))
    x1 = min(w, int((x + bw + pad * bw) * w))
    y1 = min(h, int((y + bh + pad * bh) * h))
    if x1 <= x0 or y1 <= y0:
        x0, y0, x1, y1 = 0, 0, w, h
    crop = image[y0:y1, x0:x1]
    ys = (np.linspace(0, crop.shape[0] - 1, 112)).astype(np.int32)
    xs = (np.linspace(0, crop.shape[1] - 1, 112)).astype(np.int32)
    return crop[ys][:, xs]


NMS_CONTAIN = 0.6


def _nms(dets: Any, thresh: float) -> Any:
    """Keep the best box per face. A tile edge can cut a face into a smaller
    box that sits inside the full one; that is the same face, not a second."""
    np = _numpy()
    if len(dets) == 0:
        return dets
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        contain = inter / np.minimum(areas[i], areas[order[1:]])
        order = order[np.where((ovr <= thresh) & (contain <= NMS_CONTAIN))[0] + 1]
    return dets[keep]


def _distance2bbox(points: Any, distance: Any) -> Any:
    np = _numpy()
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points: Any, distance: Any) -> Any:
    np = _numpy()
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


_insight_cache: dict[tuple, tuple[Any, Any]] = {}


def _insight_sessions(root: Path, ort: Any) -> tuple[Any, Any]:
    """Detector and recognizer sessions, created once per model file version.
    Building both per photo cost 0.44 s each and churned memory."""
    det_path = buffalo_dir(root) / DET_NAME
    rec_path = buffalo_dir(root) / REC_NAME
    if not det_path.is_file() or not rec_path.is_file():
        raise fail("models-missing")
    key = tuple(
        (str(path), int(st.st_size), int(st.st_mtime_ns))
        for path, st in ((det_path, det_path.stat()), (rec_path, rec_path.stat()))
    )
    hit = _insight_cache.get(key)
    if hit is not None:
        return hit
    sess_opts = ort.SessionOptions()
    sess_opts.inter_op_num_threads = 1
    # Inference runs with the server lock released, so it may use half the
    # cores; the other half stay free for requests and the encoders.
    sess_opts.intra_op_num_threads = max(1, (os.cpu_count() or 2) // 2)
    det = ort.InferenceSession(str(det_path), sess_opts, providers=["CPUExecutionProvider"])
    rec = ort.InferenceSession(str(rec_path), sess_opts, providers=["CPUExecutionProvider"])
    _insight_cache.clear()
    _insight_cache[key] = (det, rec)
    return det, rec


def align_portrait(image: Any, landmarks_xy: Any, size: int = 640) -> Any:
    """Pin five photo landmarks to a scaled ArcFace template on a square canvas.

    ``landmarks_xy`` are pixel coordinates on ``image``. The eyes land in the
    same place on every frame.
    """
    np = _numpy()
    template = np.asarray(_ARCFACE_DST, dtype=np.float64)
    scale = (float(size) * 0.62) / 112.0
    offset = (float(size) - 112.0 * scale) / 2.0
    dst = template * scale + offset
    mat = _similarity_matrix(dst, np.asarray(landmarks_xy, dtype=np.float64).reshape((5, 2)))
    h, w = image.shape[:2]
    out = np.zeros((size, size, 3), dtype=np.uint8)
    ys, xs = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    src_x = mat[0, 0] * xs + mat[0, 1] * ys + mat[0, 2]
    src_y = mat[1, 0] * xs + mat[1, 1] * ys + mat[1, 2]
    src_x = np.clip(np.rint(src_x).astype(np.int32), 0, max(0, w - 1))
    src_y = np.clip(np.rint(src_y).astype(np.int32), 0, max(0, h - 1))
    out[:, :] = image[src_y, src_x]
    return out


# Encoder threads and the face drain can both reach InsightFace. One session
# is not safe to run from two threads.
_DETECT_LOCK = threading.Lock()


def detect_insightface(
    root: Path,
    width: int,
    height: int,
    rgb: bytes,
    *,
    min_side_px: int = DEFAULT_MIN_SIDE_PX,
    min_det: float = INSIGHT_DET_MIN,
    landmarks_only: bool = False,
) -> list[dict[str, Any]]:
    with _DETECT_LOCK:
        return _detect_insightface(
            root,
            width,
            height,
            rgb,
            min_side_px=min_side_px,
            min_det=min_det,
            landmarks_only=landmarks_only,
        )


def detect_shared_frame(root: Path, width: int, height: int, rgb: bytes) -> list[dict[str, Any]]:
    """Faces for an upright frame already decoded beside a thumb or preview."""
    status = faces_status(root)
    quality = face_quality_settings(root, str(status.get("backend") or ""))
    return detect_insightface(
        root,
        width,
        height,
        rgb,
        min_side_px=int(quality["minSidePx"]),
        min_det=float(quality["minDetScore"]),
    )


def _detect_insightface(
    root: Path,
    width: int,
    height: int,
    rgb: bytes,
    *,
    min_side_px: int = DEFAULT_MIN_SIDE_PX,
    min_det: float = INSIGHT_DET_MIN,
    landmarks_only: bool = False,
) -> list[dict[str, Any]]:
    np = _numpy()
    ort = _ort()
    image = np.frombuffer(rgb, dtype=np.uint8).reshape((height, width, 3))
    det, rec = _insight_sessions(root, ort)
    input_size = (DET_INPUT, DET_INPUT)
    input_name = det.get_inputs()[0].name
    center_cache: dict[tuple[int, int, int], Any] = {}

    def run_window(x0: int, y0: int, x1: int, y1: int) -> tuple[Any, Any] | tuple[None, None]:
        crop = image[y0:y1, x0:x1]
        ch, cw = crop.shape[:2]
        if ch < 8 or cw < 8:
            return None, None
        new_width, new_height, det_scale = letterbox_size(cw, ch, input_size)
        resized = _resize_rgb(crop, new_width, new_height)
        blob = np.zeros((1, 3, input_size[1], input_size[0]), dtype=np.float32)
        blob[0, 0, :new_height, :new_width] = (resized[:, :, 2] - 127.5) / 128.0
        blob[0, 1, :new_height, :new_width] = (resized[:, :, 1] - 127.5) / 128.0
        blob[0, 2, :new_height, :new_width] = (resized[:, :, 0] - 127.5) / 128.0
        net_outs = det.run(None, {input_name: blob})
        scores_list = []
        bboxes_list = []
        kps_list = []
        fmc = 3
        feat_strides = [8, 16, 32]
        num_anchors = 2
        use_kps = len(net_outs) == 9
        for idx, stride in enumerate(feat_strides):
            scores = net_outs[idx]
            bbox_preds = net_outs[idx + fmc] * stride
            if use_kps:
                kps_preds = net_outs[idx + fmc * 2] * stride
            height_s = input_size[1] // stride
            width_s = input_size[0] // stride
            key = (height_s, width_s, stride)
            if key in center_cache:
                anchor_centers = center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:height_s, :width_s][::-1], axis=-1).astype(
                    np.float32
                )
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * num_anchors, axis=1).reshape((-1, 2))
                center_cache[key] = anchor_centers
            pos_inds = np.where(scores.ravel() >= min_det)[0]
            bboxes = _distance2bbox(anchor_centers, bbox_preds.reshape((-1, 4)))
            scores_list.append(scores.ravel()[pos_inds])
            bboxes_list.append(bboxes[pos_inds])
            if use_kps:
                kps_list.append(_distance2kps(anchor_centers, kps_preds.reshape((-1, 10)))[pos_inds])
        if not scores_list:
            return None, None
        scores_cat = np.concatenate(scores_list, axis=0)
        if scores_cat.size == 0:
            return None, None
        pre = np.hstack([np.concatenate(bboxes_list, axis=0), scores_cat[:, None]])
        pre[:, :4] /= det_scale
        pre[:, 0] += x0
        pre[:, 1] += y0
        pre[:, 2] += x0
        pre[:, 3] += y0
        kps = None
        if use_kps and kps_list:
            kps = np.concatenate(kps_list, axis=0) / det_scale
            kps[:, 0::2] += x0
            kps[:, 1::2] += y0
        return pre, kps

    rows = []
    kps_rows = []
    for window in iter_detect_windows(width, height):
        pre, kps = run_window(*window)
        if pre is None:
            continue
        rows.append(pre)
        kps_rows.append(kps)
    if not rows:
        return []
    pre = np.concatenate(rows, axis=0)
    keep = _nms(pre, 0.4)
    all_kps = None
    if any(kps is not None for kps in kps_rows):
        parts = []
        for pre_part, kps in zip(rows, kps_rows):
            if kps is None:
                parts.append(np.zeros((len(pre_part), 10), dtype=np.float32))
            else:
                parts.append(kps)
        all_kps = np.concatenate(parts, axis=0)
    kept_kps = []
    for det_row in keep:
        if all_kps is None or len(all_kps) == 0:
            kept_kps.append(None)
            continue
        dists = np.abs(pre[:, 0] - det_row[0]) + np.abs(pre[:, 1] - det_row[1])
        kept_kps.append(all_kps[int(np.argmin(dists))])
    rec_input = rec.get_inputs()[0].name
    faces: list[dict[str, Any]] = []
    for det_row, kps in zip(keep, kept_kps):
        x1, y1, x2, y2, score = (float(v) for v in det_row)
        if not passes_det_score(score, min_det):
            continue
        x1 = max(0.0, min(float(width - 1), x1))
        y1 = max(0.0, min(float(height - 1), y1))
        x2 = max(x1 + 1.0, min(float(width), x2))
        y2 = max(y1 + 1.0, min(float(height), y2))
        box = _clamp_box([x1 / width, y1 / height, (x2 - x1) / width, (y2 - y1) / height])
        if not passes_min_side(box, width, height, min_side_px):
            continue
        landmarks = _landmark_pairs(kps, width, height) if kps is not None else None
        if landmarks_only:
            row = {
                "box": box,
                "detScore": score,
                "shortSidePx": box_short_side_px(box, width, height),
            }
            if landmarks is not None:
                row["landmarks"] = landmarks
            faces.append(row)
            continue
        if kps is not None:
            aligned = _affine_112(image, np.asarray(kps).reshape((5, 2)))
        else:
            aligned = _crop_112(image, box)
        rec_blob = ((aligned.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None, ...]
        emb = rec.run(None, {rec_input: rec_blob})[0].reshape(-1)
        row = {
            "box": box,
            "embedding": l2_normalize([float(x) for x in emb.tolist()]),
            "detScore": score,
            "shortSidePx": box_short_side_px(box, width, height),
        }
        if landmarks is not None:
            row["landmarks"] = landmarks
        faces.append(row)
    faces.sort(key=lambda face: (face["box"][0], face["box"][1]))
    return faces


def letterbox_size(
    width: int,
    height: int,
    input_size: tuple[int, int] = (DET_INPUT, DET_INPUT),
) -> tuple[int, int, float]:
    """Fit a window into the SCRFD 640 canvas. Returns (new_w, new_h, scale)."""
    if width <= 0 or height <= 0:
        return 1, 1, 1.0
    im_ratio = height / width
    model_ratio = input_size[1] / input_size[0]
    if im_ratio > model_ratio:
        new_height = input_size[1]
        new_width = max(1, int(new_height / im_ratio))
    else:
        new_width = input_size[0]
        new_height = max(1, int(new_width * im_ratio))
    return new_width, new_height, new_height / float(height)


def detect_px_on_canvas(
    face_side_px: float,
    image_w: int,
    image_h: int,
    window_w: int | None = None,
    window_h: int | None = None,
) -> float:
    """How large a face becomes on the 640 detect canvas after letterbox."""
    w = window_w if window_w is not None else image_w
    h = window_h if window_h is not None else image_h
    _, _, scale = letterbox_size(w, h)
    return float(face_side_px) * scale


def iter_detect_windows(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Full-frame window plus overlapping 1280 tiles on large stills."""
    windows = [(0, 0, width, height)]
    if width <= 0 or height <= 0 or max(width, height) < TILE_TRIGGER:
        return windows
    tile = min(TILE_SRC, width, height)
    if tile < 64:
        return windows
    step = max(1, tile - TILE_OVERLAP)
    xs = list(range(0, max(1, width - tile + 1), step))
    if xs[-1] + tile < width:
        xs.append(width - tile)
    ys = list(range(0, max(1, height - tile + 1), step))
    if ys[-1] + tile < height:
        ys.append(height - tile)
    extras: list[tuple[int, int, int, int]] = []
    for y in ys:
        for x in xs:
            win = (x, y, x + tile, y + tile)
            if win == (0, 0, width, height):
                continue
            extras.append(win)
    if len(extras) > TILE_MAX:
        factor = max(1, math.ceil(len(extras) / TILE_MAX))
        extras = extras[::factor][:TILE_MAX]
    return windows + extras


def named_assignment_threshold(base: float, det: dict[str, Any]) -> float:
    """Named people need a clearer match when the box is small or det is weak."""
    weak = False
    side = det.get("shortSidePx")
    if isinstance(side, (int, float)) and not isinstance(side, bool) and side < NAMED_WEAK_SIDE_PX:
        weak = True
    score = det.get("detScore")
    if isinstance(score, (int, float)) and not isinstance(score, bool) and score < NAMED_WEAK_DET:
        weak = True
    if not weak:
        return float(base)
    return min(0.95, float(base) + NAMED_WEAK_BUMP)


def _resize_rgb(image: Any, new_width: int, new_height: int) -> Any:
    np = _numpy()
    h, w = image.shape[:2]
    ys = (np.linspace(0, h - 1, new_height)).astype(np.int32)
    xs = (np.linspace(0, w - 1, new_width)).astype(np.int32)
    return image[ys][:, xs]


def detect_faces_on_still(
    root: Path,
    path: Path,
    backend: str,
    *,
    min_side_px: int = DEFAULT_MIN_SIDE_PX,
    min_det: float = INSIGHT_DET_MIN,
    landmarks_only: bool = False,
) -> list[dict[str, Any]]:
    width, height, rgb = decode_still_rgb(path)
    if backend == BACKEND_FIXTURE:
        return detect_fixture(width, height, rgb, min_side_px=min_side_px)
    if backend == BACKEND_INSIGHT:
        return detect_insightface(
            root,
            width,
            height,
            rgb,
            min_side_px=min_side_px,
            min_det=min_det,
            landmarks_only=landmarks_only,
        )
    raise fail("models-missing")


def _box_iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = (float(v) for v in a)
    bx, by, bw, bh = (float(v) for v in b)
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return inter / union


def fill_face_landmarks(root: Path) -> dict[str, Any]:
    """Store the five scan points on faces that only have a box and a fingerprint.

    Who the face belongs to does not change.
    """
    from library.item_store import write
    from library.records import ordered_item

    status = faces_status(root)
    if not status.get("ready"):
        raise fail("models-missing")
    backend = status.get("backend")
    if type(backend) is not str or not backend:
        raise fail("models-missing")
    updated = 0
    missed = 0
    items = 0
    for item_id in iter_item_ids(root):
        try:
            item = load_item(root, item_id)
        except Exception:
            continue
        faces = [face for face in (item.get("faces") or []) if isinstance(face, dict)]
        if not faces:
            continue
        pending = [
            face
            for face in faces
            if not (isinstance(face.get("landmarks"), list) and len(face["landmarks"]) == 5)
        ]
        if not pending:
            continue
        path = _still_path(item, root)
        if path is None:
            missed += len(pending)
            continue
        try:
            found = detect_faces_on_still(root, path, backend, landmarks_only=True)
        except Exception:
            missed += len(pending)
            continue
        changed = False
        for face in pending:
            box = face.get("box")
            if not isinstance(box, list) or len(box) != 4:
                missed += 1
                continue
            best = None
            best_iou = 0.3
            for det in found:
                landmarks = det.get("landmarks")
                det_box = det.get("box")
                if not isinstance(landmarks, list) or len(landmarks) != 5 or not isinstance(det_box, list):
                    continue
                score = _box_iou(box, det_box)
                if score > best_iou:
                    best_iou = score
                    best = landmarks
            if best is None:
                missed += 1
                continue
            face["landmarks"] = best
            changed = True
            updated += 1
        if changed:
            write(root, item_id, ordered_item(item))
            items += 1
        if items and items % 25 == 0:
            print(f"eye points stored on {updated} faces", flush=True)
    return {"ok": True, "faces": updated, "missed": missed, "items": items}


def _centroid(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        return []
    length = len(embeddings[0])
    acc = [0.0] * length
    for emb in embeddings:
        for i, value in enumerate(emb):
            if i < length:
                acc[i] += float(value)
    n = float(len(embeddings))
    return l2_normalize([value / n for value in acc])


def _nearest_person(
    embedding: list[float],
    centroids: dict[str, list[float]],
    threshold: float,
) -> tuple[str | None, float | None]:
    best_id = None
    best = threshold
    for person_id, centroid in centroids.items():
        if not centroid:
            continue
        score = cosine(embedding, centroid)
        if score > best:
            best = score
            best_id = person_id
    if best_id is None:
        return None, None
    return best_id, best


def _strip_items_from_index(index: dict[str, Any], item_ids: set[str]) -> dict[str, Any]:
    people = {}
    for person_id, rec in (index.get("people") or {}).items():
        if not isinstance(rec, dict):
            continue
        faces = [
            ref
            for ref in (rec.get("faces") or [])
            if not (isinstance(ref, dict) and ref.get("itemId") in item_ids)
        ]
        people[person_id] = {"centroid": list(rec.get("centroid") or []), "faces": faces}
    next_index = dict(index)
    next_index["people"] = people
    return next_index


def _named_person_ids(root: Path, person_ids: list[str]) -> set[str]:
    named: set[str] = set()
    for person_id in person_ids:
        person = try_load_person(root, person_id)
        if person is None:
            continue
        name = person.get("name")
        if type(name) is str and name.strip():
            named.add(person_id)
    return named


def cluster_detections(
    root: Path,
    detections: list[dict[str, Any]],
    index: dict[str, Any],
    *,
    replace_centroids: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], int, int]:
    threshold = float(index.get("matchThreshold") or FIXTURE_THRESHOLD)
    people = dict(index.get("people") or {})
    centroids = {
        person_id: list(rec.get("centroid") or [])
        for person_id, rec in people.items()
        if isinstance(rec, dict)
    }
    named_ids = _named_person_ids(root, list(centroids.keys()))
    named_centroids = {pid: vec for pid, vec in centroids.items() if pid in named_ids}
    unnamed_centroids = {pid: vec for pid, vec in centroids.items() if pid not in named_ids}
    created = 0
    reused = 0
    assigned: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for det in detections:
        needed_named = named_assignment_threshold(threshold, det)
        named_id, named_score = _nearest_person(det["embedding"], named_centroids, needed_named)
        unnamed_id, unnamed_score = _nearest_person(
            det["embedding"], unnamed_centroids, threshold
        )
        person_id = None
        match_score = None
        candidates: list[tuple[float, str]] = []
        if named_id is not None and named_score is not None:
            candidates.append((float(named_score), named_id))
        if unnamed_id is not None and unnamed_score is not None:
            candidates.append((float(unnamed_score), unnamed_id))
        if candidates:
            candidates.sort(key=lambda pair: pair[0], reverse=True)
            match_score, person_id = candidates[0]
        if person_id is not None:
            reused += 1
            assigned.append({**det, "personId": person_id, "matchScore": match_score})
        else:
            pending.append(det)
    pending.sort(key=lambda det: (det["itemId"], det["box"][0], det["box"][1]))
    new_clusters: list[dict[str, Any]] = []
    for det in pending:
        matched = None
        match_score = 1.0
        for cluster in new_clusters:
            score = cosine(det["embedding"], cluster["centroid"])
            if score > threshold:
                matched = cluster
                match_score = score
                break
        if matched is None:
            person_id = new_person_id(root)
            while person_id in people or any(c["personId"] == person_id for c in new_clusters):
                person_id = new_person_id(root)
            matched = {
                "personId": person_id,
                "embeddings": [det["embedding"]],
                "centroid": det["embedding"],
            }
            new_clusters.append(matched)
            created += 1
            match_score = 1.0
        else:
            matched["embeddings"].append(det["embedding"])
            matched["centroid"] = _centroid(matched["embeddings"])
        assigned.append({**det, "personId": matched["personId"], "matchScore": match_score})
    for cluster in new_clusters:
        people[cluster["personId"]] = {"centroid": cluster["centroid"], "faces": []}
        centroids[cluster["personId"]] = cluster["centroid"]
    by_person: dict[str, list[list[float]]] = {}
    if replace_centroids:
        face_refs: dict[str, list[dict[str, Any]]] = {pid: [] for pid in people}
    else:
        face_refs = {pid: list((people[pid].get("faces") or [])) for pid in people}
    for det in assigned:
        pid = det["personId"]
        by_person.setdefault(pid, []).append(det["embedding"])
        ref = {"itemId": det["itemId"], "box": det["box"]}
        if ref not in face_refs[pid]:
            face_refs[pid].append(ref)
    for pid, rec in people.items():
        embs = by_person.get(pid) or []
        if embs and (replace_centroids or not (rec.get("centroid") or [])):
            people[pid]["centroid"] = _centroid(embs)
        elif embs:
            # Weight the stored mean by the faces behind it, or every new face
            # drags the person halfway toward itself.
            weight = float(max(1, len(rec.get("faces") or [])))
            total = [float(v) * weight for v in rec.get("centroid") or []]
            for emb in embs:
                for i in range(min(len(total), len(emb))):
                    total[i] += float(emb[i])
            people[pid]["centroid"] = l2_normalize(total)
        people[pid]["faces"] = face_refs[pid]
    next_index = {
        "schemaVersion": 1,
        "backend": index.get("backend"),
        "matchThreshold": threshold,
        "people": people,
    }
    return assigned, next_index, created, reused


def face_boxes_equal(left: Any, right: Any, eps: float = 1e-4) -> bool:
    if left is None and right is None:
        return True
    if not isinstance(left, list) or not isinstance(right, list):
        return False
    if len(left) != 4 or len(right) != 4:
        return False
    try:
        return all(abs(float(left[i]) - float(right[i])) <= eps for i in range(4))
    except (TypeError, ValueError):
        return False


def _clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _landmark_pairs(kps: Any, width: int, height: int) -> list[list[float]] | None:
    if kps is None or width <= 0 or height <= 0:
        return None
    np = _numpy()
    pts = np.asarray(kps, dtype=np.float64).reshape((5, 2))
    return [
        [_clamp_unit(float(px) / width), _clamp_unit(float(py) / height)]
        for px, py in pts
    ]


def _face_record(det: dict[str, Any]) -> dict[str, Any]:
    rec: dict[str, Any] = {"personId": det["personId"], "box": det["box"]}
    embedding = det.get("embedding")
    if isinstance(embedding, list) and embedding:
        rec["embedding"] = pack_embedding(embedding)
    landmarks = det.get("landmarks")
    if isinstance(landmarks, list) and len(landmarks) == 5:
        rec["landmarks"] = landmarks
    det_score = det.get("detScore")
    match_score = det.get("matchScore")
    if isinstance(det_score, (int, float)) and not isinstance(det_score, bool):
        rec["detScore"] = _clamp_unit(det_score)
    if isinstance(match_score, (int, float)) and not isinstance(match_score, bool):
        rec["matchScore"] = _clamp_unit(match_score)
    return rec


def _item_pixel_size(item: dict[str, Any]) -> tuple[int, int]:
    meta = item.get("metadata") or {}
    width = meta.get("width") or 0
    height = meta.get("height") or 0
    try:
        return int(width), int(height)
    except (TypeError, ValueError):
        return 0, 0


def face_passes_stored_gates(
    face: dict[str, Any],
    item: dict[str, Any],
    *,
    min_side_px: int,
    match_threshold: float,
    min_det: float,
) -> bool:
    box = face.get("box")
    width, height = _item_pixel_size(item)
    if isinstance(box, list) and len(box) == 4 and width > 0 and height > 0:
        if not passes_min_side([float(v) for v in box], width, height, min_side_px):
            return False
    det_score = face.get("detScore")
    if isinstance(det_score, (int, float)) and not isinstance(det_score, bool):
        if not passes_det_score(float(det_score), min_det):
            return False
    match_score = face.get("matchScore")
    if isinstance(match_score, (int, float)) and not isinstance(match_score, bool):
        if float(match_score) <= float(match_threshold):
            return False
    return True


def _prune_empty_unnamed(
    root: Path,
    remaining_ids: set[str],
    changes: list[dict[str, Any]],
) -> None:
    from library.catalog_io import load_people

    for person in load_people(root):
        person_id = person["id"]
        if person_id in remaining_ids:
            continue
        named = type(person.get("name")) is str and bool(person.get("name"))
        if named:
            continue
        if any(change.get("path") == person_rel(person_id) for change in changes):
            continue
        changes.append(
            {
                "path": person_rel(person_id),
                "before": ordered_person(person),
                "after": None,
            }
        )


def cleanup_faces(root: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = read_infer_payload(payload)
    status = faces_status(root)
    backend = status.get("backend") or BACKEND_INSIGHT
    quality = face_quality_settings(root, backend)
    wanted = parsed["itemIds"]
    item_ids = wanted if wanted is not None else list(iter_item_ids(root))
    changes: list[dict[str, Any]] = []
    kept = 0
    dropped = 0
    remaining: set[str] = set()
    touched = set(item_ids)
    overrides: dict[str, list[dict[str, Any]]] = {}
    for item_id in item_ids:
        item = load_item(root, item_id)
        before = clone(item)
        faces = list(item.get("faces") or [])
        next_faces = []
        for face in faces:
            if face_passes_stored_gates(
                face,
                item,
                min_side_px=int(quality["minSidePx"]),
                match_threshold=float(quality["matchThreshold"]),
                min_det=float(quality["minDetScore"]),
            ):
                next_faces.append(face)
                pid = face.get("personId")
                if type(pid) is str and pid:
                    remaining.add(pid)
            else:
                dropped += 1
        kept += len(next_faces)
        item["faces"] = collapse_faces(next_faces)
        overrides[item_id] = item["faces"]
        after = ordered_item(item)
        if after != before:
            changes.append({"path": item_rel(item_id), "before": before, "after": after})
    for item_id in iter_item_ids(root):
        if item_id in touched:
            continue
        item = load_item(root, item_id)
        for face in item.get("faces") or []:
            pid = face.get("personId")
            if type(pid) is str and pid:
                remaining.add(pid)
    _prune_empty_unnamed(root, remaining, changes)
    if changes:
        entry = make_history_entry(root, "faces-cleanup", changes)
        transact(root, plan_append(root, entry) + changes)
    before_index = load_index(root)
    if before_index is not None:
        after_index = _index_from_items(root, before_index, overrides)
        after_index["matchThreshold"] = quality["matchThreshold"]
        if after_index != before_index:
            write_index(root, after_index)
    return {
        "ok": True,
        "backend": backend,
        "cleanup": True,
        "items": len(item_ids),
        "faces": kept,
        "dropped": dropped,
        "peopleCreated": 0,
        "peopleReused": 0,
        "skipped": 0,
    }


def request_faces_rescan(root: Path) -> dict[str, Any]:
    status = _require_models(root)
    current = load_index(root) or _empty_index(
        status["backend"],
        float((load_manifest(root) or {}).get("matchThreshold") or INSIGHT_THRESHOLD),
    )
    after = _index_from_items(root, current, keep_unbacked=False)
    after["scanned"] = {}
    after["forceRescan"] = True
    if after != current:
        write_index(root, after)
    return {"ok": True, "queued": True, "backend": status["backend"]}


def infer_faces(
    root: Path,
    payload: dict[str, Any] | None = None,
    *,
    detected: dict[str, list[dict[str, Any]]] | None = None,
    mirror: bool = True,
) -> dict[str, Any]:
    """Detect, cluster and publish faces for the wanted items (all when none).

    ``detected`` maps item id -> faces already found by detect_faces_on_still;
    the drain computes those with the server lock released and passes them in,
    with ``mirror=False`` so the portable faces.json is written once at the end.
    """
    parsed = read_infer_payload(payload)
    if parsed["cleanup"] and not parsed["force"]:
        return cleanup_faces(root, parsed)
    status = _require_models(root)
    backend = status["backend"]
    quality = face_quality_settings(root, backend)
    manifest = load_manifest(root) or {}
    stored_index = load_index(root)
    index = stored_index or _empty_index(
        backend, float(manifest.get("matchThreshold") or quality["matchThreshold"])
    )
    wanted = parsed["itemIds"]
    force = parsed["force"]
    item_ids = wanted if wanted is not None else list(iter_item_ids(root))
    if force:
        index = _strip_items_from_index(index, set(item_ids))
    index = dict(index)
    index["matchThreshold"] = quality["matchThreshold"]
    detections: list[dict[str, Any]] = []
    skipped = 0
    scanned = 0
    scanned_ids: list[str] = []
    for item_id in item_ids:
        item = load_item(root, item_id)
        if item.get("kind") not in {"photo", "live"}:
            skipped += 1
            continue
        if not force and item.get("faces"):
            skipped += 1
            continue
        path = _still_path(item, root)
        if path is None:
            skipped += 1
            continue
        scanned += 1
        scanned_ids.append(item_id)
        found = detected.get(item_id) if detected else None
        if found is None:
            found = detect_faces_on_still(
                root,
                path,
                backend,
                min_side_px=int(quality["minSidePx"]),
                min_det=float(quality["minDetScore"]),
            )
        for face in found:
            rec = {
                "itemId": item_id,
                "box": _clamp_box(face["box"]),
                "embedding": l2_normalize(face["embedding"]),
            }
            if "detScore" in face:
                rec["detScore"] = face["detScore"]
            landmarks = face.get("landmarks")
            if isinstance(landmarks, list) and len(landmarks) == 5:
                rec["landmarks"] = landmarks
            side = face.get("shortSidePx")
            if isinstance(side, (int, float)) and not isinstance(side, bool):
                rec["shortSidePx"] = float(side)
            detections.append(rec)
    assigned, next_index, created, reused = cluster_detections(
        root,
        detections,
        index,
        replace_centroids=force and wanted is None,
    )
    scanned_map = {} if force and wanted is None else dict(index.get("scanned") or {})
    for item_id in scanned_ids:
        scanned_map[item_id] = True
    next_index = dict(next_index)
    next_index["scanned"] = scanned_map
    next_index["matchThreshold"] = quality["matchThreshold"]
    if wanted is not None and index.get("forceRescan"):
        next_index["forceRescan"] = True
    changes: list[dict[str, Any]] = []
    seen_new: set[str] = set()
    for person_id in sorted({det["personId"] for det in assigned}):
        if try_load_person(root, person_id) is not None:
            continue
        if person_id in seen_new:
            continue
        seen_new.add(person_id)
        changes.append(
            {
                "path": person_rel(person_id),
                "before": None,
                "after": ordered_person({"schemaVersion": 1, "id": person_id, "name": None}),
            }
        )
    by_item: dict[str, list[dict[str, Any]]] = {}
    for det in assigned:
        by_item.setdefault(det["itemId"], []).append(_face_record(det))
    if force:
        for item_id in scanned_ids:
            by_item.setdefault(item_id, [])
    remaining: set[str] = set()
    for item_id, faces in by_item.items():
        item = load_item(root, item_id)
        before = clone(item)
        if force:
            item["faces"] = collapse_faces(faces)
        else:
            item["faces"] = collapse_faces(list(item.get("faces") or []) + faces)
        after = ordered_item(item)
        if after != before:
            changes.append({"path": item_rel(item_id), "before": before, "after": after})
    if force and wanted is None:
        for item_id in iter_item_ids(root):
            if item_id in by_item:
                item_faces = by_item[item_id]
            else:
                item_faces = load_item(root, item_id).get("faces") or []
            for face in item_faces:
                pid = face.get("personId")
                if type(pid) is str and pid:
                    remaining.add(pid)
        _prune_empty_unnamed(root, remaining, changes)
        next_index = _index_from_items(root, next_index, by_item)
        next_index["scanned"] = scanned_map
        next_index["matchThreshold"] = quality["matchThreshold"]
    if changes:
        entry = make_history_entry(root, "faces-infer", changes)
        transact(root, plan_append(root, entry) + changes)
    if next_index != stored_index:
        write_index(root, next_index, mirror=mirror)
    return {
        "ok": True,
        "backend": backend,
        "items": scanned,
        "faces": len(assigned),
        "peopleCreated": len(seen_new),
        "peopleReused": reused,
        "skipped": skipped,
    }


def scanned_item_ids(root: Path) -> set[str]:
    index = _index_readonly(root)
    if index is None:
        return set()
    scanned = index.get("scanned") or {}
    if not isinstance(scanned, dict):
        return set()
    return {key for key in scanned if type(key) is str}


def faces_force_rescan(root: Path) -> bool:
    index = _index_readonly(root)
    return bool(index and index.get("forceRescan"))


def _mark_faces_scanned(root: Path, item_id: str) -> None:
    current = load_index(root)
    if current is None:
        return
    scanned = dict(current.get("scanned") or {})
    if scanned.get(item_id) is True:
        return
    after = dict(current)
    scanned[item_id] = True
    after["scanned"] = scanned
    from library.atomic import atomic_write_json

    atomic_write_json(index_path(root), after)


def _file_signature(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return int(st.st_size), int(st.st_mtime_ns)


def infer_faces_step(root: Path, *, io_context=nullcontext) -> bool:
    """Find faces in one photo. Decode and ONNX run inside io_context (the
    server releases its lock there); clustering and publication happen under
    the lock after checking the file did not change meanwhile."""
    status = faces_status(root)
    if not status.get("ready"):
        return False
    force = faces_force_rescan(root)
    already = scanned_item_ids(root)
    from library.item_index import iter_items

    for item in iter_items(root):
        item_id = item.get("id")
        if type(item_id) is not str:
            continue
        if item_id in already:
            continue
        if item.get("kind") not in {"photo", "live"}:
            continue
        if not force and item.get("faces"):
            continue
        path = _still_path(item, root)
        if path is None:
            if force:
                _mark_faces_scanned(root, item_id)
                return True
            continue
        from library.activity import note_item

        note_item("infer-faces", "Faces", item)
        backend = status["backend"]
        quality = face_quality_settings(root, backend)
        signature = _file_signature(path)
        try:
            with io_context():
                found = detect_faces_on_still(
                    root,
                    path,
                    backend,
                    min_side_px=int(quality["minSidePx"]),
                    min_det=float(quality["minDetScore"]),
                )
        except Exception:
            _mark_faces_scanned(root, item_id)
            return True
        try:
            current = load_item(root, item_id)
        except AppError:
            return True
        if _still_path(current, root) != path or _file_signature(path) != signature:
            return True
        try:
            infer_faces(
                root,
                {"itemIds": [item_id], "force": force},
                detected={item_id: found},
                mirror=False,
            )
        except Exception:
            _mark_faces_scanned(root, item_id)
            return True
        return True
    if force:
        _finish_rescan(root)
    settle_index_mirror(root)
    return False


def _finish_rescan(root: Path) -> None:
    """End of Re-run Faces: drop unnamed people left with no faces, then
    re-derive the index once from the fresh fingerprints."""
    from library.item_index import iter_items

    remaining = {
        face.get("personId")
        for item in iter_items(root)
        for face in item.get("faces") or []
        if type(face.get("personId")) is str
    }
    changes: list[dict[str, Any]] = []
    _prune_empty_unnamed(root, remaining, changes)
    if changes:
        entry = make_history_entry(root, "faces-cleanup", changes)
        transact(root, plan_append(root, entry) + changes)
    current = load_index(root)
    if current is None:
        return
    after = _index_from_items(root, current)
    after.pop("forceRescan", None)
    write_index(root, after)
