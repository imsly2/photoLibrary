"""Build a fully processed scratch library with named people for browser timing.

Copies N real JPEGs, scans them (previews with-source so records and
renditions live beside the copies), drains previews / faces / objects /
rating with the real local models, then names the largest face clusters.
The result under .qa/<scratch>/ can be copied per server for before/after
runs. Never touches the real library.

usage: python ui_fixture.py --count 400 --scratch ui-400
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO))
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

from ai_drain import REAL, fixture, install_models  # noqa: E402

NAMES = ("Ada", "Ben", "Cara", "Dev", "Ema", "Finn", "Gus", "Hana", "Ivy", "Jon")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=400)
    ap.add_argument("--scratch", default="ui-400")
    ap.add_argument("--reuse", action="store_true")
    args = ap.parse_args()
    scratch = REPO / ".qa" / args.scratch
    pics = fixture(scratch, args.count, args.reuse)
    root = scratch / "library-data"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    install_models(root)

    from library.service import Library
    from library.settings import defaults, write_settings_file

    settings = defaults()
    settings.update(ratingMode="basic", transcribeVideos=False, previewStore="with-source", addFolderDefault="ask")
    write_settings_file(root, settings)
    lib = Library(root)
    lib.ensure_settings()
    t0 = time.perf_counter()
    lib.scan({"path": str(pics), "mode": "serve-from-there", "previewStore": "with-source"})
    print(f"scan {time.perf_counter() - t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    steps = 0
    while lib.drain_step():
        steps += 1
        if steps % 100 == 0:
            print(f"  drain step {steps} at {time.perf_counter() - t0:.0f}s", flush=True)
    print(f"drain {steps} steps {time.perf_counter() - t0:.1f}s", flush=True)

    from library.people_panel import apply_person_update, people_index

    people = people_index(root).get("people") or []
    people.sort(key=lambda person: -(person.get("itemCount") or person.get("count") or 0))
    named = []
    for person, name in zip(people, NAMES):
        apply_person_update(root, person["id"], {"name": name})
        named.append({"id": person["id"], "name": name, "count": person.get("itemCount") or person.get("count")})
    summary = {"pictures": args.count, "scratch": str(scratch), "named": named, "people": len(people)}
    (scratch / "fixture.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
