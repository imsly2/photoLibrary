import json, sys, time, random
from pathlib import Path
import numpy as np

sys.path.insert(0, r"J:\slyOS\projects\photoLibrary")
from library import faces as F
from library.catalog_io import load_item
from library.paths import library_path

root = Path(r"J:\slyOS\projects\photoLibrary\library-data")
idx = json.loads((root / "models/faces/index.json").read_text(encoding="utf-8"))
ids = sorted({r["itemId"] for p in idx["people"].values() for r in p["faces"]})
first = load_item(root, ids[0])
print("item record stored at:", library_path(root, f"catalog/items/{ids[0]}.json"))
print("its faces field:", json.dumps(first.get("faces"), indent=1)[:700])

random.Random(3).shuffle(ids)
np_ = np
det, rec = F._insight_sessions(root, F._ort())
name = det.get_inputs()[0].name
rows = []
for item_id in ids[:12]:
    path = F._still_path(load_item(root, item_id), root)
    if path is None:
        continue
    t = time.perf_counter()
    w, h, rgb = F.decode_rgb(path)
    t_decode = time.perf_counter() - t
    windows = F.iter_detect_windows(w, h)
    blob = np.zeros((1, 3, 640, 640), dtype=np.float32)
    t = time.perf_counter()
    for _ in windows:
        det.run(None, {name: blob})
    t_det = time.perf_counter() - t
    t = time.perf_counter()
    rec.run(None, {rec.get_inputs()[0].name: np.zeros((1, 3, 112, 112), dtype=np.float32)})
    t_rec = time.perf_counter() - t
    rows.append((w, h, len(windows), t_decode, t_det, t_rec))
    print("%5dx%-5d windows %2d  decode %.2fs  detect %.2fs  recognize/face %.3fs" % rows[-1])
a = np.array([r[3:] for r in rows])
print("AVG decode %.2fs  detect %.2fs  recognize/face %.3fs" % tuple(a.mean(axis=0)))
