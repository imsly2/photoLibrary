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
URL="http://127.0.0.1:8765/"
for _ in $(seq 1 50); do
  if command -v curl >/dev/null 2>&1 && curl -sf "${URL}api/health" >/dev/null; then
    break
  fi
  sleep 0.2
done
if [ "$NO_BROWSER" -eq 0 ]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
fi
wait "$PID"
