"""Likely same-person pairs from face centroids. Never merges by itself."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json, load_json
from library.errors import fail
from library.faces import cosine, load_index
from library.paths import library_path
from library.people_panel import people_index


SUGGEST_MIN_SCORE = 0.55
NOT_SAME_REL = "catalog/people-not-same.json"
MAX_SUGGESTIONS = 50


def not_same_path(root: Path) -> Path:
    return library_path(root, NOT_SAME_REL)


def _pair_key(a: str, b: str) -> list[str]:
    return [a, b] if a < b else [b, a]


def load_not_same_pairs(root: Path) -> set[tuple[str, str]]:
    path = not_same_path(root)
    if not path.is_file():
        return set()
    try:
        data = load_json(path)
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    rows = data.get("pairs")
    if not isinstance(rows, list):
        return set()
    out: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            continue
        a, b = row[0], row[1]
        if type(a) is not str or type(b) is not str or not a or not b or a == b:
            continue
        key = _pair_key(a, b)
        out.add((key[0], key[1]))
    return out


def read_not_same_payload(value: Any) -> dict[str, str]:
    data = value if isinstance(value, dict) else None
    if data is None:
        raise fail("invalid-argument")
    extra = set(data) - {"a", "b"}
    if extra:
        raise fail("invalid-argument")
    a = data.get("a")
    b = data.get("b")
    if type(a) is not str or type(b) is not str or not a or not b or a == b:
        raise fail("invalid-argument")
    return {"a": a, "b": b}


def remember_not_same(root: Path, a: str, b: str) -> dict[str, Any]:
    payload = read_not_same_payload({"a": a, "b": b})
    from library.catalog_io import try_load_person

    if try_load_person(root, payload["a"]) is None or try_load_person(root, payload["b"]) is None:
        raise fail("not-found")
    pairs = load_not_same_pairs(root)
    key = _pair_key(payload["a"], payload["b"])
    pairs.add((key[0], key[1]))
    ordered = {"schemaVersion": 1, "pairs": [list(pair) for pair in sorted(pairs)]}
    atomic_write_json(not_same_path(root), ordered)
    return ordered


def _centroid(entry: Any) -> list[float] | None:
    if not isinstance(entry, dict):
        return None
    raw = entry.get("centroid")
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    out: list[float] = []
    for value in raw:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        out.append(float(value))
    return out


def _keep_drop(left: dict[str, Any], right: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if left.get("named") and not right.get("named"):
        return left, right
    if right.get("named") and not left.get("named"):
        return right, left
    left_count = int(left.get("itemCount") or 0)
    right_count = int(right.get("itemCount") or 0)
    if left_count != right_count:
        return (left, right) if left_count > right_count else (right, left)
    if left["id"] <= right["id"]:
        return left, right
    return right, left


def people_suggestions(root: Path) -> dict[str, Any]:
    index = load_index(root)
    rows = people_index(root)["people"]
    by_id = {row["id"]: row for row in rows}
    if index is None:
        return {"suggestions": []}
    people = index.get("people") or {}
    if not isinstance(people, dict):
        return {"suggestions": []}
    blocked = load_not_same_pairs(root)
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    ids = [person_id for person_id in people if person_id in by_id]
    ids.sort()
    for i, left_id in enumerate(ids):
        left_vec = _centroid(people.get(left_id))
        if left_vec is None:
            continue
        for right_id in ids[i + 1 :]:
            if (left_id, right_id) in blocked or (right_id, left_id) in blocked:
                continue
            key = _pair_key(left_id, right_id)
            if (key[0], key[1]) in blocked:
                continue
            right_vec = _centroid(people.get(right_id))
            if right_vec is None:
                continue
            score = cosine(left_vec, right_vec)
            if score <= SUGGEST_MIN_SCORE:
                continue
            keep, drop = _keep_drop(by_id[left_id], by_id[right_id])
            scored.append((score, keep, drop))
    scored.sort(key=lambda row: (-row[0], row[1]["id"], row[2]["id"]))
    suggestions = []
    for score, keep, drop in scored[:MAX_SUGGESTIONS]:
        suggestions.append(
            {
                "keepId": keep["id"],
                "dropId": drop["id"],
                "score": round(float(score), 4),
                "keep": keep,
                "drop": drop,
            }
        )
    return {"suggestions": suggestions}
