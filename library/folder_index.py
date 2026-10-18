"""F23 folder library: static index.html + index.js for offline browsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_text


def write_index(lib_dir: Path, records: list[dict], *, folder_name: str) -> None:
    """Write lib_dir/index.html and lib_dir/index.js for one folder library."""
    lib_dir = Path(lib_dir)
    lib_dir.mkdir(parents=True, exist_ok=True)
    payload = _build_payload(records, folder_name=_as_str(folder_name, "Photos"))
    js_text = _dumps_for_script(payload)
    html_text = _INDEX_HTML
    _write_if_changed(lib_dir / "index.js", js_text)
    _write_if_changed(lib_dir / "index.html", html_text)


def _write_if_changed(path: Path, text: str) -> None:
    if path.is_file():
        try:
            if path.read_text(encoding="utf-8") == text:
                return
        except OSError:
            pass
    atomic_write_text(path, text)


def _dumps_for_script(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("</", r"<\/")
    return f"window.LIBRARY = {raw};\n"


def _as_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_bool(value: Any) -> bool:
    return value is True


def _as_int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _people_names(people: Any) -> list[str]:
    if not isinstance(people, list):
        return []
    names: list[str] = []
    for entry in people:
        if isinstance(entry, dict):
            name = entry.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        elif isinstance(entry, str) and entry:
            names.append(entry)
    return names


def _tag_labels(things: Any) -> list[str]:
    if not isinstance(things, list):
        return []
    labels: list[str] = []
    for entry in things:
        if isinstance(entry, str) and entry:
            labels.append(entry)
        elif isinstance(entry, dict):
            label = entry.get("label")
            if isinstance(label, str) and label:
                labels.append(label)
    return labels


def _quality_fields(quality: Any) -> dict[str, Any]:
    if not isinstance(quality, dict):
        return {"stars": None, "suggested": None, "pick": False, "reject": False}
    return {
        "stars": _as_int_or_none(quality.get("stars")),
        "suggested": _as_int_or_none(quality.get("suggested")),
        "pick": _as_bool(quality.get("pick")),
        "reject": _as_bool(quality.get("reject")),
    }


def _thumb_ready(record: dict, kind: str) -> bool:
    renditions = record.get("renditions")
    if not isinstance(renditions, dict):
        return False
    status = renditions.get("status")
    if not isinstance(status, dict):
        return False
    slot = "poster" if kind == "video" else "thumb"
    return status.get(slot) == "ready"


def _item_from_record(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    path = record.get("path")
    if not isinstance(path, str) or not path:
        return None
    path = path.replace("\\", "/")
    kind = record.get("kind")
    if kind not in ("photo", "video", "live"):
        kind = "photo"
    q = _quality_fields(record.get("quality"))
    return {
        "path": path,
        "id": _as_str(record.get("id")),
        "kind": kind,
        "filename": _as_str(record.get("filename")) or path.split("/")[-1],
        "capturedAt": record.get("capturedAt") if isinstance(record.get("capturedAt"), str) else None,
        "placeName": record.get("placeName") if isinstance(record.get("placeName"), str) else None,
        "people": _people_names(record.get("people")),
        "tags": _tag_labels(record.get("things")),
        "stars": q["stars"],
        "suggested": q["suggested"],
        "pick": q["pick"],
        "reject": q["reject"],
        "favorite": _as_bool(record.get("favorite")),
        "thumbReady": _thumb_ready(record, kind),
    }


def _sort_key(item: dict[str, Any]) -> str:
    ca = item.get("capturedAt")
    if isinstance(ca, str) and ca:
        return ca
    return ""


def _build_payload(records: list[dict], *, folder_name: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if not isinstance(records, list):
        records = []
    for record in records:
        item = _item_from_record(record)
        if item is not None:
            items.append(item)
    items.sort(key=_sort_key, reverse=True)
    return {"folderName": folder_name, "items": items}


_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Folder library</title>
<style>
:root {
  color-scheme: dark;
  --bg: #121214;
  --surface: #1c1c1f;
  --border: #2e2e33;
  --text: #e8e8ec;
  --muted: #9a9aa3;
  --accent: #6ea8fe;
  --placeholder: #2a2a30;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font: 14px/1.45 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
}
header {
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  position: sticky;
  top: 0;
  z-index: 2;
}
header h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}
header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}
#grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  padding: 1rem;
}
.tile {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  background: var(--placeholder);
  border: 1px solid var(--border);
  cursor: pointer;
  padding: 0;
}
.tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.tile.placeholder img { opacity: 0; }
.tile .ph {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: 1.5rem;
}
.badge {
  position: absolute;
  top: 6px;
  left: 6px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 5px;
  border-radius: 4px;
  background: rgba(0,0,0,0.65);
  color: #fff;
}
.stars {
  position: absolute;
  bottom: 6px;
  right: 6px;
  font-size: 0.7rem;
  color: #f5c542;
  text-shadow: 0 1px 2px rgba(0,0,0,0.8);
}
#overlay {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 10;
  background: rgba(0,0,0,0.92);
  flex-direction: column;
}
#overlay.open { display: flex; }
.viewer-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: 1rem;
}
.viewer-main img,
.viewer-main video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}
#info {
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding: 1rem 1.25rem 1.25rem;
  max-height: 40vh;
  overflow: auto;
}
#info h2 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  word-break: break-all;
}
#info dl {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 1rem;
  font-size: 0.9rem;
}
#info dt { color: var(--muted); }
#info dd { margin: 0; }
.pick { color: var(--accent); font-weight: 600; }
.nav-hint {
  text-align: center;
  color: var(--muted);
  font-size: 0.75rem;
  padding: 0.25rem;
}
</style>
</head>
<body>
<header>
  <h1 id="folder-title"></h1>
  <p id="folder-count"></p>
</header>
<div id="grid"></div>
<div id="overlay" role="dialog" aria-modal="true">
  <div class="nav-hint">← → prev/next · Esc close</div>
  <div class="viewer-main" id="viewer-media"></div>
  <div id="info"></div>
</div>
<script src="index.js"></script>
<script>
(function () {
  var data = window.LIBRARY || { folderName: "", items: [] };
  var items = data.items || [];
  var idx = -1;

  function encPath(rel) {
    return rel.split("/").map(function (s) { return encodeURIComponent(s); }).join("/");
  }
  function derivedUrl(rel, suffix) {
    return encPath(rel + suffix);
  }
  function originalUrl(rel) {
    return "../" + encPath(rel);
  }
  function thumbSuffix(kind) {
    return kind === "video" ? ".poster.webp" : ".thumb.webp";
  }

  document.getElementById("folder-title").textContent = data.folderName || "Photos";
  document.getElementById("folder-count").textContent =
    items.length + (items.length === 1 ? " picture" : " pictures");

  var grid = document.getElementById("grid");
  items.forEach(function (item, i) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tile";
    btn.setAttribute("aria-label", item.filename || item.path);
    var ph = document.createElement("div");
    ph.className = "ph";
    ph.textContent = "◇";
    var img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    if (item.thumbReady) {
      img.src = derivedUrl(item.path, thumbSuffix(item.kind));
    } else {
      btn.classList.add("placeholder");
    }
    img.onerror = function () {
      btn.classList.add("placeholder");
      img.style.display = "none";
    };
    btn.appendChild(img);
    btn.appendChild(ph);
    if (item.kind === "video") {
      var b = document.createElement("span");
      b.className = "badge";
      b.textContent = "VIDEO";
      btn.appendChild(b);
    } else if (item.kind === "live") {
      var b2 = document.createElement("span");
      b2.className = "badge";
      b2.textContent = "LIVE";
      btn.appendChild(b2);
    }
    if (item.stars != null && item.stars > 0) {
      var st = document.createElement("span");
      st.className = "stars";
      st.textContent = "\\u2605".repeat(Math.min(item.stars, 5));
      btn.appendChild(st);
    }
    btn.addEventListener("click", function () { openViewer(i); });
    grid.appendChild(btn);
  });

  var overlay = document.getElementById("overlay");
  var mediaHost = document.getElementById("viewer-media");
  var info = document.getElementById("info");

  function openViewer(i) {
    idx = i;
    renderViewer();
    overlay.classList.add("open");
  }
  function closeViewer() {
    overlay.classList.remove("open");
    mediaHost.innerHTML = "";
    idx = -1;
  }
  function renderViewer() {
    if (idx < 0 || idx >= items.length) return;
    var item = items[idx];
    mediaHost.innerHTML = "";
    if (item.kind === "video") {
      var v = document.createElement("video");
      v.controls = true;
      v.poster = derivedUrl(item.path, ".poster.webp");
      var src = document.createElement("source");
      src.src = derivedUrl(item.path, ".proxy.mp4");
      src.type = "video/mp4";
      v.appendChild(src);
      v.onerror = function () {
        v.innerHTML = "";
        var s2 = document.createElement("source");
        s2.src = originalUrl(item.path);
        v.appendChild(s2);
      };
      mediaHost.appendChild(v);
    } else {
      var im = document.createElement("img");
      im.alt = item.filename || "";
      im.src = derivedUrl(item.path, ".preview.webp");
      im.onerror = function () { im.src = originalUrl(item.path); };
      mediaHost.appendChild(im);
    }
    var html = "<h2>" + esc(item.filename || item.path) + "</h2><dl>";
    if (item.capturedAt) html += row("Date", formatDate(item.capturedAt));
    if (item.placeName) html += row("Place", esc(item.placeName));
    if (item.people && item.people.length)
      html += row("People", esc(item.people.join(", ")));
    if (item.tags && item.tags.length)
      html += row("Tags", esc(item.tags.join(", ")));
    var rating = [];
    if (item.stars != null) rating.push(item.stars + " star(s)");
    if (item.pick) rating.push('<span class="pick">Pick</span>');
    if (item.reject) rating.push("Reject");
    if (item.favorite) rating.push("Favorite");
    if (rating.length) html += row("Rating", rating.join(" · "));
    html += "</dl>";
    info.innerHTML = html;
  }
  function row(label, val) {
    return "<dt>" + esc(label) + "</dt><dd>" + val + "</dd>";
  }
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function formatDate(iso) {
    try {
      var d = new Date(iso);
      if (!isNaN(d.getTime())) return d.toLocaleString();
    } catch (e) {}
    return esc(iso);
  }

  document.addEventListener("keydown", function (e) {
    if (!overlay.classList.contains("open")) return;
    if (e.key === "Escape") { e.preventDefault(); closeViewer(); }
    if (e.key === "ArrowLeft") { e.preventDefault(); if (idx > 0) { idx--; renderViewer(); } }
    if (e.key === "ArrowRight") { e.preventDefault(); if (idx < items.length - 1) { idx++; renderViewer(); } }
  });
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) closeViewer();
  });
})();
</script>
</body>
</html>
"""
