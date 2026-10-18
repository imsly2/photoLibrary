"""Optional local object detection. Writes Things through annotate only."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from library.annotate import apply_annotate, normalize_name
from library.atomic import atomic_write_bytes, atomic_write_json, load_json
from library.catalog_io import iter_item_ids, load_item, try_load_thing
from library.errors import fail
from library.media import ffprobe_json, sha256_file
from library.renditions import rendition_abs
from library.volumes import location_file, location_matches_stat

INPUT_SIZE = 640
MODEL_NAME = "yolov8n.onnx"
KIND = "objects"
CONF_MIN = 0.25
IOU_MAX = 0.45
MAX_DETS = 20
SKIP_LABELS = frozenset({"person"})

MODEL_URLS = (
    "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx",
    "https://huggingface.co/unileon-robotics/YOLO8-ONNX/resolve/main/yolov8n.onnx",
    "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx",
)

RUNTIME_PACKAGES = ("onnxruntime",)

COCO_NAMES = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)


def models_dir(root: Path) -> Path:
    return root / "models"


def model_rel() -> str:
    return f"models/{MODEL_NAME}"


def model_path(root: Path) -> Path:
    return models_dir(root) / MODEL_NAME


def objects_manifest_path(root: Path) -> Path:
    return models_dir(root) / "objects.json"


def objects_state_path(root: Path) -> Path:
    return models_dir(root) / "objects-state.json"


def model_installed(root: Path) -> bool:
    path = model_path(root)
    return path.is_file() and path.stat().st_size > 1_000_000


def read_analyze_payload(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    extra = set(value.keys()) - {"itemId"}
    if extra:
        raise fail("invalid-argument")
    if "itemId" not in value:
        return None
    item_id = value.get("itemId")
    if type(item_id) is not str or item_id == "":
        raise fail("invalid-argument")
    return {"itemId": item_id}


def analyze_status(root: Path) -> dict[str, Any]:
    installed = model_installed(root)
    state = _load_state(root)
    pending = 0
    if installed:
        for item_id in iter_item_ids(root):
            item = load_item(root, item_id)
            still = _still_for_detect(item, root)
            if still is None:
                continue
            # Catalog IDs are immutable content hashes. Status only needs to
            # know whether this ID has a recorded analysis; the worker keeps
            # verifying source bytes before deciding whether to re-analyze.
            record = (state.get("items") or {}).get(item_id)
            if not isinstance(record, dict) or not record.get("sha256"):
                pending += 1
    return {
        "ok": True,
        "installed": installed,
        "model": model_rel() if installed else None,
        "pending": pending,
    }


def setup_objects(root: Path) -> dict[str, Any]:
    models_dir(root).mkdir(parents=True, exist_ok=True)
    _ensure_runtime()
    dest = model_path(root)
    if not model_installed(root):
        _download_model(dest)
    if not model_installed(root):
        raise fail("io-error")
    digest = sha256_file(dest)
    manifest = {
        "schemaVersion": 1,
        "kind": KIND,
        "model": MODEL_NAME,
        "input": INPUT_SIZE,
        "labels": list(COCO_NAMES),
        "sha256": digest,
        "bytes": dest.stat().st_size,
    }
    atomic_write_json(objects_manifest_path(root), manifest)
    return {
        "ok": True,
        "kind": KIND,
        "model": MODEL_NAME,
        "path": model_rel(),
        "sha256": digest,
        "bytes": manifest["bytes"],
    }


def analyze_objects(root: Path, item_id: str | None = None) -> dict[str, Any]:
    if not model_installed(root):
        raise fail("model-unavailable")
    _ensure_runtime()
    if item_id is not None:
        if type(item_id) is not str or item_id == "":
            raise fail("invalid-argument")
        load_item(root, item_id)
        ids = [item_id]
        force = True
    else:
        ids = iter_item_ids(root)
        force = False
    analyzed = 0
    tagged = 0
    skipped = 0
    items: list[dict[str, Any]] = []
    state = _load_state(root)
    for current_id in ids:
        item = load_item(root, current_id)
        still = _still_for_detect(item, root)
        if still is None:
            skipped += 1
            continue
        digest = sha256_file(still)
        if not force and _already_analyzed(state, current_id, digest):
            skipped += 1
            continue
        names = _analyze_one(root, current_id, still, digest, state)
        analyzed += 1
        if names:
            tagged += 1
        items.append({"id": current_id, "things": names})
    _save_state(root, state)
    return {
        "ok": True,
        "analyzed": analyzed,
        "tagged": tagged,
        "skipped": skipped,
        "items": items,
    }


def analyze_step(root: Path) -> bool:
    if not model_installed(root):
        return False
    try:
        _ensure_runtime()
    except Exception:
        return False
    state = _load_state(root)
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        still = _still_for_detect(item, root)
        if still is None:
            continue
        digest = sha256_file(still)
        if _already_analyzed(state, item_id, digest):
            continue
        from library.activity import note_item

        note_item("objects", "Objects", item)
        try:
            _analyze_one(root, item_id, still, digest, state)
        except Exception:
            state.setdefault("items", {})[item_id] = {"sha256": digest, "names": []}
        _save_state(root, state)
        return True
    return False


def detections_to_things(
    detections: list[dict[str, Any]],
    item: dict[str, Any],
    root: Path,
) -> list[dict[str, Any]]:
    """Name-only Things. Skip people. Do not rename existing entities."""
    existing: set[tuple[str, tuple[float, ...] | None]] = set()
    named: dict[str, str] = {}
    for ref in item.get("things") or []:
        thing_id = ref.get("thingId")
        box = ref.get("box")
        box_key = tuple(box) if isinstance(box, list) else None
        if type(thing_id) is str:
            existing.add((thing_id, box_key))
            thing = try_load_thing(root, thing_id)
            if thing and thing.get("name"):
                named[normalize_name(thing["name"])] = thing_id
                for alias in thing.get("aliases") or []:
                    if alias:
                        named[normalize_name(alias)] = thing_id
    out: list[dict[str, Any]] = []
    seen_label: set[str] = set()
    for det in detections:
        label = det.get("name")
        if type(label) is not str or label == "":
            continue
        if normalize_name(label) in SKIP_LABELS:
            continue
        folded = normalize_name(label)
        box = det.get("box")
        if box is not None:
            box = _clip_box(box)
            if box is None:
                continue
        if folded in named:
            thing_id = named[folded]
            box_key = tuple(box) if box is not None else None
            if (thing_id, box_key) in existing:
                continue
        if folded in seen_label and box is None:
            continue
        seen_label.add(folded)
        entry: dict[str, Any] = {"name": label}
        if box is not None:
            entry["box"] = box
        out.append(entry)
    return out


def _analyze_one(
    root: Path,
    item_id: str,
    still: Path,
    digest: str,
    state: dict[str, Any],
) -> list[str]:
    detections = detect_objects(still, model_path(root))
    item = load_item(root, item_id)
    payload_things = detections_to_things(detections, item, root)
    names = []
    for det in detections:
        label = det.get("name")
        if type(label) is str and normalize_name(label) not in SKIP_LABELS:
            if label not in names:
                names.append(label)
    if payload_things:
        apply_annotate(root, item_id, {"things": payload_things})
        item = load_item(root, item_id)
        names = []
        for ref in item.get("things") or []:
            thing = try_load_thing(root, ref.get("thingId") or "")
            if thing and thing.get("name") and thing["name"] not in names:
                names.append(thing["name"])
    state.setdefault("items", {})[item_id] = {"sha256": digest, "names": names}
    return names


def detect_objects(image_path: Path, onnx_path: Path) -> list[dict[str, Any]]:
    session, np = _session(onnx_path)
    tensor, pad_x, pad_y, new_w, new_h = _letterbox_tensor(image_path, np)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: tensor})
    if not outputs:
        return []
    return _parse_yolo(outputs[0], np, pad_x, pad_y, new_w, new_h)


def _still_for_detect(item: dict[str, Any], root: Path) -> Path | None:
    rend = item.get("renditions") or {}
    status = rend.get("status") or {}
    for slot in ("preview", "thumb", "poster"):
        if status.get(slot) != "ready":
            continue
        path = rendition_abs(item, slot, root)
        if path is not None and path.is_file() and path.stat().st_size > 0:
            return path
    return _current_still_file(item, root)


def _current_still_file(item: dict[str, Any], root: Path) -> Path | None:
    wanted = "motion" if item.get("kind") == "video" else "still"
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == wanted
    ]
    if item.get("kind") == "video" and not candidates:
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


def _letterbox_tensor(path: Path, np: Any) -> tuple[Any, float, float, float, float]:
    width, height = _probe_size(path)
    if width is None or height is None or width <= 0 or height <= 0:
        raise fail("decode-error")
    scale = min(INPUT_SIZE / width, INPUT_SIZE / height)
    new_w = width * scale
    new_h = height * scale
    pad_x = (INPUT_SIZE - new_w) / 2
    pad_y = (INPUT_SIZE - new_h) / 2
    vf = (
        f"scale={INPUT_SIZE}:{INPUT_SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={INPUT_SIZE}:{INPUT_SIZE}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            vf,
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        capture_output=True,
        check=False,
    )
    expected = INPUT_SIZE * INPUT_SIZE * 3
    if proc.returncode != 0 or len(proc.stdout) != expected:
        raise fail("decode-error")
    arr = np.frombuffer(proc.stdout, dtype=np.uint8).reshape(1, INPUT_SIZE, INPUT_SIZE, 3)
    arr = arr.astype("float32") / 255.0
    arr = np.transpose(arr, (0, 3, 1, 2))
    return arr, pad_x, pad_y, new_w, new_h


def _probe_size(path: Path) -> tuple[int | None, int | None]:
    payload = ffprobe_json(path)
    if not isinstance(payload, dict):
        return None, None
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") != "video":
            continue
        width = stream.get("width")
        height = stream.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
    return None, None


def _parse_yolo(
    raw: Any,
    np: Any,
    pad_x: float,
    pad_y: float,
    new_w: float,
    new_h: float,
) -> list[dict[str, Any]]:
    data = np.array(raw)
    if data.ndim == 3:
        data = data[0]
    if data.ndim != 2:
        return []
    if data.shape[0] in {84, 85} and data.shape[1] > data.shape[0]:
        data = data.T
    if data.shape[1] < 6:
        return []
    boxes = data[:, :4]
    scores = data[:, 4:]
    if scores.shape[1] > len(COCO_NAMES):
        scores = scores[:, : len(COCO_NAMES)]
    class_ids = np.argmax(scores, axis=1)
    class_scores = scores[np.arange(scores.shape[0]), class_ids]
    if float(np.max(class_scores)) > 1.0:
        class_scores = 1.0 / (1.0 + np.exp(-class_scores))
    picked: list[dict[str, Any]] = []
    for index in range(int(class_scores.shape[0])):
        score = float(class_scores[index])
        if score < CONF_MIN:
            continue
        class_id = int(class_ids[index])
        if class_id < 0 or class_id >= len(COCO_NAMES):
            continue
        label = COCO_NAMES[class_id]
        if normalize_name(label) in SKIP_LABELS:
            continue
        cx, cy, bw, bh = (float(v) for v in boxes[index])
        box = _map_box(cx, cy, bw, bh, pad_x, pad_y, new_w, new_h)
        if box is None:
            continue
        picked.append({"name": label, "box": box, "score": score})
    picked.sort(key=lambda row: row["score"], reverse=True)
    keep = _nms(picked)
    return keep[:MAX_DETS]


def _map_box(
    cx: float,
    cy: float,
    bw: float,
    bh: float,
    pad_x: float,
    pad_y: float,
    new_w: float,
    new_h: float,
) -> list[float] | None:
    if new_w <= 0 or new_h <= 0:
        return None
    x1 = (cx - bw / 2 - pad_x) / new_w
    y1 = (cy - bh / 2 - pad_y) / new_h
    x2 = (cx + bw / 2 - pad_x) / new_w
    y2 = (cy + bh / 2 - pad_y) / new_h
    return _clip_box([x1, y1, x2 - x1, y2 - y1])


def _clip_box(box: Any) -> list[float] | None:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        x, y, width, height = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    x2 = min(1.0, max(0.0, x + width))
    y2 = min(1.0, max(0.0, y + height))
    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    width = x2 - x
    height = y2 - y
    if width <= 0 or height <= 0:
        return None
    if x + width > 1:
        width = 1 - x
    if y + height > 1:
        height = 1 - y
    if width <= 0 or height <= 0:
        return None
    return [round(x, 6), round(y, 6), round(width, 6), round(height, 6)]


def _nms(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep: list[dict[str, Any]] = []
    for row in rows:
        if any(_iou(row["box"], kept["box"]) > IOU_MAX and row["name"] == kept["name"] for kept in keep):
            continue
        keep.append(row)
    return keep


def _iou(a: list[float], b: list[float]) -> float:
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    if union <= 0:
        return 0.0
    return inter / union


def _session(onnx_path: Path) -> tuple[Any, Any]:
    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError as exc:
        raise fail("dependency-missing") from exc
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    return session, np


def _ensure_runtime() -> None:
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        return
    except ImportError:
        pass
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *RUNTIME_PACKAGES],
        capture_output=True,
        text=True,
        check=False,
    )
    import importlib
    import site

    importlib.invalidate_caches()
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.append(user_site)
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
    except ImportError as exc:
        raise fail("dependency-missing") from exc
    if proc.returncode != 0:
        raise fail("dependency-missing")


def _download_model(dest: Path) -> None:
    last_error: Exception | None = None
    for url in MODEL_URLS:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "library-setup-ml"})
            with urllib.request.urlopen(request, timeout=120) as resp:
                data = resp.read()
            if not data or len(data) < 1_000_000:
                continue
            atomic_write_bytes(dest, data)
            if dest.is_file() and dest.stat().st_size == len(data):
                return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise fail("io-error") from last_error
    raise fail("io-error")


def _load_state(root: Path) -> dict[str, Any]:
    path = objects_state_path(root)
    if not path.is_file():
        return {"schemaVersion": 1, "items": {}}
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": 1, "items": {}}
    if not isinstance(data, dict):
        return {"schemaVersion": 1, "items": {}}
    items = data.get("items")
    if not isinstance(items, dict):
        items = {}
    return {"schemaVersion": 1, "items": items}


def _save_state(root: Path, state: dict[str, Any]) -> None:
    atomic_write_json(
        objects_state_path(root),
        {"schemaVersion": 1, "items": state.get("items") or {}},
    )
    try:
        from library.portable import mirror_objects

        mirror_objects(root)
    except Exception:
        return


def _already_analyzed(state: dict[str, Any], item_id: str, digest: str) -> bool:
    rec = (state.get("items") or {}).get(item_id)
    if not isinstance(rec, dict):
        return False
    return rec.get("sha256") == digest

