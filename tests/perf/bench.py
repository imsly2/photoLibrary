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
    added_times: list[float] = field(default_factory=list)
    last_added: int = 0
    last_scan_done: int = 0
    last_scan_phase: str = ""
    scan_total: int = 0
    timeline: list[dict[str, Any]] = field(default_factory=list)
    viewer_item_id: str | None = None
    viewer_triggered: bool = False
    scan_running: bool = False
    job_latencies: list[float] = field(default_factory=list)
    items_latencies: list[float] = field(default_factory=list)
    bookkeeping_samples: list[float] = field(default_factory=list)
    queued_at: dict[str, float] = field(default_factory=dict)
    ready_renditions: set[str] = field(default_factory=set)
    last_still_ready_at: float = 0.0


def _record_added_crossing(state: RunState, now: float, added: int) -> None:
    if added > state.last_added:
        for _ in range(state.last_added, added):
            state.added_times.append(now)
        state.last_added = added


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
        if done > state.last_scan_done:
            for _ in range(state.last_scan_done, done):
                state.added_times.append(now)
            state.last_scan_done = done
    elif state.last_scan_phase == "scan":
        total_use = total or state.scan_total
        if total_use > 0 and state.last_scan_done < total_use:
            for _ in range(state.last_scan_done, total_use):
                state.added_times.append(now)
            state.last_scan_done = total_use
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


