import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

d = Path(sys.argv[1])
E = np.load(d / "embs.npy").astype(np.float64)
E /= np.linalg.norm(E, axis=1, keepdims=True)
crops = np.load(d / "crops.npy")
meta = json.loads((d / "meta.json").read_text())


def greedy(th, order=None):
    """Same rule as faces.cluster_detections: join first cluster whose centroid beats th."""
    clusters = []
    for i in (order if order is not None else range(len(E))):
        for c in clusters:
            cen = c["sum"] / np.linalg.norm(c["sum"])
            if E[i] @ cen > th:
                c["m"].append(i); c["sum"] += E[i]; break
        else:
            clusters.append({"m": [i], "sum": E[i].copy()})
    return sorted(clusters, key=lambda c: -len(c["m"]))


S = E @ E.T
iu = np.triu_indices(len(E), 1)
v = S[iu]
print("pairwise face cosine quantiles:", {q: round(float(np.quantile(v, q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)})
hist, edges = np.histogram(v, bins=20, range=(-0.2, 1.0))
for h, e in zip(hist, edges):
    print("  %5.2f %s" % (e, "#" * int(60 * h / hist.max())))

result = {}
for th in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80):
    cl = greedy(th)
    sizes = [len(c["m"]) for c in cl]
    result[th] = {"clusters": len(cl), "singletons": sizes.count(1), "top": sizes[:8]}
    print("th %.2f clusters %3d singletons %3d top %s" % (th, len(cl), sizes.count(1), sizes[:8]))
(d / "sweep.json").write_text(json.dumps(result, indent=2))


def sheet(th, name, per_row=14, cell=72, rows=12):
    cl = [c for c in greedy(th) if len(c["m"]) >= 2][:rows]
    W = 60 + per_row * cell
    img = Image.new("RGB", (W, len(cl) * cell + 30), (24, 24, 24))
    dr = ImageDraw.Draw(img)
    dr.text((6, 8), "threshold %.2f - each row is one 'person' (%d faces shown max)" % (th, per_row), fill=(230, 230, 230))
    for r, c in enumerate(cl):
        y = 30 + r * cell
        dr.text((6, y + 28), "%d" % len(c["m"]), fill=(255, 200, 80))
        for k, i in enumerate(c["m"][:per_row]):
            img.paste(Image.fromarray(crops[i]).resize((cell - 4, cell - 4)), (60 + k * cell, y + 2))
    img.save(d / name)
    print("wrote", d / name)


sheet(0.45, "sheet-045.png")
sheet(0.80, "sheet-080.png")
