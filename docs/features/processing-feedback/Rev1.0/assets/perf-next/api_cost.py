"""Server-side cost of each catalog endpoint the page calls on every load.

Runs the same Library calls the HTTP handlers run (snapshot under the lock,
build outside it), one at a time, on a processed scratch root. Reports the
median of 5 for each, so the browser timeline can be split into "server
work" and "waiting behind other requests". Pass --profile to print the top
functions of the slowest endpoint.

usage: python api_cost.py --scratch ui-400 --label after [--repo <worktree>] [--profile]
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import pstats
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
if "--repo" in sys.argv:
    REPO = Path(sys.argv[sys.argv.index("--repo") + 1]).resolve()
sys.path.insert(0, str(REPO))
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", default="ui-400")
    ap.add_argument("--label", default="after")
    ap.add_argument("--repo")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args()
    root = HERE.parents[5] / ".qa" / args.scratch / "library-data"

    from library.service import Library

    lib = Library(root)
    lib.ensure_settings()
    while lib.drain_step():
        pass
    item_query = {"sort": "date", "dir": "desc", "hideRejects": "1"}
    people = lib.people_list() if hasattr(lib, "people_list") else None
    person = (people or {}).get("people", [{}])[0].get("id") if isinstance(people, dict) else None

    def items():
        return lib.items_from_snapshot(lib.snapshot_catalog(), item_query)

    def items_person():
        return lib.items_from_snapshot(lib.snapshot_catalog(), {**item_query, "person": person or ""})

    def groups():
        return lib.groups_from_snapshot(lib.snapshot_catalog(), {**item_query, "level": "years"})

    def sources():
        return lib.sources_from_snapshot(lib.snapshot_sources())

    def settings():
        lib.read_ready()
        return lib.ensure_settings()

    def jobs():
        return lib.jobs_from_snapshot(lib.snapshot_catalog())

    def people_fn():
        lib.read_ready()
        return lib.people_list()

    def tags():
        lib.read_ready()
        return lib.tags_built()

    def snapshot_only():
        return lib.snapshot_catalog()

    calls = {
        "/api/items": items,
        "/api/items?person": items_person,
        "/api/groups?level=years": groups,
        "/api/sources": sources,
        "/api/settings": settings,
        "/api/jobs": jobs,
        "/api/people": people_fn,
        "/api/tags": tags,
        "snapshot_catalog (under lock)": snapshot_only,
    }
    result: dict[str, object] = {"label": args.label, "repo": str(REPO), "items": len(list(items())), "medianMs": {}, "payloadKB": {}}
    for name, fn in calls.items():
        times = []
        payload = None
        for _ in range(5):
            t0 = time.perf_counter()
            payload = fn()
            times.append((time.perf_counter() - t0) * 1000)
        result["medianMs"][name] = round(statistics.median(times), 1)
        try:
            result["payloadKB"][name] = round(len(json.dumps(payload)) / 1024, 1)
        except TypeError:
            pass
    result["pageLoadSumMs"] = round(sum(result["medianMs"][k] for k in ("/api/items", "/api/groups?level=years", "/api/sources", "/api/settings", "/api/jobs", "/api/people", "/api/tags")), 1)
    print(json.dumps(result, indent=2))
    out = HERE / f"api-cost-{args.label}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)
    if args.profile:
        slowest = max(("/api/people", "/api/tags", "/api/sources", "/api/items"), key=lambda k: result["medianMs"][k])
        print("profile of", slowest)
        prof = cProfile.Profile()
        prof.enable()
        for _ in range(3):
            calls[slowest]()
        prof.disable()
        pstats.Stats(prof).sort_stats("cumulative").print_stats(22)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
