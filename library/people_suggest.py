"""Likely same-person pairs from face centroids. Never merges by itself."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json, load_json
from library.errors import fail
from library.faces import cosine, index_path, load_index
from library.paths import library_path
from library.people_panel import people_index


SUGGEST_MIN_SCORE = 0.55
NOT_SAME_REL = "catalog/people-not-same.json"
MAX_SUGGESTIONS = 50

_guard = threading.Lock()
_cache: dict[str, tuple[Any, dict[str, Any]]] = {}


def not_same_path(root: Path) -> Path:
    return library_path(root, NOT_SAME_REL)


def invalidate_suggestions(root: Path) -> None:
    from library.item_index import root_key

    with _guard:
        _cache.pop(root_key(root), None)


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
    invalidate_suggestions(root)
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
    left_name = (left.get("name") or "").casefold()
    right_name = (right.get("name") or "").casefold()
    if left_name != right_name:
        return (left, right) if left_name < right_name else (right, left)
    if left["id"] <= right["id"]:
        return left, right
    return right, left


def _file_sig(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
        return (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        return (0, 0)


def _cache_key(root: Path) -> tuple[Any, ...]:
    from library.people_panel import people_generation

    return (
        _file_sig(index_path(root)),
        _file_sig(not_same_path(root)),
        people_generation(root),
    )


def people_suggestions(root: Path) -> dict[str, Any]:
    from library.item_index import root_key

    key = root_key(root)
    cache_token = _cache_key(root)
    with _guard:
        hit = _cache.get(key)
        if hit is not None and hit[0] == cache_token:
            return hit[1]

    payload = _compute_suggestions(root)
    with _guard:
        _cache[key] = (cache_token, payload)
    return payload


def _compute_suggestions(root: Path) -> dict[str, Any]:
    index = load_index(root)
    rows = people_index(root)["people"]
    by_id = {row["id"]: row for row in rows}
    if index is None:
        return {"suggestions": []}
    people = index.get("people") or {}
    if not isinstance(people, dict):
        return {"suggestions": []}
    blocked = load_not_same_pairs(root)
    ids = [person_id for person_id in people if person_id in by_id]
    ids.sort()
    vectors: list[list[float]] = []
    kept_ids: list[str] = []
    for person_id in ids:
        vec = _centroid(people.get(person_id))
        if vec is None:
            continue
        kept_ids.append(person_id)
        vectors.append(vec)
    if len(kept_ids) < 2:
        return {"suggestions": []}

    scored = _score_pairs_numpy(kept_ids, vectors, by_id, blocked)
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


def _score_pairs_numpy(
    ids: list[str],
    vectors: list[list[float]],
    by_id: dict[str, dict[str, Any]],
    blocked: set[tuple[str, str]],
) -> list[tuple[float, dict[str, Any], dict[str, Any]]]:
    """Pair scores via unnormalized dot product (same as library.faces.cosine)."""
    import numpy as np

    lengths = {len(vec) for vec in vectors}
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    if len(lengths) == 1:
        matrix = np.asarray(vectors, dtype=np.float64)
        # Centroids on this library are unit length; still use raw dots so the
        # score matches faces.cosine exactly (no renormalize).
        sims = matrix @ matrix.T
        n = len(ids)
        ii, jj = np.triu_indices(n, k=1)
        pair_scores = sims[ii, jj]
        mask = pair_scores > SUGGEST_MIN_SCORE
        ii = ii[mask]
        jj = jj[mask]
        pair_scores = pair_scores[mask]
        for i, j, score in zip(ii.tolist(), jj.tolist(), pair_scores.tolist(), strict=True):
            left_id = ids[i]
            right_id = ids[j]
            key = _pair_key(left_id, right_id)
            if (key[0], key[1]) in blocked:
                continue
            keep, drop = _keep_drop(by_id[left_id], by_id[right_id])
            scored.append((float(score), keep, drop))
        return scored

    # Mixed lengths: fall back to the same pairwise cosine (rare).
    for i, left_id in enumerate(ids):
        left_vec = vectors[i]
        for j in range(i + 1, len(ids)):
            right_id = ids[j]
            key = _pair_key(left_id, right_id)
            if (key[0], key[1]) in blocked:
                continue
            score = cosine(left_vec, vectors[j])
            if score <= SUGGEST_MIN_SCORE:
                continue
            keep, drop = _keep_drop(by_id[left_id], by_id[right_id])
            scored.append((score, keep, drop))
    return scored