def _reading_metrics(added_times: list[float], t0: float, scan_done: float | None) -> dict[str, Any]:
    if not added_times or scan_done is None:
        return {"rate": None, "tenthRatio": None}
    duration = max(scan_done - t0, 1e-6)
    rate = len(added_times) / duration
    if len(added_times) < 10:
        return {"rate": rate, "tenthRatio": None}
    n = len(added_times)
    tenth = max(1, n // 10)
    first_span = added_times[tenth - 1] - t0
    last_span = added_times[-1] - added_times[-tenth]
    first_mean = first_span / tenth if tenth else None
    last_mean = last_span / tenth if tenth else None
    ratio = (
        last_mean / first_mean
        if first_mean and last_mean and first_mean > 0
        else None
    )
    return {"rate": rate, "tenthRatio": ratio}


def _track_bookkeeping(
    state: RunState,
    items: list[dict[str, Any]],
    now: float,
    scan_complete: bool,
    ffmpeg: dict[str, float],
) -> None:
    if not scan_complete or state.milestones.scan_done is None:
        state.ready_renditions.clear()
        state.last_still_ready_at = 0.0
        return
    if now - state.milestones.scan_done < 2.0:
        return
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
            if state.last_still_ready_at > state.milestones.scan_done:
                gap = now - state.last_still_ready_at
                if 0 < gap < 4.0:
                    state.bookkeeping_samples.append(max(0.0, gap - base) * 1000.0)
            state.last_still_ready_at = now


def _latency_worker(base: str, stop: threading.Event, state: RunState) -> None:
    while not stop.is_set():
        try:
            elapsed, status, _ = _http_json(base, "/api/jobs", timeout=60.0)
            if status == 200:
                state.job_latencies.append(elapsed * 1000.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if stop.is_set():
            break
        time.sleep(0.5)
        try:
            elapsed, status, _ = _http_json(base, "/api/items", timeout=60.0)
            if status == 200:
                state.items_latencies.append(elapsed * 1000.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.5)


def _poll_loop(
    base: str,
    state: RunState,
    count: int,
    ffmpeg: dict[str, float],
    deadline: float,
) -> None:
    expected_items = count + 1
    thumbs_needed = max(1, (expected_items * 10) // 100)
    poll_idx = 0
    while time.monotonic() < deadline:
        now = time.monotonic()
        t_rel = now - state.milestones.t0
        poll_idx += 1
        try:
            _, _, activity = _http_json(base, "/api/activity", timeout=30.0)
            _update_scan_from_activity(state, activity, now, expected_items)

            if poll_idx % 5 == 0:
                _, _, sources = _http_json(base, "/api/sources", timeout=30.0)
                added = _scan_added(sources)
                if _scan_running(sources):
                    state.scan_running = True
                state.timeline.append(
                    {
                        "t": round(t_rel, 3),
                        "scanAdded": added,
                        "scanRunning": state.scan_running,
                        "activity": _compact_activity(activity),
                    }
                )
            else:
                _, _, items_raw = _http_json(base, "/api/items", timeout=60.0)
                items = items_raw if isinstance(items_raw, list) else []
                scan_complete = state.milestones.scan_done is not None
                _track_bookkeeping(state, items, now, scan_complete, ffmpeg)

                if state.milestones.first_thumb is None:
                    for item in items:
                        if not _item_thumb_ready(item):
                            continue
                        iid = item.get("id")
                        if not isinstance(iid, str):
                            continue
                        which = "poster" if item.get("kind") == "video" else "thumb"
                        _, ok = _http_body_ok(
                            base,
                            f"/api/media/{urllib.parse.quote(iid, safe='')}?which={which}",
                        )
                        if ok:
                            state.milestones.first_thumb = now
                            break

                if state.milestones.all_grid is None and _grid_complete(items):
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
                            state.viewer_triggered = True
                            state.viewer_item_id = pick["id"]
                            state.milestones.viewer_open = now

                if state.milestones.everything is None and items and not _any_queued(items):
                    state.milestones.everything = now

                if (
                    state.milestones.scan_done is None
                    and len(items) >= expected_items
                    and not state.scan_running
                ):
                    state.milestones.scan_done = now

                state.timeline.append(
                    {
                        "t": round(t_rel, 3),
                        "items": len(items),
                        "thumbsReady": _thumb_ready_count(items),
                        "queued": _any_queued(items),
                    }
                )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            state.timeline.append({"t": round(t_rel, 3), "error": str(exc)})

        if (
            state.viewer_triggered
            and state.milestones.viewer_preview is None
            and state.viewer_item_id
        ):
            _, ok = _http_body_ok(
                base,
                f"/api/media/{urllib.parse.quote(state.viewer_item_id, safe='')}?which=preview",
            )
            if ok:
                state.milestones.viewer_preview = time.monotonic()

        if state.milestones.everything is not None:
            break
        time.sleep(0.1)


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
) -> list[dict[str, Any]]:
    m = state.milestones
    t0 = m.t0
    reading = _reading_metrics(state.added_times, t0, m.scan_done)

    def since(start: float | None) -> float | None:
        if start is None:
            return None
        return start - t0

    bk_mean = (
        statistics.mean(state.bookkeeping_samples)
        if state.bookkeeping_samples
        else None
    )

    rows = [
        {
            "id": "readingRate",
            "budget": f">= {budgets['readingRateMinPicturesPerSec']} pictures/s",
            "target": budgets["readingRateMinPicturesPerSec"],
            "measured": reading["rate"],
            "pass": reading["rate"] is not None
            and reading["rate"] >= budgets["readingRateMinPicturesPerSec"],
        },
        {
            "id": "readingTenthRatio",
            "budget": f"<= {budgets['readingTenthRatioMax']}",
            "target": budgets["readingTenthRatioMax"],
            "measured": reading["tenthRatio"],
            "pass": reading["tenthRatio"] is not None
            and reading["tenthRatio"] > 0
            and reading["tenthRatio"] <= budgets["readingTenthRatioMax"],
        },
        {
            "id": "firstThumb",
            "budget": f"<= {budgets['firstThumbMaxSec']} s",
            "target": budgets["firstThumbMaxSec"],
            "measured": since(m.first_thumb),
            "pass": m.first_thumb is not None
            and since(m.first_thumb) <= budgets["firstThumbMaxSec"],
        },
        {
            "id": "allThumbsPoster",
            "budget": f"<= {_scaled_budget(budgets, 'allThumbsPosterMaxSec', count):.1f} s (scaled)",
            "target": _scaled_budget(budgets, "allThumbsPosterMaxSec", count),
            "measured": since(m.all_grid),
            "pass": m.all_grid is not None
            and since(m.all_grid) <= _scaled_budget(budgets, "allThumbsPosterMaxSec", count),
        },
        {
            "id": "viewerPreview",
            "budget": f"<= {budgets['viewerPreviewMaxSec']} s from viewer open",
            "target": budgets["viewerPreviewMaxSec"],
            "measured": (
                (m.viewer_preview - m.viewer_open)
                if m.viewer_preview is not None and m.viewer_open is not None
                else None
            ),
            "pass": m.viewer_preview is not None
            and m.viewer_open is not None
            and (m.viewer_preview - m.viewer_open) <= budgets["viewerPreviewMaxSec"],
        },
        {
            "id": "everythingDone",
            "budget": f"<= {_scaled_budget(budgets, 'everythingDoneMaxSec', count):.1f} s (scaled)",
            "target": _scaled_budget(budgets, "everythingDoneMaxSec", count),
            "measured": since(m.everything),
            "pass": m.everything is not None
            and since(m.everything) <= _scaled_budget(budgets, "everythingDoneMaxSec", count),
        },
        {
            "id": "bookkeeping",
            "budget": f"<= {budgets['bookkeepingMaxMs']} ms/job",
            "target": budgets["bookkeepingMaxMs"],
            "measured": bk_mean,
            "pass": bk_mean is not None and bk_mean <= budgets["bookkeepingMaxMs"],
        },
        {
            "id": "apiJobsP95",
            "budget": f"<= {budgets['apiJobsP95MaxMs']} ms",
            "target": budgets["apiJobsP95MaxMs"],
            "measured": _percentile(state.job_latencies, 95),
            "pass": _percentile(state.job_latencies, 95) is not None
            and _percentile(state.job_latencies, 95) <= budgets["apiJobsP95MaxMs"],
        },
        {
            "id": "apiItemsP95",
            "budget": f"<= {budgets['apiItemsP95MaxMs']} ms",
            "target": budgets["apiItemsP95MaxMs"],
            "measured": _percentile(state.items_latencies, 95),
            "pass": _percentile(state.items_latencies, 95) is not None
            and _percentile(state.items_latencies, 95) <= budgets["apiItemsP95MaxMs"],
        },
    ]
    if timed_out:
        for row in rows:
            if row["measured"] is None:
                row["pass"] = False
    return rows


def _print_table(rows: list[dict[str, Any]]) -> None:
    print()
    print(f"{'Budget':<22} {'Target':<18} {'Measured':<18} {'Result':<6}")
    print("-" * 66)
    for row in rows:
        measured = row["measured"]
        if isinstance(measured, float):
            text = f"{measured:.3f}"
        elif measured is None:
            text = "n/a"
        else:
            text = str(measured)
        result = "PASS" if row["pass"] else "FAIL"
        print(f"{row['id']:<22} {row['budget']:<18} {text:<18} {result:<6}")
    print()


def run_bench(
    count: int,
    label: str,
    app: Path,
    port: int,
    keep: bool,
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

        latency_thread = threading.Thread(
            target=_latency_worker,
            args=(base, stop_latency, state),
            name="bench-latency",
            daemon=True,
        )
        latency_thread.start()

        deadline = time.monotonic() + max(300.0, 4.0 * count)
        _poll_loop(base, state, count, ffmpeg, deadline)
        timed_out = state.milestones.everything is None and time.monotonic() >= deadline

        stop_latency.set()
        latency_thread.join(timeout=5.0)

        rows = _build_results(state, count, budgets, ffmpeg, timed_out)
        _print_table(rows)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        payload = {
            "label": label,
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
                state.added_times,
                state.milestones.t0,
                state.milestones.scan_done,
            ),
            "viewerItemId": state.viewer_item_id,
            "timeline": state.timeline[-400:],
            "bookkeepingSampleCount": len(state.bookkeeping_samples),
        }

        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact = ARTIFACT_DIR / f"bench-{stamp}-{label}.json"
        latest = ARTIFACT_DIR / f"latest-{label}.json"
        text = json.dumps(payload, indent=2) + "\n"
        artifact.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")
        print(f"Artifact: {artifact}")

        exit_code = 0 if all(r["pass"] for r in rows) else 1
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F7 processing speed benchmark")
    parser.add_argument("--count", type=int, default=80)
    parser.add_argument("--label", default="default")
    parser.add_argument("--app", type=Path, default=REPO_ROOT)
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    if args.port == 8785:
        print("Refusing port 8785 (production server).", file=sys.stderr)
        return 2
    return run_bench(args.count, args.label, args.app, args.port, args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
