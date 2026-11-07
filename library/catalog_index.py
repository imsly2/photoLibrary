"""Compact catalog index for browse filters. Rebuildable; not source of truth."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from library import folder_library, item_store
from library.catalog_io import (
    iter_source_ids,
    load_places,
    load_things,
    people_dir,
    places_dir,
    things_dir,
)
from library.favorites import favorite_ids, favorites_path
from library.item_index import iter_items, root_key
from library.rating import FLAG_BLURRY, quality_view
from library.recent import load_recent_ids, recent_path
from library.stacks import annotate_stacks

COLS = [
    "id",
    "k",
    "f",
    "at",
    "n",
    "z",
    "s",
    "p",
    "u",
    "g",
    "r",
    "bits",
    "sc",
    "tv",
    "said",
    "dur",
    "w",
    "h",
]

MAX_BYTES = 4_500_000
BIT_PICK = 1
BIT_REJECT = 2
BIT_BLURRY = 4
BIT_THUMB = 8
BIT_POSTER = 16
BIT_HIDDEN = 32
BIT_LIVE = 64
BIT_BURST = 128
BIT_RECENT = 256

_WS = re.compile(r"\s+")
_guard = threading.Lock()
_cache: dict[str, tuple[Any, bytes, str]] = {}
_said_trim_notes: list[str] = []
_bump: dict[str, int] = {}


def bump(root: Path) -> None:
    key = root_key(root)
    with _guard:
        _bump[key] = _bump.get(key, 0) + 1
        _cache.pop(key, None)


def invalidate(root: Path) -> None:
    bump(root)


def said_trim_notes() -> list[str]:
    return list(_said_trim_notes)


def _file_sig(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
        return (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        return (0, 0)


def generation(root: Path) -> tuple[Any, ...]:
    key = root_key(root)
    return (
        item_store.write_count(),
        _file_sig(favorites_path(root)),
        _file_sig(recent_path(root)),
        _file_sig(people_dir(root)),
        _file_sig(places_dir(root)),
        _file_sig(things_dir(root)),
        _bump.get(key, 0),
    )


def _captured_at_ms(value: Any) -> int:
    """ISO capturedAt → Unix epoch milliseconds; missing/invalid → 0."""
    if type(value) is not str or not value:
        return 0
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(round(parsed.timestamp() * 1000.0))


def _version_token(gen: tuple[Any, ...]) -> str:
    return hashlib.sha1(repr(gen).encode("utf-8")).hexdigest()[:16]


def _current_location(item: dict[str, Any]) -> dict[str, Any] | None:
    locs = [loc for loc in (item.get("locations") or []) if loc.get("current") is True]
    if not locs:
        locs = list(item.get("locations") or [])
    return locs[0] if locs else None


def _said_text(item: dict[str, Any]) -> str:
    rec = item.get("transcript")
    if not isinstance(rec, dict) or rec.get("status") != "ready":
        return ""
    parts: list[str] = []
    for keyword in rec.get("keywords") or []:
        if type(keyword) is str and keyword.strip():
            parts.append(keyword.strip())
    summary = rec.get("summary")
    if type(summary) is str and summary.strip():
        parts.append(summary.strip())
    text = rec.get("text")
    if type(text) is str and text.strip():
        parts.append(text.strip())
    else:
        for seg in rec.get("segments") or []:
            seg_text = seg.get("text") if isinstance(seg, dict) else None
            if type(seg_text) is str and seg_text.strip():
                parts.append(seg_text.strip())
    if not parts:
        return ""
    return _WS.sub(" ", " ".join(parts)).strip()


def _thumb_mtime_ns(root: Path, item: dict[str, Any], folders: dict[tuple[str, str], Path | None]) -> int:
    """Rendition file mtime_ns, or 0 if not ready / unreachable."""
    rend = item.get("renditions") or {}
    if (rend.get("status") or {}).get("thumb") != "ready":
        return 0
    relative = rend.get("thumb")
    if type(relative) is not str or not relative:
        return 0
    store = rend.get("store")
    source_id = str(rend.get("sourceId") or "")
    key = (str(store or ""), source_id)
    if key not in folders:
        if store in folder_library.STORES:
            lib = folder_library.for_source_id(root, source_id, store)
            folders[key] = None if lib is None else lib.dir
        else:
            folders[key] = None
    base = folders[key]
    if base is None:
        return 0
    path = base.joinpath(*relative.replace("\\", "/").split("/"))
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _bits_and_stack(item: dict[str, Any], view: dict[str, Any]) -> tuple[int, int]:
    bits = 0
    if view.get("pick") is True:
        bits |= BIT_PICK
    if view.get("reject") is True:
        bits |= BIT_REJECT
    if view.get("blurry") is True or FLAG_BLURRY in (view.get("flags") or []):
        bits |= BIT_BLURRY
    rend = item.get("renditions") or {}
    status = rend.get("status") or {}
    if status.get("thumb") == "ready":
        bits |= BIT_THUMB
    if status.get("poster") == "ready":
        bits |= BIT_POSTER
    stack = item.get("stack")
    sc = 1
    if isinstance(stack, dict):
        kind = stack.get("kind")
        count = stack.get("count")
        sc = int(count) if type(count) is int and count > 0 else 1
        if stack.get("representative") is not True:
            bits |= BIT_HIDDEN
        if kind == "live":
            bits |= BIT_LIVE
        elif kind == "burst":
            bits |= BIT_BURST
    return bits, sc


def build_payload(root: Path) -> dict[str, Any]:
    """Build the compact index object from the in-memory item index."""
    items = list(iter_items(root))
    for item in items:
        item.pop("stack", None)
    annotate_stacks(items)

    sources = list(iter_source_ids(root))
    source_ix = {source_id: i for i, source_id in enumerate(sources)}

    places_rows = [{"id": p["id"], "name": p.get("name")} for p in load_places(root)]
    places_rows.sort(key=lambda row: row["id"])
    place_ix = {row["id"]: i for i, row in enumerate(places_rows)}

    from library.people_panel import cached_load_people

    people_rows = [{"id": p["id"], "name": p.get("name")} for p in cached_load_people(root)]
    people_rows.sort(key=lambda row: row["id"])
    people_ix = {row["id"]: i for i, row in enumerate(people_rows)}

    things_rows = [{"id": t["id"], "name": t.get("name")} for t in load_things(root)]
    things_rows.sort(key=lambda row: row["id"])
    thing_ix = {row["id"]: i for i, row in enumerate(things_rows)}

    marked = favorite_ids(root)
    recent = set(load_recent_ids(root))
    folders: dict[tuple[str, str], Path | None] = {}
    rows: list[list[Any]] = []
    for item in items:
        item_id = item.get("id")
        if type(item_id) is not str or not item_id:
            continue
        kind = item.get("kind")
        if kind not in {"photo", "live", "video"}:
            kind = "photo"
        loc = _current_location(item)
        size = 0
        source_i = -1
        if isinstance(loc, dict):
            raw_size = loc.get("sizeBytes")
            if type(raw_size) is int:
                size = raw_size
            sid = loc.get("sourceId")
            if type(sid) is str and sid in source_ix:
                source_i = source_ix[sid]
        place_id = item.get("placeId")
        place_i = place_ix.get(place_id, -1) if type(place_id) is str else -1
        person_set: list[int] = []
        seen_p: set[str] = set()
        for face in item.get("faces") or []:
            pid = face.get("personId") if isinstance(face, dict) else None
            if type(pid) is not str or not pid or pid in seen_p:
                continue
            seen_p.add(pid)
            ix = people_ix.get(pid)
            if ix is not None:
                person_set.append(ix)
        thing_set: list[int] = []
        seen_t: set[str] = set()
        for ref in item.get("things") or []:
            tid = ref.get("thingId") if isinstance(ref, dict) else None
            if type(tid) is not str or not tid or tid in seen_t:
                continue
            seen_t.add(tid)
            ix = thing_ix.get(tid)
            if ix is not None:
                thing_set.append(ix)
        view = quality_view(item)
        stars = view.get("stars")
        star_count = int(stars) if type(stars) is int and 1 <= stars <= 5 else 0
        bits, sc = _bits_and_stack(item, view)
        if item_id in recent:
            bits |= BIT_RECENT
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        duration_sec = meta.get("durationSec")
        if isinstance(duration_sec, (int, float)) and not isinstance(duration_sec, bool):
            dur_ms = int(round(float(duration_sec) * 1000.0))
        else:
            dur_ms = 0
        width = meta.get("width")
        height = meta.get("height")
        w = int(width) if type(width) is int and width > 0 else 0
        h = int(height) if type(height) is int and height > 0 else 0
        filename = item.get("filename")
        rows.append(
            [
                item_id,
                kind,
                1 if item_id in marked else 0,
                _captured_at_ms(item.get("capturedAt")),
                filename if type(filename) is str else "",
                size,
                source_i,
                place_i,
                person_set,
                thing_set,
                star_count,
                bits,
                sc,
                _thumb_mtime_ns(root, item, folders),
                _said_text(item),
                dur_ms,
                w,
                h,
            ]
        )

    gen = generation(root)
    payload = {
        "v": _version_token(gen),
        "sources": sources,
        "places": places_rows,
        "people": people_rows,
        "things": things_rows,
        "cols": list(COLS),
        "items": rows,
    }
    return _fit_payload(payload)


def _encoded_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _zero_column(items: list[list[Any]], col: str) -> int:
    idx = COLS.index(col)
    changed = 0
    for row in items:
        if row[idx] != 0:
            row[idx] = 0
            changed += 1
    return changed


def _fit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep JSON <= MAX_BYTES. Prefer shortening said; then drop bulky ints.

    SHA-256 item ids alone are ~1.9 MB on this library, so after said is gone
    the escape hatch zeros tv / dur / w / h (still present as 0; the full
    record from GET /api/items/<id> keeps the real values). Never zero z —
    size sort needs sizeBytes. If still over after that, stop and report.
    """
    global _said_trim_notes
    _said_trim_notes = []
    body_len = _encoded_size(payload)
    if body_len <= MAX_BYTES:
        return payload
    items = payload["items"]
    said_i = COLS.index("said")
    over = body_len - MAX_BYTES
    for cap in (400, 200, 80, 40, 0):
        changed = False
        for row in items:
            text = row[said_i]
            if type(text) is not str or len(text) <= cap:
                continue
            row[said_i] = text[:cap].rstrip()
            changed = True
        if not changed and cap > 0:
            continue
        body_len = _encoded_size(payload)
        if body_len <= MAX_BYTES:
            _said_trim_notes.append(
                f"truncated said to {cap} chars; overage was ~{over} bytes"
            )
            return payload
    _said_trim_notes.append(f"cleared said; still need ~{body_len - MAX_BYTES} bytes")
    # Drop thumbnail versions next — mtime_ns ints are ~19 digits each.
    # Never zero z (sizeBytes): size sort needs it.
    for col, label in (
        ("tv", "tv (thumb mtime_ns)"),
        ("dur", "dur"),
        ("w", "w"),
        ("h", "h"),
    ):
        n = _zero_column(items, col)
        if n:
            _said_trim_notes.append(f"zeroed {label} on {n} rows")
        body_len = _encoded_size(payload)
        if body_len <= MAX_BYTES:
            _said_trim_notes.append(f"fit at {body_len} bytes after zeroing {label}")
            return payload
    _said_trim_notes.append(
        f"still {body_len} bytes after tv/dur/w/h zeroed; refusing to drop z/ids/names"
    )
    return payload


def encode_index(root: Path) -> tuple[bytes, str]:
    """Return cached (body, version). Rebuilds only when generation changes."""
    key = root_key(root)
    gen = generation(root)
    with _guard:
        hit = _cache.get(key)
        if hit is not None and hit[0] == gen:
            return hit[1], hit[2]
    payload = build_payload(root)
    # Generation may have moved during build; stamp with the build's v.
    v = str(payload["v"])
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # Re-read generation after build so a concurrent write does not pin a stale body.
    gen_after = generation(root)
    if gen_after != gen:
        # Rare race: store under the newer token only if payload still matches needs.
        v = _version_token(gen_after)
        payload["v"] = v
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        gen = gen_after
    with _guard:
        _cache[key] = (gen, body, v)
    return body, v


def warm(root: Path) -> tuple[bytes, str]:
    """Build and cache the index. Read-only aside from the memory cache."""
    return encode_index(root)
