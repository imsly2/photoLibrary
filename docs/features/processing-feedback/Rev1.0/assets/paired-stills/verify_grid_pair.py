"""Focused grid-only drain check for paired photo publication."""
from __future__ import annotations

import json
from pathlib import Path

from library import renditions
from library.catalog_io import iter_item_ids, load_item
from library.media import sha256_file
from tests.qa.processing_feedback import fixture_library, scan


def main() -> None:
    folder = Path(__file__).resolve().parent / "qa-grid-only"
    if folder.exists():
        raise RuntimeError(f"artifact directory already exists: {folder}")
    library, media = fixture_library(folder)
    scan(library, media)
    photo = next(
        load_item(library.root, item_id)
        for item_id in iter_item_ids(library.root)
        if load_item(library.root, item_id)["kind"] == "photo"
    )
    source = renditions._primary_still_path(photo, library.root)
    if source is None:
        raise RuntimeError("fixture photo source missing")
    before_hash = sha256_file(source)
    status = photo["renditions"]["status"]
    if status.get("thumb") != "queued" or status.get("preview") != "queued":
        raise RuntimeError(f"both photo outputs must be queued: {status}")
    renditions.reset_profile_counters()
    library._scanning = True
    try:
        if not library.drain_step():
            raise RuntimeError("grid-only rendition step did no work")
    finally:
        library._scanning = False
    after = load_item(library.root, photo["id"])
    final_status = after["renditions"]["status"]
    if final_status.get("thumb") != "ready" or final_status.get("preview") != "ready":
        raise RuntimeError(f"paired outputs not ready: {final_status}")
    if renditions.profile_counters["encode_calls"] != 1:
        raise RuntimeError(f"expected one paired encode: {renditions.profile_counters}")
    if sha256_file(source) != before_hash:
        raise RuntimeError("source original bytes changed")
    result = {
        "gridOnlyPair": True,
        "itemId": photo["id"],
        "encodeCalls": renditions.profile_counters["encode_calls"],
        "status": final_status,
        "sourceSha256Unchanged": True,
    }
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
