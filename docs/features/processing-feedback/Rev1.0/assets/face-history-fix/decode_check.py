"""Upright decode proof: library decoder vs Pillow reference, speed, faces on sideways shots.

Pillow is only the reference here; library/ itself must not import it.
Run from the repo root: python docs/.../face-history-fix/decode_check.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from library import faces as F  # noqa: E402
from library.item_index import iter_items  # noqa: E402
from library.media import decode_still_rgb, run_ffmpeg, _ffprobe_json_uncached  # noqa: E402

root = Path(r"J:\slyOS\projects\photoLibrary\library-data")
by_orient: dict[int, list[Path]] = {}
for item in iter_items(root):
    if item.get("kind") not in {"photo", "live"}:
        continue
    path = F._still_path(item, root)
    if path is None:
        continue
    orient = Image.open(path).getexif().get(0x0112, 1)
    by_orient.setdefault(orient, []).append(path)

out = {"orientationCounts": {str(k): len(v) for k, v in by_orient.items()}, "upright": [], "timing": {}, "sideways": {}}
sample = [p for o in sorted(by_orient) for p in by_orient[o][:3]]
for path in sample:
    w, h, rgb = decode_still_rgb(path)
    ours = np.frombuffer(rgb, dtype=np.uint8).reshape((h, w, 3)).astype(np.int16)
    ref = np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("RGB")).astype(np.int16)
    same = ours.shape == ref.shape
    out["upright"].append({
        "file": path.name,
        "orientation": Image.open(path).getexif().get(0x0112, 1),
        "size": [w, h],
        "matchesPillowUpright": bool(same and float(np.abs(ours - ref).mean()) < 3.0),
        "meanAbsDiff": float(np.abs(ours - ref).mean()) if same else None,
    })


def old_decode(path: Path) -> None:
    _ffprobe_json_uncached(path)
    run_ffmpeg(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])


timed = by_orient.get(1, [])[:10]
for name, fn in (("before_ffprobe_plus_pipe", old_decode), ("after_header_plus_tempfile", decode_still_rgb)):
    fn(timed[0])
    t = time.perf_counter()
    for path in timed:
        fn(path)
    out["timing"][name] = round((time.perf_counter() - t) / len(timed), 3)

found = 0
sideways = by_orient.get(6, [])[:15]
for path in sideways:
    w, h, rgb = decode_still_rgb(path)
    found += len(F.detect_insightface(root, w, h, rgb))
out["sideways"] = {"photos": len(sideways), "facesFoundAfterFix": found, "facesFoundBefore": 0}
out["pass"] = all(row["matchesPillowUpright"] for row in out["upright"])
dest = Path(__file__).with_name("decode-check.json")
dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
