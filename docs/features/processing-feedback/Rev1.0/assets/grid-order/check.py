"""Add a fresh folder and watch the grid like the page does: do tiles get pushed down, does the top fill first?

usage: check.py <app-dir> <label> <port>
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP = Path(sys.argv[1]).resolve()
LABEL = sys.argv[2]
PORT = int(sys.argv[3])
COUNT = 120
TOP = 20
HERE = Path(__file__).resolve().parent
RUN = HERE / f"run-{LABEL}-{time.strftime('%H%M%S')}"
SRC = Path(r"J:\Pictures\1. Favorites Pictures")


def call(path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read() or b"null")


media, root = RUN / "media", RUN / "library-data"
media.mkdir(parents=True)
root.mkdir()
pics = sorted(SRC.glob("*.JPG"))
for path in pics[:: max(1, len(pics) // COUNT)][:COUNT]:
    shutil.copy2(path, media / path.name)
(root / "settings.json").write_text(json.dumps({"schemaVersion": 1, "port": PORT, "listenHost": "127.0.0.1",
                                                "addFolderDefault": "ask", "language": "en", "sort": "date",
                                                "dir": "desc"}) + "\n", encoding="utf-8")
env = dict(os.environ, PATH=r"C:\ffmpeg\bin;" + os.environ["PATH"], PYTHONPATH=str(APP))
python = Path(r"J:\slyOS\projects\photoLibrary\.venv\Scripts\python.exe")
proc = subprocess.Popen([str(python), "-m", "library", "--root", str(root), "serve"], cwd=APP, env=env,
                        stdout=open(RUN / "stdout.log", "w"), stderr=open(RUN / "stderr.log", "w"))
try:
    for _ in range(150):
        try:
            call("/api/health")
            break
        except OSError:
            time.sleep(0.2)
    t0 = time.monotonic()
    call("/api/sources", {"path": str(media), "mode": "serve-from-there", "previewStore": "with-server"})
    polls, prev = [], None
    pushes = moved_tiles = 0
    top_done = all_done = None
    while time.monotonic() - t0 < 180:
        items = [i for i in call("/api/items") if not str(i["id"]).startswith("pending-")]
        now = round(time.monotonic() - t0, 2)
        order = [i["id"] for i in items]
        ready = {i["id"] for i in items if ((i.get("renditions") or {}).get("status") or {}).get("thumb") == "ready"}
        if prev is not None:
            before = {item_id: n for n, item_id in enumerate(prev)}
            moved = [item_id for n, item_id in enumerate(order) if item_id in before and n > before[item_id]]
            if moved:
                pushes += 1
                moved_tiles += len(moved)
        prev = order
        top_ready = sum(1 for item_id in order[:TOP] if item_id in ready)
        polls.append({"t": now, "tiles": len(order), "thumbs": len(ready), "topThumbs": top_ready})
        if len(order) == COUNT and top_ready == TOP and top_done is None:
            top_done = now
        if len(order) == COUNT and len(ready) == COUNT:
            all_done = now
            break
        time.sleep(0.25)
    first_full_screen = next((p["t"] for p in polls if p["tiles"] >= TOP and p["topThumbs"] == TOP), None)
    result = {"label": LABEL, "app": str(APP), "pictures": COUNT, "pollsWithTilesPushedDown": pushes,
              "tilesPushedDown": moved_tiles, "polls": len(polls),
              "firstScreenfulOfPicturesSec": first_full_screen, "finalTop20ThumbsSec": top_done,
              "allThumbsSec": all_done, "timeline": polls}
    (RUN / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "timeline"}, indent=2))
finally:
    proc.terminate()
