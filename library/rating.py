"""Photo rating: Basic technical scores, optional local Smart aesthetic, user stars.

Never deletes or auto-rejects. Processing skips unchanged size+mtime. User
stars / pick / reject always win over a suggestion.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_bytes, atomic_write_json, load_json, transact
from library.catalog_io import item_rel, iter_item_ids, load_item
from library.errors import fail
from library.history import make_history_entry, plan_append
from library.media import mtime_iso
from library.paths import library_path
from library.records import clone, ordered_item
from library.volumes import location_file, location_matches_stat

KIND = "rate"
QUEUE_ID = "rate"
MODEL_NAME = "nima-mobilenet.onnx"
ENGINE = "nima-mobilenet"
RUNTIME_PACKAGES = ("numpy", "onnxruntime")
BUILDER_PACKAGES = ("onnx", "numpy")
WORKING_SIDE = 1024
SMART_SIDE = 224
WEIGHTS_REL = "catalog/rating-weights.json"
WEIGHTS_SCHEMA = 1

DEFAULT_WEIGHTS = {
    "sharpness": 0.45,
    "exposure": 0.35,
    "face": 0.20,
}
SMART_BLEND = 0.35
LEARN_STEP = 0.03
FLAG_BLURRY = "blurry"
FLAG_DARK = "too-dark"
FLAG_BRIGHT = "too-bright"
FLAGS = frozenset({FLAG_BLURRY, FLAG_DARK, FLAG_BRIGHT})
QUALITY_STATUSES = frozenset({"ready", "unscored", "error"})
RATING_MODES = frozenset({"off", "basic", "smart"})
METRIC_KEYS = (
    "sharpness",
    "laplacianVar",
    "sharpnessNorm",
    "exposure",
    "meanBrightness",
    "contrast",
    "clipDark",
    "clipBright",
    "faceQuality",
    "faceCount",
    "faceSharpness",
    "aesthetic",
    "basic",
)
QUALITY_KEYS = (
    "schemaVersion",
    "status",
    "suggested",
    "stars",
    "pick",
    "reject",
    "flags",
    "metrics",
    "bestOfGroup",
    "mode",
    "sourceSizeBytes",
    "sourceModifiedAt",
    "model",
    "device",
)

MODEL_URLS = (
    "https://huggingface.co/cromsc/nima-mobilenet-aesthetic/resolve/main/nima_mobilenet_aesthetic.onnx",
    "https://huggingface.co/cromsc/nima-mobilenet-aesthetic/resolve/main/nima_mobilenet_aesthetic.onnx?download=true",
)

_SESSION: Any = None
_SESSION_PATH: str | None = None


def models_dir(root: Path) -> Path:
    return root / "models" / "aesthetic"


def model_path(root: Path) -> Path:
    return models_dir(root) / MODEL_NAME


def manifest_path(root: Path) -> Path:
    return models_dir(root) / "aesthetic.json"


def weights_path(root: Path) -> Path:
    return library_path(root, WEIGHTS_REL)


def model_installed(root: Path) -> bool:
    path = model_path(root)
    return path.is_file() and path.stat().st_size > 400


def rating_mode(root: Path) -> str:
    try:
        from library.settings import load_settings_file

        mode = load_settings_file(root).get("ratingMode", "basic")
    except Exception:
        return "basic"
    if type(mode) is not str or mode not in RATING_MODES:
        return "basic"
    return mode


def rating_learn(root: Path) -> bool:
    try:
        from library.settings import load_settings_file

        return bool(load_settings_file(root).get("ratingLearn", False))
    except Exception:
        return False


def rating_enabled(root: Path) -> bool:
    return rating_mode(root) != "off"


def _photo_like(item: dict[str, Any]) -> bool:
    return item.get("kind") in {"photo", "live"}


def empty_metrics() -> dict[str, Any]:
    return {key: None for key in METRIC_KEYS}


def empty_quality() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": "unscored",
        "suggested": None,
        "stars": None,
        "pick": False,
        "reject": False,
        "flags": [],
        "metrics": empty_metrics(),
        "bestOfGroup": False,
        "mode": None,
        "sourceSizeBytes": 0,
        "sourceModifiedAt": "",
        "model": None,
        "device": None,
    }


def read_quality(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise fail("invalid-catalog")
    extra = set(value) - set(QUALITY_KEYS)
    missing = set(QUALITY_KEYS) - set(value)
    if extra or missing:
        raise fail("invalid-catalog")
    if value["schemaVersion"] != 1:
        raise fail("invalid-catalog")
    status = value["status"]
    if type(status) is not str or status not in QUALITY_STATUSES:
        raise fail("invalid-catalog")
    suggested = value["suggested"]
    if suggested is not None and (type(suggested) is not int or suggested < 1 or suggested > 5):
        raise fail("invalid-catalog")
    stars = value["stars"]
    if stars is not None and (type(stars) is not int or stars < 1 or stars > 5):
        raise fail("invalid-catalog")
    if type(value["pick"]) is not bool or type(value["reject"]) is not bool:
        raise fail("invalid-catalog")
    if type(value["bestOfGroup"]) is not bool:
        raise fail("invalid-catalog")
    flags = value["flags"]
    if not isinstance(flags, list) or any(flag not in FLAGS for flag in flags):
        raise fail("invalid-catalog")
    metrics = _read_metrics(value["metrics"])
    mode = value["mode"]
    if mode is not None and (type(mode) is not str or mode not in RATING_MODES):
        raise fail("invalid-catalog")
    size = value["sourceSizeBytes"]
    if type(size) is not int or size < 0:
        raise fail("invalid-catalog")
    modified = value["sourceModifiedAt"]
    if type(modified) is not str:
        raise fail("invalid-catalog")
    model = value["model"]
    if model is not None and type(model) is not str:
        raise fail("invalid-catalog")
    device = value["device"]
    if device is not None and type(device) is not str:
        raise fail("invalid-catalog")
    return {
        "schemaVersion": 1,
        "status": status,
        "suggested": suggested,
        "stars": stars,
        "pick": value["pick"],
        "reject": value["reject"],
        "flags": [flag for flag in flags if flag in FLAGS],
        "metrics": metrics,
        "bestOfGroup": value["bestOfGroup"],
        "mode": mode,
        "sourceSizeBytes": size,
        "sourceModifiedAt": modified,
        "model": model,
        "device": device,
    }


def _read_metrics(value: Any) -> dict[str, Any]:
    if value is None:
        return empty_metrics()
    if not isinstance(value, dict):
        raise fail("invalid-catalog")
    extra = set(value) - set(METRIC_KEYS)
    if extra:
        raise fail("invalid-catalog")
    out = empty_metrics()
    for key in METRIC_KEYS:
        raw = value.get(key)
        if raw is None:
            continue
        if type(raw) is bool or not isinstance(raw, (int, float)):
            raise fail("invalid-catalog")
        number = float(raw)
        if not math.isfinite(number):
            raise fail("invalid-catalog")
        out[key] = number
    return out


def quality_view(item: dict[str, Any]) -> dict[str, Any]:
    rec = item.get("quality")
    if not isinstance(rec, dict):
        rec = empty_quality()
    yours = rec.get("stars")
    suggested = rec.get("suggested")
    effective = yours if type(yours) is int else suggested
    flags = [flag for flag in (rec.get("flags") or []) if flag in FLAGS]
    return {
        "suggested": suggested if type(suggested) is int else None,
        "yours": yours if type(yours) is int else None,
        "stars": effective if type(effective) is int else None,
        "pick": rec.get("pick") is True,
        "reject": rec.get("reject") is True,
        "flags": flags,
        "bestOfGroup": rec.get("bestOfGroup") is True,
        "mode": rec.get("mode"),
        "blurry": FLAG_BLURRY in flags,
    }


def effective_stars(item: dict[str, Any]) -> int | None:
    view = item.get("rating") if isinstance(item.get("rating"), dict) else quality_view(item)
    stars = view.get("stars")
    return stars if type(stars) is int else None


def read_rate_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {"itemId": None, "force": False}
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    extra = set(value) - {"itemId", "force"}
    if extra:
        raise fail("invalid-argument")
    item_id = value.get("itemId")
    if item_id is None:
        parsed_id = None
    else:
        if type(item_id) is not str or item_id == "":
            raise fail("invalid-argument")
        parsed_id = item_id
    force = value.get("force", False)
    if type(force) is not bool:
        raise fail("invalid-argument")
    return {"itemId": parsed_id, "force": force}


def read_user_rating_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise fail("invalid-argument")
    extra = set(body) - {"stars", "pick", "reject", "clear"}
    if extra:
        raise fail("invalid-argument")
    if not body:
        raise fail("invalid-argument")
    out: dict[str, Any] = {}
    if "clear" in body:
        if body.get("clear") is not True:
            raise fail("invalid-argument")
        out["clear"] = True
        return out
    if "stars" in body:
        stars = body.get("stars")
        if stars is not None and (type(stars) is not int or stars < 1 or stars > 5):
            raise fail("invalid-argument")
        out["stars"] = stars
    if "pick" in body:
        if type(body.get("pick")) is not bool:
            raise fail("invalid-argument")
        out["pick"] = body["pick"]
    if "reject" in body:
        if type(body.get("reject")) is not bool:
            raise fail("invalid-argument")
        out["reject"] = body["reject"]
    if not out:
        raise fail("invalid-argument")
    return out


def rate_status(root: Path) -> dict[str, Any]:
    mode = rating_mode(root)
    installed = model_installed(root)
    pending, done, error = rate_counts(root)
    available = mode != "off"
    return {
        "ok": True,
        "installed": installed,
        "enabled": available,
        "mode": mode,
        "learn": rating_learn(root),
        "model": MODEL_NAME if installed else None,
        "engine": ENGINE,
        "pending": pending if available else 0,
        "done": done,
        "error": error,
    }


def rate_counts(root: Path, items: list[dict[str, Any]] | None = None) -> tuple[int, int, int]:
    """Count from quality records. The worker still checks the original file."""
    from library.item_index import iter_item_ids as cached_ids
    from library.item_index import load_item as cached_item

    pending = 0
    done = 0
    error = 0
    enabled = rating_enabled(root)
    if items is None:
        rows = [cached_item(root, item_id) for item_id in cached_ids(root)]
    else:
        rows = items
    for item in rows:
        if not _photo_like(item):
            continue
        if not any(
            loc.get("current") is True and loc.get("component") == "still"
            for loc in item.get("locations") or []
        ):
            continue
        rec = item.get("quality")
        if isinstance(rec, dict) and rec.get("status") == "error":
            error += 1
            continue
        if isinstance(rec, dict) and rec.get("status") == "ready":
            done += 1
        elif enabled:
            pending += 1
    return pending, done, error


def setup_aesthetic(root: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    backend = "default"
    if payload is not None:
        if not isinstance(payload, dict) or set(payload) - {"backend"}:
            raise fail("invalid-argument")
        raw = payload.get("backend")
        if raw is None:
            backend = "default"
        elif type(raw) is not str or raw not in {"default", "fixture"}:
            raise fail("invalid-argument")
        else:
            backend = raw
    if backend == "fixture" and os.environ.get("LIBRARY_TEST") != "1":
        raise fail("invalid-argument")
    models_dir(root).mkdir(parents=True, exist_ok=True)
    _ensure_runtime()
    dest = model_path(root)
    kind = "fixture"
    if backend == "fixture" or os.environ.get("LIBRARY_TEST") == "1" and backend != "default":
        _write_compact_onnx(dest)
        kind = "fixture"
    else:
        downloaded = False
        if not model_installed(root) or dest.stat().st_size < 1_000_000:
            downloaded = _try_download_model(dest)
        if downloaded or (dest.is_file() and dest.stat().st_size > 1_000_000):
            kind = "nima-mobilenet"
        else:
            _write_compact_onnx(dest)
            kind = "fixture"
    if not dest.is_file() or dest.stat().st_size < 400:
        raise fail("io-error")
    digest = _sha256_file(dest)
    device = _pick_device()
    manifest = {
        "schemaVersion": 1,
        "kind": KIND,
        "model": MODEL_NAME,
        "engine": ENGINE,
        "backend": kind,
        "input": SMART_SIDE,
        "sha256": digest,
        "bytes": dest.stat().st_size,
        "device": device,
    }
    atomic_write_json(manifest_path(root), manifest)
    return {
        "ok": True,
        "kind": KIND,
        "model": MODEL_NAME,
        "engine": ENGINE,
        "backend": kind,
        "path": f"models/aesthetic/{MODEL_NAME}",
        "sha256": digest,
        "bytes": manifest["bytes"],
        "device": device,
    }


def rate_photos(root: Path, item_id: str | None = None, *, force: bool = False) -> dict[str, Any]:
    if not rating_enabled(root):
        return {"ok": True, "rated": 0, "skipped": 0, "errors": 0, "items": [], "mode": "off"}
    mode = rating_mode(root)
    if mode == "smart":
        try:
            _ensure_runtime()
        except Exception:
            pass
    force_one = bool(force)
    if item_id is not None:
        load_item(root, item_id)
        ids = [item_id]
    else:
        ids = iter_item_ids(root)
    rated = 0
    skipped = 0
    errors = 0
    items: list[dict[str, Any]] = []
    for current_id in ids:
        item = load_item(root, current_id)
        if not _photo_like(item):
            skipped += 1
            continue
        still = _current_still_file(item, root)
        if still is None:
            skipped += 1
            continue
        if not force_one and _already_scored(item, still):
            skipped += 1
            continue
        try:
            record = _rate_one(root, current_id, still)
        except Exception:
            _publish_quality(root, current_id, _error_record(item, still, mode))
            errors += 1
            continue
        rated += 1
        items.append(
            {
                "id": current_id,
                "suggested": record.get("suggested"),
                "flags": record.get("flags") or [],
                "bestOfGroup": record.get("bestOfGroup"),
            }
        )
    refresh_best_of_groups(root)
    return {
        "ok": True,
        "rated": rated,
        "skipped": skipped,
        "errors": errors,
        "items": items,
        "mode": mode,
    }


def rate_step(root: Path) -> bool:
    if not rating_enabled(root):
        return False
    mode = rating_mode(root)
    if mode == "smart":
        try:
            _ensure_runtime()
        except Exception:
            pass
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        if not _photo_like(item):
            continue
        still = _current_still_file(item, root)
        if still is None:
            continue
        if _already_scored(item, still):
            continue
        from library.activity import note_item

        note_item("rate", "Rating", item)
        try:
            _rate_one(root, item_id, still)
        except Exception:
            _publish_quality(root, item_id, _error_record(item, still, mode))
        refresh_best_of_groups(root)
        return True
    return False


def apply_user_rating(root: Path, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    from library.catalog_io import item_read
    from library.favorites import favorite_ids

    if type(item_id) is not str or not item_id:
        raise fail("invalid-argument")
    item = load_item(root, item_id)
    before = item
    after = clone(item)
    current = read_quality(item.get("quality")) or empty_quality()
    if patch.get("clear"):
        current["stars"] = None
        current["pick"] = False
        current["reject"] = False
    else:
        if "stars" in patch:
            current["stars"] = patch["stars"]
        if "pick" in patch:
            current["pick"] = patch["pick"]
            if patch["pick"]:
                current["reject"] = False
        if "reject" in patch:
            current["reject"] = patch["reject"]
            if patch["reject"]:
                current["pick"] = False
    after["quality"] = current
    after = ordered_item(after)
    if before == after:
        return item_read(after, root, favorite_ids(root))
    file_change = {"path": item_rel(item_id), "before": before, "after": after}
    entry = make_history_entry(root, "rate", [file_change])
    transact(root, plan_append(root, entry) + [file_change])
    if rating_learn(root) and not patch.get("clear"):
        _nudge_weights(root, current, patch)
    return item_read(load_item(root, item_id), root, favorite_ids(root))


def reset_rating_weights(root: Path) -> dict[str, Any]:
    path = weights_path(root)
    before = _load_weights_file(root)
    after = _default_weights_record()
    if path.exists():
        file_change = {"path": WEIGHTS_REL, "before": before, "after": after}
        entry = make_history_entry(root, "rate", [file_change])
        transact(root, plan_append(root, entry) + [file_change])
    return {"ok": True, "weights": _active_weights(root), "reset": True}


def read_weights_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict) or set(body) - {"reset"}:
        raise fail("invalid-argument")
    if body.get("reset") is not True:
        raise fail("invalid-argument")
    return {"reset": True}


def _already_scored(item: dict[str, Any], still: Path) -> bool:
    rec = item.get("quality")
    if not isinstance(rec, dict):
        return False
    if rec.get("status") not in {"ready", "error"}:
        return False
    try:
        stat = still.stat()
    except OSError:
        return False
    size = rec.get("sourceSizeBytes")
    modified = rec.get("sourceModifiedAt")
    if size != int(stat.st_size):
        return False
    if type(modified) is not str or modified == "":
        return False
    return modified == mtime_iso(still)


def _current_still_file(item: dict[str, Any], root: Path) -> Path | None:
    wanted = "still"
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == wanted
    ]
    if not candidates:
        candidates = [loc for loc in item.get("locations") or [] if loc.get("current") is True]
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


def _rate_one(root: Path, item_id: str, still: Path) -> dict[str, Any]:
    item = load_item(root, item_id)
    mode = rating_mode(root)
    rgb, width, height = decode_rgb(still, WORKING_SIDE)
    metrics = compute_basic(rgb, width, height, item.get("faces") or [])
    aesthetic = None
    device = None
    model_name = None
    if mode == "smart" and model_installed(root):
        try:
            aesthetic, device = compute_smart(root, still)
            model_name = MODEL_NAME
        except Exception:
            aesthetic = None
    metrics["aesthetic"] = aesthetic
    weights = _active_weights(root)
    suggested, flags, basic = combine_score(metrics, mode, weights, aesthetic)
    metrics["basic"] = basic
    record = read_quality(item.get("quality")) or empty_quality()
    record["status"] = "ready"
    record["suggested"] = suggested
    record["flags"] = flags
    record["metrics"] = metrics
    record["mode"] = mode
    record["sourceSizeBytes"] = int(still.stat().st_size)
    record["sourceModifiedAt"] = mtime_iso(still)
    record["model"] = model_name
    record["device"] = device
    _publish_quality(root, item_id, record)
    return record


def _error_record(item: dict[str, Any], still: Path, mode: str) -> dict[str, Any]:
    record = read_quality(item.get("quality")) or empty_quality()
    record["status"] = "error"
    record["mode"] = mode
    try:
        record["sourceSizeBytes"] = int(still.stat().st_size)
        record["sourceModifiedAt"] = mtime_iso(still)
    except OSError:
        pass
    return record


def _publish_quality(root: Path, item_id: str, record: dict[str, Any]) -> None:
    before = load_item(root, item_id)
    after = clone(before)
    kept = read_quality(before.get("quality")) or empty_quality()
    merged = dict(record)
    merged["stars"] = kept.get("stars")
    merged["pick"] = kept.get("pick") is True
    merged["reject"] = kept.get("reject") is True
    if "bestOfGroup" not in merged:
        merged["bestOfGroup"] = kept.get("bestOfGroup") is True
    after["quality"] = merged
    after = ordered_item(after)
    if before == after:
        return
    transact(root, [{"path": item_rel(item_id), "before": before, "after": after}])


def decode_rgb(path: Path, max_side: int) -> tuple[bytes, int, int]:
    width, height = _probe_size(path)
    if width is None or height is None or width <= 0 or height <= 0:
        raise fail("decode-error")
    work_w, work_h = _working_size(width, height, max_side)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"scale={work_w}:{work_h}",
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
    expected = work_w * work_h * 3
    if proc.returncode != 0 or len(proc.stdout) != expected:
        raise fail("decode-error")
    return proc.stdout, work_w, work_h


def _working_size(width: int, height: int, cap: int) -> tuple[int, int]:
    if max(width, height) <= cap:
        return width, height
    if width >= height:
        return cap, max(1, int(round(height * cap / width)))
    return max(1, int(round(width * cap / height))), cap


def _probe_size(path: Path) -> tuple[int | None, int | None]:
    from library.media import ffprobe_json

    try:
        probe = ffprobe_json(path)
    except Exception:
        return None, None
    streams = probe.get("streams") if isinstance(probe, dict) else None
    if not isinstance(streams, list):
        return None, None
    for stream in streams:
        if not isinstance(stream, dict) or stream.get("codec_type") != "video":
            continue
        width = stream.get("width")
        height = stream.get("height")
        if type(width) is int and type(height) is int and width > 0 and height > 0:
            return width, height
    return None, None


def _gray_luma(rgb: bytes, width: int, height: int) -> list[int]:
    gray: list[int] = []
    pixels = width * height
    for i in range(pixels):
        o = i * 3
        r, g, b = rgb[o], rgb[o + 1], rgb[o + 2]
        gray.append((r * 299 + g * 587 + b * 114) // 1000)
    return gray


def laplacian_var(gray: list[int], width: int, height: int) -> float:
    if width < 3 or height < 3:
        return 0.0
    acc = 0.0
    acc2 = 0.0
    n = 0
    for y in range(1, height - 1):
        row = y * width
        up = row - width
        down = row + width
        for x in range(1, width - 1):
            v = gray[up + x] + gray[down + x] + gray[row + x - 1] + gray[row + x + 1] - 4 * gray[row + x]
            acc += v
            acc2 += v * v
            n += 1
    if n <= 0:
        return 0.0
    mean = acc / n
    return max(0.0, acc2 / n - mean * mean)


def sharpness_score(variance: float, width: int, height: int) -> tuple[float, float]:
    pixels = max(1, width * height)
    # Variance of Laplacian grows with megapixels on the same scene; normalize.
    megapixels = pixels / 1_000_000.0
    norm = variance / max(0.25, megapixels)
    score = 1.0 - math.exp(-norm / 90.0)
    return max(0.0, min(1.0, score)), norm


def compute_basic(
    rgb: bytes,
    width: int,
    height: int,
    faces: list[dict[str, Any]],
) -> dict[str, Any]:
    gray = _gray_luma(rgb, width, height)
    variance = laplacian_var(gray, width, height)
    sharp, sharp_norm = sharpness_score(variance, width, height)
    hist = [0] * 256
    total = 0.0
    total2 = 0.0
    for value in gray:
        hist[value] += 1
        total += value
        total2 += value * value
    count = max(1, len(gray))
    mean = total / count / 255.0
    second = total2 / count
    contrast = math.sqrt(max(0.0, second - (total / count) ** 2)) / 128.0
    contrast = max(0.0, min(1.0, contrast))
    clip_dark = sum(hist[:8]) / count
    clip_bright = sum(hist[248:]) / count
    exposure = _exposure_score(mean, contrast, clip_dark, clip_bright)
    face_q, face_count, face_sharp = _face_quality(rgb, gray, width, height, faces)
    metrics = empty_metrics()
    metrics.update(
        {
            "sharpness": sharp,
            "laplacianVar": variance,
            "sharpnessNorm": sharp_norm,
            "exposure": exposure,
            "meanBrightness": mean,
            "contrast": contrast,
            "clipDark": clip_dark,
            "clipBright": clip_bright,
            "faceQuality": face_q,
            "faceCount": float(face_count),
            "faceSharpness": face_sharp,
            "aesthetic": None,
            "basic": None,
        }
    )
    return metrics


def _exposure_score(mean: float, contrast: float, clip_dark: float, clip_bright: float) -> float:
    mid = 1.0 - min(1.0, abs(mean - 0.48) / 0.48)
    clip = min(1.0, clip_dark * 2.2 + clip_bright * 2.2)
    contrast_term = min(1.0, contrast / 0.55)
    score = 0.55 * mid + 0.25 * (1.0 - clip) + 0.20 * contrast_term
    return max(0.0, min(1.0, score))


def _face_quality(
    rgb: bytes,
    gray: list[int],
    width: int,
    height: int,
    faces: list[dict[str, Any]],
) -> tuple[float, int, float]:
    scores: list[float] = []
    sharps: list[float] = []
    for face in faces:
        if not isinstance(face, dict):
            continue
        box = face.get("box")
        if not isinstance(box, list) or len(box) != 4:
            continue
        try:
            x, y, w, h = (float(v) for v in box)
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        px = max(0, min(width - 1, int(x * width)))
        py = max(0, min(height - 1, int(y * height)))
        pw = max(1, min(width - px, int(w * width)))
        ph = max(1, min(height - py, int(h * height)))
        crop: list[int] = []
        for row in range(py, py + ph):
            start = row * width + px
            crop.extend(gray[start : start + pw])
        if len(crop) < 9:
            continue
        var = laplacian_var(crop, pw, ph)
        face_sharp, _ = sharpness_score(var, pw, ph)
        short = min(pw, ph)
        size_score = max(0.0, min(1.0, short / 160.0))
        scores.append(0.5 * size_score + 0.5 * face_sharp)
        sharps.append(face_sharp)
    if not scores:
        return 0.0, 0, 0.0
    return max(scores), len(scores), max(sharps)


def combine_score(
    metrics: dict[str, Any],
    mode: str,
    weights: dict[str, float],
    aesthetic: float | None,
) -> tuple[int, list[str], float]:
    sharp = float(metrics.get("sharpness") or 0.0)
    exposure = float(metrics.get("exposure") or 0.0)
    face = float(metrics.get("faceQuality") or 0.0)
    face_count = int(metrics.get("faceCount") or 0)
    w_s = float(weights.get("sharpness") or DEFAULT_WEIGHTS["sharpness"])
    w_e = float(weights.get("exposure") or DEFAULT_WEIGHTS["exposure"])
    w_f = float(weights.get("face") or DEFAULT_WEIGHTS["face"])
    if face_count <= 0:
        w_f = 0.0
    total = w_s + w_e + w_f
    if total <= 0:
        w_s, w_e, w_f, total = 0.45, 0.35, 0.0, 0.80
    basic = (w_s * sharp + w_e * exposure + w_f * face) / total
    blended = basic
    if mode == "smart" and aesthetic is not None:
        blended = (1.0 - SMART_BLEND) * basic + SMART_BLEND * max(0.0, min(1.0, aesthetic))
    suggested = int(max(1, min(5, round(1.0 + 4.0 * blended))))
    flags: list[str] = []
    if sharp < 0.28:
        flags.append(FLAG_BLURRY)
    mean = float(metrics.get("meanBrightness") or 0.0)
    clip_dark = float(metrics.get("clipDark") or 0.0)
    clip_bright = float(metrics.get("clipBright") or 0.0)
    if mean < 0.18 or clip_dark > 0.35:
        flags.append(FLAG_DARK)
    if mean > 0.88 or clip_bright > 0.22:
        flags.append(FLAG_BRIGHT)
    return suggested, flags, blended


def compute_smart(root: Path, still: Path) -> tuple[float, str]:
    session, np_mod, device = _smart_session(root)
    tensor = _smart_tensor(still, session, np_mod)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: tensor})
    if not outputs:
        raise fail("decode-error")
    score = _nima_mean(outputs[0], np_mod)
    return max(0.0, min(1.0, score)), device


def _smart_tensor(still: Path, session: Any, np_mod: Any) -> Any:
    width, height = SMART_SIDE, SMART_SIDE
    try:
        shape = session.get_inputs()[0].shape
        if isinstance(shape, (list, tuple)) and len(shape) == 4:
            if type(shape[2]) is int and type(shape[3]) is int and shape[2] > 0:
                height = int(shape[2])
                width = int(shape[3])
            elif type(shape[1]) is int and type(shape[2]) is int and shape[1] > 8:
                height = int(shape[1])
                width = int(shape[2])
    except Exception:
        pass
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(still),
            "-vf",
            (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
            ),
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
    expected = width * height * 3
    if proc.returncode != 0 or len(proc.stdout) != expected:
        raise fail("decode-error")
    arr = np_mod.frombuffer(proc.stdout, dtype=np_mod.uint8).reshape(1, height, width, 3)
    arr = arr.astype("float32") / 255.0
    if _compact_model(session):
        return np_mod.transpose(arr, (0, 3, 1, 2))
    mean = np_mod.array([0.485, 0.456, 0.406], dtype="float32").reshape(1, 1, 1, 3)
    std = np_mod.array([0.229, 0.224, 0.225], dtype="float32").reshape(1, 1, 1, 3)
    arr = (arr - mean) / std
    arr = np_mod.transpose(arr, (0, 3, 1, 2))
    return arr


def _compact_model(session: Any) -> bool:
    try:
        meta = session.get_modelmeta()
        if getattr(meta, "graph_name", "") == "library-aesthetic":
            return True
    except Exception:
        pass
    try:
        path = session._model_path  # type: ignore[attr-defined]
        return bool(path) and Path(str(path)).stat().st_size < 10_000
    except Exception:
        return False


def _nima_mean(raw: Any, np_mod: Any) -> float:
    arr = np_mod.asarray(raw, dtype="float32").reshape(-1)
    if arr.size == 1:
        value = float(arr[0])
        if 0.0 <= value <= 1.0:
            return value
        if 1.0 <= value <= 10.0:
            return (value - 1.0) / 9.0
        return max(0.0, min(1.0, value / 10.0))
    if arr.size >= 10:
        bins = arr[:10]
        bins = bins - np_mod.max(bins)
        exp = np_mod.exp(bins)
        probs = exp / np_mod.maximum(np_mod.sum(exp), 1e-8)
        nima = float(np_mod.sum(probs * np_mod.arange(1, 11, dtype="float32")))
        return (nima - 1.0) / 9.0
    return float(max(0.0, min(1.0, arr.mean())))


def _smart_session(root: Path) -> tuple[Any, Any, str]:
    global _SESSION, _SESSION_PATH
    dest = model_path(root)
    device = _pick_device()
    key = f"{dest}:{dest.stat().st_mtime_ns}:{device}"
    if _SESSION is not None and _SESSION_PATH == key:
        import numpy as np

        return _SESSION, np, device
    import numpy as np
    import onnxruntime as ort

    providers = ["CPUExecutionProvider"]
    if device == "cuda":
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(str(dest), providers=providers)
    _SESSION = session
    _SESSION_PATH = key
    return session, np, device


def _pick_device() -> str:
    try:
        import onnxruntime as ort

        if "CUDAExecutionProvider" in ort.get_available_providers():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def refresh_best_of_groups(root: Path) -> None:
    from library.duplicates import list_duplicate_groups
    from library.stacks import annotate_stacks

    items = [load_item(root, item_id) for item_id in iter_item_ids(root)]
    annotate_stacks(items)
    groups: list[list[str]] = []
    seen: set[str] = set()
    for item in items:
        stack = item.get("stack")
        if not isinstance(stack, dict):
            continue
        ids = [item_id for item_id in (stack.get("itemIds") or []) if type(item_id) is str]
        key = stack.get("id") or ",".join(ids)
        if len(ids) < 2 or key in seen:
            continue
        seen.add(str(key))
        groups.append(ids)
    for group in list_duplicate_groups(items):
        ids = [item_id for item_id in (group.get("itemIds") or []) if type(item_id) is str]
        key = group.get("key") or ",".join(ids)
        if len(ids) < 2 or key in seen:
            continue
        seen.add(str(key))
        groups.append(ids)
    by_id = {item["id"]: item for item in items if type(item.get("id")) is str}
    for ids in groups:
        winner = _best_of(ids, by_id)
        if winner is None:
            continue
        for item_id in ids:
            item = by_id.get(item_id)
            if item is None:
                continue
            rec = read_quality(item.get("quality"))
            if rec is None:
                continue
            want = item_id == winner
            if rec.get("bestOfGroup") is want:
                continue
            rec["bestOfGroup"] = want
            _publish_quality(root, item_id, rec)
            item["quality"] = rec


def _best_of(ids: list[str], by_id: dict[str, dict[str, Any]]) -> str | None:
    ranked: list[tuple[float, float, str]] = []
    for item_id in ids:
        item = by_id.get(item_id)
        if item is None:
            continue
        rec = item.get("quality") if isinstance(item.get("quality"), dict) else {}
        if rec.get("status") != "ready":
            continue
        metrics = rec.get("metrics") if isinstance(rec.get("metrics"), dict) else {}
        basic = metrics.get("basic")
        sharp = metrics.get("sharpness")
        suggested = rec.get("suggested")
        score = float(basic) if isinstance(basic, (int, float)) else (float(suggested) / 5.0 if type(suggested) is int else 0.0)
        sharpness = float(sharp) if isinstance(sharp, (int, float)) else 0.0
        ranked.append((score, sharpness, item_id))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][2]


def default_weights() -> dict[str, float]:
    return dict(DEFAULT_WEIGHTS)


def _default_weights_record() -> dict[str, Any]:
    return {"schemaVersion": WEIGHTS_SCHEMA, **default_weights()}


def _load_weights_file(root: Path) -> dict[str, Any] | None:
    path = weights_path(root)
    if not path.is_file():
        return None
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _active_weights(root: Path) -> dict[str, float]:
    if not rating_learn(root):
        return default_weights()
    data = _load_weights_file(root)
    if not isinstance(data, dict):
        return default_weights()
    out = default_weights()
    for key in out:
        raw = data.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(float(raw)):
            out[key] = max(0.05, min(0.85, float(raw)))
    total = sum(out.values())
    if total <= 0:
        return default_weights()
    return {key: value / total for key, value in out.items()}


def _nudge_weights(root: Path, quality: dict[str, Any], patch: dict[str, Any]) -> None:
    metrics = quality.get("metrics") if isinstance(quality.get("metrics"), dict) else {}
    if not metrics:
        return
    current = _active_weights(root)
    sign = 0.0
    if patch.get("pick") is True or (type(patch.get("stars")) is int and patch["stars"] >= 4):
        sign = 1.0
    elif patch.get("reject") is True or (type(patch.get("stars")) is int and patch["stars"] <= 2):
        sign = -1.0
    if sign == 0.0:
        return
    mapping = {
        "sharpness": float(metrics.get("sharpness") or 0.0),
        "exposure": float(metrics.get("exposure") or 0.0),
        "face": float(metrics.get("faceQuality") or 0.0),
    }
    next_weights = dict(current)
    for key, value in mapping.items():
        next_weights[key] = max(0.05, min(0.85, current[key] + sign * LEARN_STEP * (value - 0.5)))
    total = sum(next_weights.values())
    if total <= 0:
        return
    record = {"schemaVersion": WEIGHTS_SCHEMA, **{key: next_weights[key] / total for key in next_weights}}
    before = _load_weights_file(root)
    file_change = {"path": WEIGHTS_REL, "before": before, "after": record}
    transact(root, [file_change])


def _try_download_model(dest: Path) -> bool:
    for url in MODEL_URLS:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "library-setup-ml"})
            with urllib.request.urlopen(request, timeout=180) as resp:
                data = resp.read()
            if not data or len(data) < 1_000_000:
                continue
            atomic_write_bytes(dest, data)
            if dest.is_file() and dest.stat().st_size == len(data):
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return False


def _write_compact_onnx(dest: Path) -> None:
    _ensure_onnx_builder()
    import numpy as np
    from onnx import TensorProto, helper, numpy_helper, save

    x = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, SMART_SIDE, SMART_SIDE])
    y = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 10])
    scale = numpy_helper.from_array(
        np.array([[0.0, 0.4, 0.8, 1.2, 1.8, 2.6, 3.4, 4.2, 3.0, 1.5]], dtype=np.float32),
        name="scale",
    )
    bias = numpy_helper.from_array(
        np.array([[3.5, 4.0, 3.2, 2.0, 1.0, 0.4, 0.1, 0.0, 0.0, 0.0]], dtype=np.float32),
        name="bias",
    )
    nodes = [
        helper.make_node("Split", ["input"], ["r", "g", "b"], axis=1, split=[1, 1, 1]),
        helper.make_node("Sub", ["r", "g"], ["rg"]),
        helper.make_node("Sub", ["g", "b"], ["gb"]),
        helper.make_node("Sub", ["b", "r"], ["br"]),
        helper.make_node("Abs", ["rg"], ["arg"]),
        helper.make_node("Abs", ["gb"], ["agb"]),
        helper.make_node("Abs", ["br"], ["abr"]),
        helper.make_node("Add", ["arg", "agb"], ["ab1"]),
        helper.make_node("Add", ["ab1", "abr"], ["sat"]),
        helper.make_node("ReduceMean", ["sat"], ["color"], axes=[2, 3], keepdims=0),
        helper.make_node("MatMul", ["color", "scale"], ["scaled"]),
        helper.make_node("Add", ["scaled", "bias"], ["output"]),
    ]
    graph = helper.make_graph(nodes, "library-aesthetic", [x], [y], [scale, bias])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 11)], ir_version=7)
    dest.parent.mkdir(parents=True, exist_ok=True)
    save(model, str(dest))


def _ensure_runtime() -> None:
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401

        return
    except ImportError:
        pass
    _pip_install(RUNTIME_PACKAGES)
    _import_or_fail(("numpy", "onnxruntime"))


def _ensure_onnx_builder() -> None:
    try:
        import numpy  # noqa: F401
        import onnx  # noqa: F401

        return
    except ImportError:
        pass
    _pip_install(BUILDER_PACKAGES)
    _import_or_fail(("numpy", "onnx"))


def _pip_install(packages: tuple[str, ...]) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *packages],
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


def _import_or_fail(names: tuple[str, ...]) -> None:
    for name in names:
        try:
            __import__(name)
        except ImportError as exc:
            raise fail("dependency-missing") from exc


def _sha256_file(path: Path) -> str:
    from library.media import sha256_file

    return sha256_file(path)
