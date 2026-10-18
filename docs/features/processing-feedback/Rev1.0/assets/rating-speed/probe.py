"""One-off: time and compare rating.compute_basic before/after on real photos."""
import json, os, sys, time
from pathlib import Path

os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ["PATH"]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from library import rating

SAMPLES = Path(__file__).resolve().parents[1] / "ffmpeg-variants" / "samples"
faces = [{"box": [0.3, 0.2, 0.2, 0.25]}, {"box": [0.6, 0.5, 0.1, 0.1]}]
out = {}
for path in sorted(SAMPLES.glob("*.jpg"))[:4]:
    t = time.perf_counter()
    rgb, w, h = rating.decode_rgb(path, rating.WORKING_SIDE)
    decode = time.perf_counter() - t
    t = time.perf_counter()
    metrics = rating.compute_basic(rgb, w, h, faces)
    out[path.name] = {"decodeMs": round(decode * 1000), "computeMs": round((time.perf_counter() - t) * 1000), "metrics": metrics}
    print(path.name, out[path.name]["decodeMs"], out[path.name]["computeMs"], flush=True)
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
