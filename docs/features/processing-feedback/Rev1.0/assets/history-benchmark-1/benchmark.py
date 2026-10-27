"""Source-only history benchmark. No media reads, catalog writes, or scans.

Run from any directory with Python 3.12+: python benchmark.py
Only results.json beside this script is written. Saved planner functions freeze
the measured baseline and implementation independently of future code changes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE_PATH = "catalog/sources/123456789abc.json"
ENTRY_ID = "abcdefabcdef"


def canonical(value: Any) -> str:
    # library.atomic.dumps_canonical, frozen for reproducibility.
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def endpoints(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for change in changes:
        if change["path"] not in by_path:
            by_path[change["path"]] = dict(change)
        else:
            by_path[change["path"]]["after"] = change["after"]
    return list(by_path.values())


def workload(n: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = {
        "schemaVersion": 1, "id": "123456789abc", "name": "Fixture",
        "mode": "serve-from-there", "origin": {
            "volumeSerial": "fixture", "pathFromVolumeRoot": "fixture",
            "lastKnownPath": "X:/fixture",
        }, "copyRoot": None, "previewStore": "with-source", "files": {},
        "scan": {"state": "running", "added": 0, "skipped": 0, "errors": []},
    }
    changes = [{"path": SOURCE_PATH, "before": None, "after": copy.deepcopy(source)}]
    for index in range(1, n + 1):
        for state in ("pending", "indexed"):
            before = copy.deepcopy(source)
            source["files"][f"IMG_{index:04}.jpg"] = {
                "destination": None,
                "itemId": f"{index:064x}" if state == "indexed" else f"pending-123456789abc-{index:064x}",
                "component": "still", "sizeBytes": 1234567,
                "modifiedAt": "2026-10-18T12:00:00Z", "sha256": f"{index:064x}",
                "state": state,
            }
            changes.append({"path": SOURCE_PATH, "before": before, "after": copy.deepcopy(source)})
    extra = [changes.pop()]
    entry = {"schemaVersion": 1, "id": ENTRY_ID, "operation": "scan",
             "createdAt": "2026-10-18T12:00:00Z", "changes": changes}
    return entry, extra


def measure(snapshot: str, entry: dict[str, Any], extra: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    code = (HERE / snapshot).read_text(encoding="utf-8")
    namespace = {"json": json, "Path": Path, "Any": Any, "load_entry": lambda root, ident: entry}
    exec(compile(code, snapshot, "exec"), namespace)
    started = time.perf_counter()
    planned = namespace["plan_extend_entry"](Path("."), ENTRY_ID, extra)
    planned_at = time.perf_counter()
    encoded = canonical(planned).encode("utf-8")
    serialized_at = time.perf_counter()
    after = planned[0]["after"]
    assert planned[0]["before"] == entry, "rollback snapshot changed"
    assert planned[1:] == extra, "actual transaction change sequence changed"
    return {
        "historyBytesAfter": len(canonical(after).encode("utf-8")),
        "transactionChangesBytes": len(encoded),
        "planSeconds": round(planned_at - started, 6),
        "serializeSeconds": round(serialized_at - planned_at, 6),
        "planAndSerializeSeconds": round(serialized_at - started, 6),
        "historyChangeCountAfter": len(after["changes"]),
        "rollbackSnapshotPreserved": True,
        "transactionChangeSequencePreserved": True,
    }, after["changes"]


def main() -> None:
    metadata = json.loads((HERE / "provenance.json").read_text(encoding="utf-8"))
    result = {
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(),
        "provenance": metadata,
        "workload": "Synthetic in-memory source snapshots only; two source updates per file (pending then indexed). No item snapshots, media reads, disk transactions, fsync, portable mirrors, or real scans. After measures steady-state coalesced history, not one-time migration of an existing large history.",
        "timing": "One measured planning call and one canonical serialization per variant and size; descriptive measurements, not performance thresholds. Workload creation and output-file I/O excluded. All byte counts are UTF-8.",
        "snapshotSha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("baseline-plan.py", "coalesced-plan.py")},
        "measurements": [],
    }
    for n in (50, 100, 200):
        entry, extra = workload(n)
        baseline, baseline_changes = measure("baseline-plan.py", entry, extra)
        compact_entry = {**entry, "changes": endpoints(entry["changes"])}
        coalesced, coalesced_changes = measure("coalesced-plan.py", compact_entry, extra)
        assert endpoints(baseline_changes) == coalesced_changes, "undo/redo endpoints differ"
        row = {"files": n, "baseline": baseline, "coalesced": coalesced,
               "undoRedoEndpointsEquivalent": True}
        result["measurements"].append(row)
        print(json.dumps(row), flush=True)
    (HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
