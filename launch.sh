#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
NO_BROWSER=0
for arg in "$@"; do
  if [ "$arg" = "--no-browser" ]; then
    NO_BROWSER=1
  fi
done

have_python=0
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"; then
    have_python=1
    PYTHON=python3
  fi
fi
if [ "$have_python" -eq 0 ] && command -v python >/dev/null 2>&1; then
  if python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"; then
    have_python=1
    PYTHON=python
  fi
fi
if [ "$have_python" -eq 0 ] || ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Python 3.12+ and ffmpeg must be on PATH. Install them with the platform package manager, then re-run launch.sh." >&2
  exit 1
fi

"$PYTHON" -m library serve &
PID=$!
read_url() {
  "$PYTHON" -c 'import json; from pathlib import Path; p = Path("library-data/settings.json"); port, host = 8765, "127.0.0.1";
data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {};
port = int(data.get("port") or port); host = str(data.get("listenHost") or host);
host = "127.0.0.1" if host in ("0.0.0.0", "::") else host; print(f"http://{host}:{port}/")'
}
URL="$(read_url)"
ready=0
for _ in $(seq 1 50); do
  URL="$(read_url)"
  if command -v curl >/dev/null 2>&1 && curl -sf "${URL}api/health" | grep -q '"ok"'; then
    ready=1
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    break
  fi
  sleep 0.2
done
if [ "$ready" -eq 0 ]; then
  echo "Library could not start. Its listen port is already in use." >&2
  exit 1
fi
echo "$URL"
if [ "$NO_BROWSER" -eq 0 ]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
fi
wait "$PID"
