"""Slice S00 diagnostic assertions. This log is not the grade."""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from library.settings import KEY_ORDER, defaults
from tests.qa.probe import (
    VALID_HEIF_BRANDS,
    metadata_matches,
    mtime_utc,
    probe_file,
    sha256_file,
)
from tests.qa.roots import UnmarkedRootError, prepare_root

PRODUCT_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_FIXTURES = PRODUCT_ROOT / "tests" / "fixtures"
SCENARIO_IDS = [
    "duplicate",
    "collision",
    "modified",
    "unsafe/Unicode paths",
    "interruption",
    "pending annotation",
    "absent source",
    "moved library",
    "moved linked volume",
    "preview missing",
    "denied/relocate interrupted",
    "HEIC failure",
    "format coverage",
    "orphan/mismatch live",
    "date edge",
    "empty/no-GPS",
    "settings/history",
    "annotation",
]
BASE_FILES = [
    "a/IMG_1042.jpg",
    "a/near.jpg",
    "b/far.jpg",
    "b/no-exif.jpg",
    "b/created.jpg",
    "b/holiday_20200102.jpg",
    "b/holiday_2020-01-03.jpg",
    "b/oriented.jpg",
    "a/clip.mp4",
    "live/LIVE_0001.jpg",
    "live/LIVE_0001.mov",
]
FORMAT_FILES = [
    "formats/quad.png",
    "formats/quad.gif",
    "formats/quad.webp",
    "formats/quad.heic",
    "formats/quad.heif",
    "formats/quad.tiff",
    "formats/quad.bmp",
    "formats/clip.mov",
    "formats/clip.m4v",
    "formats/clip.avi",
    "formats/clip.mkv",
    "formats/clip.webm",
    "formats/broken.heic",
]
LIVE_ID = "11111111-2222-4333-8444-555555555555"


class Checks:
    def __init__(self) -> None:
        self.assertions: list[dict[str, Any]] = []

    def check(self, name: str, cond: bool, detail: str = "") -> bool:
        ok = bool(cond)
        self.assertions.append({"name": name, "pass": ok, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""), flush=True)
        return ok

    def ok(self) -> bool:
        return all(item["pass"] for item in self.assertions)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(PRODUCT_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


def run_library(root: Path, args: list[str], *, env: dict[str, str] | None = None, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "library", "--root", str(root), *args],
        cwd=str(PRODUCT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env or _env(),
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(
            proc.args, timeout, output=stdout, stderr=stderr
        )
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def run_qa(args: list[str], timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tests.qa", *args],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_env(),
    )


def find_free_port(lo: int = 18765, hi: int = 18864) -> int:
    for port in range(lo, hi + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            sock.close()
    raise RuntimeError("no free port in 18765-18864")


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), 0.25):
            return True
    except OSError:
        return False


def start_server(root: Path, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "library", "--root", str(root), "serve"],
        cwd=str(PRODUCT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env or _env(),
    )


def wait_health(url: str, proc: subprocess.Popen[str], timeout: float = 15) -> tuple[int, Any]:
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"serve exited {proc.returncode} stdout={stdout!r} stderr={stderr!r}"
            )
        try:
            status, body = request_json(url.rstrip("/") + "/api/health", timeout=0.5)
            if status == 200:
                return status, body
        except OSError as exc:
            last_exc = exc
            time.sleep(0.1)
    raise RuntimeError(f"health timeout last={last_exc}")


def stop_owned(
    proc: subprocess.Popen[str] | None,
    extra_pids: list[int] | None = None,
) -> None:
    if proc is None and not extra_pids:
        return
    pids: list[int] = []
    if proc is not None and proc.poll() is None:
        pids.append(proc.pid)
    for pid in extra_pids or []:
        if type(pid) is int and pid > 0:
            pids.append(pid)
    if os.name == "nt":
        seen: set[int] = set()
        for pid in pids:
            if pid in seen:
                continue
            seen.add(pid)
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        if proc is not None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        return
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def parse_json(text: str) -> Any:
    return json.loads(text)


