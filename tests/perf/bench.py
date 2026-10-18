"""F7 processing-speed benchmark: scratch server, HTTP add-folder, budget table."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import tempfile
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
VIDEO_FILE_SUFFIXES = frozenset({".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"})
LOCK_TRACE_HTTP_ONLY_NOTE = (
    "lock_trace records only HTTP handlers that use Hold() in library/server.py; "
    "scan/drain/background work is not attributed."
)

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


def _git_identity(app: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "-C", str(app), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(app), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            check=True,
        ).stdout
        diff = subprocess.run(
            ["git", "-C", str(app), "diff", "--binary", "HEAD"],
            capture_output=True,
            check=True,
        ).stdout
        return {
            "commit": commit,
            "dirty": bool(status),
            "statusSha256": hashlib.sha256(status).hexdigest(),
            "diffSha256": hashlib.sha256(diff).hexdigest(),
        }
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": None, "statusSha256": None, "diffSha256": None}


def _inside(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return child.resolve() != parent.resolve()
    except (OSError, ValueError):
        return False


def _new_scratch_root() -> Path:
    BENCH_ROOT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="run-", dir=BENCH_ROOT)).resolve()
    if not _inside(BENCH_ROOT, root):
        raise HarnessError(f"scratch path escaped benchmark root: {root}")
    return root


def _fixture_manifest(fixture_dir: Path, count: int) -> dict[str, Any]:
    files = sorted(
        (p for p in fixture_dir.rglob("*") if p.is_file() and ".library" not in p.parts),
        key=lambda p: p.relative_to(fixture_dir).as_posix().casefold(),
    )
    entries = []
    for path in files:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(block)
        entries.append({
            "path": path.relative_to(fixture_dir).as_posix(),
            "sizeBytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    body = {"expectedJpegs": count, "files": entries}
    body["sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return body


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
    if not _inside(BENCH_ROOT, tmp):
        raise HarnessError(f"refusing to write ffmpeg baseline outside scratch: {tmp}")
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
            if not _inside(BENCH_ROOT, tmp):
                raise HarnessError(f"refusing to remove ffmpeg output outside scratch: {tmp}")
            tmp.unlink()
        raise HarnessError(f"ffmpeg baseline failed for {source}")
    if not _inside(BENCH_ROOT, tmp):
        raise HarnessError(f"refusing to remove ffmpeg output outside scratch: {tmp}")
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


def _ensure_fixture(count: int, scratch_root: Path) -> Path:
    fixture_dir = scratch_root / f"pictures-{count}"
    if not _inside(scratch_root, fixture_dir):
        raise HarnessError(f"fixture path escaped scratch root: {fixture_dir}")
    fixture_dir.mkdir(parents=True, exist_ok=False)
    jpgs_src, mov_src = _collect_source_media(FIXTURE_SOURCE)
    if len(jpgs_src) < count:
        raise HarnessError(
            f"need {count} JPEGs under {FIXTURE_SOURCE}, found {len(jpgs_src)}"
        )
    if mov_src is None:
        raise HarnessError(f"no .mov found under {FIXTURE_SOURCE}")

    for src in jpgs_src[:count]:
        rel = src.relative_to(FIXTURE_SOURCE)
        dest = fixture_dir / rel
        if not _inside(fixture_dir, dest):
            raise HarnessError(f"fixture copy path escaped scratch fixture: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    rel_mov = mov_src.relative_to(FIXTURE_SOURCE)
    dest_mov = fixture_dir / rel_mov
    if not _inside(fixture_dir, dest_mov):
        raise HarnessError(f"video fixture path escaped scratch fixture: {dest_mov}")
    dest_mov.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mov_src, dest_mov)
    if not _fixture_ready(fixture_dir, count, True):
        raise HarnessError("copied fixture does not contain the expected JPEG/MOV set")
    return fixture_dir


def _prepare_library_root(port: int, scratch_root: Path) -> Path:
    lib_root = scratch_root / "library-data"
    if not _inside(scratch_root, lib_root):
        raise HarnessError(f"library path escaped scratch root: {lib_root}")
    lib_root.mkdir(parents=True, exist_ok=False)
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


def _start_server(
    app: Path,
    lib_root: Path,
    stdout_path: Path,
    stderr_path: Path,
    lock_trace_path: Path | None = None,
) -> subprocess.Popen[Any]:
    env = _ffmpeg_env()
    env["PYTHONPATH"] = str(app.resolve())
    if lock_trace_path is not None:
        if not _inside(BENCH_ROOT, lock_trace_path):
            raise HarnessError(f"lock trace path escaped benchmark root: {lock_trace_path}")
        lock_trace_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_trace_path.exists():
            lock_trace_path.unlink()
        env["LIBRARY_LOCK_TRACE"] = str(lock_trace_path.resolve())
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
    return _popen_logged(
        cmd,
        cwd=app.resolve(),
        env=env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def _popen_logged(
    cmd: list[str], *, cwd: Path, env: dict[str, str], stdout_path: Path, stderr_path: Path
) -> subprocess.Popen[Any]:
    for path in (stdout_path, stderr_path):
        if not _inside(BENCH_ROOT, path):
            raise HarnessError(f"server log escaped benchmark root: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
        return subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
        )


def _port_is_occupied(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        try:
            probe.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _stderr_tail(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()
    except OSError:
        return ""


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


def _rendition_file_nonempty(
    item: dict[str, Any], slot: str, lib_root: Path, fixture_dir: Path
) -> bool:
    rend = item.get("renditions") or {}
    rel = rend.get(slot)
    if type(rel) is not str or not rel:
        return False
    rel_path = Path(rel.replace("\\", "/"))
    if rel_path.is_absolute() or ".." in rel_path.parts:
        return False
    if rel.startswith(".library/"):
        root = fixture_dir
    elif rel.startswith("renditions/"):
        root = lib_root
    else:
        return False
    try:
        output = (root / rel_path).resolve()
        output.relative_to(root.resolve())
        return output.is_file() and output.stat().st_size > 0
    except (OSError, ValueError):
        return False


def _grid_complete(items: list[dict[str, Any]], lib_root: Path, fixture_dir: Path) -> bool:
    for item in items:
        if not _item_thumb_ready(item):
            return False
        slot = "poster" if item.get("kind") == "video" else "thumb"
        if not _rendition_file_nonempty(item, slot, lib_root, fixture_dir):
            return False
    return bool(items)


def _any_queued(items: list[dict[str, Any]]) -> bool:
    for item in items:
        status = ((item.get("renditions") or {}).get("status") or {})
        for slot in ALL_RENDITION_SLOTS:
            if status.get(slot) == "queued":
                return True
    return False


def _rendition_completion(
    items: list[dict[str, Any]], expected_items: int, lib_root: Path, fixture_dir: Path
) -> dict[str, Any]:
    counts = {"ready": 0, "notApplicable": 0, "queued": 0, "error": 0, "missingOrUnknown": 0}
    bad_files: list[dict[str, str]] = []
    invalid_not_applicable: list[dict[str, str]] = []
    unexpected_ready: list[dict[str, str]] = []
    invalid_kinds: list[dict[str, str]] = []
    policies = {
        "photo": ({"thumb", "preview"}, {"poster", "proxy", "playback"}, set()),
        "video": ({"poster", "proxy"}, {"thumb", "preview"}, {"playback"}),
        "live": ({"thumb", "preview", "poster", "proxy"}, set(), {"playback"}),
    }
    for item in items:
        item_id = str(item.get("id") or "")
        kind = item.get("kind")
        policy = policies.get(kind)
        if policy is None:
            invalid_kinds.append({"itemId": item_id, "kind": str(kind)})
            required_slots, not_applicable_only, optional_playback = set(), set(), set()
        else:
            required_slots, not_applicable_only, optional_playback = policy
        rend = item.get("renditions") or {}
        status = rend.get("status") or {}
        for slot in ALL_RENDITION_SLOTS:
            value = status.get(slot)
            if value == "ready":
                counts["ready"] += 1
                if not _rendition_file_nonempty(item, slot, lib_root, fixture_dir):
                    bad_files.append({"itemId": item_id, "slot": slot})
                if slot in not_applicable_only:
                    unexpected_ready.append({"itemId": item_id, "slot": slot})
            elif value == "not-applicable":
                counts["notApplicable"] += 1
                if slot in required_slots or (slot not in not_applicable_only and slot not in optional_playback):
                    invalid_not_applicable.append({"itemId": item_id, "slot": slot})
            elif value == "queued":
                counts["queued"] += 1
            elif value == "error":
                counts["error"] += 1
            else:
                counts["missingOrUnknown"] += 1
    expected_slots = expected_items * len(ALL_RENDITION_SLOTS)
    observed_slots = sum(counts.values())
    item_count_ok = len(items) == expected_items
    terminal = (
        item_count_ok
        and observed_slots == expected_slots
        and counts["queued"] == 0
        and counts["missingOrUnknown"] == 0
    )
    return {
        "expectedItems": expected_items,
        "observedItems": len(items),
        "itemCountMatched": item_count_ok,
        "expectedSlotCount": expected_slots,
        "observedSlotCount": observed_slots,
        "slotCounts": counts,
        "terminal": terminal,
        "successful": (
            terminal
            and counts["error"] == 0
            and not bad_files
            and not invalid_not_applicable
            and not unexpected_ready
            and not invalid_kinds
        ),
        "nonemptyFileFailures": bad_files,
        "invalidNotApplicable": invalid_not_applicable,
        "unexpectedReadySlots": unexpected_ready,
        "invalidKinds": invalid_kinds,
    }


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
    file_read_bytes: dict[str, int] = field(default_factory=dict)
    lock_trace_path: Path | None = None
    lock_trace_snapshots: list[dict[str, Any]] = field(default_factory=list)
    lock_trace_prev_max: dict[str, float] = field(default_factory=dict)
    lock_hold_events: list[dict[str, Any]] = field(default_factory=list)
    job_latency_samples: list[dict[str, float]] = field(default_factory=list)
    items_latency_samples: list[dict[str, float]] = field(default_factory=list)
    api_counts: dict[str, dict[str, Any]] = field(default_factory=dict)
    rendition_terminal: float | None = None
    rendition_completion: dict[str, Any] = field(default_factory=dict)
    final_jobs: dict[str, Any] | None = None
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
    bookkeeping_events: list[dict[str, Any]] = field(default_factory=list)
    ready_renditions: set[str] = field(default_factory=set)
    last_still_ready_at: float = 0.0
    seen_journal_paths: set[str] = field(default_factory=set)
    seen_item_paths: set[str] = field(default_factory=set)
    poll_in_flight: bool = False


def _note_api(state: RunState, route: str, status: int | None) -> None:
    counts = state.api_counts.setdefault(route, {"samples": 0, "successes": 0, "failures": 0, "statuses": {}})
    counts["samples"] += 1
    if status == 200:
        counts["successes"] += 1
    else:
        counts["failures"] += 1
    key = str(status) if status is not None else "transport-error"
    counts["statuses"][key] = counts["statuses"].get(key, 0) + 1


def _server_items_dir(lib_root: Path) -> Path:
    return lib_root / "catalog" / "items"


def _server_journal_dirs(lib_root: Path) -> list[Path]:
    dirs: list[Path] = []
    base = lib_root / "catalog" / "sources"
    if not base.is_dir():
        return dirs
    for child in base.iterdir():
        if child.is_dir() and child.name.endswith(".files"):
            dirs.append(child)
    return dirs


def _mirror_items_dir(fixture_dir: Path) -> Path:
    return fixture_dir / ".library" / "catalog" / "items"


def _item_catalog_key(item: dict[str, Any]) -> str:
    locations = item.get("locations") or []
    if isinstance(locations, list):
        for loc in locations:
            if not isinstance(loc, dict) or loc.get("current") is False:
                continue
            rel = loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath")
            if type(rel) is str and rel.strip():
                return f"{loc.get('volumeSerial') or loc.get('sourceId') or ''}:{rel.replace(chr(92), '/').casefold()}"
    rel = _item_rel_key(item)
    if rel:
        return rel
    item_id = item.get("id")
    return str(item_id) if type(item_id) is str else ""


def _dedupe_catalog_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per picture: prefer hash id over pending-* when both exist."""
    by_key: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _item_catalog_key(item)
        if not key:
            continue
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = item
            continue
        prev_id = str(prev.get("id") or "")
        new_id = str(item.get("id") or "")
        if prev_id.startswith("pending-") and not new_id.startswith("pending-"):
            by_key[key] = item
    return list(by_key.values())


