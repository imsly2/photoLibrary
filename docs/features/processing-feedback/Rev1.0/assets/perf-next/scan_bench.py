"""How much does a scan read, and where does the time go?

Scans N real JPEGs (copies under .qa/<scratch>/pictures) with the library
code of this checkout (or --repo <worktree>) and records, per file, how many
bytes were read from disk and how many ffprobe/ffmpeg processes ran, plus
wall time per phase. The first scan runs after the copy (files are warm in
the OS cache either way, so this measures our own work, not the J: drive).

usage: python scan_bench.py --count 40 --label head [--repo J:\\...\\wt-before] [--reuse]
"""

from __future__ import annotations

import argparse
import builtins
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
if "--repo" in sys.argv:
    REPO = Path(sys.argv[sys.argv.index("--repo") + 1]).resolve()
sys.path.insert(0, str(REPO))
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

from ai_drain import fixture  # noqa: E402

counters = {"bytes": 0, "opens": 0, "procs": 0}
_real_open = builtins.open


def counting_open(file, mode="r", *args, **kwargs):
    handle = _real_open(file, mode, *args, **kwargs)
    if "r" in mode and "b" in mode and type(file) is not int:
        counters["opens"] += 1
        real_read = handle.read

        def read(n=-1):
            data = real_read(n)
            counters["bytes"] += len(data)
            return data

        handle.read = read
    return handle


class CountingPopen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        counters["procs"] += 1
        super().__init__(*args, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--label", default="head")
    ap.add_argument("--scratch", default="scan-40")
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--repo")
    args = ap.parse_args()
    scratch = HERE.parents[5] / ".qa" / args.scratch
    pics = fixture(scratch, args.count, args.reuse)
    files = sorted(p for p in pics.iterdir() if p.is_file())
    total_bytes = sum(p.stat().st_size for p in files)
    root = scratch / "library-data"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    from library.service import Library
    from library.settings import defaults, write_settings_file

    settings = defaults()
    settings.update(ratingMode="off", transcribeVideos=False, previewStore="with-source")
    write_settings_file(root, settings)
    lib = Library(root)
    lib.ensure_settings()

    builtins.open = counting_open
    io.open = counting_open
    subprocess.Popen = CountingPopen
    t0 = time.perf_counter()
    lib.scan({"path": str(pics), "mode": "serve-from-there", "previewStore": "with-source"})
    scan_s = time.perf_counter() - t0
    scan_counts = dict(counters)
    for key in counters:
        counters[key] = 0
    t0 = time.perf_counter()
    steps = 0
    while lib.drain_step():
        steps += 1
    drain_s = time.perf_counter() - t0
    drain_counts = dict(counters)
    builtins.open = _real_open
    io.open = _real_open

    result = {
        "label": args.label,
        "repo": str(REPO),
        "files": len(files),
        "fileBytesMB": round(total_bytes / 1e6, 1),
        "scan": {
            "seconds": round(scan_s, 2),
            "perFileMs": round(scan_s / len(files) * 1000, 1),
            "bytesReadMB": round(scan_counts["bytes"] / 1e6, 1),
            "readsPerFileBytes": round(scan_counts["bytes"] / total_bytes, 2),
            "binaryOpens": scan_counts["opens"],
            "processes": scan_counts["procs"],
        },
        "previewDrain": {
            "seconds": round(drain_s, 2),
            "steps": steps,
            "perFileMs": round(drain_s / len(files) * 1000, 1),
            "bytesReadMB": round(drain_counts["bytes"] / 1e6, 1),
            "binaryOpens": drain_counts["opens"],
            "processes": drain_counts["procs"],
        },
    }
    out = HERE / f"scan-{args.label}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
