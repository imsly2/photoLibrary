import json, sys, time, random
from pathlib import Path
import numpy as np

sys.path.insert(0, r"J:\slyOS\projects\photoLibrary")
from library import faces as F
from library.catalog_io import load_item

root = Path(r"J:\slyOS\projects\photoLibrary\library-data")
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 150

idx = json.loads((root / "models/faces/index.json").read_text(encoding="utf-8"))
item_ids = sorted({ref["itemId"] for r in idx["people"].values() for ref in r.get("faces") or []})
random.Random(7).shuffle(item_ids)
item_ids = item_ids[:limit]

embs, crops, meta = [], [], []
t0 = time.time()
for n, item_id in enumerate(item_ids):
    item = load_item(root, item_id)
    path = F._still_path(item, root)
    if path is None:
        continue
    try:
        w, h, rgb = F.decode_rgb(path)
        found = F.detect_insightface(root, w, h, rgb)
    except Exception as exc:
        print("skip", item_id[:10], exc)
        continue
    image = np.frombuffer(rgb, dtype=np.uint8).reshape((h, w, 3))
    for face in found:
        lm = face.get("landmarks")
        if lm is None:
            continue
        kps = np.array([[x * w, y * h] for x, y in lm])
        crops.append(F._affine_112(image, kps))
        embs.append(face["embedding"])
        meta.append({"itemId": item_id, "box": face["box"], "det": face["detScore"], "side": face["shortSidePx"]})
    if n % 10 == 0:
        print(n, len(embs), "%.0fs" % (time.time() - t0), flush=True)

np.save(out / "embs.npy", np.array(embs, dtype=np.float32))
np.save(out / "crops.npy", np.array(crops, dtype=np.uint8))
(out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
print("done", len(embs), "faces from", len(item_ids), "items in %.0fs" % (time.time() - t0))
