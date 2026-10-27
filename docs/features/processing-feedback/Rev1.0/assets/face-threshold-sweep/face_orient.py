import sys, collections
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, r"J:\slyOS\projects\photoLibrary")
from library import faces as F
from library.item_index import iter_items

root = Path(r"J:\slyOS\projects\photoLibrary\library-data")
by_orient = collections.defaultdict(list)
exts = collections.Counter()
for item in iter_items(root):
    if item.get("kind") not in {"photo", "live"}:
        continue
    p = F._still_path(item, root)
    if p is None:
        continue
    exts[p.suffix.lower()] += 1
    try:
        o = Image.open(p).getexif().get(0x0112, 1)
    except Exception:
        o = "pil-cannot-open"
    if len(by_orient[o]) < 2:
        by_orient[o].append(p)
print("extensions:", dict(exts))
for o, paths in by_orient.items():
    for p in paths:
        try:
            w, h, rgb = F.decode_rgb(p)
            ff = np.frombuffer(rgb, dtype=np.uint8).reshape((h, w, 3)).astype(np.int16)
        except Exception as exc:
            print(o, p.name, "ffmpeg failed", exc); continue
        if o == "pil-cannot-open":
            print(o, p.name, "ffmpeg", (w, h)); continue
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        pil = np.asarray(im).astype(np.int16)
        same = pil.shape == ff.shape
        diff = float(np.abs(pil - ff).mean()) if same else None
        print("orient", o, p.name, "ffmpeg", (w, h), "pil", im.size, "mean abs diff", diff)
