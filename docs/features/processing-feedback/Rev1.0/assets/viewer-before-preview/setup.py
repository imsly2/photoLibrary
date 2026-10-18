"""Scratch server with processing paused, so the viewer opens pictures that have no preview yet."""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parents[1]
PORT = 8816
RUN = HERE / f"run-{time.strftime('%H%M%S')}"
MEDIA = RUN / "media"
ROOT = RUN / "library-data"
PICS = ["IMG_0023.JPG", "IMG_0240.JPG", "IMG_2518.JPG"]


def call(path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read() or b"null")


MEDIA.mkdir(parents=True)
ROOT.mkdir()
for name in PICS:
    shutil.copy2(Path(r"J:\Pictures\1. Favorites Pictures") / name, MEDIA / name)
(ROOT / "settings.json").write_text(json.dumps({"schemaVersion": 1, "port": PORT, "listenHost": "127.0.0.1",
                                                "addFolderDefault": "ask", "language": "en"}) + "\n", encoding="utf-8")
env = dict(os.environ, PATH=r"C:\ffmpeg\bin;" + os.environ["PATH"], PYTHONPATH=str(APP))
proc = subprocess.Popen([str(APP / ".venv" / "Scripts" / "python.exe"), "-m", "library", "--root", str(ROOT), "serve"],
                        cwd=APP, env=env, stdout=open(RUN / "stdout.log", "w"), stderr=open(RUN / "stderr.log", "w"))
for _ in range(100):
    try:
        call("/api/health")
        break
    except OSError:
        time.sleep(0.2)
call("/api/jobs", {"action": "pause"})
call("/api/sources", {"path": str(MEDIA), "mode": "serve-from-there", "previewStore": "with-server"})
for _ in range(100):
    items = call("/api/items")
    if len(items) == len(PICS) and not any(str(i["id"]).startswith("pending-") for i in items):
        break
    time.sleep(0.2)
for item in items:
    meta = item.get("metadata") or {}
    print(item["id"], item.get("filename") or item.get("name"), meta.get("width"), meta.get("height"),
          meta.get("orientation"), (item.get("renditions") or {}).get("status"))
print(f"pid {proc.pid} run {RUN}")
