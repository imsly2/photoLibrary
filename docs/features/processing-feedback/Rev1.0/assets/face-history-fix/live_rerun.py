"""Restart is already done. Set the match threshold, re-run faces, record pace.

Writes live-rerun/result.json. Does not delete undo history.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8785"
OUT = Path(__file__).resolve().parent / "live-rerun"
UNDO = Path(r"J:\slyOS\projects\photoLibrary\library-data\undo\entries")
DEADLINE_S = 40 * 60


def request(method: str, path: str, body: dict | None = None, timeout: float = 60):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload


def faces_queue(jobs: dict) -> dict:
    for row in jobs.get("queues") or []:
        if row.get("id") == "infer-faces":
            return row
    return {}


def undo_index() -> dict[str, int]:
    found = {}
    if not UNDO.is_dir():
        return found
    for path in UNDO.glob("*.json"):
        try:
            found[path.name] = path.stat().st_size
        except OSError:
            continue
    return found


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before_undo = undo_index()
    status, settings = request("PUT", "/api/settings", {"faceMatchThreshold": 0.45})
    if status != 200:
        raise SystemExit(f"settings {status} {settings}")
    status, jobs = request("POST", "/api/jobs", {"action": "resume"})
    if status != 200:
        raise SystemExit(f"resume {status} {jobs}")
    paused_after_resume = bool(jobs.get("paused"))
    status, jobs = request("POST", "/api/jobs", {"action": "rerun-faces"})
    if status != 200:
        raise SystemExit(f"rerun {status} {jobs}")
    started = time.time()
    samples = []
    per_photo = []
    last_file = ""
    last_change = started
    saw_work = False
    idle_hits = 0
    while time.time() - started < DEADLINE_S:
        now = time.time()
        try:
            _, activity = request("GET", "/api/activity", timeout=10)
            _, jobs = request("GET", "/api/jobs", timeout=10)
        except Exception as exc:
            samples.append({"t": round(now - started, 1), "error": str(exc)})
            time.sleep(1)
            continue
        face = faces_queue(jobs)
        pending = int(face.get("pending") or 0)
        done = int(face.get("done") or 0)
        state = face.get("state") or ""
        filename = activity.get("file") or ""
        phase = activity.get("phase") or ""
        if pending > 0 or state == "running" or phase == "infer-faces":
            saw_work = True
        if filename and filename != last_file and phase == "infer-faces":
            if last_file:
                per_photo.append(
                    {
                        "file": last_file,
                        "wallSec": round(now - last_change, 3),
                        "activitySec": activity.get("elapsedSeconds"),
                    }
                )
            last_file = filename
            last_change = now
        if len(samples) == 0 or now - started - samples[-1]["t"] >= 5:
            fresh = undo_index()
            new_sizes = [fresh[name] for name in fresh if name not in before_undo]
            samples.append(
                {
                    "t": round(now - started, 1),
                    "pending": pending,
                    "done": done,
                    "state": state,
                    "phase": phase,
                    "file": filename,
                    "elapsedOnFile": activity.get("elapsedSeconds"),
                    "paused": jobs.get("paused"),
                    "newUndo": len(new_sizes),
                    "newUndoMeanKB": round(sum(new_sizes) / len(new_sizes) / 1024, 2) if new_sizes else 0,
                }
            )
            print(
                f"t={samples[-1]['t']} pending={pending} done={done} state={state} "
                f"file={filename} newUndo={len(new_sizes)}",
                flush=True,
            )
        if saw_work and pending == 0 and state != "running" and phase != "infer-faces":
            idle_hits += 1
            if idle_hits >= 4:
                break
        else:
            idle_hits = 0
        time.sleep(0.4)
    if last_file:
        per_photo.append(
            {
                "file": last_file,
                "wallSec": round(time.time() - last_change, 3),
                "activitySec": None,
            }
        )
    fresh = undo_index()
    new_files = sorted(name for name in fresh if name not in before_undo)
    new_sizes = [fresh[name] for name in new_files]
    _, people = request("GET", "/api/people", timeout=120)
    rows = people.get("people") if isinstance(people, dict) else people
    rows = rows if isinstance(rows, list) else []
    counts = [int(person.get("itemCount") or 0) for person in rows]
    counts.sort(reverse=True)
    walls = [row["wallSec"] for row in per_photo if row.get("wallSec")]

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    payload = {
        "threshold": settings.get("faceMatchThreshold"),
        "pausedAfterResume": paused_after_resume,
        "seconds": round(time.time() - started, 1),
        "sawWork": saw_work,
        "photosTimed": len(per_photo),
        "secPerPhoto": {
            "mean": mean(walls),
            "max": round(max(walls), 3) if walls else None,
            "first20mean": mean(walls[:20]),
            "last20mean": mean(walls[-20:]) if walls else None,
        },
        "undo": {
            "beforeFiles": len(before_undo),
            "beforeBytes": sum(before_undo.values()),
            "newFiles": len(new_files),
            "newBytes": sum(new_sizes),
            "newMeanKB": round(sum(new_sizes) / len(new_sizes) / 1024, 2) if new_sizes else None,
            "newMaxKB": round(max(new_sizes) / 1024, 2) if new_sizes else None,
            "newMinKB": round(min(new_sizes) / 1024, 2) if new_sizes else None,
        },
        "people": {
            "total": len(rows),
            "named": sum(1 for person in rows if person.get("name")),
            "visible": sum(1 for person in rows if person.get("visible")),
            "singleFace": sum(1 for value in counts if value <= 1),
            "top": counts[:12],
        },
        "facesQueue": faces_queue(jobs),
        "samples": samples,
        "perPhoto": per_photo,
    }
    (OUT / "result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("seconds", "secPerPhoto", "undo", "people")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
