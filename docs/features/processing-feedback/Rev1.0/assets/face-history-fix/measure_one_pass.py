"""Time three ways to preview a still and detect faces.

A is today's path: encode a 1600 px preview from the original, then decode
the original again for InsightFace.
B is one ffmpeg process: the same preview plus a full-resolution upright RGB
temp file, then detect on that RGB.
C detects on the 1600 px preview instead of the original.

Writes measure-one-pass.json next to this script. Does not touch the library.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"J:\slyOS\projects\photoLibrary")
sys.path.insert(0, str(ROOT))

from library.faces import detect_insightface  # noqa: E402
from library.media import _upright_size, decode_still_rgb, run_ffmpeg  # noqa: E402
from library.metadata import exif_orientation  # noqa: E402
from library.renditions import WEBP_ENCODE, _scale_filter  # noqa: E402

LIBRARY = ROOT / "library-data"
PICTURES = Path(r"J:\Pictures\1. Favorites Pictures")
OUT = Path(__file__).resolve().parent / "measure-one-pass.json"
PREVIEW_CAP = 1600
SAMPLE = 16
PRIORITY = {"creationflags": 0x00004000} if os.name == "nt" else {}


def sample_photos() -> list[Path]:
    files = sorted(PICTURES.glob("*.JPG")) + sorted(PICTURES.glob("*.jpg"))
    buckets: dict[int, list[Path]] = {}
    for path in files:
        try:
            orient = exif_orientation(path)
        except Exception:
            orient = 0
        buckets.setdefault(orient, []).append(path)
    picked: list[Path] = []
    # Spread orientations first, then fill from the largest buckets.
    order = sorted(buckets, key=lambda key: (-len(buckets[key]), key))
    while len(picked) < SAMPLE and any(buckets[key] for key in order):
        for key in order:
            if buckets[key] and len(picked) < SAMPLE:
                picked.append(buckets[key].pop(len(buckets[key]) // 2))
    return picked


def iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2, bx2, by2 = ax + aw, ay + ah, bx + bw, by + bh
    iw = max(0.0, min(ax2, bx2) - max(ax, bx))
    ih = max(0.0, min(ay2, by2) - max(ay, by))
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def match_faces(left: list[dict], right: list[dict]) -> dict:
    pairs = []
    for i, face in enumerate(left):
        for j, other in enumerate(right):
            score = iou(face["box"], other["box"])
            if score > 0.5:
                pairs.append((score, i, j))
    pairs.sort(reverse=True)
    used_l: set[int] = set()
    used_r: set[int] = set()
    cosines = []
    for score, i, j in pairs:
        if i in used_l or j in used_r:
            continue
        used_l.add(i)
        used_r.add(j)
        emb_a = left[i]["embedding"]
        emb_b = right[j]["embedding"]
        cosines.append(sum(x * y for x, y in zip(emb_a, emb_b)))
    return {
        "facesA": len(left),
        "facesC": len(right),
        "matched": len(cosines),
        "missedByC": len(left) - len(used_l),
        "extraInC": len(right) - len(used_r),
        "cosineMean": (sum(cosines) / len(cosines)) if cosines else None,
        "cosineMin": min(cosines) if cosines else None,
    }


def write_preview(source: Path, dest: Path) -> bool:
    from library.renditions import write_webp

    return write_webp(source, dest, PREVIEW_CAP)


def one_ffmpeg(source: Path, preview: Path, rgb_path: Path, width: int, height: int) -> tuple[bool, str]:
    scale = _scale_filter(PREVIEW_CAP)
    preview.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source),
        "-filter_complex",
        f"[0:v]split=2[full][prev];[prev]{scale}[p]",
        "-map",
        "[p]",
        "-frames:v",
        "1",
        *WEBP_ENCODE,
        str(preview),
        "-map",
        "[full]",
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        str(rgb_path),
    ]
    proc = run_ffmpeg(cmd, **PRIORITY)
    expected = width * height * 3
    size = rgb_path.stat().st_size if rgb_path.is_file() else 0
    ok = proc.returncode == 0 and preview.is_file() and preview.stat().st_size > 0 and size >= expected
    err = (proc.stderr or b"").decode("utf-8", "replace")[-400:]
    return ok, err if not ok else ""


def detect(width: int, height: int, rgb: bytes) -> tuple[float, list[dict]]:
    started = time.perf_counter()
    faces = detect_insightface(LIBRARY, width, height, rgb)
    return time.perf_counter() - started, faces


def slim(face: dict) -> dict:
    return {"box": face["box"], "embedding": face["embedding"]}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> None:
    photos = sample_photos()
    if len(photos) < 10:
        raise SystemExit(f"need at least 10 photos, found {len(photos)}")
    work = Path(tempfile.mkdtemp(prefix="one-pass-"))
    # Warm the ONNX sessions on the first photo so photo timings are the work.
    warm_w, warm_h, warm_rgb = decode_still_rgb(photos[0])
    detect(warm_w, warm_h, warm_rgb)

    rows = []
    for index, path in enumerate(photos):
        width, height = _upright_size(path)
        row: dict = {
            "file": path.name,
            "orient": exif_orientation(path),
            "upright": [width, height],
            "megapixels": round(width * height / 1e6, 2),
        }
        preview_a = work / f"a-{index}.webp"
        preview_b = work / f"b-{index}.webp"
        rgb_b = work / f"b-{index}.rgb"

        started = time.perf_counter()
        preview_ok = write_preview(path, preview_a)
        t_preview = time.perf_counter() - started
        started = time.perf_counter()
        aw, ah, argb = decode_still_rgb(path)
        t_decode = time.perf_counter() - started
        t_det_a, faces_a = detect(aw, ah, argb)
        row["A"] = {
            "previewSec": round(t_preview, 3),
            "decodeSec": round(t_decode, 3),
            "detectSec": round(t_det_a, 3),
            "totalSec": round(t_preview + t_decode + t_det_a, 3),
            "faces": len(faces_a),
            "previewOk": preview_ok,
        }

        started = time.perf_counter()
        b_ok, b_err = one_ffmpeg(path, preview_b, rgb_b, width, height)
        t_ffmpeg = time.perf_counter() - started
        t_det_b = None
        rgb_same = False
        if b_ok:
            brgb = rgb_b.read_bytes()[: width * height * 3]
            rgb_same = brgb == argb
            t_det_b, faces_b = detect(width, height, brgb)
            row["B"] = {
                "ffmpegSec": round(t_ffmpeg, 3),
                "detectSec": round(t_det_b, 3),
                "totalSec": round(t_ffmpeg + t_det_b, 3),
                "faces": len(faces_b),
                "rgbIdenticalToA": rgb_same,
                "previewBytes": preview_b.stat().st_size,
            }
        else:
            row["B"] = {"ok": False, "error": b_err, "ffmpegSec": round(t_ffmpeg, 3)}

        started = time.perf_counter()
        cw, ch, crgb = decode_still_rgb(preview_a)
        t_decode_c = time.perf_counter() - started
        t_det_c, faces_c = detect(cw, ch, crgb)
        compared = match_faces([slim(face) for face in faces_a], [slim(face) for face in faces_c])
        row["C"] = {
            "previewSize": [cw, ch],
            "decodeSec": round(t_decode_c, 3),
            "detectSec": round(t_det_c, 3),
            "totalSec": round(t_preview + t_decode_c + t_det_c, 3),
            **compared,
        }
        rows.append(row)
        for leftover in (preview_a, preview_b, rgb_b):
            leftover.unlink(missing_ok=True)
        print(
            f"{path.name} {width}x{height} A {row['A']['totalSec']}s "
            f"B {row['B'].get('totalSec')} rgb={row['B'].get('rgbIdenticalToA')} "
            f"C faces {compared['facesC']}/{compared['facesA']} cos {compared['cosineMean']}",
            flush=True,
        )

    def col(path_key: str, field: str) -> list[float]:
        return [float(row[path_key][field]) for row in rows if field in row[path_key]]

    summary = {
        "photos": len(rows),
        "A_mean_totalSec": round(mean(col("A", "totalSec")) or 0, 3),
        "A_mean_previewSec": round(mean(col("A", "previewSec")) or 0, 3),
        "A_mean_decodeSec": round(mean(col("A", "decodeSec")) or 0, 3),
        "A_mean_detectSec": round(mean(col("A", "detectSec")) or 0, 3),
        "B_mean_totalSec": round(mean(col("B", "totalSec")) or 0, 3),
        "B_mean_ffmpegSec": round(mean(col("B", "ffmpegSec")) or 0, 3),
        "B_mean_detectSec": round(mean(col("B", "detectSec")) or 0, 3),
        "B_rgb_identical": sum(1 for row in rows if row["B"].get("rgbIdenticalToA")),
        "C_mean_totalSec": round(mean(col("C", "totalSec")) or 0, 3),
        "C_mean_detectSec": round(mean(col("C", "detectSec")) or 0, 3),
        "C_faces_vs_A": {
            "facesA": sum(row["C"]["facesA"] for row in rows),
            "facesC": sum(row["C"]["facesC"] for row in rows),
            "matched": sum(row["C"]["matched"] for row in rows),
            "missedByC": sum(row["C"]["missedByC"] for row in rows),
            "extraInC": sum(row["C"]["extraInC"] for row in rows),
        },
        "C_cosine_mean": None,
    }
    cosines = [row["C"]["cosineMean"] for row in rows if row["C"]["cosineMean"] is not None]
    if cosines:
        summary["C_cosine_mean"] = round(sum(cosines) / len(cosines), 4)
        summary["C_cosine_min"] = round(min(row["C"]["cosineMin"] for row in rows if row["C"]["cosineMin"] is not None), 4)

    a_total = summary["A_mean_totalSec"]
    b_total = summary["B_mean_totalSec"]
    saved = round(a_total - b_total, 3)
    identical = summary["B_rgb_identical"] == len(rows) and summary["B_rgb_identical"] > 0
    c_faces = summary["C_faces_vs_A"]
    c_miss = c_faces["missedByC"]
    c_extra = c_faces["extraInC"]
    cosine = summary["C_cosine_mean"]
    c_quality_loss = c_miss > 0 or c_extra > 0 or (cosine is not None and cosine < 0.98)
    c_sentence = (
        f" C found {c_faces['facesC']} faces against A's {c_faces['facesA']} "
        f"({c_miss} missed, {c_extra} extra, cosine mean {cosine})."
    )
    if identical and saved >= 0.1:
        recommendation = (
            "B is a clear win: the full-resolution RGB matches today's decode on every "
            f"photo and the mean drops by {saved}s. Make the combined ffmpeg the default "
            "preview+face decode. No new setting."
        )
        adopt = "B"
    elif identical:
        recommendation = (
            f"B matches today's pixels. Mean A {a_total}s, mean B {b_total}s "
            f"(B minus A = {round(b_total - a_total, 3)}s). A gap under a tenth of a "
            "second is the second JPEG decode, not enough to retile the pipeline."
        )
        adopt = None
    else:
        recommendation = (
            "Do not ship B. Its RGB did not match today's upright decode, so face "
            "fingerprints would move."
        )
        adopt = None
    if c_quality_loss:
        recommendation += " Do not detect on the 1600 px preview." + c_sentence
        if adopt == "B":
            recommendation += " Ship B only; keep detection on the original pixels."
    else:
        recommendation += " C matched A's faces and embeddings on this sample." + c_sentence

    payload = {
        "library": str(LIBRARY),
        "pictures": str(PICTURES),
        "previewCap": PREVIEW_CAP,
        "note": (
            "Faces wait until every rendition in the drain finishes, so a face "
            "pass cannot start while previews are still encoding. A decodes the "
            "original twice (preview, then faces). B decodes it once. C never "
            "sees pixels above 1600 px, so the 1280-tile pass on a large phone "
            "photo does not run."
        ),
        "adopt": adopt,
        "recommendation": recommendation,
        "summary": summary,
        "photos": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "adopt": adopt, "summary": summary}, indent=2), flush=True)


if __name__ == "__main__":
    main()
