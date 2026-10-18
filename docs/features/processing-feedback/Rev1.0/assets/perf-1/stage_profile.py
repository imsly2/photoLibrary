"""Serial scan + drain profile on a copied fixture. Never touches the real library.

usage: python profile.py --count 80 --label baseline
Writes <label>.json next to this script.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import pstats
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO))
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

REAL = Path(r"J:\Pictures\1. Favorites Pictures")
SCRATCH = REPO / ".qa" / "perf-1"

STAGES = {
    "sha256_file": "hash original",
    "read_capture": "EXIF/metadata",
    "read_content_identifier": "content id",
    "plan_extend_entry": "history extend (plan)",
    "load_entry": "history load",
    "transact": "transaction total",
    "write_manifest": "transaction manifests",
    "apply_payload": "transaction payloads",
    "purge_orphan_undo_files": "undo purge",
    "mirror_changes": "portable mirror",
    "next_rendition_job": "pick next job",
    "write_webp": "ffmpeg webp",
    "write_proxy": "ffmpeg proxy",
    "write_playback": "ffmpeg playback",
    "_windows_mount_for_serial": "drive-letter scan",
    "publish_ready": "publish ready",
    "pair_live_items": "live pairing",
    "rebuild_sqlite": "sqlite rebuild",
    "dumps": "json dumps",
    "loads": "json loads",
    "load": "json load",
}


def fixture(count: int) -> Path:
    pics = SCRATCH / "pictures"
    if pics.exists():
        shutil.rmtree(pics)
    pics.mkdir(parents=True)
    jpgs = sorted(p for p in REAL.rglob("*.jpg") if ".library" not in p.parts)[:count]
    movs = sorted(p for p in REAL.rglob("*.mov") if ".library" not in p.parts)[:1]
    for src in jpgs + movs:
        dest = pics / src.relative_to(REAL)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return pics


def stage_table(prof: cProfile.Profile) -> dict[str, dict[str, float]]:
    stats = pstats.Stats(prof).stats
    out: dict[str, dict[str, float]] = {}
    for (filename, _line, func), (_cc, nc, _tt, ct, _callers) in stats.items():
        if func not in STAGES:
            continue
        if func in {"dumps", "loads", "load"} and "json" not in filename:
            continue
        label = STAGES[func]
        row = out.setdefault(label, {"calls": 0, "seconds": 0.0})
        row["calls"] += nc
        row["seconds"] = round(row["seconds"] + ct, 3)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["seconds"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--reuse", action="store_true", help="keep the existing fixture copy")
    ap.add_argument("--scratch", default="perf-1", help="folder name under .qa/ (one per agent)")
    ap.add_argument("--all-queues", action="store_true", help="also drain faces/objects/rating")
    args = ap.parse_args()

    global SCRATCH
    SCRATCH = REPO / ".qa" / args.scratch
    pics = SCRATCH / "pictures" if args.reuse else fixture(args.count)
    root = SCRATCH / "library-data"
    if root.exists():
        shutil.rmtree(root)
    shutil.rmtree(pics / ".library", ignore_errors=True)

    import library.atomic as atomic
    from library.service import Library

    written = {"files": 0, "bytes": 0}
    real_write = atomic.atomic_write_bytes

    def counting_write(path, data):
        written["files"] += 1
        written["bytes"] += len(data)
        return real_write(path, data)

    atomic.atomic_write_bytes = counting_write

    lib = Library(root)
    lib.ensure_settings()

    per_file: list[float] = []
    last = [time.perf_counter()]

    def on_progress(kind: str, rel: str) -> None:
        now = time.perf_counter()
        per_file.append(round(now - last[0], 4))
        last[0] = now

    prof = cProfile.Profile()
    t0 = time.perf_counter()
    last[0] = t0
    prof.enable()
    lib.scan(
        {"path": str(pics), "mode": "serve-from-there", "previewStore": "with-source"},
        on_progress=on_progress,
    )
    prof.disable()
    scan_seconds = time.perf_counter() - t0
    scan_written = dict(written)
    scan_stages = stage_table(prof)

    written.update(files=0, bytes=0)
    from library.catalog_io import iter_item_ids, load_item

    steps: list[dict[str, object]] = []
    prof = cProfile.Profile()
    t0 = time.perf_counter()
    while True:
        before = {
            i: dict((load_item(root, i).get("renditions") or {}).get("status") or {})
            for i in iter_item_ids(root)
        }
        s = time.perf_counter()
        prof.enable()
        if args.all_queues:
            worked = lib.drain_step()
        else:
            from library.renditions import drain_step as renditions_step

            worked = renditions_step(root)
        prof.disable()
        took = time.perf_counter() - s
        if not worked:
            break
        slot = None
        for i in iter_item_ids(root):
            after = (load_item(root, i).get("renditions") or {}).get("status") or {}
            for k, v in after.items():
                if before.get(i, {}).get(k) != v and k in {"thumb", "preview", "poster", "proxy", "playback"}:
                    slot = k
        steps.append({"slot": slot, "seconds": round(took, 4)})
        if len(steps) > 6 * (args.count + 2):
            break
    drain_seconds = time.perf_counter() - t0
    drain_stages = stage_table(prof)

    by_slot: dict[str, list[float]] = {}
    for st in steps:
        by_slot.setdefault(str(st["slot"]), []).append(float(st["seconds"]))
    n = len(per_file)
    tenth = max(1, n // 10)
    undo = root / "undo" / "entries"
    result = {
        "label": args.label,
        "fixture": {"jpg": args.count, "mov": 1, "source": str(REAL), "copy": str(pics)},
        "scan": {
            "files": n,
            "seconds": round(scan_seconds, 2),
            "perFileMeanFirstTenth": round(sum(per_file[:tenth]) / tenth, 4),
            "perFileMeanLastTenth": round(sum(per_file[-tenth:]) / tenth, 4),
            "jsonFilesWritten": scan_written["files"],
            "jsonMBWritten": round(scan_written["bytes"] / 1e6, 2),
            "stages": scan_stages,
        },
        "drain": {
            "steps": len(steps),
            "seconds": round(drain_seconds, 2),
            "perSlotMeanSeconds": {k: round(sum(v) / len(v), 3) for k, v in by_slot.items()},
            "perSlotCount": {k: len(v) for k, v in by_slot.items()},
            "jsonFilesWritten": written["files"],
            "jsonMBWritten": round(written["bytes"] / 1e6, 2),
            "stages": drain_stages,
        },
        "undoEntryBytes": sorted((p.stat().st_size for p in undo.glob("*.json")), reverse=True),
    }
    out = HERE / f"{args.label}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("scan", "drain")}, indent=2)[:6000])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