def copy_committed_fixtures(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(COMMITTED_FIXTURES / "manifest.json", output / "manifest.json")
    dest_media = output / "media"
    if dest_media.exists():
        shutil.rmtree(dest_media)
    shutil.copytree(COMMITTED_FIXTURES / "media", dest_media)


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_committed(checks: Checks) -> dict[str, Any]:
    manifest_path = COMMITTED_FIXTURES / "manifest.json"
    checks.check("committed-manifest-exists", manifest_path.is_file(), str(manifest_path))
    manifest = load_manifest(manifest_path)
    files = {item["path"]: item for item in manifest.get("files", [])}
    required = BASE_FILES + FORMAT_FILES + ["family/旅行 photo.jpg"]
    for rel in required:
        checks.check(f"fixture-listed:{rel}", rel in files, rel)
    long_paths = [p for p in files if len(p) > 80]
    checks.check(
        "long-nested-path-present",
        any("/" in p and len(p) < 240 for p in long_paths),
        str(long_paths),
    )
    for rel, rec in files.items():
        path = COMMITTED_FIXTURES / "media" / Path(*rel.split("/"))
        checks.check(f"fixture-exists:{rel}", path.is_file(), str(path))
        if not path.is_file():
            continue
        digest = sha256_file(path)
        checks.check(
            f"fixture-hash:{rel}",
            digest == rec["sha256"],
            f"want {rec['sha256']} got {digest}",
        )
        checks.check(
            f"fixture-size:{rel}",
            path.stat().st_size == rec["sizeBytes"],
        )
        checks.check(
            f"fixture-mtime:{rel}",
            mtime_utc(path) == rec["mtime"],
            f"want {rec['mtime']} got {mtime_utc(path)}",
        )
        extraction = probe_file(path)
        if rel == "formats/broken.heic":
            checks.check("broken-heic-invalid", extraction.get("validImage") is not True)
            checks.check("broken-heic-not-jpeg", extraction.get("isJpeg") is not True)
            brands = extraction.get("ftypBrands") or []
            checks.check(
                "broken-heic-no-valid-brand",
                not any(b.strip() in VALID_HEIF_BRANDS for b in brands),
                str(brands),
            )
            continue
        problems = metadata_matches(rec["expectedMetadata"], extraction)
        checks.check(
            f"fixture-metadata:{rel}",
            not problems,
            "; ".join(problems),
        )
        if rel.endswith(".heic") or rel.endswith(".heif"):
            brands = extraction.get("ftypBrands") or []
            checks.check(
                f"heif-ftyp:{rel}",
                extraction.get("validHeifBrand") is True and extraction.get("isJpeg") is not True,
                str(brands),
            )
    still_ext = probe_file(COMMITTED_FIXTURES / "media" / "live" / "LIVE_0001.jpg")
    movie_ext = probe_file(COMMITTED_FIXTURES / "media" / "live" / "LIVE_0001.mov")
    checks.check(
        "live-content-identifier",
        still_ext.get("contentIdentifier") == LIVE_ID
        and movie_ext.get("contentIdentifier") == LIVE_ID,
        f"still={still_ext.get('contentIdentifier')} movie={movie_ext.get('contentIdentifier')}",
    )
    ids = [s.get("id") for s in manifest.get("scenarios", [])]
    checks.check("scenario-ids", ids == SCENARIO_IDS, str(ids))
    return manifest


def write_isolated_port(root: Path, port: int) -> None:
    proc = run_library(root, ["settings", "get"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    proc = run_library(root, ["settings", "set", "port", str(port)])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


def probe_dependencies(log_path: Path, checks: Checks) -> None:
    lines = []
    py_ver = sys.version.replace("\n", " ")
    lines.append(f"python: {py_ver}")
    checks.check("python-3.12+", sys.version_info >= (3, 12), py_ver)
    for name in ("ffmpeg", "ffprobe"):
        proc = subprocess.run([name, "-version"], capture_output=True, text=True)
        first = (proc.stdout or proc.stderr).splitlines()[0] if (proc.stdout or proc.stderr) else ""
        lines.append(f"{name}: {first}")
        checks.check(f"{name}-present", proc.returncode == 0 and bool(first), first or "missing")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def assert_no_pillow_in_server(checks: Checks) -> None:
    hits = []
    for path in (PRODUCT_ROOT / "library").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PIL" in text or "pillow" in text.lower():
            hits.append(str(path))
    checks.check("server-does-not-import-pillow", hits == [], ", ".join(hits))
    sys.modules.pop("PIL", None)
    import library.server  # noqa: F401

    checks.check("import-library.server-without-PIL", "PIL" not in sys.modules)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    owned: list[subprocess.Popen[str]] = []
    owned_pids: list[int] = []
    commands: list[str] = []
    recovery: dict[str, Any] = {}
    try:
        probe_dependencies(artifacts / "dependency-probe.log", checks)
        assert_no_pillow_in_server(checks)
        manifest = validate_committed(checks)
        (artifacts / "fixture-manifest.json").write_text(
            (COMMITTED_FIXTURES / "manifest.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        sandbox = artifacts / "fixture-sandbox"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        proc = run_qa(["fixtures", "--output", str(sandbox)])
        commands.append("python -m tests.qa fixtures --output <sandbox>")
        checks.check("fixtures-command-exit", proc.returncode == 0, proc.stderr)
        if proc.returncode == 0:
            for rel in BASE_FILES + FORMAT_FILES:
                src = COMMITTED_FIXTURES / "media" / rel
                dst = sandbox / "media" / rel
                checks.check(
                    f"sandbox-hash:{rel}",
                    dst.is_file() and sha256_file(src) == sha256_file(dst),
                )

        unmarked = artifacts / "unmarked-root"
        unmarked.mkdir(parents=True)
        (unmarked / "stray.txt").write_text("nope", encoding="utf-8")
        refused = False
        detail = ""
        try:
            prepare_root(unmarked)
        except UnmarkedRootError as exc:
            refused = True
            detail = str(exc)
        checks.check("refuse-unmarked-nonempty-root", refused, detail)

        defaults_root = artifacts / "defaults-root"
        if defaults_root.exists():
            shutil.rmtree(defaults_root)
        prepare_root(defaults_root)
        got = run_library(defaults_root, ["settings", "get"])
        commands.append("python -m library settings get")
        checks.check("first-open-settings-exit", got.returncode == 0, got.stderr)
        settings_obj = parse_json(got.stdout) if got.returncode == 0 else {}
        order = list(settings_obj.keys()) if isinstance(settings_obj, dict) else []
        checks.check("settings-key-order", order == list(KEY_ORDER), str(order))
        checks.check("settings-defaults", settings_obj == defaults(), str(settings_obj))
        disk = json.loads((defaults_root / "settings.json").read_text(encoding="utf-8"))
        checks.check("settings-file-matches", disk == defaults())
        (artifacts / "settings.json").write_text(
            json.dumps(disk, indent=2) + "\n", encoding="utf-8"
        )

        empty_undo = run_library(defaults_root, ["undo"])
        checks.check("empty-undo-success", empty_undo.returncode == 0, empty_undo.stderr)

        offline = artifacts / "offline-history"
        if offline.exists():
            shutil.rmtree(offline)
        prepare_root(offline)
        run_library(offline, ["settings", "get"])
        setp = run_library(offline, ["settings", "set", "port", "8770"])
        checks.check("offline-set-port", setp.returncode == 0, setp.stderr)
        after_set = parse_json(run_library(offline, ["settings", "get"]).stdout)
        checks.check("offline-get-8770", after_set.get("port") == 8770, str(after_set.get("port")))
        und = run_library(offline, ["undo"])
        checks.check("offline-undo", und.returncode == 0, und.stderr)
        after_undo = parse_json(run_library(offline, ["settings", "get"]).stdout)
        checks.check("offline-get-8765", after_undo.get("port") == 8765, str(after_undo.get("port")))
        red = run_library(offline, ["redo"])
        checks.check("offline-redo", red.returncode == 0, red.stderr)
        after_redo = parse_json(run_library(offline, ["settings", "get"]).stdout)
        checks.check("offline-redo-8770", after_redo.get("port") == 8770)

        isolated = Path(root)
        if isolated.exists():
            shutil.rmtree(isolated)
        prepare_root(isolated)
        isolated_port = find_free_port()
        write_isolated_port(isolated, isolated_port)
        server = start_server(isolated)
        owned.append(server)
        url = f"http://127.0.0.1:{isolated_port}/"
        health_status, health_body = wait_health(url, server)
        checks.check("isolated-health", health_status == 200 and health_body == {"ok": True}, str(health_body))
        (artifacts / "health.json").write_text(
            json.dumps(health_body, indent=2) + "\n", encoding="utf-8"
        )
        rt_status, runtime = request_json(url.rstrip("/") + "/api/runtime")
        from library.paths import root_text, roots_equal

        checks.check("runtime-schema", rt_status == 200 and runtime.get("schemaVersion") == 1)
        server_pid = runtime.get("pid")
        if type(server_pid) is int:
            owned_pids.append(server_pid)
        checks.check(
            "runtime-pid",
            type(server_pid) is int and server_pid > 0,
            f"runtime={server_pid} popen={server.pid}",
        )
        checks.check("runtime-root", roots_equal(runtime.get("root", ""), isolated), str(runtime.get("root")))
        checks.check("runtime-url", runtime.get("url") == url, str(runtime.get("url")))
        page = urllib.request.urlopen(url, timeout=2).read().decode("utf-8")
        checks.check("empty-page-title", "<title>Library</title>" in page)
        checks.check("empty-page-copy", "No pictures yet" in page)
        checks.check("empty-page-add-folder", "Add folder" in page)

        reopen = run_library(isolated, ["serve"], timeout=10)
        checks.check("reopen-exit", reopen.returncode == 0, reopen.stderr)
        checks.check("reopen-url", reopen.stdout.strip() == url, reopen.stdout.strip())
        rt2_status, runtime2 = request_json(url.rstrip("/") + "/api/runtime")
        checks.check(
            "reopen-same-pid",
            runtime2.get("pid") == server_pid,
            f"first={server_pid} second={runtime2.get('pid')}",
        )

        put_status, put_body = request_json(
            url.rstrip("/") + "/api/settings", method="PUT", body={"port": 8770}
        )
        checks.check("http-set-port", put_status == 200 and put_body.get("port") == 8770)
        cli_get = run_library(isolated, ["settings", "get"])
        checks.check("cli-forwards-get", cli_get.returncode == 0 and parse_json(cli_get.stdout).get("port") == 8770, cli_get.stderr)
        undo_status, _ = request_json(url.rstrip("/") + "/api/undo", method="POST", body={})
        checks.check("http-undo", undo_status == 200)
        after_http_undo = parse_json(run_library(isolated, ["settings", "get"]).stdout)
        checks.check("http-undo-8765-or-isolated", after_http_undo.get("port") == isolated_port)
        redo_status, _ = request_json(url.rstrip("/") + "/api/redo", method="POST", body={})
        checks.check("http-redo", redo_status == 200)
        after_http_redo = parse_json(run_library(isolated, ["settings", "get"]).stdout)
        checks.check("http-redo-8770", after_http_redo.get("port") == 8770)
        cli_undo = run_library(isolated, ["undo"])
        checks.check("cli-forward-undo", cli_undo.returncode == 0, cli_undo.stderr)
        restored = parse_json(run_library(isolated, ["settings", "get"]).stdout)
        checks.check("cli-undo-restores-isolated-port", restored.get("port") == isolated_port)

        before_invalid = json.loads((isolated / "settings.json").read_text(encoding="utf-8"))
        bad_status, bad_body = request_json(
            url.rstrip("/") + "/api/settings",
            method="PUT",
            body={"port": 0},
        )
        checks.check(
            "invalid-port",
            bad_status == 400 and isinstance(bad_body, dict) and bad_body.get("error") == "invalid-argument",
            str(bad_body),
        )
        unknown_status, unknown_body = request_json(
            url.rstrip("/") + "/api/settings",
            method="PUT",
            body={"notAKey": 1},
        )
        checks.check(
            "unknown-key",
            unknown_status == 400 and unknown_body.get("error") == "invalid-argument",
        )
        bool_status, bool_body = request_json(
            url.rstrip("/") + "/api/settings",
            method="PUT",
            body={"thumbPx": True},
        )
        checks.check(
            "bool-as-number",
            bool_status == 400 and bool_body.get("error") == "invalid-argument",
        )
        after_invalid = json.loads((isolated / "settings.json").read_text(encoding="utf-8"))
        checks.check("invalid-does-not-change-file", before_invalid == after_invalid)

        missing_status, missing_body = request_json(
            url.rstrip("/") + "/api/media/missing?which=original"
        )
        checks.check(
            "missing-media-not-found",
            missing_status == 404 and missing_body == {"error": "not-found"},
            str(missing_body),
        )
        log_text = (isolated / "logs" / "server.log").read_text(encoding="utf-8")
        log_ok = False
        for line in log_text.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and "/api/media/missing?which=original" in parts[1] and parts[2] == "not-found":
                if "T" in parts[0]:
                    log_ok = True
        checks.check("server-log-404-line", log_ok, log_text[-400:])

        unknown_asset_status, unknown_asset = request_json(url.rstrip("/") + "/assets/nope.css")
        checks.check(
            "unknown-asset-404",
            unknown_asset_status == 404 and unknown_asset == {"error": "not-found"},
        )

        last_status = None
        last_body = None
        for value in range(1, 502):
            last_status, last_body = request_json(
                url.rstrip("/") + "/api/settings",
                method="PUT",
                body={"tourPictures": value},
                timeout=10.0,
            )
            if last_status != 200:
                break
        checks.check("history-501-writes", last_status == 200, str(last_body))
        state = json.loads((isolated / "undo" / "state.json").read_text(encoding="utf-8"))
        checks.check("history-cap-500", len(state.get("entries") or []) == 500, str(len(state.get("entries") or [])))
        entry_files = list((isolated / "undo" / "entries").glob("*.json"))
        checks.check("history-entry-files-500", len(entry_files) == 500, str(len(entry_files)))

        dummy_port = find_free_port()
        dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dummy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        dummy.bind(("127.0.0.1", dummy_port))
        dummy.listen(5)
        dummy_root = artifacts / "dummy-root"
        if dummy_root.exists():
            shutil.rmtree(dummy_root)
        prepare_root(dummy_root)
        write_isolated_port(dummy_root, dummy_port)
        dummy_launch = run_library(dummy_root, ["serve"], timeout=10)
        checks.check("dummy-port-in-use-exit", dummy_launch.returncode == 1, dummy_launch.stderr)
        try:
            dummy_err = parse_json(dummy_launch.stderr.strip().splitlines()[-1])
        except Exception:
            dummy_err = {}
        checks.check("dummy-port-in-use-code", dummy_err.get("error") == "port-in-use", dummy_launch.stderr)
        still_accepts = False
        try:
            with socket.create_connection(("127.0.0.1", dummy_port), 1):
                still_accepts = True
        except OSError:
            still_accepts = False
        checks.check("dummy-still-accepts", still_accepts)
        dummy.close()

        default_note = {"8765": "occupied-left-running"}
        if not port_open(8765):
            default_root = artifacts / "default-port-root"
            if default_root.exists():
                shutil.rmtree(default_root)
            prepare_root(default_root)
            default_server = start_server(default_root)
            owned.append(default_server)
            default_url = "http://127.0.0.1:8765/"
            d_status, d_body = wait_health(default_url, default_server)
            checks.check("default-port-health", d_status == 200 and d_body == {"ok": True})
            d_rt, d_runtime = request_json(default_url.rstrip("/") + "/api/runtime")
            default_pid = d_runtime.get("pid")
            if type(default_pid) is int:
                owned_pids.append(default_pid)
            checks.check(
                "default-port-pid",
                type(default_pid) is int and default_pid > 0,
                str(default_pid),
            )
            second = run_library(default_root, ["serve"], timeout=10)
            checks.check("default-port-reopen", second.returncode == 0 and second.stdout.strip() == default_url)
            d_rt2, d_runtime2 = request_json(default_url.rstrip("/") + "/api/runtime")
            checks.check("default-port-same-pid", d_runtime2.get("pid") == default_pid, str(d_runtime2.get("pid")))
            stop_owned(default_server, extra_pids=[default_pid])
            owned.remove(default_server)
            closed = False
            deadline = time.time() + 5
            while time.time() < deadline:
                if not port_open(8765):
                    closed = True
                    break
                time.sleep(0.1)
            checks.check("default-port-stopped", closed)
            default_note = {"8765": "owned-launch-then-stopped", "pid": default_pid}
        else:
            try:
                occupant_status, occupant = request_json("http://127.0.0.1:8765/api/health", timeout=0.8)
            except OSError as exc:
                occupant_status, occupant = None, str(exc)
            checks.check(
                "default-port-occupant-probed",
                type(occupant_status) is int,
                f"status={occupant_status} body={occupant}",
            )
            checks.check("default-port-occupant-left-up", port_open(8765))
            default_note = {
                "8765": "occupied-left-running",
                "probe": {"status": occupant_status, "body": occupant},
            }

        busy_root = artifacts / "busy-root"
        if busy_root.exists():
            shutil.rmtree(busy_root)
        prepare_root(busy_root)
        run_library(busy_root, ["settings", "get"])
        lock_log = artifacts / "lock-holder.log"
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys,time; from pathlib import Path; from library.lock import WriteLock; "
                "lock=WriteLock(Path(sys.argv[1])); lock.acquire(); print('LOCKED', flush=True); time.sleep(60)",
                str(busy_root),
            ],
            cwd=str(PRODUCT_ROOT),
            stdout=open(lock_log, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            text=True,
            env=_env(),
        )
        owned.append(holder)
        locked = False
        deadline = time.time() + 10
        while time.time() < deadline:
            if lock_log.exists() and "LOCKED" in lock_log.read_text(encoding="utf-8"):
                locked = True
                break
            if holder.poll() is not None:
                break
            time.sleep(0.05)
        checks.check(
            "lock-holder-acquired",
            locked,
            lock_log.read_text(encoding="utf-8") if lock_log.exists() else "no-log",
        )
        before_busy = json.loads((busy_root / "settings.json").read_text(encoding="utf-8"))
        busy_set = run_library(busy_root, ["settings", "set", "port", "8770"])
        checks.check("second-writer-busy-exit", busy_set.returncode == 1, busy_set.stderr)
        try:
            busy_err = parse_json(busy_set.stderr.strip().splitlines()[-1])
        except Exception:
            busy_err = {}
        checks.check("second-writer-busy-code", busy_err.get("error") == "busy", busy_set.stderr)
        after_busy = json.loads((busy_root / "settings.json").read_text(encoding="utf-8"))
        checks.check("busy-does-not-change-settings", before_busy == after_busy)
        stop_owned(holder)
        if holder in owned:
            owned.remove(holder)

        def barrier_case(name: str, expect_port: int) -> dict[str, Any]:
            broot = artifacts / f"barrier-{name}"
            if broot.exists():
                shutil.rmtree(broot)
            prepare_root(broot)
            run_library(broot, ["settings", "get"])
            env = _env()
            env["LIBRARY_TEST"] = "1"
            env["LIBRARY_TEST_BARRIER"] = name
            crashed = run_library(broot, ["settings", "set", "port", "8770"], env=env)
            recovered = run_library(broot, ["settings", "get"])
            port = parse_json(recovered.stdout).get("port") if recovered.returncode == 0 else None
            txn = broot / ".transactions"
            txn_left = txn.exists() and any(txn.iterdir())
            return {
                "exit": crashed.returncode,
                "stderr": crashed.stderr.strip(),
                "port": port,
                "transactionsPresent": txn_left,
            }

        prepared = barrier_case("settings-prepared", 8765)
        checks.check("barrier-prepared-exit-86", prepared["exit"] == 86, prepared["stderr"])
        checks.check("barrier-prepared-port-8765", prepared["port"] == 8765, str(prepared["port"]))
        committed = barrier_case("settings-committed", 8770)
        checks.check("barrier-committed-exit-86", committed["exit"] == 86, committed["stderr"])
        checks.check("barrier-committed-port-8770", committed["port"] == 8770, str(committed["port"]))
        checks.check("barrier-committed-txn-removed", committed["transactionsPresent"] is False)
        recovery = {
            "prepared": prepared,
            "committed": committed,
            "defaultPort": default_note,
        }
        (artifacts / "recovery.json").write_text(
            json.dumps(recovery, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        for proc in list(owned):
            stop_owned(proc, extra_pids=owned_pids)

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest_hash = sha256_file(COMMITTED_FIXTURES / "manifest.json") if (COMMITTED_FIXTURES / "manifest.json").is_file() else ""
    result = {
        "slice": "S00",
        "pass": checks.ok(),
        "assertions": checks.assertions,
        "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version},
        "fixtureManifestHash": manifest_hash,
        "revision": revision,
        "commands": commands,
        "artifactPaths": {
            "result.json": str(artifacts / "result.json"),
            "stdout.log": str(artifacts / "stdout.log"),
            "health.json": str(artifacts / "health.json"),
            "settings.json": str(artifacts / "settings.json"),
            "recovery.json": str(artifacts / "recovery.json"),
            "dependency-probe.log": str(artifacts / "dependency-probe.log"),
            "fixture-manifest.json": str(artifacts / "fixture-manifest.json"),
        },
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if checks.ok() else 1
