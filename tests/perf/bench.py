"""F7 processing-speed benchmark: scratch server, HTTP add-folder, budget table."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_SOURCE = Path(r"J:\Pictures\1. Favorites Pictures")
FFMPEG_BIN = Path(r"C:\ffmpeg\bin")
BENCH_ROOT = REPO_ROOT / ".qa" / "bench"
ARTIFACT_DIR = (
    REPO_ROOT
    / "docs"
    / "features"
    / "processing-feedback"
    / "Rev1.0"
    / "assets"
    / "perf-bench"
)
BUDGETS_PATH = Path(__file__).with_name("budgets.json")

STILL_SLOTS = ("thumb", "preview")
VIDEO_GRID_SLOTS = ("poster",)
ALL_RENDITION_SLOTS = ("thumb", "preview", "poster", "proxy", "playback")

UI_POLL_INTERVAL_SEC = 1.0
DISK_POLL_INTERVAL_SEC = 0.1
VIEWER_PREVIEW_RETRY_SEC = 0.2  # library.js watchViewerStill tick interval

def _ffmpeg_scale_filter(cap: int) -> str:
    return (
        f"scale="
        f"'if(gte(iw,ih),min(iw,{cap}),-2)':"
        f"'if(lt(iw,ih),min(ih,{cap}),-2)'"
    )



class HarnessError(Exception):
    """Non-budget failure (exit 2)."""


def _ffmpeg_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _git_commit(app: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(app), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _load_budgets() -> dict[str, Any]:
    with BUDGETS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _scaled_budget(budgets: dict[str, Any], key: str, count: int) -> float:
    base = float(budgets[key])
    baseline = int(budgets.get("countBaseline", 80))
    if key in budgets.get("scaleLinearWithCount", []):
        return base * (count / baseline)
    return base


def _http_json(
    base: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[float, int, Any]:
    url = base.rstrip("/") + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            elapsed = time.perf_counter() - start
            if not raw:
                return elapsed, resp.status, None
            try:
                return elapsed, resp.status, json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return elapsed, resp.status, raw
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - start
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return elapsed, exc.code, payload


def _http_body_ok(base: str, path: str, timeout: float = 30.0) -> tuple[float, bool]:
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, method="GET")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            elapsed = time.perf_counter() - start
            return elapsed, resp.status == 200 and len(body) > 0
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return time.perf_counter() - start, False


def _run_ffmpeg_webp(source: Path, cap: int) -> float:
    vf = _ffmpeg_scale_filter(cap)
    tmp = source.with_suffix(f".bench-{cap}.webp")
    if tmp.exists():
        tmp.unlink()
    ffmpeg = FFMPEG_BIN / "ffmpeg.exe"
    if not ffmpeg.is_file():
        ffmpeg = FFMPEG_BIN / "ffmpeg"
    cmd = [
        str(ffmpeg),
        "-y",
        "-i",
        str(source),
        "-vf",
        vf,
        "-frames:v",
        "1",
        "-f",
        "webp",
        str(tmp),
    ]
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        env=_ffmpeg_env(),
        check=False,
    )
    elapsed = time.perf_counter() - start
    if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size <= 0:
        if tmp.exists():
            tmp.unlink()
        raise HarnessError(f"ffmpeg baseline failed for {source}")
    tmp.unlink()
    return elapsed


def _baseline_ffmpeg_ms(fixture_dir: Path, sample_n: int = 10) -> dict[str, float]:
    jpgs = sorted(fixture_dir.rglob("*.jpg"), key=lambda p: str(p).lower())
    if len(jpgs) < 1:
        raise HarnessError("fixture has no JPEGs for ffmpeg baseline")
    sample = jpgs[: min(sample_n, len(jpgs))]
    thumb_times = [_run_ffmpeg_webp(p, 320) for p in sample]
    preview_times = [_run_ffmpeg_webp(p, 1600) for p in sample]
    return {
        "thumbSecMean": statistics.mean(thumb_times),
        "previewSecMean": statistics.mean(preview_times),
        "sampleCount": len(sample),
    }


def _collect_source_media(source_root: Path) -> tuple[list[Path], Path | None]:
    jpgs: list[Path] = []
    mov: Path | None = None
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if ".library" in path.parts:
            continue
        rel = path.relative_to(source_root)
        suffix = path.suffix.lower()
        if suffix == ".jpg":
            jpgs.append(path)
        elif suffix == ".mov" and mov is None:
            mov = path
    jpgs.sort(key=lambda p: str(p.relative_to(source_root)).lower())
    return jpgs, mov


def _fixture_ready(fixture_dir: Path, count: int, need_mov: bool) -> bool:
    jpgs = list(fixture_dir.rglob("*.jpg"))
    movs = list(fixture_dir.rglob("*.mov"))
    if len(jpgs) != count:
        return False
    if need_mov and len(movs) != 1:
        return False
    return True


def _ensure_fixture(count: int) -> Path:
    fixture_dir = BENCH_ROOT / f"pictures-{count}"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    jpgs_src, mov_src = _collect_source_media(FIXTURE_SOURCE)
    if len(jpgs_src) < count:
        raise HarnessError(
            f"need {count} JPEGs under {FIXTURE_SOURCE}, found {len(jpgs_src)}"
        )
    if mov_src is None:
        raise HarnessError(f"no .mov found under {FIXTURE_SOURCE}")

    if not _fixture_ready(fixture_dir, count, True):
        if fixture_dir.exists():
            for child in fixture_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        for src in jpgs_src[:count]:
            rel = src.relative_to(FIXTURE_SOURCE)
            dest = fixture_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        rel_mov = mov_src.relative_to(FIXTURE_SOURCE)
        dest_mov = fixture_dir / rel_mov
        dest_mov.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mov_src, dest_mov)

    lib = fixture_dir / ".library"
    if lib.exists():
        shutil.rmtree(lib)
    return fixture_dir


def _prepare_library_root(port: int) -> Path:
    lib_root = BENCH_ROOT / "library-data"
    if lib_root.exists():
        shutil.rmtree(lib_root)
    lib_root.mkdir(parents=True)
    settings = {
        "schemaVersion": 1,
        "previewStore": "with-server",
        "unavailableItems": "show",
        "addFolderDefault": "ask",
        "playProxies": "days-and-all",
        "listenHost": "127.0.0.1",
        "port": port,
        "thumbPx": 320,
        "previewPx": 1600,
        "proxyWidth": 480,
        "placeMatchMeters": 100,
        "tourOrbitSec": 8,
        "tourPictures": 5,
        "tourPictureSec": 3,
        "sort": "date",
        "dir": "desc",
        "zoomLevel": "years",
        "language": "en",
        "faceMatchThreshold": 0.8,
        "faceMinSidePx": 80,
        "transcribeVideos": True,
        "ratingMode": "basic",
        "ratingLearn": False,
    }
    (lib_root / "settings.json").write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )
    return lib_root


def _start_server(app: Path, lib_root: Path) -> subprocess.Popen[Any]:
    env = _ffmpeg_env()
    env["PYTHONPATH"] = str(app.resolve())
    python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    if not FFMPEG_BIN.is_dir():
        raise HarnessError(f"ffmpeg not found at {FFMPEG_BIN}")
    cmd = [
        str(python),
        "-m",
        "library",
        "--root",
        str(lib_root.resolve()),
        "serve",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(app.resolve()),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _wait_health(base: str, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _, status, body = _http_json(base, "/api/health", timeout=2.0)
            if status == 200 and body == {"ok": True}:
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.2)
    raise HarnessError("server did not become healthy")


def _stop_server(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _scan_added(sources: Any) -> int:
    total = 0
    if not isinstance(sources, list):
        return 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        scan = source.get("scan") or {}
        total += int(scan.get("added") or 0)
    return total


def _scan_running(sources: Any) -> bool:
    if not isinstance(sources, list):
        return False
    for source in sources:
        if not isinstance(source, dict):
            continue
        scan = source.get("scan") or {}
        if scan.get("state") == "running":
            return True
    return False


def _item_thumb_ready(item: dict[str, Any]) -> bool:
    kind = item.get("kind")
    status = ((item.get("renditions") or {}).get("status") or {})
    if kind == "video":
        return status.get("poster") == "ready"
    return status.get("thumb") == "ready"


def _grid_complete(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if not _item_thumb_ready(item):
            return False
    return bool(items)


def _any_queued(items: list[dict[str, Any]]) -> bool:
    for item in items:
        status = ((item.get("renditions") or {}).get("status") or {})
        for slot in ALL_RENDITION_SLOTS:
            if status.get(slot) == "queued":
                return True
    return False


def _photos_with_preview_queued(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        if item.get("kind") not in (None, "photo", "live"):
            continue
        status = ((item.get("renditions") or {}).get("status") or {})
        if status.get("preview") == "queued":
            out.append(item)
    return out


def _thumb_ready_count(items: list[dict[str, Any]]) -> int:
    n = 0
    for item in items:
        kind = item.get("kind")
        status = ((item.get("renditions") or {}).get("status") or {})
        if kind == "video":
            if status.get("poster") == "ready":
                n += 1
        elif status.get("thumb") == "ready":
            n += 1
    return n


@dataclass
class Milestones:
    t0: float = 0.0
    first_thumb: float | None = None
    all_grid: float | None = None
    viewer_open: float | None = None
    viewer_preview: float | None = None
    everything: float | None = None
    scan_done: float | None = None


@dataclass
class RunState:
    milestones: Milestones = field(default_factory=Milestones)
    file_read_at: dict[str, float] = field(default_factory=dict)
    last_scan_done: int = 0
    last_scan_phase: str = ""
    scan_total: int = 0
    scan_running: bool = False
    timeline: list[dict[str, Any]] = field(default_factory=list)
    viewer_item_id: str | None = None
    viewer_triggered: bool = False
    viewer_want_sent: bool = False
    last_preview_probe: float = 0.0
    thumb_media_candidate: str | None = None
    thumb_media_kind: str = "photo"
    job_latencies: list[float] = field(default_factory=list)
    items_latencies: list[float] = field(default_factory=list)
    bookkeeping_events: list[dict[str, Any]] = field(default_factory=list)
    ready_renditions: set[str] = field(default_factory=set)
    last_still_ready_at: float = 0.0
    seen_journal_paths: set[str] = field(default_factory=set)
    seen_item_paths: set[str] = field(default_factory=set)
    poll_in_flight: bool = False


def _catalog_item_dirs(lib_root: Path, fixture_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    for base in (lib_root / "catalog", fixture_dir / ".library" / "catalog"):
        folder = base / "items"
        if folder.is_dir():
            dirs.append(folder)
    return dirs


def _catalog_journal_dirs(lib_root: Path, fixture_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    for base in (lib_root / "catalog" / "sources", fixture_dir / ".library" / "catalog" / "sources"):
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if child.is_dir() and child.name.endswith(".files"):
                dirs.append(child)
    return dirs


def _try_load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _item_rel_key(item: dict[str, Any]) -> str | None:
    name = item.get("filename")
    if type(name) is str and name.strip():
        return name.strip().lower()
    locations = item.get("locations") or []
    if isinstance(locations, list) and locations:
        loc = locations[0]
        if isinstance(loc, dict):
            last = loc.get("lastKnownPath")
            if type(last) is str and last.strip():
                return Path(last).name.lower()
    return None


def _note_file_read(state: RunState, rel_key: str, now: float) -> None:
    key = rel_key.replace("\\", "/").lower()
    if key and key not in state.file_read_at:
        state.file_read_at[key] = now


def _scan_disk_reading(
    state: RunState,
    lib_root: Path,
    fixture_dir: Path,
    now: float,
) -> None:
    for journal_dir in _catalog_journal_dirs(lib_root, fixture_dir):
        for path in journal_dir.glob("*.json"):
            key = str(path)
            if key in state.seen_journal_paths:
                continue
            body = _try_load_json_file(path)
            if body is None:
                continue
            rel = body.get("rel")
            if type(rel) is not str:
                continue
            state.seen_journal_paths.add(key)
            _note_file_read(state, rel, now)

    for items_dir in _catalog_item_dirs(lib_root, fixture_dir):
        for path in items_dir.glob("*.json"):
            key = str(path)
            if key in state.seen_item_paths:
                continue
            item = _try_load_json_file(path)
            if item is None:
                continue
            state.seen_item_paths.add(key)
            rel = _item_rel_key(item)
            if rel:
                _note_file_read(state, rel, now)


def _collect_disk_items(lib_root: Path, fixture_dir: Path) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for items_dir in _catalog_item_dirs(lib_root, fixture_dir):
        for path in items_dir.glob("*.json"):
            item = _try_load_json_file(path)
            if item is None:
                continue
            item_id = item.get("id")
            if type(item_id) is not str or not item_id:
                continue
            by_id[item_id] = item
    return list(by_id.values())


def _sorted_catalog_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[str, str]:
        captured = item.get("capturedAt")
        if type(captured) is str:
            return (captured, str(item.get("id") or ""))
        return ("", str(item.get("id") or ""))

    return sorted(items, key=sort_key)


def _update_scan_from_activity(
    state: RunState, activity: Any, now: float, expected_items: int
) -> None:
    if not isinstance(activity, dict):
        return
    scan = activity.get("scan")
    if not isinstance(scan, dict):
        scan = {}
    phase = str(scan.get("phase") or activity.get("phase") or "idle")
    done = int(scan.get("done") or activity.get("done") or 0)
    total = int(scan.get("total") or activity.get("total") or 0)
    if total > 0:
        state.scan_total = total

    if phase == "scan":
        state.scan_running = True
        state.last_scan_done = max(state.last_scan_done, done)
    elif state.last_scan_phase == "scan":
        total_use = total or state.scan_total
        state.last_scan_done = max(state.last_scan_done, done, total_use)
        state.scan_running = False
        if state.milestones.scan_done is None:
            state.milestones.scan_done = now

    state.last_scan_phase = phase

    if (
        state.milestones.scan_done is None
        and phase != "scan"
        and state.scan_total > 0
        and state.last_scan_done >= state.scan_total
    ):
        state.milestones.scan_done = now


def _reading_metrics(
    file_read_at: dict[str, float], t0: float, scan_done: float | None
) -> dict[str, Any]:
    times = sorted(file_read_at.values())
    if not times or scan_done is None:
        return {"rate": None, "tenthRatio": None, "files": len(times), "scanWallSec": None}
    duration = max(scan_done - t0, 1e-6)
    rate = len(times) / duration
    scan_wall = scan_done - t0
    if len(times) < 10:
        return {
            "rate": rate,
            "tenthRatio": None,
            "files": len(times),
            "scanWallSec": scan_wall,
        }
    tenth = max(1, len(times) // 10)
    deltas: list[float] = [times[0] - t0]
    for i in range(1, len(times)):
        deltas.append(times[i] - times[i - 1])
    first_mean = statistics.mean(deltas[:tenth])
    last_mean = statistics.mean(deltas[-tenth:])
    ratio = (
        last_mean / first_mean
        if first_mean > 0 and last_mean > 0
        else None
    )
    return {
        "rate": rate,
        "tenthRatio": ratio,
        "files": len(times),
        "scanWallSec": scan_wall,
    }


def _track_bookkeeping(
    state: RunState,
    items: list[dict[str, Any]],
    now: float,
    ffmpeg: dict[str, float],
) -> None:
    for item in items:
        if item.get("kind") not in (None, "photo", "live"):
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        status = ((item.get("renditions") or {}).get("status") or {})
        for slot in STILL_SLOTS:
            key = f"{item_id}:{slot}"
            if status.get(slot) != "ready" or key in state.ready_renditions:
                continue
            state.ready_renditions.add(key)
            base = ffmpeg["thumbSecMean"] if slot == "thumb" else ffmpeg["previewSecMean"]
            gap = now - state.last_still_ready_at if state.last_still_ready_at > 0 else 0.0
            bk_ms = max(0.0, gap - base) * 1000.0 if gap > 0 else None
            state.bookkeeping_events.append(
                {
                    "at": now,
                    "gapSec": gap,
                    "slot": slot,
                    "bookkeepingMs": bk_ms,
                }
            )
            state.last_still_ready_at = now


BOOKKEEPING_MIN_SAMPLES = 5


def _finalize_bookkeeping(state: RunState) -> dict[str, Any]:
    events = sorted(state.bookkeeping_events, key=lambda e: float(e.get("at") or 0))
    scan_done = state.milestones.scan_done

    steady: list[float] = []
    if scan_done is not None:
        steady_cutoff = scan_done + 2.0
        for ev in events:
            at = float(ev.get("at") or 0)
            if at < steady_cutoff:
                continue
            gap = float(ev.get("gapSec") or 0)
            ms = ev.get("bookkeepingMs")
            if ms is None or not (0 < gap < 4.0):
                continue
            steady.append(float(ms))

    if len(steady) >= BOOKKEEPING_MIN_SAMPLES:
        return {
            "meanMs": statistics.mean(steady),
            "window": "postScanSteady",
            "sampleCount": len(steady),
            "samplesMs": steady,
        }

    first_thumb = state.milestones.first_thumb
    fallback: list[float] = []
    skipped_first = False
    if first_thumb is not None:
        for ev in events:
            at = float(ev.get("at") or 0)
            if at < first_thumb:
                continue
            gap = float(ev.get("gapSec") or 0)
            ms = ev.get("bookkeepingMs")
            if ms is None or gap <= 0 or gap > 4.0:
                continue
            if not skipped_first:
                skipped_first = True
                continue
            fallback.append(float(ms))

    if len(fallback) >= BOOKKEEPING_MIN_SAMPLES:
        return {
            "meanMs": statistics.mean(fallback),
            "window": "afterFirstThumb",
            "sampleCount": len(fallback),
            "samplesMs": fallback,
        }

    return {
        "meanMs": None,
        "window": "none",
        "sampleCount": len(fallback),
        "samplesMs": fallback,
        "steadyAttemptCount": len(steady),
    }


def _budget_row(
    row_id: str,
    budget: str,
    target: float,
    value: float | None,
    *,
    reason: str,
    ok: bool | None,
) -> dict[str, Any]:
    if value is None or ok is None:
        return {
            "id": row_id,
            "budget": budget,
            "target": target,
            "measured": None,
            "measuredDisplay": f"n/a ({reason})",
            "result": "NO DATA",
            "pass": False,
        }
    passed = ok
    return {
        "id": row_id,
        "budget": budget,
        "target": target,
        "measured": value,
        "measuredDisplay": f"{value:.3f}",
        "result": "PASS" if passed else "FAIL",
        "pass": passed,
    }


def _ui_emulator_loop(
    base: str,
    stop: threading.Event,
    state: RunState,
    expected_items: int,
) -> None:
    """Match library.js: activity 1 Hz; poll 1 Hz health -> jobs + items while processing."""
    next_activity = time.monotonic()
    next_poll = time.monotonic()
    while not stop.is_set():
        now = time.monotonic()
        if now >= next_activity:
            next_activity = now + UI_POLL_INTERVAL_SEC
            try:
                _, _, activity = _http_json(base, "/api/activity", timeout=30.0)
                _update_scan_from_activity(state, activity, now, expected_items)
            except (urllib.error.URLError, TimeoutError, OSError):
                pass

        if now >= next_poll and not state.poll_in_flight:
            next_poll = now + UI_POLL_INTERVAL_SEC
            state.poll_in_flight = True
            try:
                _, health_status, _ = _http_json(base, "/api/health", timeout=10.0)
                if health_status != 200:
                    continue
                elapsed, status, _ = _http_json(base, "/api/jobs", timeout=60.0)
                if status == 200:
                    state.job_latencies.append(elapsed * 1000.0)
                if state.milestones.everything is None:
                    elapsed, status, _ = _http_json(base, "/api/items", timeout=120.0)
                    if status == 200:
                        state.items_latencies.append(elapsed * 1000.0)
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            finally:
                state.poll_in_flight = False

        time.sleep(0.05)


def _heavy_items_loop(base: str, stop: threading.Event, state: RunState) -> None:
    """Stress mode: hammer GET /api/items every 100 ms (legacy bench load)."""
    while not stop.is_set():
        if state.milestones.everything is not None:
            return
        try:
            elapsed, status, _ = _http_json(base, "/api/items", timeout=120.0)
            if status == 200:
                state.items_latencies.append(elapsed * 1000.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(DISK_POLL_INTERVAL_SEC)


def _confirm_first_thumb_media(base: str, state: RunState, now: float) -> None:
    if state.milestones.first_thumb is not None or not state.thumb_media_candidate:
        return
    iid = state.thumb_media_candidate
    item_kind = state.thumb_media_kind or "photo"
    which = "poster" if item_kind == "video" else "thumb"
    _, ok = _http_body_ok(
        base,
        f"/api/media/{urllib.parse.quote(iid, safe='')}?which={which}",
    )
    if ok:
        state.milestones.first_thumb = now


def _open_viewer(base: str, state: RunState, item_id: str, now: float) -> None:
    state.viewer_triggered = True
    state.viewer_item_id = item_id
    state.milestones.viewer_open = now
    if not state.viewer_want_sent:
        state.viewer_want_sent = True
        _http_json(
            base,
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/want",
            method="POST",
            body={},
            timeout=30.0,
        )


def _probe_viewer_preview(base: str, state: RunState, now: float) -> None:
    if not state.viewer_triggered or state.milestones.viewer_preview is not None:
        return
    if now - state.last_preview_probe < VIEWER_PREVIEW_RETRY_SEC:
        return
    state.last_preview_probe = now
    if not state.viewer_item_id:
        return
    _, ok = _http_body_ok(
        base,
        f"/api/media/{urllib.parse.quote(state.viewer_item_id, safe='')}?which=preview",
    )
    if ok:
        state.milestones.viewer_preview = now


def _disk_poll_loop(
    base: str,
    state: RunState,
    lib_root: Path,
    fixture_dir: Path,
    count: int,
    ffmpeg: dict[str, float],
    deadline: float,
) -> None:
    expected_items = count + 1
    thumbs_needed = max(1, (expected_items * 10) // 100)
    while time.monotonic() < deadline:
        now = time.monotonic()
        t_rel = now - state.milestones.t0
        _scan_disk_reading(state, lib_root, fixture_dir, now)
        items = _sorted_catalog_items(_collect_disk_items(lib_root, fixture_dir))
        _track_bookkeeping(state, items, now, ffmpeg)

        if state.milestones.first_thumb is None:
            for item in items:
                if not _item_thumb_ready(item):
                    continue
                iid = item.get("id")
                if not isinstance(iid, str):
                    continue
                state.thumb_media_candidate = iid
                state.thumb_media_kind = item.get("kind") if type(item.get("kind")) is str else "photo"
                _confirm_first_thumb_media(base, state, now)
                break

        if state.milestones.all_grid is None and len(items) >= expected_items and _grid_complete(items):
            state.milestones.all_grid = now

        if not state.viewer_triggered:
            thumbs = _thumb_ready_count(items)
            if thumbs >= thumbs_needed or (
                t_rel >= 5.0 and state.milestones.scan_done is None
            ):
                queued = _photos_with_preview_queued(items)
                pick = queued[-1] if queued else None
                if pick is None:
                    for item in reversed(items):
                        if item.get("kind") in (None, "photo", "live"):
                            pick = item
                            break
                if pick and isinstance(pick.get("id"), str):
                    _open_viewer(base, state, pick["id"], now)

        if state.milestones.everything is None and len(items) >= expected_items and not _any_queued(items):
            state.milestones.everything = now

        if (
            state.milestones.scan_done is None
            and len(state.file_read_at) >= expected_items
            and not state.scan_running
        ):
            state.milestones.scan_done = now
        if state.milestones.scan_done is None and not state.scan_running and len(items) >= expected_items:
            state.milestones.scan_done = now

        _probe_viewer_preview(base, state, now)

        if len(state.timeline) < 500 or int(t_rel * 10) % 10 == 0:
            state.timeline.append(
                {
                    "t": round(t_rel, 3),
                    "diskItems": len(items),
                    "filesRead": len(state.file_read_at),
                    "thumbsReady": _thumb_ready_count(items),
                    "queued": _any_queued(items) if items else True,
                }
            )

        if state.milestones.everything is not None:
            break
        time.sleep(DISK_POLL_INTERVAL_SEC)


def _compact_activity(activity: Any) -> dict[str, Any]:
    if not isinstance(activity, dict):
        return {}
    scan = activity.get("scan")
    if isinstance(scan, dict):
        return {
            "phase": scan.get("phase"),
            "done": scan.get("done"),
            "total": scan.get("total"),
            "file": scan.get("file"),
        }
    return {"phase": activity.get("phase"), "done": activity.get("done")}


def _build_results(
    state: RunState,
    count: int,
    budgets: dict[str, Any],
    ffmpeg: dict[str, float],
    timed_out: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    m = state.milestones
    t0 = m.t0
    reading = _reading_metrics(state.file_read_at, t0, m.scan_done)
    bk = _finalize_bookkeeping(state)

    def since(start: float | None) -> float | None:
        if start is None:
            return None
        return start - t0

    def timeout_reason(milestone: str) -> str:
        return "timed out" if timed_out else f"{milestone} not reached"

    rate = reading["rate"]
    rate_reason = "scan did not finish"
    if m.scan_done is None:
        rate_reason = timeout_reason("scan")
    elif not state.file_read_at:
        rate_reason = "no files on disk"

    ratio = reading["tenthRatio"]
    ratio_reason = "fewer than 10 files indexed"
    if m.scan_done is None:
        ratio_reason = timeout_reason("scan")
    elif len(state.file_read_at) < 10:
        ratio_reason = "fewer than 10 files indexed"

    viewer_lat: float | None = None
    if m.viewer_preview is not None and m.viewer_open is not None:
        viewer_lat = m.viewer_preview - m.viewer_open
    viewer_reason = "viewer not opened"
    if m.viewer_open is None:
        viewer_reason = timeout_reason("viewer open")
    elif m.viewer_preview is None:
        viewer_reason = timeout_reason("viewer preview")

    jobs_p95 = _percentile(state.job_latencies, 95)
    items_p95 = _percentile(state.items_latencies, 95)

    bk_mean = bk["meanMs"]
    bk_reason = f"fewer than {BOOKKEEPING_MIN_SAMPLES} completion gaps"
    if bk.get("steadyAttemptCount") is not None and bk["sampleCount"] < BOOKKEEPING_MIN_SAMPLES:
        bk_reason = (
            f"fewer than {BOOKKEEPING_MIN_SAMPLES} gaps "
            f"(steady={bk.get('steadyAttemptCount', 0)}, fallback={bk['sampleCount']})"
        )

    rows = [
        _budget_row(
            "readingRate",
            f">= {budgets['readingRateMinPicturesPerSec']} pictures/s",
            budgets["readingRateMinPicturesPerSec"],
            rate,
            reason=rate_reason,
            ok=rate >= budgets["readingRateMinPicturesPerSec"] if rate is not None else None,
        ),
        _budget_row(
            "readingTenthRatio",
            f"<= {budgets['readingTenthRatioMax']}",
            budgets["readingTenthRatioMax"],
            ratio,
            reason=ratio_reason,
            ok=(
                ratio <= budgets["readingTenthRatioMax"]
                if ratio is not None and ratio > 0
                else None
            ),
        ),
        _budget_row(
            "firstThumb",
            f"<= {budgets['firstThumbMaxSec']} s",
            budgets["firstThumbMaxSec"],
            since(m.first_thumb),
            reason=timeout_reason("first thumb"),
            ok=(
                since(m.first_thumb) <= budgets["firstThumbMaxSec"]
                if m.first_thumb is not None
                else None
            ),
        ),
        _budget_row(
            "allThumbsPoster",
            f"<= {_scaled_budget(budgets, 'allThumbsPosterMaxSec', count):.1f} s (scaled)",
            _scaled_budget(budgets, "allThumbsPosterMaxSec", count),
            since(m.all_grid),
            reason=timeout_reason("all grid thumbs"),
            ok=(
                since(m.all_grid) <= _scaled_budget(budgets, "allThumbsPosterMaxSec", count)
                if m.all_grid is not None
                else None
            ),
        ),
        _budget_row(
            "viewerPreview",
            f"<= {budgets['viewerPreviewMaxSec']} s from viewer open",
            budgets["viewerPreviewMaxSec"],
            viewer_lat,
            reason=viewer_reason,
            ok=(
                viewer_lat <= budgets["viewerPreviewMaxSec"]
                if viewer_lat is not None
                else None
            ),
        ),
        _budget_row(
            "everythingDone",
            f"<= {_scaled_budget(budgets, 'everythingDoneMaxSec', count):.1f} s (scaled)",
            _scaled_budget(budgets, "everythingDoneMaxSec", count),
            since(m.everything),
            reason=timeout_reason("all renditions"),
            ok=(
                since(m.everything) <= _scaled_budget(budgets, "everythingDoneMaxSec", count)
                if m.everything is not None
                else None
            ),
        ),
        _budget_row(
            "bookkeeping",
            f"<= {budgets['bookkeepingMaxMs']} ms/job",
            budgets["bookkeepingMaxMs"],
            bk_mean if isinstance(bk_mean, (int, float)) else None,
            reason=bk_reason,
            ok=(
                float(bk_mean) <= budgets["bookkeepingMaxMs"]
                if isinstance(bk_mean, (int, float))
                else None
            ),
        ),
        _budget_row(
            "apiJobsP95",
            f"<= {budgets['apiJobsP95MaxMs']} ms",
            budgets["apiJobsP95MaxMs"],
            jobs_p95,
            reason="no /api/jobs samples",
            ok=jobs_p95 <= budgets["apiJobsP95MaxMs"] if jobs_p95 is not None else None,
        ),
        _budget_row(
            "apiItemsP95",
            f"<= {budgets['apiItemsP95MaxMs']} ms",
            budgets["apiItemsP95MaxMs"],
            items_p95,
            reason="no /api/items samples",
            ok=items_p95 <= budgets["apiItemsP95MaxMs"] if items_p95 is not None else None,
        ),
    ]
    return rows, bk


def _print_table(rows: list[dict[str, Any]]) -> None:
    print()
    print(f"{'Budget':<22} {'Target':<18} {'Measured':<28} {'Result':<8}")
    print("-" * 78)
    for row in rows:
        text = row.get("measuredDisplay")
        if not text:
            measured = row.get("measured")
            text = f"{measured:.3f}" if isinstance(measured, float) else "n/a (no data)"
        result = row.get("result") or ("PASS" if row.get("pass") else "FAIL")
        print(f"{row['id']:<22} {row['budget']:<18} {text:<28} {result:<8}")
    print()


def run_bench(
    count: int,
    label: str,
    app: Path,
    port: int,
    keep: bool,
    load: str = "ui",
) -> int:
    budgets = _load_budgets()
    app = app.resolve()
    fixture_dir = _ensure_fixture(count)
    ffmpeg = _baseline_ffmpeg_ms(fixture_dir)
    lib_root = _prepare_library_root(port)
    base = f"http://127.0.0.1:{port}"

    proc: subprocess.Popen[Any] | None = None
    stop_latency = threading.Event()
    state = RunState()
    timed_out = False
    exit_code = 2

    try:
        try:
            _, status, _ = _http_json(base, "/api/health", timeout=0.5)
            if status == 200:
                raise HarnessError(f"port {port} already in use")
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        proc = _start_server(app, lib_root)
        _wait_health(base)

        body = {
            "path": str(fixture_dir.resolve()),
            "mode": "serve-from-there",
            "previewStore": "with-source",
        }
        state.milestones.t0 = time.monotonic()
        _, status, _ = _http_json(base, "/api/sources", method="POST", body=body, timeout=120.0)
        if status not in (200, 202):
            raise HarnessError(f"add folder failed with HTTP {status}")

        expected_items = count + 1
        ui_thread = threading.Thread(
            target=_ui_emulator_loop,
            args=(base, stop_latency, state, expected_items),
            name="bench-ui-poll",
            daemon=True,
        )
        ui_thread.start()
        heavy_thread: threading.Thread | None = None
        if load == "heavy":
            heavy_thread = threading.Thread(
                target=_heavy_items_loop,
                args=(base, stop_latency, state),
                name="bench-heavy-items",
                daemon=True,
            )
            heavy_thread.start()

        deadline = time.monotonic() + max(300.0, 4.0 * count)
        _disk_poll_loop(base, state, lib_root, fixture_dir, count, ffmpeg, deadline)
        timed_out = state.milestones.everything is None and time.monotonic() >= deadline

        stop_latency.set()
        ui_thread.join(timeout=5.0)
        if heavy_thread is not None:
            heavy_thread.join(timeout=5.0)

        rows, bookkeeping = _build_results(state, count, budgets, ffmpeg, timed_out)
        _print_table(rows)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        payload = {
            "label": label,
            "load": load,
            "count": count,
            "appPath": str(app),
            "gitCommit": _git_commit(app),
            "port": port,
            "fixtureDir": str(fixture_dir),
            "libraryRoot": str(lib_root),
            "machine": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python": sys.version.split()[0],
            },
            "ffmpegBaseline": ffmpeg,
            "budgets": budgets,
            "scaledTargets": {
                "allThumbsPosterMaxSec": _scaled_budget(
                    budgets, "allThumbsPosterMaxSec", count
                ),
                "everythingDoneMaxSec": _scaled_budget(
                    budgets, "everythingDoneMaxSec", count
                ),
            },
            "timeoutSec": max(300.0, 4.0 * count),
            "timedOut": timed_out,
            "results": rows,
            "milestonesSec": {
                "firstThumb": (
                    state.milestones.first_thumb - state.milestones.t0
                    if state.milestones.first_thumb
                    else None
                ),
                "allGrid": (
                    state.milestones.all_grid - state.milestones.t0
                    if state.milestones.all_grid
                    else None
                ),
                "viewerOpen": (
                    state.milestones.viewer_open - state.milestones.t0
                    if state.milestones.viewer_open
                    else None
                ),
                "viewerPreviewLatency": (
                    state.milestones.viewer_preview - state.milestones.viewer_open
                    if state.milestones.viewer_preview
                    and state.milestones.viewer_open
                    else None
                ),
                "everything": (
                    state.milestones.everything - state.milestones.t0
                    if state.milestones.everything
                    else None
                ),
                "scanDone": (
                    state.milestones.scan_done - state.milestones.t0
                    if state.milestones.scan_done
                    else None
                ),
            },
            "latencyMs": {
                "jobs": {
                    "p50": _percentile(state.job_latencies, 50),
                    "p95": _percentile(state.job_latencies, 95),
                    "max": max(state.job_latencies) if state.job_latencies else None,
                    "n": len(state.job_latencies),
                },
                "items": {
                    "p50": _percentile(state.items_latencies, 50),
                    "p95": _percentile(state.items_latencies, 95),
                    "max": max(state.items_latencies) if state.items_latencies else None,
                    "n": len(state.items_latencies),
                },
            },
            "reading": _reading_metrics(
                state.file_read_at,
                state.milestones.t0,
                state.milestones.scan_done,
            ),
            "viewerItemId": state.viewer_item_id,
            "timeline": state.timeline[-400:],
            "bookkeeping": bookkeeping,
        }

        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact = ARTIFACT_DIR / f"bench-{stamp}-{label}.json"
        latest = ARTIFACT_DIR / f"latest-{label}.json"
        text = json.dumps(payload, indent=2) + "\n"
        artifact.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")
        print(f"Artifact: {artifact}")

        exit_code = 0 if all(r.get("result") == "PASS" for r in rows) else 1
    except HarnessError as exc:
        print(f"Harness error: {exc}", file=sys.stderr)
        exit_code = 2
    finally:
        stop_latency.set()
        _stop_server(proc)
        if not keep and lib_root.exists():
            for _ in range(5):
                try:
                    shutil.rmtree(lib_root)
                    break
                except OSError:
                    time.sleep(0.3)
    return exit_code


def _compare_reports(path_a: Path, path_b: Path) -> int:
    try:
        a = json.loads(path_a.read_text(encoding="utf-8"))
        b = json.loads(path_b.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Compare failed: {exc}", file=sys.stderr)
        return 2
    ra = {r["id"]: r for r in a.get("results", []) if isinstance(r, dict)}
    rb = {r["id"]: r for r in b.get("results", []) if isinstance(r, dict)}
    ids = list(dict.fromkeys(list(ra.keys()) + list(rb.keys())))
    label_a = a.get("label", path_a.stem)
    label_b = b.get("label", path_b.stem)
    print()
    print(f"{'Budget':<22} {label_a + ' measured':<18} {label_b + ' measured':<18} {'Delta':<12}")
    print("-" * 72)
    for bid in ids:
        ma = ra.get(bid, {}).get("measured")
        mb = rb.get(bid, {}).get("measured")
        da = ra.get(bid, {}).get("measuredDisplay") or (
            f"{ma:.3f}" if isinstance(ma, float) else ("n/a" if ma is None else str(ma))
        )
        db = rb.get(bid, {}).get("measuredDisplay") or (
            f"{mb:.3f}" if isinstance(mb, float) else ("n/a" if mb is None else str(mb))
        )
        delta = "n/a"
        if isinstance(ma, (int, float)) and isinstance(mb, (int, float)):
            delta = f"{mb - ma:+.3f}"
        print(f"{bid:<22} {da:<18} {db:<18} {delta:<12}")
    print()
    print(f"A: {path_a}  commit={a.get('gitCommit', '?')}  load={a.get('load', '?')}")
    print(f"B: {path_b}  commit={b.get('gitCommit', '?')}  load={b.get('load', '?')}")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F7 processing speed benchmark")
    parser.add_argument("--count", type=int, default=80)
    parser.add_argument("--label", default="default")
    parser.add_argument("--app", type=Path, default=REPO_ROOT)
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument(
        "--load",
        choices=("ui", "heavy"),
        default="ui",
        help="ui = 1 Hz poll like library.js (default); heavy = stress /api/items at 100 ms",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar="JSON",
        type=Path,
        help="Print two bench JSON results side by side",
    )
    args = parser.parse_args(argv)
    if args.compare:
        return _compare_reports(args.compare[0], args.compare[1])
    if args.port == 8785:
        print("Refusing port 8785 (production server).", file=sys.stderr)
        return 2
    return run_bench(args.count, args.label, args.app, args.port, args.keep, args.load)


if __name__ == "__main__":
    raise SystemExit(main())
