"""Computed Live/burst stacks. Read-only; originals and item JSON stay put."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


BURST_GAP_SEC = 2.5
LIVE_MOTION_MAX_SEC = 6.0
STEM_RE = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)(?P<ext>\.[^.]+)$", re.IGNORECASE)


def _parse_captured(value: Any) -> float | None:
    if type(value) is not str or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _parent_key(item: dict[str, Any]) -> tuple[str, str]:
    locs = [loc for loc in (item.get("locations") or []) if loc.get("current") is True]
    if not locs:
        locs = list(item.get("locations") or [])
    loc = locs[0] if locs else {}
    source = loc.get("sourceId") if type(loc.get("sourceId")) is str else ""
    path = (
        loc.get("libraryRelativePath")
        or loc.get("pathFromVolumeRoot")
        or loc.get("lastKnownPath")
        or item.get("filename")
        or ""
    )
    parent = str(Path(str(path)).parent).replace("\\", "/").casefold()
    return source, parent


def _filename(item: dict[str, Any]) -> str:
    name = item.get("filename")
    return name if type(name) is str else ""


def _bare_stem(filename: str) -> str:
    return Path(filename).stem.casefold()


def _stem_parts(filename: str) -> tuple[str, int] | None:
    match = STEM_RE.match(filename)
    if match is None:
        return None
    return match.group("prefix").casefold(), int(match.group("num"))


def _duration(item: dict[str, Any]) -> float | None:
    meta = item.get("metadata") or {}
    value = meta.get("durationSec")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _stack_payload(
    kind: str,
    item_ids: list[str],
    index: int,
) -> dict[str, Any]:
    return {
        "id": kind + ":" + item_ids[0],
        "kind": kind,
        "itemIds": list(item_ids),
        "count": len(item_ids),
        "index": index,
        "representative": index == 0,
    }


def _apply_stack(by_id: dict[str, dict[str, Any]], kind: str, item_ids: list[str]) -> None:
    if len(item_ids) < 1:
        return
    best = 0
    for index, item_id in enumerate(item_ids):
        item = by_id.get(item_id)
        if item is None:
            continue
        quality = item.get("quality") if isinstance(item.get("quality"), dict) else {}
        if quality.get("bestOfGroup") is True:
            best = index
            break
    for index, item_id in enumerate(item_ids):
        item = by_id.get(item_id)
        if item is None or item.get("stack"):
            continue
        payload = _stack_payload(kind, item_ids, index)
        payload["representative"] = index == best
        item["stack"] = payload


def _short_video(item: dict[str, Any]) -> bool:
    if item.get("kind") != "video":
        return False
    duration = _duration(item)
    return duration is None or duration <= LIVE_MOTION_MAX_SEC


def annotate_stacks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a computed `stack` on items that belong to a Live pair or burst.

    Does not rewrite catalog JSON or original bytes. A live catalog item is
    one tile. Unpaired still+short-video with the same stem group as Live
    without merging records. Sequential stills close in time group as burst.
    """
    by_id = {item.get("id"): item for item in items if type(item.get("id")) is str}
    claimed: set[str] = set()

    for item in items:
        if item.get("kind") != "live":
            continue
        item_id = item.get("id")
        if type(item_id) is not str:
            continue
        item["stack"] = _stack_payload("live", [item_id], 0)
        claimed.add(item_id)

    stem_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in items:
        item_id = item.get("id")
        if type(item_id) is not str or item_id in claimed:
            continue
        name = _filename(item)
        if not name:
            continue
        key = _parent_key(item) + (_bare_stem(name),)
        stem_groups.setdefault(key, []).append(item)
    for group in stem_groups.values():
        stills = [item for item in group if item.get("kind") == "photo"]
        motions = [item for item in group if _short_video(item)]
        if len(stills) != 1 or len(motions) != 1:
            continue
        still = stills[0]
        motion = motions[0]
        ids = [still["id"], motion["id"]]
        _apply_stack(by_id, "live", ids)
        claimed.update(ids)

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        item_id = item.get("id")
        if type(item_id) is not str or item_id in claimed:
            continue
        if item.get("kind") != "photo":
            continue
        buckets.setdefault(_parent_key(item), []).append(item)

    for bucket in buckets.values():
        bucket.sort(
            key=lambda rec: (
                rec.get("capturedAt") or "",
                _filename(rec),
                rec.get("id") or "",
            )
        )
        run: list[dict[str, Any]] = []

        def flush() -> None:
            nonlocal run
            if len(run) >= 2:
                ids = [rec["id"] for rec in run]
                _apply_stack(by_id, "burst", ids)
                claimed.update(ids)
            run = []

        for item in bucket:
            parts = _stem_parts(_filename(item))
            if parts is None:
                flush()
                continue
            if not run:
                run = [item]
                continue
            prev = run[-1]
            prev_parts = _stem_parts(_filename(prev))
            if prev_parts is None:
                flush()
                run = [item]
                continue
            prefix, num = parts
            prev_prefix, prev_num = prev_parts
            prev_ts = _parse_captured(prev.get("capturedAt"))
            ts = _parse_captured(item.get("capturedAt"))
            close = prev_ts is not None and ts is not None and abs(ts - prev_ts) <= BURST_GAP_SEC
            sequential = prefix == prev_prefix and 0 <= num - prev_num <= 1
            if close and sequential:
                run.append(item)
            else:
                flush()
                run = [item]
        flush()
    return items