def _collect_items_from_dir(items_dir: Path) -> list[dict[str, Any]]:
    if not items_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in items_dir.glob("*.json"):
        item = _try_load_json_file(path)
        if item is None:
            continue
        item_id = item.get("id")
        if type(item_id) is not str or not item_id:
            continue
        out.append(item)
    return out


def _collect_server_catalog_items(lib_root: Path) -> list[dict[str, Any]]:
    return _dedupe_catalog_items(_collect_items_from_dir(_server_items_dir(lib_root)))


def _rendition_status_sig(item: dict[str, Any]) -> tuple[Any, ...]:
    status = ((item.get("renditions") or {}).get("status") or {})
    return tuple(status.get(slot) for slot in ALL_RENDITION_SLOTS)


def _portable_mirror_report(
    lib_root: Path, fixture_dir: Path, expected_items: int
) -> dict[str, Any]:
    server = {
        _item_catalog_key(item): _rendition_status_sig(item)
        for item in _collect_server_catalog_items(lib_root)
    }
    mirror_items = _dedupe_catalog_items(_collect_items_from_dir(_mirror_items_dir(fixture_dir)))
    mirror = {_item_catalog_key(item): _rendition_status_sig(item) for item in mirror_items}
    matched = 0
    for key, sig in server.items():
        if mirror.get(key) == sig:
            matched += 1
    return {
        "serverItems": len(server),
        "mirrorItems": len(mirror),
        "expectedItems": expected_items,
        "matchedItems": matched,
        "complete": len(server) == expected_items and len(mirror) == expected_items and matched == expected_items,
    }


