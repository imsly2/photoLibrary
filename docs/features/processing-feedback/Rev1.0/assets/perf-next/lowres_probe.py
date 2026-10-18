"""Does decoding JPEGs at reduced size (ffmpeg -lowres) make previews faster?

For each JPEG in the scan fixture: encode the 1600 px preview the way
renditions.py does, then again with the mjpeg decoder's DCT-domain downscale
(-lowres 1 = half size, still above the 1600 px cap for a 12 MP photo), and
compare wall time, output size and SSIM between the two previews.

usage: python lowres_probe.py [--scratch scan-40]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO))
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

from library.renditions import WEBP_ENCODE, _scale_filter  # noqa: E402


def encode(src: Path, dest: Path, cap: int, lowres: int | None) -> float:
    cmd = ["ffmpeg", "-nostdin", "-y"]
    if lowres:
        cmd += ["-lowres", str(lowres)]
    cmd += ["-i", str(src), "-vf", _scale_filter(cap), "-frames:v", "1", *WEBP_ENCODE, str(dest)]
    t0 = time.perf_counter()
    subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=120, check=True)
    return time.perf_counter() - t0


def ssim(a: Path, b: Path) -> float | None:
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-i", str(a), "-i", str(b), "-lavfi", "ssim", "-f", "null", "-"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
    )
    match = re.search(r"All:([0-9.]+)", proc.stderr)
    return float(match.group(1)) if match else None


def dims(path: Path) -> str:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    return proc.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", default="scan-40")
    ap.add_argument("--cap", type=int, default=1600)
    ap.add_argument("--lowres", type=int, default=1)
    args = ap.parse_args()
    pics = REPO / ".qa" / args.scratch / "pictures"
    files = sorted(p for p in pics.iterdir() if p.suffix.lower() in {".jpg", ".jpeg"})
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        tmp = Path(temp)
        for src in files:
            plain, low = tmp / "plain.webp", tmp / "low.webp"
            # Alternate order so disk cache and CPU boost favour neither.
            t_plain = encode(src, plain, args.cap, None)
            t_low = encode(src, low, args.cap, args.lowres)
            t_plain2 = encode(src, plain, args.cap, None)
            t_low2 = encode(src, low, args.cap, args.lowres)
            rows.append({
                "file": src.name,
                "source": dims(src),
                "plainMs": round(min(t_plain, t_plain2) * 1000, 1),
                "lowresMs": round(min(t_low, t_low2) * 1000, 1),
                "plainOut": dims(plain),
                "lowresOut": dims(low),
                "plainBytes": plain.stat().st_size,
                "lowresBytes": low.stat().st_size,
                "ssim": ssim(plain, low),
            })
            print(json.dumps(rows[-1]), flush=True)
    plain_ms = [r["plainMs"] for r in rows]
    low_ms = [r["lowresMs"] for r in rows]
    result = {
        "cap": args.cap,
        "lowres": args.lowres,
        "files": len(rows),
        "plainMedianMs": round(statistics.median(plain_ms), 1),
        "lowresMedianMs": round(statistics.median(low_ms), 1),
        "plainTotalMs": round(sum(plain_ms), 1),
        "lowresTotalMs": round(sum(low_ms), 1),
        "sameOutputDims": sum(1 for r in rows if r["plainOut"] == r["lowresOut"]),
        "ssimMin": min((r["ssim"] for r in rows if r["ssim"] is not None), default=None),
        "ssimMedian": statistics.median([r["ssim"] for r in rows if r["ssim"] is not None]) if rows else None,
        "rows": rows,
    }
    out = HERE / f"lowres-{args.cap}-l{args.lowres}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
