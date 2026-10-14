"""Optional local face inference. Never uploads. Never guesses a name."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
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
from library.errors import fail
from library.history import make_history_entry, plan_append
from library.media import ffprobe_json
from library.paths import library_path
from library.records import clone, ordered_item, ordered_person
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
INSIGHT_THRESHOLD = 0.35
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
    extra = set(value.keys()) - {"force", "itemIds"}
    if extra:
        raise fail("invalid-argument")
    force = value.get("force", False)
    if type(force) is not bool:
        raise fail("invalid-argument")
    item_ids = value.get("itemIds")
    if item_ids is None:
        return {"force": force, "itemIds": None}
    if not isinstance(item_ids, list) or not item_ids:
        raise fail("invalid-argument")
    out: list[str] = []
    for item_id in item_ids:
        if type(item_id) is not str or not item_id:
            raise fail("invalid-argument")
        out.append(item_id)
    return {"force": force, "itemIds": out}


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


def decode_rgb(path: Path) -> tuple[int, int, bytes]:
    probe = ffprobe_json(path)
    if probe is None:
        raise fail("decode-error")
    width = 0
    height = 0
    for stream in probe.get("streams") or []:
        if stream.get("codec_type") == "video":
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            break
    if width <= 0 or height <= 0:
        raise fail("decode-error")
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise fail("dependency-missing") from exc
    expected = width * height * 3
    if proc.returncode != 0 or len(proc.stdout) < expected:
        raise fail("decode-error")
    return width, height, proc.stdout[:expected]


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


def detect_fixture(width: int, height: int, rgb: bytes) -> list[dict[str, Any]]:
    faces: list[dict[str, Any]] = []
    for x, y, w, h in _flood_boxes(width, height, rgb):
        faces.append(
            {
                "box": [
                    x / width,
                    y / height,
                    w / width,
                    h / height,
                ],
                "embedding": _identity_embedding(width, height, rgb, (x, y, w, h)),
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
    mat[:, :2] = r.T * scale
    mat[:, 2] = t
    return mat


def _affine_112(image: Any, kps: Any) -> Any:
    np = _numpy()
    mat = _similarity_matrix(kps, np.asarray(_ARCFACE_DST, dtype=np.float64))
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


def _nms(dets: Any, thresh: float) -> Any:
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
        order = order[np.where(ovr <= thresh)[0] + 1]
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


def detect_insightface(root: Path, width: int, height: int, rgb: bytes) -> list[dict[str, Any]]:
    np = _numpy()
    ort = _ort()
    image = np.frombuffer(rgb, dtype=np.uint8).reshape((height, width, 3))
    det_path = buffalo_dir(root) / DET_NAME
    rec_path = buffalo_dir(root) / REC_NAME
    if not det_path.is_file() or not rec_path.is_file():
        raise fail("models-missing")
    sess_opts = ort.SessionOptions()
    sess_opts.inter_op_num_threads = 1
    sess_opts.intra_op_num_threads = 1
    det = ort.InferenceSession(str(det_path), sess_opts, providers=["CPUExecutionProvider"])
    rec = ort.InferenceSession(str(rec_path), sess_opts, providers=["CPUExecutionProvider"])
    input_size = (640, 640)
    im_ratio = height / width
    model_ratio = input_size[1] / input_size[0]
    if im_ratio > model_ratio:
        new_height = input_size[1]
        new_width = int(new_height / im_ratio)
    else:
        new_width = input_size[0]
        new_height = int(new_width * im_ratio)
    det_scale = new_height / float(height)
    resized = _resize_rgb(image, new_width, new_height)
    blob = np.zeros((1, 3, input_size[1], input_size[0]), dtype=np.float32)
    blob[0, 0, :new_height, :new_width] = (resized[:, :, 2] - 127.5) / 128.0
    blob[0, 1, :new_height, :new_width] = (resized[:, :, 1] - 127.5) / 128.0
    blob[0, 2, :new_height, :new_width] = (resized[:, :, 0] - 127.5) / 128.0
    input_name = det.get_inputs()[0].name
    net_outs = det.run(None, {input_name: blob})
    scores_list = []
    bboxes_list = []
    kps_list = []
    fmc = 3
    feat_strides = [8, 16, 32]
    num_anchors = 2
    use_kps = len(net_outs) == 9
    center_cache: dict[tuple[int, int, int], Any] = {}
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
        pos_inds = np.where(scores.ravel() >= 0.5)[0]
        bboxes = _distance2bbox(anchor_centers, bbox_preds.reshape((-1, 4)))
        pos_scores = scores.ravel()[pos_inds]
        pos_bboxes = bboxes[pos_inds]
        scores_list.append(pos_scores)
        bboxes_list.append(pos_bboxes)
        if use_kps:
            kpss = _distance2kps(anchor_centers, kps_preds.reshape((-1, 10)))
            kps_list.append(kpss[pos_inds])
    if not scores_list:
        return []
    scores_cat = np.concatenate(scores_list, axis=0)
    bboxes_cat = np.concatenate(bboxes_list, axis=0)
    if scores_cat.size == 0:
        return []
    pre = np.hstack([bboxes_cat, scores_cat[:, None]])
    pre[:, :4] /= det_scale
    keep = _nms(pre, 0.4)
    if use_kps and kps_list:
        kpss = np.concatenate(kps_list, axis=0) / det_scale
        order = scores_cat.argsort()[::-1]
        kpss = kpss[order]
        # NMS keep indices are into the score-sorted? insightface nms is on concatenated order
        # Recompute kps for kept rows by matching boxes.
        kept_kps = []
        for det_row in keep:
            # find nearest original row
            dists = np.abs(pre[:, 0] - det_row[0]) + np.abs(pre[:, 1] - det_row[1])
            kept_kps.append(kpss[int(np.argmin(dists))] if len(kpss) else None)
    else:
        kept_kps = [None] * len(keep)
    rec_input = rec.get_inputs()[0].name
    faces: list[dict[str, Any]] = []
    for det_row, kps in zip(keep, kept_kps):
        x1, y1, x2, y2, _score = (float(v) for v in det_row)
        x1 = max(0.0, min(float(width - 1), x1))
        y1 = max(0.0, min(float(height - 1), y1))
        x2 = max(x1 + 1.0, min(float(width), x2))
        y2 = max(y1 + 1.0, min(float(height), y2))
        box = _clamp_box([x1 / width, y1 / height, (x2 - x1) / width, (y2 - y1) / height])
        if kps is not None:
            aligned = _affine_112(image, np.asarray(kps).reshape((5, 2)))
        else:
            aligned = _crop_112(image, box)
        blob = ((aligned.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None, ...]
        emb = rec.run(None, {rec_input: blob})[0].reshape(-1)
        faces.append({"box": box, "embedding": l2_normalize([float(x) for x in emb.tolist()])})
    faces.sort(key=lambda face: (face["box"][0], face["box"][1]))
    return faces


def _resize_rgb(image: Any, new_width: int, new_height: int) -> Any:
    np = _numpy()
    h, w = image.shape[:2]
    ys = (np.linspace(0, h - 1, new_height)).astype(np.int32)
    xs = (np.linspace(0, w - 1, new_width)).astype(np.int32)
    return image[ys][:, xs]


def detect_faces_on_still(root: Path, path: Path, backend: str) -> list[dict[str, Any]]:
    width, height, rgb = decode_rgb(path)
    if backend == BACKEND_FIXTURE:
        return detect_fixture(width, height, rgb)
    if backend == BACKEND_INSIGHT:
        return detect_insightface(root, width, height, rgb)
    raise fail("models-missing")


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
) -> str | None:
    best_id = None
    best = threshold
    for person_id, centroid in centroids.items():
        if not centroid:
            continue
        score = cosine(embedding, centroid)
        if score > best:
            best = score
            best_id = person_id
    return best_id


def cluster_detections(
    root: Path,
    detections: list[dict[str, Any]],
    index: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], int, int]:
    threshold = float(index.get("matchThreshold") or FIXTURE_THRESHOLD)
    people = dict(index.get("people") or {})
    centroids = {
        person_id: list(rec.get("centroid") or [])
        for person_id, rec in people.items()
        if isinstance(rec, dict)
    }
    created = 0
    reused = 0
    assigned: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for det in detections:
        person_id = _nearest_person(det["embedding"], centroids, threshold)
        if person_id is not None:
            reused += 1
            assigned.append({**det, "personId": person_id})
        else:
            pending.append(det)
    pending.sort(key=lambda det: (det["itemId"], det["box"][0], det["box"][1]))
    new_clusters: list[dict[str, Any]] = []
    for det in pending:
        matched = None
        for cluster in new_clusters:
            if cosine(det["embedding"], cluster["centroid"]) > threshold:
                matched = cluster
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
        else:
            matched["embeddings"].append(det["embedding"])
            matched["centroid"] = _centroid(matched["embeddings"])
        assigned.append({**det, "personId": matched["personId"]})
    for cluster in new_clusters:
        people[cluster["personId"]] = {"centroid": cluster["centroid"], "faces": []}
        centroids[cluster["personId"]] = cluster["centroid"]
    by_person: dict[str, list[list[float]]] = {}
    face_refs: dict[str, list[dict[str, Any]]] = {pid: list((people[pid].get("faces") or [])) for pid in people}
    for det in assigned:
        pid = det["personId"]
        by_person.setdefault(pid, []).append(det["embedding"])
        ref = {"itemId": det["itemId"], "box": det["box"]}
        if ref not in face_refs[pid]:
            face_refs[pid].append(ref)
    for pid, embs in by_person.items():
        existing = [people[pid].get("centroid") or []]
        if existing[0]:
            people[pid]["centroid"] = _centroid(existing + embs)
        else:
            people[pid]["centroid"] = _centroid(embs)
        people[pid]["faces"] = face_refs[pid]
    next_index = {
        "schemaVersion": 1,
        "backend": index.get("backend"),
        "matchThreshold": threshold,
        "people": people,
    }
    return assigned, next_index, created, reused


def plan_merge_index(root: Path, keep_id: str, drop_id: str) -> dict[str, Any] | None:
    current = load_index(root)
    if current is None:
        return None
    people = dict(current.get("people") or {})
    if drop_id not in people and keep_id not in people:
        return None
    before = clone(current)
    keep = dict(people.get(keep_id) or {"centroid": [], "faces": []})
    drop = dict(people.get(drop_id) or {"centroid": [], "faces": []})
    embs = []
    if keep.get("centroid"):
        embs.append(list(keep["centroid"]))
    if drop.get("centroid"):
        embs.append(list(drop["centroid"]))
    faces = list(keep.get("faces") or [])
    for ref in drop.get("faces") or []:
        rewritten = dict(ref)
        if rewritten not in faces:
            faces.append(rewritten)
    people[keep_id] = {
        "centroid": _centroid(embs) if embs else [],
        "faces": faces,
    }
    people.pop(drop_id, None)
    after = {
        "schemaVersion": 1,
        "backend": current.get("backend"),
        "matchThreshold": current.get("matchThreshold"),
        "people": people,
    }
    if after == before:
        return None
    return {"path": INDEX_REL, "before": before, "after": after}


def infer_faces(root: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = read_infer_payload(payload)
    status = _require_models(root)
    backend = status["backend"]
    manifest = load_manifest(root) or {}
    index = load_index(root) or _empty_index(backend, float(manifest.get("matchThreshold") or FIXTURE_THRESHOLD))
    wanted = parsed["itemIds"]
    force = parsed["force"]
    item_ids = wanted if wanted is not None else iter_item_ids(root)
    detections: list[dict[str, Any]] = []
    skipped = 0
    scanned = 0
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
        for face in detect_faces_on_still(root, path, backend):
            detections.append(
                {
                    "itemId": item_id,
                    "box": _clamp_box(face["box"]),
                    "embedding": l2_normalize(face["embedding"]),
                }
            )
    assigned, next_index, created, reused = cluster_detections(root, detections, index)
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
        by_item.setdefault(det["itemId"], []).append(
            {"personId": det["personId"], "box": det["box"]}
        )
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
    before_index = load_index(root)
    if next_index != before_index:
        changes.append({"path": INDEX_REL, "before": before_index, "after": next_index})
    if changes:
        entry = make_history_entry(root, "faces-infer", changes)
        transact(root, plan_append(root, entry) + changes)
    return {
        "ok": True,
        "backend": backend,
        "items": scanned,
        "faces": len(assigned),
        "peopleCreated": len(seen_new),
        "peopleReused": reused,
        "skipped": skipped,
    }