def _measure_portable_mirror_lag(
    lib_root: Path, fixture_dir: Path, everything_at: float, expected_items: int, *, timeout: float = 10.0
) -> dict[str, Any]:
    deadline = everything_at + timeout
    latest = _portable_mirror_report(lib_root, fixture_dir, expected_items)
    while time.monotonic() < deadline:
        latest = _portable_mirror_report(lib_root, fixture_dir, expected_items)
        if latest["complete"]:
            return {**latest, "lagSec": time.monotonic() - everything_at, "timedOut": False}
        time.sleep(DISK_POLL_INTERVAL_SEC)
    return {**latest, "lagSec": None, "timedOut": True}


def _try_load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _item_rel_key(item: dict[str, Any]) -> str | None:
    locations = item.get("locations") or []
    if isinstance(locations, list):
        for loc in locations:
            if not isinstance(loc, dict) or loc.get("current") is False:
                continue
            path = loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or loc.get("lastKnownPath")
            if type(path) is str and path.strip():
                return path.strip().replace("\\", "/").casefold()
    name = item.get("filename")
    if type(name) is str and name.strip():
        return name.strip().casefold()
    return None


def _is_video_rel(rel: str) -> bool:
    ext = Path(rel.replace("\\", "/")).suffix.lower()
    return ext in VIDEO_FILE_SUFFIXES


