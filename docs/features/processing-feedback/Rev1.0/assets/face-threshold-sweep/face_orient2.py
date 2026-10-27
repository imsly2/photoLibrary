import sys, collections
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, r"J:\slyOS\projects\photoLibrary")
from library import faces as F
from library.item_index import iter_items

root = Path(r"J:\slyOS\projects\photoLibrary\library-data")
count = collections.Counter()
sideways = []
for item in iter_items(root):
    if item.get("kind") not in {"photo", "live"}:
        continue
    p = F._still_path(item, root)
    if p is None:
        continue
    o = Image.open(p).getexif().get(0x0112, 1)
    count[o] += 1
    if o in (5, 6, 7, 8):
        sideways.append((p, item))
print("EXIF orientation counts:", dict(count))
print("item metadata size for a sideways photo:", sideways[0][1].get("metadata", {}).get("width"), sideways[0][1].get("metadata", {}).get("height"))
found_ff = found_pil = 0
for p, _ in sideways[:15]:
    w, h, rgb = F.decode_rgb(p)
    a = len(F.detect_insightface(root, w, h, rgb))
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    b = len(F.detect_insightface(root, im.size[0], im.size[1], im.tobytes()))
    found_ff += a; found_pil += b
    print(p.name, "faces sideways:", a, " upright:", b)
print("TOTAL sideways %d vs upright %d" % (found_ff, found_pil))
