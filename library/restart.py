"""Stop only this Library serve process, then relaunch on Windows."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from library.paths import APP_FOLDER
from library.settings import DEFAULTS, load_settings_file, settings_path

SKIP_ENV = "LIBRARY_SKIP_RESTART"


def skip_restart() -> bool:
    raw = (os.environ.get(SKIP_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes"}


def listen_target(root: Path | None = None) -> tuple[str, int]:
    folder = Path(root) if root is not None else (APP_FOLDER / "library-data")
    host = str(DEFAULTS.get("listenHost") or "127.0.0.1")
    port = int(DEFAULTS.get("port") or 8765)
    try:
        if settings_path(folder).exists():
            settings = load_settings_file(folder)
            host = str(settings.get("listenHost") or host)
            port = int(settings.get("port") or port)
    except Exception:
        pass
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    return host, port


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def is_this_library_serve(command: str, app_folder: Path | None = None) -> bool:
    """True only for this app folder's `python -m library serve`."""
    text = (command or "").replace('"', " ").replace("'", " ")
    collapsed = " ".join(text.split())
    low = collapsed.lower()
    if "-m library" not in low or " serve" not in low:
        return False
    if " setup" in low or " update" in low:
        return False
    root = _norm(str(app_folder or APP_FOLDER))
    return bool(root) and root in _norm(collapsed)


def _windows_command(pid: int) -> str:
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process -Filter \"ProcessId="
                + str(int(pid))
                + "\").CommandLine",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return (proc.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _linux_command(pid: int) -> str:
    path = Path("/proc") / str(int(pid)) / "cmdline"
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()


def process_command(pid: int) -> str:
    if os.name == "nt":
        return _windows_command(pid)
    return _linux_command(pid)


def _windows_listeners(port: int) -> list[int]:
    pids: list[int] = []
    try:
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return pids
    needle = ":" + str(int(port))
    for line in (proc.stdout or "").splitlines():
        low = line.lower()
        if "listening" not in low or needle not in line.replace(" ", ""):
            if "listen" not in low:
                continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[1] if parts[0].lower().startswith("tcp") else ""
        if not local.endswith(needle) and needle not in local:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0 and pid not in pids:
            pids.append(pid)
    return pids


def _linux_listeners(port: int) -> list[int]:
    pids: list[int] = []
    try:
        proc = subprocess.run(
            ["ss", "-ltnp"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
        needle = ":" + str(int(port))
        for line in blob.splitlines():
            if needle not in line:
                continue
            marker = "pid="
            index = line.find(marker)
            if index < 0:
                continue
            rest = line[index + len(marker) :]
            digits = ""
            for ch in rest:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits:
                pid = int(digits)
                if pid > 0 and pid not in pids:
                    pids.append(pid)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return pids


def find_library_serve_pids(root: Path | None = None, app_folder: Path | None = None) -> list[int]:
    _host, port = listen_target(root)
    app = Path(app_folder) if app_folder is not None else APP_FOLDER
    candidates = _windows_listeners(port) if os.name == "nt" else _linux_listeners(port)
    matched: list[int] = []
    for pid in candidates:
        if pid == os.getpid():
            continue
        command = process_command(pid)
        if is_this_library_serve(command, app):
            matched.append(pid)
    return matched


def stop_this_library(root: Path | None = None, app_folder: Path | None = None) -> list[int]:
    stopped: list[int] = []
    for pid in find_library_serve_pids(root, app_folder):
        try:
            os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except OSError:
            continue
    deadline = time.time() + 4
    while time.time() < deadline:
        still = [pid for pid in stopped if _pid_alive(pid)]
        if not still:
            break
        time.sleep(0.15)
    for pid in stopped:
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return stopped


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_library(app_folder: Path | None = None) -> bool:
    app = Path(app_folder) if app_folder is not None else APP_FOLDER
    launch = app / "Launch.bat"
    library = app / "Library.bat"
    target = launch if launch.is_file() else library
    if not target.is_file():
        return False
    if os.name == "nt":
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(target)],
            cwd=str(app),
            close_fds=True,
        )
        return True
    return False


def relaunch_if_updated(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """If Update wrote new code and Library is running, stop only that serve and relaunch."""
    out = dict(payload)
    out.setdefault("restarting", False)
    if skip_restart():
        out["restartSkipped"] = True
        return out
    if not out.get("ok") or not out.get("updated"):
        return out
    running = find_library_serve_pids(root)
    if not running:
        return out
    stop_this_library(root)
    started = start_library()
    out["restarting"] = True
    out["code"] = "restarting"
    sha = out.get("git_sha") or out.get("revision") or ""
    if started:
        out["message"] = "Updated to " + str(sha) + " on main. Restarting Library..."
    else:
        out["message"] = "Updated to " + str(sha) + " on main. Start Library.bat to open the new copy."
    return out


def schedule_relaunch(root: Path, delay: float = 1.5) -> bool:
    """Detach a helper that stops this serve and starts Library.bat after the HTTP response."""
    if skip_restart():
        return False
    running = find_library_serve_pids(root)
    if not running:
        return False
    helper = (
        "import time, sys; "
        "time.sleep(" + str(float(delay)) + "); "
        "from pathlib import Path; "
        "from library.restart import start_library, stop_this_library; "
        "root = Path(sys.argv[1]); "
        "stop_this_library(root); "
        "start_library()"
    )
    kwargs: dict[str, Any] = {
        "args": [sys.executable, "-c", helper, str(root)],
        "cwd": str(APP_FOLDER),
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(**kwargs)
    return True


def attach_restart_plan(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("restarting", False)
    if skip_restart() or not out.get("ok") or not out.get("updated"):
        return out
    if schedule_relaunch(root):
        sha = out.get("git_sha") or out.get("revision") or ""
        out["restarting"] = True
        out["code"] = "restarting"
        out["message"] = "Updated to " + str(sha) + " on main. Restarting Library..."
    return out