def _size_from_item(item: dict[str, Any]) -> int:
    locations = item.get("locations") or []
    if isinstance(locations, list):
        for loc in locations:
            if isinstance(loc, dict):
                size = loc.get("sizeBytes")
                if type(size) is int and size > 0:
                    return size
    return 0


def _note_file_read(
    state: RunState, rel_key: str, now: float, size_bytes: int = 0
) -> None:
    key = rel_key.replace("\\", "/").lower()
    if not key:
        return
    if key not in state.file_read_at:
        state.file_read_at[key] = now
    if size_bytes > 0:
        state.file_read_bytes[key] = size_bytes


def _read_lock_trace(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _poll_lock_trace(state: RunState, now: float) -> None:
    path = state.lock_trace_path
    if path is None:
        return
    report = _read_lock_trace(path)
    if not report:
        return
    t_rel = now - state.milestones.t0
    for holder, stats in report.items():
        if not isinstance(stats, dict):
            continue
        max_ms = float(stats.get("maxMs") or 0)
        prev = state.lock_trace_prev_max.get(holder, 0.0)
        if max_ms > prev + 0.01:
            state.lock_hold_events.append(
                {
                    "holder": holder,
                    "holdMs": max_ms,
                    "tRelSec": round(max(0.0, t_rel - max_ms / 1000.0), 3),
                    "tEndRelSec": round(t_rel, 3),
                    "approximateStart": True,
                }
            )
        state.lock_trace_prev_max[holder] = max(prev, max_ms)
    state.lock_trace_snapshots.append({"tRelSec": round(t_rel, 3), "report": report})


def _summarize_lock_holds(state: RunState) -> dict[str, Any]:
    path = state.lock_trace_path
    final = _read_lock_trace(path) if path else {}
    by_holder: dict[str, Any] = {}
    for holder, stats in final.items():
        if not isinstance(stats, dict):
            continue
        by_holder[holder] = {
            "count": int(stats.get("n") or 0),
            "p95Ms": float(stats.get("p95Ms") or 0),
            "maxMs": float(stats.get("maxMs") or 0),
        }
    top = sorted(
        state.lock_hold_events,
        key=lambda row: float(row.get("holdMs") or 0),
        reverse=True,
    )
    seen: set[str] = set()
    top_unique: list[dict[str, Any]] = []
    for row in top:
        holder = str(row.get("holder") or "")
        if holder in seen:
            continue
        seen.add(holder)
        top_unique.append(row)
        if len(top_unique) >= 10:
            break
    if len(top_unique) < 10:
        for holder, stats in sorted(
            by_holder.items(), key=lambda kv: -kv[1]["maxMs"]
        ):
            if holder in seen:
                continue
            top_unique.append(
                {
                    "holder": holder,
                    "holdMs": stats["maxMs"],
                    "tRelSec": None,
                    "tEndRelSec": None,
                    "approximateStart": False,
                    "fromFinalAggregateOnly": True,
                }
            )
            if len(top_unique) >= 10:
                break
    return {
        "note": LOCK_TRACE_HTTP_ONLY_NOTE,
        "tracePath": str(path) if path else None,
        "byHolder": by_holder,
        "topHolds": top_unique[:10],
        "snapshotCount": len(state.lock_trace_snapshots),
    }


def _scan_disk_reading(state: RunState, lib_root: Path, now: float) -> None:
    for journal_dir in _server_journal_dirs(lib_root):
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
            size = 0
            entry = body.get("entry")
            if isinstance(entry, dict):
                raw = entry.get("sizeBytes")
                if type(raw) is int and raw > 0:
                    size = raw
            _note_file_read(state, rel, now, size)

    items_dir = _server_items_dir(lib_root)
    if items_dir.is_dir():
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
                _note_file_read(state, rel, now, _size_from_item(item))


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
    file_read_at: dict[str, float],
    file_read_bytes: dict[str, int],
    t0: float,
    scan_done: float | None,
) -> dict[str, Any]:
    times = sorted(file_read_at.values())
    scan_wall = (scan_done - t0) if scan_done is not None else None
    if not times:
        return {
            "rate": None,
            "tenthRatio": None,
            "tenthRatioPerMb": None,
            "files": 0,
            "stillPictures": 0,
            "scanWallSec": scan_wall,
            "diskReadDurationSec": None,
        }

    disk_duration = max(times[-1] - t0, 1e-6)
    rate = len(file_read_at) / disk_duration

    still_entries = [
        (file_read_at[rel], rel, file_read_bytes.get(rel, 0))
        for rel in file_read_at
        if not _is_video_rel(rel)
    ]
    still_entries.sort(key=lambda row: row[0])
    still_count = len(still_entries)

    ratio: float | None = None
    mb_ratio: float | None = None
    if still_count >= 10:
        tenth = max(1, still_count // 10)
        first_end_t = still_entries[tenth - 1][0]
        last_start_t = still_entries[still_count - tenth][0]
        last_end_t = still_entries[-1][0]
        first_span = max(first_end_t - t0, 1e-6)
        last_span = max(last_end_t - last_start_t, 1e-6)

        first_rate = tenth / first_span
        last_rate = tenth / last_span
        if first_rate > 0 and last_rate > 0:
            ratio = last_rate / first_rate

        first_mb = sum(row[2] for row in still_entries[:tenth]) / 1_000_000.0
        last_mb = sum(row[2] for row in still_entries[-tenth:]) / 1_000_000.0
        first_mb_rate = first_mb / first_span if first_span > 0 else None
        last_mb_rate = last_mb / last_span if last_span > 0 else None
        if first_mb_rate and first_mb_rate > 0 and last_mb_rate is not None:
            mb_ratio = last_mb_rate / first_mb_rate

    return {
        "rate": rate,
        "tenthRatio": ratio,
        "tenthRatioPerMb": mb_ratio,
        "files": len(file_read_at),
        "stillPictures": still_count,
        "scanWallSec": scan_wall,
        "diskReadDurationSec": disk_duration,
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
IMPLAUSIBLE_REASON = "timestamps implausible: batched writes?"


def _ffmpeg_base_sec(ffmpeg: dict[str, float], slot: str) -> float:
    return ffmpeg["thumbSecMean"] if slot == "thumb" else ffmpeg["previewSecMean"]


def _bookkeeping_ms_from_event(ev: dict[str, Any], ffmpeg: dict[str, float]) -> float | None:
    gap = float(ev.get("gapSec") or 0)
    slot = str(ev.get("slot") or "thumb")
    base = _ffmpeg_base_sec(ffmpeg, slot)
    if not (0 < gap < 4.0) or gap < base:
        return None
    return max(0.0, gap - base) * 1000.0


def _bookkeeping_samples_implausible(
    samples: list[float], source_events: list[dict[str, Any]], ffmpeg: dict[str, float]
) -> bool:
    if not samples:
        return True
    if sum(1 for s in samples if s <= 1.0) > len(samples) / 2:
        return True
    qualifying = [ev for ev in source_events if float(ev.get("gapSec") or 0) > 0]
    if not qualifying:
        return True
    bad = 0
    for ev in qualifying:
        gap = float(ev.get("gapSec") or 0)
        base = _ffmpeg_base_sec(ffmpeg, str(ev.get("slot") or "thumb"))
        if gap < base * 0.5:
            bad += 1
    return bad > len(qualifying) / 2


def _finalize_bookkeeping(state: RunState, ffmpeg: dict[str, float]) -> dict[str, Any]:
    events = sorted(state.bookkeeping_events, key=lambda e: float(e.get("at") or 0))
    scan_done = state.milestones.scan_done

    def build_window(event_filter) -> tuple[list[float], list[dict[str, Any]]]:
        picked: list[dict[str, Any]] = []
        samples: list[float] = []
        for ev in events:
            if not event_filter(ev):
                continue
            ms = _bookkeeping_ms_from_event(ev, ffmpeg)
            if ms is None:
                continue
            picked.append(ev)
            samples.append(ms)
        return samples, picked

    steady: list[float] = []
    steady_events: list[dict[str, Any]] = []
    if scan_done is not None:
        steady_cutoff = scan_done + 2.0

        def steady_filter(ev: dict[str, Any]) -> bool:
            return float(ev.get("at") or 0) >= steady_cutoff

        steady, steady_events = build_window(steady_filter)

    if len(steady) >= BOOKKEEPING_MIN_SAMPLES:
        if not _bookkeeping_samples_implausible(steady, steady_events, ffmpeg):
            return {
                "meanMs": statistics.mean(steady),
                "window": "postScanSteady",
                "sampleCount": len(steady),
                "samplesMs": steady,
            }

    first_thumb = state.milestones.first_thumb
    fallback: list[float] = []
    fallback_events: list[dict[str, Any]] = []
    skipped_first = False
    if first_thumb is not None:
        for ev in events:
            at = float(ev.get("at") or 0)
            if at < first_thumb:
                continue
            gap = float(ev.get("gapSec") or 0)
            if gap <= 0 or gap > 4.0:
                continue
            if not skipped_first:
                skipped_first = True
                continue
            ms = _bookkeeping_ms_from_event(ev, ffmpeg)
            if ms is None:
                continue
            fallback_events.append(ev)
            fallback.append(ms)

    if len(fallback) >= BOOKKEEPING_MIN_SAMPLES:
        if not _bookkeeping_samples_implausible(fallback, fallback_events, ffmpeg):
            return {
                "meanMs": statistics.mean(fallback),
                "window": "afterFirstThumb",
                "sampleCount": len(fallback),
                "samplesMs": fallback,
            }

    implausible = (
        len(steady) >= BOOKKEEPING_MIN_SAMPLES
        or len(fallback) >= BOOKKEEPING_MIN_SAMPLES
    )
    return {
        "meanMs": None,
        "window": "none",
        "sampleCount": len(fallback),
        "samplesMs": fallback,
        "steadyAttemptCount": len(steady),
        "implausible": implausible,
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
                _, activity_status, activity = _http_json(base, "/api/activity", timeout=30.0)
                _note_api(state, "/api/activity", activity_status)
                _update_scan_from_activity(state, activity, now, expected_items)
            except (urllib.error.URLError, TimeoutError, OSError):
                _note_api(state, "/api/activity", None)

        if now >= next_poll and not state.poll_in_flight:
            next_poll = now + UI_POLL_INTERVAL_SEC
            state.poll_in_flight = True
            route = "/api/health"
            try:
                _, health_status, _ = _http_json(base, "/api/health", timeout=10.0)
                _note_api(state, "/api/health", health_status)
                if health_status != 200:
                    continue
                route = "/api/jobs"
                elapsed, status, _ = _http_json(base, "/api/jobs", timeout=60.0)
                _note_api(state, "/api/jobs", status)
                if status == 200:
                    state.job_latency_samples.append(
                        {
                            "tRelSec": round(now - state.milestones.t0, 3),
                            "ms": elapsed * 1000.0,
                        }
                    )
                _poll_lock_trace(state, now)
                if state.milestones.everything is None:
                    route = "/api/items"
                    elapsed, status, _ = _http_json(base, "/api/items", timeout=120.0)
                    _note_api(state, "/api/items", status)
                    if status == 200:
                        state.items_latency_samples.append(
                            {
                                "tRelSec": round(now - state.milestones.t0, 3),
                                "ms": elapsed * 1000.0,
                            }
                        )
                    _poll_lock_trace(state, time.monotonic())
            except (urllib.error.URLError, TimeoutError, OSError):
                _note_api(state, route, None)
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
            _note_api(state, "/api/items", status)
            if status == 200:
                state.items_latency_samples.append(
                    {
                        "tRelSec": round(time.monotonic() - state.milestones.t0, 3),
                        "ms": elapsed * 1000.0,
                    }
                )
        except (urllib.error.URLError, TimeoutError, OSError):
            _note_api(state, "/api/items", None)
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
        _scan_disk_reading(state, lib_root, now)
        items = _sorted_catalog_items(_collect_server_catalog_items(lib_root))
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

        if state.milestones.all_grid is None and len(items) >= expected_items and _grid_complete(items, lib_root, fixture_dir):
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

        if state.rendition_terminal is None and len(items) >= expected_items:
            completion = _rendition_completion(items, expected_items, lib_root, fixture_dir)
            if completion["terminal"]:
                state.rendition_terminal = now
                state.rendition_completion = completion
                if completion["successful"]:
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

        _timeline_append(
            state,
            {
                "t": round(t_rel, 3),
                "diskItems": len(items),
                "filesRead": len(state.file_read_at),
                "thumbsReady": _thumb_ready_count(items),
                "queued": _any_queued(items) if items else True,
            },
        )

        if state.rendition_terminal is not None:
            break
        time.sleep(DISK_POLL_INTERVAL_SEC)


_TIMELINE_KEYS = ("diskItems", "filesRead", "thumbsReady", "queued")


def _timeline_append(state: RunState, point: dict[str, Any]) -> None:
    if state.timeline:
        last = state.timeline[-1]
        if all(last.get(k) == point.get(k) for k in _TIMELINE_KEYS):
            return
    state.timeline.append(point)


def _latency_summary(state: RunState) -> dict[str, dict[str, float | int | None]]:
    def summarize(samples: list[dict[str, float]]) -> dict[str, float | int | None]:
        values = [float(sample["ms"]) for sample in samples if "ms" in sample]
        return {
            "p50": _percentile(values, 50),
            "p95": _percentile(values, 95),
            "max": max(values) if values else None,
            "n": len(values),
        }

    return {
        "jobs": summarize(state.job_latency_samples),
        "items": summarize(state.items_latency_samples),
    }


def _queue_diagnostics(jobs: dict[str, Any] | None) -> dict[str, Any]:
    queues = jobs.get("queues") if isinstance(jobs, dict) else None
    if not isinstance(queues, list):
        return {"available": False, "queues": [], "excludedAiQueueIds": []}
    rows = [
        {
            key: q.get(key)
            for key in ("id", "state", "pending", "done", "error", "available")
        }
        for q in queues
        if isinstance(q, dict)
    ]
    return {
        "available": True,
        "queues": rows,
        "excludedAiQueueIds": [q["id"] for q in rows if q.get("id") != "renditions"],
    }


def _measurement_schema(state: RunState) -> dict[str, Any]:
    return {
        "latencyMs": _latency_summary(state),
        "reading": _reading_metrics(
            state.file_read_at,
            state.file_read_bytes,
            state.milestones.t0,
            state.milestones.scan_done,
        ),
        "apiCounts": state.api_counts,
        "renditionCompletion": state.rendition_completion,
        "renditionTerminalSec": (
            state.rendition_terminal - state.milestones.t0
            if state.rendition_terminal is not None
            else None
        ),
        "lockTrace": _summarize_lock_holds(state),
        "finalQueues": _queue_diagnostics(state.final_jobs),
    }


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
    reading = _reading_metrics(
        state.file_read_at, state.file_read_bytes, t0, m.scan_done
    )
    bk = _finalize_bookkeeping(state, ffmpeg)

    def since(start: float | None) -> float | None:
        if start is None:
            return None
        return start - t0

    def timeout_reason(milestone: str) -> str:
        if milestone == "all renditions" and state.rendition_completion:
            completion = state.rendition_completion
            if completion.get("terminal") and not completion.get("successful"):
                slots = completion.get("slotCounts") or {}
                return (
                    f"terminal rendition errors={slots.get('error', 0)}, "
                    f"invalid ready files={len(completion.get('nonemptyFileFailures') or [])}"
                )
        return "timed out" if timed_out else f"{milestone} not reached"

    rate = reading["rate"]
    rate_reason = "no files on disk"
    if not state.file_read_at:
        rate_reason = "no files on disk"
    elif rate is None:
        rate_reason = "disk read duration unknown"

    ratio = reading["tenthRatio"]
    still_n = int(reading.get("stillPictures") or 0)
    ratio_reason = "fewer than 10 still pictures indexed"
    if still_n < 10:
        ratio_reason = "fewer than 10 still pictures indexed"

    viewer_lat: float | None = None
    if m.viewer_preview is not None and m.viewer_open is not None:
        viewer_lat = m.viewer_preview - m.viewer_open
    viewer_reason = "viewer not opened"
    if m.viewer_open is None:
        viewer_reason = timeout_reason("viewer open")
    elif m.viewer_preview is None:
        viewer_reason = timeout_reason("viewer preview")

    latency = _latency_summary(state)
    jobs_p95 = latency["jobs"]["p95"]
    items_p95 = latency["items"]["p95"]

    bk_mean = bk["meanMs"]
    if bk.get("implausible"):
        bk_reason = IMPLAUSIBLE_REASON
    else:
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


def _print_info_rows(info: dict[str, Any]) -> None:
    lag = info.get("portableMirrorLagSec")
    if lag is None and info.get("portableMirrorChecked"):
        text = "n/a (>10 s or mirror missing)"
    elif lag is None:
        text = "n/a (not measured)"
    else:
        text = f"{lag:.3f}"
    print(f"{'portableMirrorLagSec':<22} {'(info)':<18} {text:<28}")
    print()


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
    if _port_is_occupied(port):
        print(f"Harness error: port {port} already has a TCP listener", file=sys.stderr)
        return 2
    scratch_root = _new_scratch_root()
    fixture_dir = _ensure_fixture(count, scratch_root)
    fixture_manifest = _fixture_manifest(fixture_dir, count)
    manifest_path = scratch_root / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(fixture_manifest, indent=2) + "\n", encoding="utf-8")
    ffmpeg = _baseline_ffmpeg_ms(fixture_dir)
    lib_root = _prepare_library_root(port, scratch_root)
    lock_trace_path = scratch_root / "lock-trace.json"
    stdout_log_path = scratch_root / "server.stdout.log"
    stderr_log_path = scratch_root / "server.stderr.log"
    base = f"http://127.0.0.1:{port}"

    proc: subprocess.Popen[Any] | None = None
    stop_latency = threading.Event()
    state = RunState()
    state.lock_trace_path = lock_trace_path
    timed_out = False
    exit_code = 2

    try:
        proc = _start_server(app, lib_root, stdout_log_path, stderr_log_path, lock_trace_path)
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

        expected_items = count + 1
        mirror_info: dict[str, Any] = {
            "portableMirrorChecked": False,
            "portableMirrorTimedOut": False,
            **_portable_mirror_report(lib_root, fixture_dir, expected_items),
        }
        if state.milestones.everything is not None:
            mirror_info["portableMirrorChecked"] = True
            mirror_result = _measure_portable_mirror_lag(
                lib_root,
                fixture_dir,
                state.milestones.everything,
                expected_items,
            )
            mirror_info.update({
                "portableMirrorLagSec": mirror_result["lagSec"],
                "portableMirrorTimedOut": mirror_result["timedOut"],
                "portableMirrorMatchedItems": mirror_result["matchedItems"],
                "portableMirrorExpectedItems": mirror_result["expectedItems"],
                "portableMirrorComplete": mirror_result["complete"],
            })

        _, final_jobs_status, final_jobs = _http_json(base, "/api/jobs", timeout=60.0)
        _note_api(state, "/api/jobs-final", final_jobs_status)
        state.final_jobs = final_jobs if final_jobs_status == 200 and isinstance(final_jobs, dict) else None

        stop_latency.set()
        ui_thread.join(timeout=5.0)
        if heavy_thread is not None:
            heavy_thread.join(timeout=5.0)

        rows, bookkeeping = _build_results(state, count, budgets, ffmpeg, timed_out)
        _print_table(rows)
        _print_info_rows(mirror_info)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        git_identity = _git_identity(app)
        payload = {
            "label": label,
            "load": load,
            "count": count,
            "appPath": str(app),
            "git": git_identity,
            "gitCommit": git_identity["commit"],
            "port": port,
            "fixtureDir": str(fixture_dir),
            "scratchRoot": str(scratch_root),
            "fixtureManifestPath": str(manifest_path),
            "fixtureManifest": fixture_manifest,
            "libraryRoot": str(lib_root),
            "serverLogs": {"stdout": str(stdout_log_path), "stderr": str(stderr_log_path)},
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
            **_measurement_schema(state),
            "viewerItemId": state.viewer_item_id,
            "bookkeeping": bookkeeping,
            "portableMirrorLagSec": mirror_info.get("portableMirrorLagSec"),
            "portableMirrorChecked": mirror_info.get("portableMirrorChecked"),
            "portableMirror": mirror_info,
            "aiQueuesExcludedFromCompletion": _queue_diagnostics(state.final_jobs)["excludedAiQueueIds"],
            "renditionCompletion": state.rendition_completion,
            "timeline": state.timeline,
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
        detail = _stderr_tail(stderr_log_path)
        print(f"Harness error: {exc}; scratch logs: {scratch_root}", file=sys.stderr)
        if detail:
            print(f"Server stderr tail:\n{detail}", file=sys.stderr)
        exit_code = 2
    finally:
        stop_latency.set()
        _stop_server(proc)
        stderr_failure = bool(_stderr_tail(stderr_log_path))
        if stderr_failure:
            print(f"Server wrote stderr; preserved logs at {scratch_root}", file=sys.stderr)
        if not keep and exit_code != 2 and not stderr_failure and scratch_root.exists():
            if not _inside(BENCH_ROOT, scratch_root):
                print(f"Refusing scratch cleanup outside {BENCH_ROOT}: {scratch_root}", file=sys.stderr)
                exit_code = 2
            else:
                for _ in range(5):
                    try:
                        shutil.rmtree(scratch_root)
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
