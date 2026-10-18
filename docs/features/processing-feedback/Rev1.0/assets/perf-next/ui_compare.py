"""Side-by-side of two ui_timing.mjs results (ms until the grid settled).

usage: python ui_compare.py ui-head.json ui-after.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def rows(result: dict, phase: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in result.get(phase) or []:
        name = row["name"]
        if name == "first-load":
            out["first picture on screen"] = f"{row.get('firstTileMs')}"
            out["first load settled"] = f"{row.get('settleMs')}{'*' if row.get('timedOut') else ''}"
        elif name == "open-picture":
            out["open picture: stand-in"] = f"{row.get('standInMs')}"
            out["open picture: original"] = f"{row.get('originalMs')}"
        elif name == "api-min-of-3-ms":
            for key, value in row.items():
                if key != "name":
                    out[f"server {key}"] = f"{value}"
        else:
            media = row.get("mediaRequests") or {}
            extra = f" ({row.get('apiRequests')} api, {media.get('thumb', '?')} thumb, {media.get('face', '?')} face req)"
            out[name] = f"{row.get('settleMs')}{'*' if row.get('timedOut') else ''}{extra}"
    return out


def main() -> int:
    a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    b = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    for phase in ("idle", "processing"):
        ra, rb = rows(a, phase), rows(b, phase)
        print(f"\n== {phase} ==  ({a['label']} | {b['label']})   * = did not settle within 20 s")
        for key in ra:
            print(f"{key:36} {ra.get(key, ''):>44} | {rb.get(key, ''):<44}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
