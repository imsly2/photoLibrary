"""One-shot census of people clusters and rating scores. Read-only."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from library.faces import cosine, load_index
from library.item_index import iter_items
from library.people_panel import PERSON_OF_INTEREST_MIN, people_index
from library.people_suggest import SUGGEST_MIN_SCORE, people_suggestions

ROOT = Path(r"J:\slyOS\projects\photoLibrary\library-data")
TARGETS = {"IMG_3582.JPG", "IMG_9081.JPG"}


def bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count < 10:
        return "3-9"
    if count < 50:
        return "10-49"
    return "50+"


def main() -> None:
    index = people_index(ROOT)
    rows = index["people"]
    visible = [row for row in rows if row.get("visible")]
    hidden = [row for row in rows if not row.get("visible")]
    face_index = load_index(ROOT) or {}
    centroids = {
        pid: list((rec or {}).get("centroid") or [])
        for pid, rec in (face_index.get("people") or {}).items()
        if isinstance(rec, dict)
    }
    by_id = {row["id"]: row for row in rows}

    suggestions = people_suggestions(ROOT)["suggestions"]
    score_bins = Counter()
    for pair in suggestions:
        score = float(pair["score"])
        if score >= 0.80:
            score_bins["0.80+"] += 1
        elif score >= 0.70:
            score_bins["0.70-0.79"] += 1
        elif score >= 0.60:
            score_bins["0.60-0.69"] += 1
        else:
            score_bins["0.55-0.59"] += 1

    visible_ids = [row["id"] for row in visible if not row.get("named")]
    pairs = []
    for i, left in enumerate(visible_ids):
        for right in visible_ids[i + 1 :]:
            a = centroids.get(left) or []
            b = centroids.get(right) or []
            if len(a) < 2 or len(b) < 2:
                continue
            pairs.append(
                {
                    "aCount": by_id[left]["itemCount"],
                    "bCount": by_id[right]["itemCount"],
                    "score": round(cosine(a, b), 4),
                }
            )
    pairs.sort(key=lambda row: -row["score"])

    photos = []
    stars = Counter()
    basic_bins = Counter()
    basics: list[float] = []
    sharp: list[float] = []
    exposure: list[float] = []
    scored = 0
    for item in iter_items(ROOT):
        name = ""
        for loc in item.get("locations") or []:
            path = str(loc.get("path") or loc.get("lastKnownPath") or "")
            if path:
                name = Path(path).name
                break
        if not name:
            name = str(item.get("filename") or "")
        if name.upper() in TARGETS or name.upper().endswith("IMG_3582.JPG") or name.upper().endswith("IMG_9081.JPG"):
            faces = []
            for face in item.get("faces") or []:
                pid = face.get("personId")
                row = by_id.get(pid) or {}
                box = face.get("box") or [0, 0, 0, 0]
                faces.append(
                    {
                        "personId": pid,
                        "x": round(float(box[0]), 3) if box else None,
                        "detScore": face.get("detScore"),
                        "matchScore": face.get("matchScore"),
                        "itemCount": row.get("itemCount"),
                        "visible": row.get("visible"),
                        "named": row.get("named"),
                    }
                )
            faces.sort(key=lambda face: face["x"] or 0)
            photos.append({"file": name, "id": item.get("id"), "faces": faces})

        quality = item.get("quality") if isinstance(item.get("quality"), dict) else None
        if not quality or quality.get("status") != "ready":
            continue
        scored += 1
        suggested = quality.get("suggested")
        if type(suggested) is int:
            stars[str(suggested)] += 1
        metrics = quality.get("metrics") if isinstance(quality.get("metrics"), dict) else {}
        basic = metrics.get("basic")
        if isinstance(basic, (int, float)) and not isinstance(basic, bool):
            basics.append(float(basic))
            if basic >= 0.9:
                basic_bins["0.90+"] += 1
            elif basic >= 0.8:
                basic_bins["0.80-0.89"] += 1
            elif basic >= 0.7:
                basic_bins["0.70-0.79"] += 1
            elif basic >= 0.5:
                basic_bins["0.50-0.69"] += 1
            else:
                basic_bins["under 0.50"] += 1
        if isinstance(metrics.get("sharpness"), (int, float)):
            sharp.append(float(metrics["sharpness"]))
        if isinstance(metrics.get("exposure"), (int, float)):
            exposure.append(float(metrics["exposure"]))

    def spread(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        ordered = sorted(values)
        def pick(q: float) -> float:
            idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
            return round(ordered[idx], 4)
        return {"min": pick(0), "p10": pick(0.10), "p50": pick(0.50), "p90": pick(0.90), "max": pick(1)}

    hidden_counts = Counter(bucket(int(row["itemCount"])) for row in hidden)
    visible_counts = [
        {"itemCount": row["itemCount"], "named": row["named"], "id": row["id"]}
        for row in visible
    ]
    report = {
        "personOfInterestMin": PERSON_OF_INTEREST_MIN,
        "suggestMinScore": SUGGEST_MIN_SCORE,
        "clusterThreshold": face_index.get("matchThreshold"),
        "peopleTotal": len(rows),
        "visible": len(visible),
        "hidden": len(hidden),
        "hiddenByCount": dict(hidden_counts),
        "visibleRows": visible_counts,
        "suggestionCount": len(suggestions),
        "suggestionScoreBins": dict(score_bins),
        "suggestionTop": [
            {
                "score": pair["score"],
                "keepCount": (pair.get("keep") or {}).get("itemCount"),
                "dropCount": (pair.get("drop") or {}).get("itemCount"),
            }
            for pair in suggestions[:8]
        ],
        "suggestionLow": [
            {
                "score": pair["score"],
                "keepCount": (pair.get("keep") or {}).get("itemCount"),
                "dropCount": (pair.get("drop") or {}).get("itemCount"),
            }
            for pair in suggestions[-5:]
        ],
        "visibleUnnamedPairs": pairs,
        "photos": photos,
        "rated": scored,
        "stars": dict(stars),
        "basicBins": dict(basic_bins),
        "basic": spread(basics),
        "sharpness": spread(sharp),
        "exposure": spread(exposure),
    }
    out = Path(__file__).with_name("result.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
