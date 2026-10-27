import json, sys, time, random
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, r"J:\slyOS\projects\photoLibrary")
from library import faces as F
from library.catalog_io import load_item

root = Path(r"J:\slyOS\projects\photoLibrary\library-data")
idx = json.loads((root / "models/faces/index.json").read_text(encoding="utf-8"))
ids = sorted({r["itemId"] for p in idx["people"].values() for r in p["faces"]})
random.Random(5).shuffle(ids)
det, rec = F._insight_sessions(root, F._ort())
print("detector input shape:", det.get_inputs()[0].shape)

paths = [p for p in (F._still_path(load_item(root, i), root) for i in ids[:10]) if p]
T = {k: [] for k in ("ffmpeg_full", "pil_full", "pil_half", "pil_quarter")}
for p in paths:
    t = time.perf_counter(); F.decode_rgb(p); T["ffmpeg_full"].append(time.perf_counter() - t)
    t = time.perf_counter(); im = Image.open(p); im.load(); np.asarray(im.convert("RGB")); T["pil_full"].append(time.perf_counter() - t)
    for key, div in (("pil_half", 2), ("pil_quarter", 4)):
        t = time.perf_counter(); im = Image.open(p); w, h = im.size; im.draft("RGB", (w // div, h // div)); im.load(); np.asarray(im.convert("RGB")); T[key].append(time.perf_counter() - t)
for k, v in T.items():
    print("%-12s avg %.3fs" % (k, sum(v) / len(v)))

# full-image detection: feed the native-resolution photo straight to the detector
p = paths[0]
w, h, rgb = F.decode_rgb(p)
img = np.frombuffer(rgb, dtype=np.uint8).reshape((h, w, 3))
H, W = (h // 32) * 32, (w // 32) * 32
blob = ((img[:H, :W, ::-1].astype(np.float32) - 127.5) / 128.0).transpose(2, 0, 1)[None]
name = det.get_inputs()[0].name
try:
    t = time.perf_counter(); det.run(None, {name: blob}); print("full-res %dx%d single pass: %.2fs" % (W, H, time.perf_counter() - t))
except Exception as exc:
    print("full-res pass failed:", str(exc)[:200])
t = time.perf_counter(); F.detect_insightface(root, w, h, rgb); print("current pipeline (13 windows + embed) on same photo: %.2fs" % (time.perf_counter() - t))
