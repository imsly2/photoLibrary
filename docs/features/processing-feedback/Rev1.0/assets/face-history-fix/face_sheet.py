"""Contact sheet of the people this re-run actually wrote.

Rows are the library's clusters (same person id), largest first. Crops come
from the stored box on the upright original. Embeddings are checked, not
re-clustered. Layout follows face-threshold-sweep/face_cluster.py.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(r"J:\slyOS\projects\photoLibrary")
sys.path.insert(0, str(ROOT))

from library.media import decode_still_rgb  # noqa: E402
from library.records import unpack_embedding  # noqa: E402

PICTURES = Path(r"J:\Pictures\1. Favorites Pictures")
LIBRARY = PICTURES / ".library"
OUT = Path(__file__).resolve().parent / "live-rerun"
PER_ROW = 14
CELL = 72
ROWS = 12


def square_box(box: list[float]) -> tuple[float, float, float, float]:
    x, y, w, h = (float(v) for v in box)
    side = max(w, h) * 1.25
    cx, cy = x + w / 2, y + h / 2
    left, top = cx - side / 2, cy - side / 2
    return left, top, side, side


def crop_rgb(rgb: bytes, width: int, height: int, box: list[float]) -> Image.Image:
    left, top, side, _ = square_box(box)
    x0 = max(0, min(width - 1, int(left * width)))
    y0 = max(0, min(height - 1, int(top * height)))
    x1 = max(x0 + 1, min(width, int((left + side) * width)))
    y1 = max(y0 + 1, min(height, int((top + side) * height)))
    image = Image.frombytes("RGB", (width, height), rgb)
    return image.crop((x0, y0, x1, y1)).resize((CELL - 4, CELL - 4), Image.Resampling.BILINEAR)


def main() -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    embedding_ok = 0
    embedding_bad = 0
    faces = 0
    for path in LIBRARY.glob("*.json"):
        if path.name in {"source.json", "favorites.json"} or path.parent.name != ".library":
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        filename = item.get("filename") or path.name[: -len(".json")]
        photo = PICTURES / filename
        for face in item.get("faces") or []:
            if not isinstance(face, dict) or not face.get("box"):
                continue
            faces += 1
            values = unpack_embedding(face.get("embedding"))
            if values is not None and len(values) == 512:
                embedding_ok += 1
            else:
                embedding_bad += 1
            person = face.get("personId") or "none"
            groups[person].append({"file": filename, "photo": photo, "box": face["box"]})

    ranked = sorted(groups.items(), key=lambda pair: -len(pair[1]))
    shown = [(person, members) for person, members in ranked if len(members) >= 2][:ROWS]
    needed: dict[Path, list[tuple[int, int, list[float]]]] = defaultdict(list)
    for row, (_person, members) in enumerate(shown):
        for col, member in enumerate(members[:PER_ROW]):
            needed[member["photo"]].append((row, col, member["box"]))

    chips: dict[tuple[int, int], Image.Image] = {}
    for photo, jobs in needed.items():
        if not photo.is_file():
            continue
        width, height, rgb = decode_still_rgb(photo)
        for row, col, box in jobs:
            chips[(row, col)] = crop_rgb(rgb, width, height, box)

    width_px = 60 + PER_ROW * CELL
    height_px = len(shown) * CELL + 30
    sheet = Image.new("RGB", (width_px, max(height_px, 40)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (6, 8),
        "threshold 0.45 - each row is one person (%d faces shown max)" % PER_ROW,
        fill=(230, 230, 230),
    )
    for row, (person, members) in enumerate(shown):
        y = 30 + row * CELL
        draw.text((6, y + 28), str(len(members)), fill=(255, 200, 80))
        for col in range(min(PER_ROW, len(members))):
            chip = chips.get((row, col))
            if chip is not None:
                sheet.paste(chip, (60 + col * CELL, y + 2))
    OUT.mkdir(parents=True, exist_ok=True)
    sheet_path = OUT / "sheet-045.png"
    sheet.save(sheet_path)
    summary = {
        "faces": faces,
        "embedding512": embedding_ok,
        "embeddingMissing": embedding_bad,
        "people": len(groups),
        "singleFacePeople": sum(1 for members in groups.values() if len(members) == 1),
        "top": [{"id": person, "faces": len(members)} for person, members in ranked[:12]],
        "sheet": str(sheet_path),
    }
    (OUT / "sheet.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
