"""AI-queue drain profile on a copied fixture with the real local models.

Scans N real JPEGs into a scratch root (never the real library), drains
previews, then times every faces / objects / rating step: wall time, how
much of it ran with the catalog lock released (io_context), how many
ffmpeg/ffprobe processes it spawned, and how many bytes of originals it
read. Writes <label>.json next to this script.

usage: python ai_drain.py --count 40 --label head [--reuse] [--scratch perf-next]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
if "--repo" in sys.argv:  # measure another checkout (a git worktree) with this same script
    REPO = Path(sys.argv[sys.argv.index("--repo") + 1]).resolve()
sys.path.insert(0, str(REPO))
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

REAL = Path(r"J:\Pictures\1. Favorites Pictures")
REAL_MODELS = HERE.parents[5] / "library-data" / "models"
MODEL_FILES = (
    "faces/manifest.json",
    "faces/buffalo_s/det_500m.onnx",
    "faces/buffalo_s/w600k_mbf.onnx",
    "objects.json",
    "yolov8n.onnx",
    "aesthetic/aesthetic.json",
    "aesthetic/nima-mobilenet.onnx",
)


def fixture(scratch: Path, count: int, reuse: bool) -> Path:
    pics = scratch / "pictures"
    if reuse and pics.is_dir():
        shutil.rmtree(pics / ".library", ignore_errors=True)
        return pics
    if pics.exists():
        shutil.rmtree(pics)
    pics.mkdir(parents=True)
    jpgs = sorted(p for p in REAL.rglob("*.jpg") if ".library" not in p.parts)
    step = max(1, len(jpgs) // count)
    for src in jpgs[::step][:count]:
        shutil.copy2(src, pics / src.name)
    return pics


def install_models(root: Path) -> None:
    for rel in MODEL_FILES:
        src = REAL_MODELS / rel
        if not src.is_file():
            raise SystemExit(f"missing real model file {src}")
        dest = root / "models" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    (root / "models" / "faces" / "index.json").write_text(
        json.dumps({"schemaVersion": 1, "backend": "insightface-buffalo_s", "matchThreshold": 0.8, "people": {}}),
        encoding="utf-8",
    )


def rss_mb() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = COUNTERS()
        counters.cb = ctypes.sizeof(COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return round(counters.PeakWorkingSetSize / 1e6, 1)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--label", default="head")
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--scratch", default="perf-next")
    ap.add_argument("--profile", action="store_true", help="cProfile each queue; top-30 cumulative to <label>.profile.txt")
    ap.add_argument("--repo", default=str(REPO))
    args = ap.parse_args()

    scratch = REPO / ".qa" / args.scratch
    pics = fixture(scratch, args.count, args.reuse)
    root = scratch / "library-data"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    install_models(root)

    from library import activity
    from library.service import Library
    from library.settings import defaults, write_settings_file

    settings = defaults()
    settings.update(ratingMode="basic", transcribeVideos=False, previewStore="with-source")
    write_settings_file(root, settings)
    lib = Library(root)
    lib.ensure_settings()

    # Count every child process and every byte read from the fixture folder.
    spawned = {"n": 0, "argv0": {}}
    real_popen = subprocess.Popen

    class CountingPopen(real_popen):  # type: ignore[misc,valid-type]
        def __init__(self, args_, *a, **kw):
            spawned["n"] += 1
            name = Path(str(args_[0])).stem if isinstance(args_, (list, tuple)) else "?"
            spawned["argv0"][name] = spawned["argv0"].get(name, 0) + 1
            super().__init__(args_, *a, **kw)

    subprocess.Popen = CountingPopen
    phase = {"id": None}
    real_note = activity.note

    def noting(kind, **kw):
        if kind != "scan":
            phase["id"] = kind
        return real_note(kind, **kw)

    activity.note = noting

    released = {"s": 0.0}

    @contextmanager
    def io_context():
        started = time.perf_counter()
        try:
            yield
        finally:
            released["s"] += time.perf_counter() - started

    t0 = time.perf_counter()
    lib.scan({"path": str(pics), "mode": "serve-from-there", "previewStore": "with-source"})
    scan_s = time.perf_counter() - t0

    # Previews first, as the server does, so the AI queues start from a settled catalog.
    t0 = time.perf_counter()
    from library.renditions import drain_step as renditions_step

    while renditions_step(root, io_context=io_context):
        pass
    previews_s = time.perf_counter() - t0

    steps: list[dict] = []
    profiles: dict[str, object] = {}
    t0 = time.perf_counter()
    while True:
        phase["id"] = None
        spawned_before = spawned["n"]
        released_before = released["s"]
        prof = None
        if args.profile:
            import cProfile

            prof = cProfile.Profile()
            prof.enable()
        s = time.perf_counter()
        worked = lib.drain_step(io_context=io_context)
        took = time.perf_counter() - s
        if prof is not None:
            prof.disable()
            if worked and phase["id"]:
                profiles.setdefault(phase["id"], []).append(prof)
        if not worked:
            break
        steps.append(
            {
                "queue": phase["id"] or "?",
                "seconds": round(took, 4),
                "unlockedSeconds": round(released["s"] - released_before, 4),
                "processes": spawned["n"] - spawned_before,
            }
        )
        if len(steps) > 10 * (args.count + 2):
            break
    drain_s = time.perf_counter() - t0

    # What one "nothing to do" drain tick costs once every queue is done. The
    # server runs this every 0.25 s for as long as it is up, holding its lock.
    idle: list[float] = []
    for _ in range(5):
        s = time.perf_counter()
        assert not lib.drain_step(io_context=io_context)
        idle.append(time.perf_counter() - s)

    by_queue: dict[str, dict] = {}
    for st in steps:
        row = by_queue.setdefault(st["queue"], {"steps": 0, "seconds": 0.0, "unlockedSeconds": 0.0, "processes": 0})
        row["steps"] += 1
        row["seconds"] += st["seconds"]
        row["unlockedSeconds"] += st["unlockedSeconds"]
        row["processes"] += st["processes"]
    for row in by_queue.values():
        row["meanSeconds"] = round(row["seconds"] / max(1, row["steps"]), 3)
        row["lockHeldSeconds"] = round(row["seconds"] - row["unlockedSeconds"], 3)
        row["seconds"] = round(row["seconds"], 3)
        row["unlockedSeconds"] = round(row["unlockedSeconds"], 3)

    from library.catalog_io import iter_item_ids, load_item

    items = [load_item(root, i) for i in iter_item_ids(root)]
    result = {
        "label": args.label,
        "repo": str(REPO),
        "pictures": args.count,
        "scanSeconds": round(scan_s, 2),
        "previewsSeconds": round(previews_s, 2),
        "aiDrainSeconds": round(drain_s, 2),
        "idleTickSeconds": {"mean": round(sum(idle) / len(idle), 4), "max": round(max(idle), 4)},
        "byQueue": by_queue,
        "processesByName": spawned["argv0"],
        "peakRssMB": rss_mb(),
        "outcome": {
            "faces": sum(len(i.get("faces") or []) for i in items),
            "itemsWithFaces": sum(1 for i in items if i.get("faces")),
            "itemsWithThings": sum(1 for i in items if i.get("things")),
            "rated": sum(1 for i in items if (i.get("quality") or {}).get("status") == "ready"),
            "ratingErrors": sum(1 for i in items if (i.get("quality") or {}).get("status") == "error"),
        },
        "steps": steps,
    }
    out = HERE / f"{args.label}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if profiles:
        import io
        import pstats

        text = io.StringIO()
        for queue, profs in profiles.items():
            stats = pstats.Stats(profs[0], stream=text)
            for extra in profs[1:]:
                stats.add(extra)
            text.write(f"\n===== {queue}: {len(profs)} steps, top 30 by cumulative =====\n")
            stats.sort_stats("cumulative").print_stats(30)
        (HERE / f"{args.label}.profile.txt").write_text(text.getvalue(), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "steps"}, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
