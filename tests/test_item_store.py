"""F23 slice 3a: an item's record file lives beside its previews in the folder library."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from library import item_index, item_store
from library.atomic import transact
from library.catalog_io import ensure_catalog_dirs, item_rel, iter_item_ids, load_item, source_rel, try_load_item
from library.paths import library_path
from library.records import make_item, make_location, make_source, renditions_for

SRC = "src_0123456789ab"
A = "a" * 64
B = "b" * 64


class ItemStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.root = (self.tmp / "library-data").resolve()
        self.root.mkdir()
        ensure_catalog_dirs(self.root)
        item_store.invalidate(self.root)
        source = make_source(
            source_id=SRC, name="Favorites", mode="serve-from-there", preview_store="with-server",
            origin={"volumeSerial": "windows:00000000", "pathFromVolumeRoot": "Pictures/Favorites",
                    "lastKnownPath": str(self.tmp / "Pictures" / "Favorites")},
        )
        transact(self.root, [{"path": source_rel(SRC), "before": None, "after": source}])
        self.lib = self.root / "folders" / f"Favorites-{SRC}"

    def tearDown(self) -> None:
        item_store.invalidate(self.root)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _item(self, item_id: str, name: str, store: str = "folder-server") -> dict:
        loc = make_location(
            source_id=SRC, role="primary", component="still", volume_serial="windows:00000000",
            path_from_volume_root=f"Pictures/Favorites/{name}", last_known_path=name,
            size_bytes=1, modified_at="2026-01-01T00:00:00Z", sha256=None,
        )
        return make_item(
            item_id=item_id, kind="photo", filename=name.rsplit("/", 1)[-1],
            captured_at="2026-01-01T00:00:00Z", captured_at_source="mtime",
            content_identifier=None, locations=[loc],
            renditions=renditions_for("photo", SRC, store=store),
        )

    def _put(self, item: dict, before: dict | None = None) -> None:
        transact(self.root, [{"path": item_rel(item["id"]), "before": before, "after": item}])

    def _legacy(self, item_id: str) -> Path:
        return self.root / "catalog" / "items" / f"{item_id}.json"

    def test_folder_item_record_is_named_after_the_picture(self) -> None:
        item = self._item(A, "2023/IMG_1.JPG")
        self._put(item)
        record = self.lib / "2023" / "IMG_1.JPG.json"
        self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["id"], A)
        self.assertFalse(self._legacy(A).exists())
        self.assertEqual(load_item(self.root, A)["filename"], "IMG_1.JPG")
        self.assertEqual(iter_item_ids(self.root), [A])
        self.assertEqual(library_path(self.root, item_rel(A)), record)

    def test_old_layout_and_pending_items_stay_in_library_data(self) -> None:
        self._put(self._item(A, "IMG_1.JPG", store="with-server"))
        pending = f"pending-{SRC}-" + "c" * 64
        self._put(self._item(pending, "IMG_2.JPG"))
        self.assertTrue(self._legacy(A).is_file())
        self.assertTrue(self._legacy(pending).is_file())
        self.assertEqual(list(self.lib.glob("*.json")) if self.lib.exists() else [], [])

    def test_moving_to_the_new_layout_removes_the_library_data_copy(self) -> None:
        old = self._item(A, "IMG_1.JPG", store="with-server")
        self._put(old)
        self._put(self._item(A, "IMG_1.JPG"), before=old)
        self.assertFalse(self._legacy(A).exists())
        self.assertTrue((self.lib / "IMG_1.JPG.json").is_file())

    def test_a_fresh_process_finds_records_by_reading_the_folder(self) -> None:
        self._put(self._item(A, "IMG_1.JPG"))
        item_store.invalidate(self.root)
        self.assertEqual(item_store.stored_path(self.root, A), self.lib / "IMG_1.JPG.json")
        self.assertEqual(try_load_item(self.root, A)["id"], A)

    def test_delete_and_undo_round_trip(self) -> None:
        item = self._item(A, "IMG_1.JPG")
        self._put(item)
        transact(self.root, [{"path": item_rel(A), "before": item, "after": None}])
        self.assertFalse((self.lib / "IMG_1.JPG.json").exists())
        self.assertIsNone(try_load_item(self.root, A))
        self._put(item)
        self.assertEqual(load_item(self.root, A)["id"], A)

    def test_a_different_item_taking_the_name_does_not_destroy_the_first(self) -> None:
        self._put(self._item(A, "IMG_1.JPG"))
        self._put(self._item(B, "IMG_1.JPG"))
        self.assertEqual(json.loads((self.lib / "IMG_1.JPG.json").read_text(encoding="utf-8"))["id"], B)
        self.assertEqual(load_item(self.root, A)["id"], A)
        self.assertEqual(iter_item_ids(self.root), [A, B])

    def test_deleting_the_folder_library_resets_that_folder(self) -> None:
        self._put(self._item(A, "IMG_1.JPG"))
        self.assertEqual(item_store.vanished_sources(self.root), set())
        shutil.rmtree(self.lib)
        self.assertEqual(item_store.vanished_sources(self.root), {SRC})
        self.assertIsNone(item_store.stored_path(self.root, A))
        self.assertEqual(iter_item_ids(self.root), [])
        self.assertEqual(item_store.vanished_sources(self.root), set(), "reported once")

    def test_item_cache_sees_folder_record_edits(self) -> None:
        item = self._item(A, "IMG_1.JPG")
        self._put(item)
        self.assertEqual([i["id"] for i in item_index.iter_items(self.root)], [A])
        edited = dict(item)
        edited["filename"] = "renamed.JPG"
        self._put(edited, before=item)
        self.assertEqual(item_index.iter_items(self.root)[0]["filename"], "renamed.JPG")


if __name__ == "__main__":
    unittest.main()
