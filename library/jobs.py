"""Background queue status and pause/resume for the serve-process drain."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.catalog_io import iter_item_ids, load_item
from library.errors import fail

QUEUE_ORDER = ("renditions", "analyze", "infer-faces", "objects", "transcribe", "rate")
QUEUE_LABELS = {
    "renditions": "Previews",
    "analyze": "Analyze",
    "infer-faces": "Faces",
    "objects": "Objects",
    "transcribe": "Transcribe",
    "rate": "Rating",
}


def _module_available(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


def _rendition_counts(root: Path) -> tuple[int, int, int]:
    pending = 0
    done = 0
    error = 0
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        status = ((item.get("renditions") or {}).get("status") or {})
        if not isinstance(status, dict):
            continue
        for state in status.values():
            if state == "queued":
                pending += 1
            elif state == "ready":
                done += 1
            elif state == "error":
                error += 1
    return pending, done, error


def _photo_like(item: dict[str, Any]) -> bool:
    return item.get("kind") in {"photo", "live"}


def _faces_counts(root: Path) -> tuple[int, int, int]:
    scanned: set[str] = set()
    force = False
    try:
        from library.faces import faces_force_rescan, scanned_item_ids

        scanned = scanned_item_ids(root)
        force = faces_force_rescan(root)
    except Exception:
        scanned = set()
    pending = 0
    done = 0
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        if not _photo_like(item):
            continue
        faces = item.get("faces") or []
        if force:
            if item_id in scanned:
                done += 1
            else:
                pending += 1
        elif faces or item_id in scanned:
            done += 1
        else:
            pending += 1
    return pending, done, 0


def _objects_counts(root: Path) -> tuple[int, int, int]:
    try:
        from library.objects import analyze_status, model_installed

        if model_installed(root):
            status = analyze_status(root)
            pending = int(status.get("pending") or 0)
            photo_like = 0
            for item_id in iter_item_ids(root):
                item = load_item(root, item_id)
                if _photo_like(item):
                    photo_like += 1
            done = max(0, photo_like - pending)
            return pending, done, 0
    except Exception:
        pass
    pending = 0
    done = 0
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        if not _photo_like(item):
            continue
        things = item.get("things") or []
        if things:
            done += 1
        else:
            pending += 1
    return pending, done, 0


def _analyze_counts(root: Path) -> tuple[int, int, int]:
    try:
        from library.places import unnamed_gps_counts

        return unnamed_gps_counts(root)
    except Exception:
        return 0, 0, 0


def _transcribe_counts(root: Path) -> tuple[int, int, int]:
    try:
        from library.transcribe import transcribe_counts

        return transcribe_counts(root)
    except Exception:
        return 0, 0, 0


def _rate_counts(root: Path) -> tuple[int, int, int]:
    try:
        from library.rating import rate_counts

        return rate_counts(root)
    except Exception:
        return 0, 0, 0


def _queue_available(root: Path, queue_id: str) -> bool:
    if queue_id == "renditions":
        return True
    if queue_id == "infer-faces":
        if not _module_available("library.faces"):
            return False
        try:
            from library.faces import faces_status

            return bool(faces_status(root).get("ready"))
        except Exception:
            return False
    if queue_id == "objects":
        if not _module_available("library.objects"):
            return False
        try:
            from library.objects import model_installed

            return bool(model_installed(root))
        except Exception:
            return False
    if queue_id == "analyze":
        if not _module_available("library.geo"):
            return False
        try:
            from library.geo import pack_ready

            return bool(pack_ready(root))
        except Exception:
            return False
    if queue_id == "transcribe":
        if not _module_available("library.transcribe"):
            return False
        try:
            from library.transcribe import model_installed, transcribe_enabled

            return bool(model_installed(root) and transcribe_enabled(root))
        except Exception:
            return False
    if queue_id == "rate":
        if not _module_available("library.rating"):
            return False
        try:
            from library.rating import rating_enabled

            return bool(rating_enabled(root))
        except Exception:
            return False
    return False


def _queue_counts(root: Path, queue_id: str) -> tuple[int, int, int]:
    if queue_id == "renditions":
        return _rendition_counts(root)
    if queue_id == "infer-faces":
        return _faces_counts(root)
    if queue_id == "objects":
        return _objects_counts(root)
    if queue_id == "transcribe":
        return _transcribe_counts(root)
    if queue_id == "rate":
        return _rate_counts(root)
    return _analyze_counts(root)


def _queue_state(pending: int, paused: bool, *, live: bool) -> str:
    if pending <= 0:
        return "idle"
    if paused:
        return "paused"
    if live:
        return "running"
    return "idle"


def jobs_status(root: Path, paused: bool) -> dict[str, Any]:
    queues: list[dict[str, Any]] = []
    processing = False
    for queue_id in QUEUE_ORDER:
        pending, done, error = _queue_counts(root, queue_id)
        available = _queue_available(root, queue_id)
        live = available and not paused
        state = "unavailable" if pending > 0 and not available else _queue_state(pending, paused, live=live)
        if state == "running":
            processing = True
        queues.append(
            {
                "id": queue_id,
                "label": QUEUE_LABELS[queue_id],
                "pending": pending,
                "done": done,
                "error": error,
                "state": state,
                "available": available,
            }
        )
    return {
        "ok": True,
        "paused": bool(paused),
        "processing": processing,
        "queues": queues,
    }


def read_jobs_action(body: Any) -> str:
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise fail("invalid-argument")
    extra = set(body) - {"action"}
    if extra:
        raise fail("invalid-argument")
    action = body.get("action")
    if action not in {"pause", "resume", "rerun-faces"}:
        raise fail("invalid-argument")
    return action
