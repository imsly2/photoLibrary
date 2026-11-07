"""Live-library load and filter benchmark. Read-only against the running server.

Measures what Steve feels on the real library (28k pictures, port 8785):
opening the page, the count, thumbnails, every filter click and its clear,
and whether anything in the server stalls small requests while that happens.

    python -m tests.perf.live_load_filter                 full run, compare to baseline
    python -m tests.perf.live_load_filter --quick         skip the slow probes
    python -m tests.perf.live_load_filter --save-baseline also store this run as the baseline

Writes docs/process/assets/load-filter/runs/<stamp>.json and .md.
Exit 0: no primary metric got worse. Exit 1: a primary metric regressed.
Exit 2: could not run (server down, library too small).
The metric list and the targets are in docs/process/LOAD-FILTER-TARGET.md.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

APP = Path(__file__).resolve().parents[2]
ASSETS = APP / "docs" / "process" / "assets" / "load-filter"
BASELINE = ASSETS / "baseline.json"
TARGETS = Path(__file__).with_name("live_targets.json")
BROWSER_SCRIPT = Path(__file__).with_name("live_load_filter.cjs")
MIN_ROWS = 25_000

# The server routes this benchmark knows. A redesign that replaces one
# updates it here; a probe whose route is gone reports "absent".
CATALOG_PATH = "/api/catalog/index"
SETTINGS_PATH = "/api/settings"
PEOPLE_PATH = "/api/people"
SUGGESTIONS_PATH = "/api/people/suggestions"


def thumb_path(item_id: str) -> str:
    return f"/api/media/{item_id}?which=thumb"


def thumb_ids(rows: list[Any]) -> list[str]:
    """Accept compact column arrays or legacy dict rows."""

    def ready_dict(row: dict[str, Any]) -> bool:
        status = ((row.get("renditions") or {}).get("status") or {}).get("thumb")
        return row.get("kind") != "video" and status in (None, "ready")

    out: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            item_id = row.get("id")
            if isinstance(item_id, str) and ready_dict(row):
                out.append(item_id)
            continue
        if not isinstance(row, (list, tuple)) or len(row) < 12:
            continue
        item_id = row[0]
        kind = row[1]
        bits = row[11]
        if not isinstance(item_id, str) or kind == "video":
            continue
        if isinstance(bits, int) and (bits & 8):
            out.append(item_id)
    return out


# --------------------------------------------------------------------- http


def get(base: str, path: str, *, timeout: float = 60.0, headers: dict[str, str] | None = None):
    req = urllib.request.Request(base + path, headers=headers or {})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read()
            return res.status, body, dict(res.headers), time.perf_counter() - started
    except urllib.error.HTTPError as exc:
        return exc.code, b"", dict(exc.headers or {}), time.perf_counter() - started


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * p)))]


def ms_stats(seconds: list[float]) -> dict[str, Any]:
    ms = [s * 1000 for s in seconds]
    if not ms:
        return {"n": 0}
    return {
        "n": len(ms),
        "p50Ms": round(pct(ms, 0.5), 1),
        "p90Ms": round(pct(ms, 0.9), 1),
        "p95Ms": round(pct(ms, 0.95), 1),
        "p99Ms": round(pct(ms, 0.99), 1),
        "maxMs": round(max(ms), 1),
        "over250": sum(1 for v in ms if v > 250),
        "over1000": sum(1 for v in ms if v > 1000),
    }


class Sampler:
    """Hit one cheap route at a fixed rate on its own thread; a stall shows as a slow sample."""

    def __init__(self, base: str, path: str, interval: float) -> None:
        self.base, self.path, self.interval = base, path, interval
        self.samples: list[float] = []
        self.slow: list[tuple[float, float]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._t0 = 0.0

    def _run(self) -> None:
        while not self._stop.is_set():
            status, _, _, took = get(self.base, self.path, timeout=120)
            if status == 200:
                self.samples.append(took)
                if took > 0.25:
                    self.slow.append((round(time.perf_counter() - self._t0, 1), round(took * 1000)))
            self._stop.wait(self.interval)

    def __enter__(self) -> "Sampler":
        self._t0 = time.perf_counter()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=130)

    def report(self) -> dict[str, Any]:
        return {"route": self.path, **ms_stats(self.samples), "slowAt": self.slow[:40]}


# ------------------------------------------------------------------- probes


def preflight(base: str) -> dict[str, Any]:
    status, _, _, _ = get(base, "/api/health", timeout=5)
    if status != 200:
        raise SystemExit(f"server not answering at {base} (status {status})")
    port = base.rsplit(":", 1)[-1].strip("/")
    others = 0
    try:
        netstat = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=30).stdout
        others = sum(1 for line in netstat.splitlines()
                     if "ESTABLISHED" in line and re.search(rf"127\.0\.0\.1:{port}\s+127\.0\.0\.1:\d+", line))
    except Exception:
        others = -1
    rev = subprocess.run(["git", "-C", str(APP), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(APP), "status", "--porcelain", "--", "library"], capture_output=True, text=True).stdout.strip())
    _, jobs, _, _ = get(base, "/api/jobs", timeout=120)
    try:
        queues = {q["id"]: q.get("state") for q in json.loads(jobs).get("queues", [])}
    except Exception:
        queues = {}
    return {"otherClients": others, "gitRev": rev, "libraryDirty": dirty, "queues": queues}


def probe_catalog(base: str, query: str = "") -> tuple[dict[str, Any], list[Any]]:
    """Measure /api/catalog/index. Query string is ignored (filters are client-side)."""
    started = time.perf_counter()
    try:
        res = urllib.request.urlopen(base + CATALOG_PATH, timeout=900)
    except urllib.error.HTTPError as exc:
        return {"absent": True, "status": exc.code}, []
    headers = time.perf_counter() - started
    body = res.read()
    total = time.perf_counter() - started
    size = len(body)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {
            "query": query or "(none)",
            "rows": 0,
            "bytes": size,
            "bytesPerRow": 0,
            "longestLine": size,
            "headersMs": round(headers * 1000),
            "firstRowMs": round(total * 1000),
            "totalSec": round(total, 2),
            "serverTiming": res.headers.get("Server-Timing"),
        }, []
    rows = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = []
    return {
        "query": query or "(none)",
        "rows": len(rows),
        "bytes": size,
        "bytesPerRow": size // max(1, len(rows)),
        "longestLine": size,
        "headersMs": round(headers * 1000),
        "firstRowMs": round(headers * 1000),
        "totalSec": round(total, 2),
        "serverTiming": res.headers.get("Server-Timing"),
    }, rows


def probe_thumbs(base: str, ids: list[str]) -> dict[str, Any]:
    if len(ids) < 900:
        return {"skipped": f"only {len(ids)} thumb ids"}

    def fetch(item_id: str, etag: str | None = None):
        status, body, headers, took = get(base, thumb_path(item_id), timeout=120,
                                          headers={"If-None-Match": etag} if etag else None)
        return status, len(body), headers.get("ETag"), took

    serial = [fetch(i) for i in ids[200:300]]
    again = [fetch(i, e) for i, (_, _, e, _) in zip(ids[200:300], serial)]
    started = time.perf_counter()
    with ThreadPoolExecutor(6) as pool:
        parallel = list(pool.map(fetch, ids[300:600]))
    parallel_sec = time.perf_counter() - started
    background: dict[str, Any] = {}
    worker = threading.Thread(target=lambda: background.update(probe_catalog(base)[0]), daemon=True)
    worker.start()
    time.sleep(1.0)
    started = time.perf_counter()
    with ThreadPoolExecutor(5) as pool:
        loaded = list(pool.map(fetch, ids[600:900]))
    loaded_sec = time.perf_counter() - started
    worker.join()
    return {
        "serial200": ms_stats([r[3] for r in serial]),
        "avgKB": round(sum(r[1] for r in serial) / len(serial) / 1024, 1),
        "serial304": {**ms_stats([r[3] for r in again]), "statuses": sorted({r[0] for r in again})},
        "parallel300Sec": round(parallel_sec, 2),
        "duringCatalog300Sec": round(loaded_sec, 2),
        "duringCatalog": ms_stats([r[3] for r in loaded]),
        "catalogWhileThumbsSec": background.get("totalSec"),
    }


def probe_people(base: str) -> dict[str, Any]:
    status, body, _, took = get(base, PEOPLE_PATH, timeout=900)
    if status != 200:
        return {"absent": True, "status": status}
    rows = json.loads(body).get("people") or []
    largest = max(rows, key=lambda r: int(r.get("itemCount") or 0), default=None)
    return {"sec": round(took, 2), "people": len(rows), "largest": largest and {"id": largest["id"], "itemCount": largest.get("itemCount")}}


def probe_filter_queries(base: str, person_id: str | None) -> dict[str, Any]:
    queries = {"recent": "?recent=1", "search2019": "?q=2019", "sortName": "?sort=name"}
    if person_id:
        queries = {"person": f"?person={person_id}", **queries}
    out = {}
    for name, query in queries.items():
        report, _ = probe_catalog(base, query)
        out[name] = report
    return out


def probe_suggestions(base: str) -> dict[str, Any]:
    status, body, _, took = get(base, SUGGESTIONS_PATH, timeout=1200)
    if status != 200:
        return {"absent": True, "status": status, "sec": round(took, 1)}
    return {"sec": round(took, 1), "bytes": len(body)}


def probe_internals() -> dict[str, Any]:
    """Run in a fresh process: cold record load, the missing-file sweep's path
    build, and the suggestion math. Read-only. Each part may vanish in a redesign."""
    proc = subprocess.run([sys.executable, "-m", "tests.perf.live_load_filter", "--internals-only"],
                          cwd=APP, capture_output=True, text=True, timeout=1800)
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": (proc.stderr or proc.stdout)[-600:]}


def _internals_main() -> None:
    out: dict[str, Any] = {}
    try:
        from library.paths import default_root
        from library import item_index

        root = default_root()
        started = time.perf_counter()
        items = item_index.iter_items(root)
        out["coldRecordLoad"] = {"rows": len(items), "sec": round(time.perf_counter() - started, 2)}
    except Exception as exc:
        print(json.dumps({"error": repr(exc)}))
        return
    try:
        from library import folder_library, renditions as R
        from library.volumes import volume_lookup_scope

        with volume_lookup_scope():
            started = time.perf_counter()
            folders: dict[str, Any] = {}
            paths = []
            for item in item_index.iter_items(root):
                rend = item.get("renditions") or {}
                status = rend.get("status") or {}
                for slot in R.STILL_SLOTS + R.VIDEO_SLOTS:
                    rel = rend.get(slot)
                    if status.get(slot) != "ready" or not isinstance(rel, str) or not rel:
                        continue
                    if rend.get("store") in R.FOLDER_STORES:
                        key = f"{rend['store']}:{rend.get('sourceId') or ''}"
                        if key not in folders:
                            lib = folder_library.for_source_id(root, rend.get("sourceId") or "", rend["store"])
                            folders[key] = None if lib is None else lib.dir
                        if folders[key] is None:
                            continue
                        path = R._folder_file(root, rend, rel)
                        if path is not None:
                            paths.append(path)
            build = time.perf_counter() - started
            started = time.perf_counter()
            missing = sum(1 for p in paths if R._usable_file(p) is None)
            out["missingSweep"] = {"renditions": len(paths), "lockedBuildSec": round(build, 2),
                                   "statSec": round(time.perf_counter() - started, 2), "missing": missing}
    except Exception as exc:
        out["missingSweep"] = {"absent": repr(exc)[:200]}
    try:
        from library.faces import cosine, load_index
        from library import people_suggest as ps

        people = (load_index(root) or {}).get("people") or {}
        ids = sorted(i for i in people if ps._centroid(people[i]))
        sub = ids[:120]
        started = time.perf_counter()
        for i, left in enumerate(sub):
            a = ps._centroid(people[left])
            for right in sub[i + 1:]:
                cosine(a, ps._centroid(people[right]))
        per_pair = (time.perf_counter() - started) / max(1, len(sub) * (len(sub) - 1) / 2)
        pairs = len(ids) * (len(ids) - 1) / 2
        entry = {"people": len(ids), "pairs": int(pairs), "pythonEstimateSec": round(per_pair * pairs, 1)}
        try:
            import numpy as np

            started = time.perf_counter()
            m = np.asarray([ps._centroid(people[i]) for i in ids], dtype=np.float32)
            m /= np.linalg.norm(m, axis=1, keepdims=True)
            sims = m @ m.T
            np.argsort(-sims[np.triu_indices(len(ids), 1)])[:50]
            entry["numpySec"] = round(time.perf_counter() - started, 3)
        except Exception as exc:
            entry["numpySec"] = repr(exc)[:120]
        out["suggestionMath"] = entry
    except Exception as exc:
        out["suggestionMath"] = {"absent": repr(exc)[:200]}
    print(json.dumps(out))


def probe_browser(base: str, quick: bool, raw_path: Path) -> dict[str, Any]:
    cmd = ["node", str(BROWSER_SCRIPT), str(raw_path), "--url", base] + (["--quick"] if quick else [])
    proc = subprocess.run(cmd, cwd=APP, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0 or not raw_path.exists():
        return {"error": (proc.stderr or proc.stdout)[-1200:]}
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    raw_path.unlink()
    return data


# ------------------------------------------------------------------ metrics
#
# (key, unit, primary). Lower is better for every metric. Primary metrics
# decide the exit code; the rest explain where time went.

CLICKS = ["photos", "all", "videos", "all2", "withPeople", "clearWithPeople", "person", "clearPerson",
          "search", "clearSearch", "sortOther", "sortBack"]

SPEC: list[tuple[str, str, bool]] = [
    ("browser.open.firstPaintMs", "ms", True),
    ("browser.open.screenPaintedMs", "ms", True),
    ("browser.open.countKnownMs", "ms", True),
    ("browser.open.settledAfterCountMs", "ms", True),
    ("browser.open.peopleReadyMs", "ms", True),
    ("browser.open.endUnpainted", "tiles", True),
    ("browser.open.longTaskMaxMs", "ms", False),
    ("browser.open.frameGapMaxMs", "ms", False),
    ("browser.open.mediaRequests", "requests", False),
]
for _click in CLICKS:
    SPEC += [
        (f"browser.click.{_click}.readyMs", "ms", True),
        (f"browser.click.{_click}.settledMs", "ms", True),
        (f"browser.click.{_click}.settledIgnoringNoSrcMs", "ms", False),
        (f"browser.click.{_click}.maxBlank", "tiles", False),
        (f"browser.click.{_click}.redownloads", "requests", True),
        (f"browser.click.{_click}.catalogRequests", "requests", False),
    ]
SPEC += [
    ("server.healthDuringBrowser.maxMs", "ms", True),
    ("server.healthDuringBrowser.p99Ms", "ms", False),
    ("server.healthDuringBrowser.over1000", "samples", False),
    ("server.settingsIdle.maxMs", "ms", True),
    ("server.settingsIdle.p90Ms", "ms", False),
    ("server.catalog.firstRowMs", "ms", False),
    ("server.catalog.totalSec", "s", False),
    ("server.catalog.bytes", "bytes", True),
    ("server.thumbs.serial200.p95Ms", "ms", True),
    ("server.thumbs.serial304.p95Ms", "ms", False),
    ("server.thumbs.parallel300Sec", "s", False),
    ("server.thumbs.duringCatalog.p95Ms", "ms", True),
    ("server.people.sec", "s", True),
    ("server.suggestions.sec", "s", True),
    ("server.filters.person.totalSec", "s", False),
    ("server.filters.search2019.totalSec", "s", False),
    ("server.filters.sortName.totalSec", "s", False),
    ("internals.coldRecordLoad.sec", "s", False),
    ("internals.missingSweep.lockedBuildSec", "s", False),
    ("internals.suggestionMath.pythonEstimateSec", "s", False),
]
SLACK = {"ms": 50.0, "s": 0.25, "tiles": 2.0, "requests": 2.0, "samples": 2.0, "bytes": 0.0}


def dig(data: dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def flatten(raw: dict[str, Any]) -> dict[str, float | None]:
    browser = raw.get("browser") or {}
    open_timeout = browser.get("openTimeoutMs") or 600000
    click_timeout = browser.get("clickTimeoutMs") or 20000
    view = {
        "browser": {"open": dict(browser.get("open") or {}), "click": browser.get("phases") or {}},
        "server": raw.get("server") or {},
        "internals": raw.get("internals") or {},
    }
    for key in ("firstPaintMs", "screenPaintedMs", "countKnownMs", "settledAfterCountMs", "peopleReadyMs"):
        if view["browser"]["open"] and view["browser"]["open"].get(key) is None:
            view["browser"]["open"][key] = open_timeout
    for phase in view["browser"]["click"].values():
        if isinstance(phase, dict) and "error" not in phase:
            phase.setdefault("readyMs", None)
            if phase["readyMs"] is None:
                phase["readyMs"] = click_timeout
            for key in ("settledMs", "settledIgnoringNoSrcMs"):
                if phase.get(key) is None:
                    phase[key] = click_timeout
    out: dict[str, float | None] = {}
    for key, _, _ in SPEC:
        value = dig(view, key)
        out[key] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    return out


def verdict(key: str, unit: str, base: float | None, now: float | None) -> str:
    if now is None:
        return "absent"
    if base is None:
        return "new"
    slack = SLACK[unit] if unit != "bytes" else base * 0.05
    if now > base * 1.25 + slack:
        return "WORSE"
    if now < base / 1.25 - slack:
        return "better"
    return "same"


def target_check(targets: dict[str, float], key: str, now: float | None) -> str:
    for pattern, limit in targets.items():
        if re.fullmatch(pattern.replace(".", r"\.").replace("*", "[^.]+"), key):
            if now is None:
                return "-"
            return "met" if now <= limit else f"miss (<= {limit:g})"
    return ""


def compare(metrics: dict[str, float | None], baseline: dict[str, Any] | None) -> tuple[list[list[str]], bool]:
    base_metrics = (baseline or {}).get("metrics") or {}
    targets = json.loads(TARGETS.read_text(encoding="utf-8")) if TARGETS.exists() else {}
    targets = {k: v for k, v in targets.items() if not k.startswith("_")}
    rows = []
    regressed = False
    for key, unit, primary in SPEC:
        now = metrics.get(key)
        base = base_metrics.get(key)
        verdict_text = verdict(key, unit, base, now)
        if primary and verdict_text == "WORSE":
            regressed = True
        fmt = lambda v: "-" if v is None else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:g}")
        rows.append([key, unit, "yes" if primary else "", fmt(base), fmt(now),
                     verdict_text if baseline else "", target_check(targets, key, now)])
    return rows, regressed


def markdown(result: dict[str, Any], rows: list[list[str]]) -> str:
    meta = result["meta"]
    lines = [
        f"# Load and filter benchmark, {meta['stamp']}",
        "",
        f"Server {meta['url']}, git {meta['preflight'].get('gitRev')}"
        f"{' (library/ has uncommitted changes)' if meta['preflight'].get('libraryDirty') else ''}, "
        f"{meta['rows']} pictures, {'quick' if meta['quick'] else 'full'} run, "
        f"{meta['preflight'].get('otherClients')} other connections open before the run.",
        f"Baseline: {meta.get('baseline') or 'none'}.",
        "",
        "| Metric | Unit | Primary | Baseline | Now | Change | Target |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8785")
    parser.add_argument("--quick", action="store_true", help="skip suggestions, internals, filter queries; shorter idle sampling")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--allow-small", action="store_true", help="run on a library under 25,000 pictures")
    parser.add_argument("--internals-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.internals_only:
        _internals_main()
        return 0

    base = args.url.rstrip("/")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    runs = ASSETS / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    say = lambda text: print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)

    raw: dict[str, Any] = {"server": {}}
    say("preflight")
    pre = preflight(base)
    if pre["otherClients"] > 0:
        say(f"warning: {pre['otherClients']} other connections to the server; close other Library tabs for a clean run")

    say("catalog")
    catalog, rows = probe_catalog(base)
    raw["server"]["catalog"] = catalog
    count = catalog.get("rows") or 0
    if not catalog.get("absent") and count < MIN_ROWS and not args.allow_small:
        print(f"library has {count} pictures; this benchmark is for the live library (>= {MIN_ROWS}). Use --allow-small to override.")
        return 2

    say("idle small-request sampling")
    with Sampler(base, SETTINGS_PATH, 0.5) as idle:
        time.sleep(20 if args.quick else 65)
    raw["server"]["settingsIdle"] = idle.report()

    say("thumbs")
    raw["server"]["thumbs"] = probe_thumbs(base, thumb_ids(rows))
    del rows

    say("people")
    raw["server"]["people"] = probe_people(base)
    if not args.quick:
        say("filter queries")
        person = (raw["server"]["people"].get("largest") or {}).get("id")
        raw["server"]["filters"] = probe_filter_queries(base, person)
        say("suggestions (can take minutes today)")
        raw["server"]["suggestions"] = probe_suggestions(base)
        say("internals (fresh process)")
        raw["internals"] = probe_internals()

    say("browser")
    with Sampler(base, "/api/health", 0.05) as health:
        raw["browser"] = probe_browser(base, args.quick, runs / f"{stamp}.browser.tmp.json")
    raw["server"]["healthDuringBrowser"] = health.report()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline.exists() else None
    metrics = flatten(raw)
    table, regressed = compare(metrics, baseline)
    result = {
        "meta": {"stamp": stamp, "url": base, "quick": args.quick, "rows": count, "preflight": pre,
                 "baseline": str(args.baseline.relative_to(APP)) if baseline else None},
        "metrics": metrics,
        "raw": raw,
    }
    out_json = runs / f"{stamp}.json"
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (runs / f"{stamp}.md").write_text(markdown(result, table), encoding="utf-8")
    if args.save_baseline:
        args.baseline.write_text(json.dumps(result, indent=2), encoding="utf-8")
        args.baseline.with_suffix(".md").write_text(markdown(result, compare(metrics, None)[0]), encoding="utf-8")
        say(f"baseline saved: {args.baseline}")

    width = max(len(r[0]) for r in table)
    for row in table:
        print(f"{row[0]:<{width}}  {row[3]:>10}  {row[4]:>10}  {row[5]:<7} {row[6]}")
    say(f"wrote {out_json}")
    if regressed and baseline and not args.save_baseline:
        say("a primary metric got worse than the baseline")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
