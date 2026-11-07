"""Size sort and the hasPeople filter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.atomic import transact
from library.catalog_io import ensure_catalog_dirs, item_rel, person_rel
from library.errors import AppError
from library.records import make_item, make_location, ordered_person, renditions_for
from library.service import Library, _validate_item_query
from library.settings import defaults, merge_patch


SRC = "src_0123456789ab"
PERSON = "person_unnamed_size"


def _item(
    item_id: str,
    name: str,
    *,
    size: int,
    kind: str = "photo",
    faces: list[dict] | None = None,
    captured: str = "2026-01-01T00:00:00Z",
) -> dict:
    component = "motion" if kind == "video" else "still"
    loc = make_location(
        source_id=SRC,
        role="primary",
        component=component,
        volume_serial="windows:00000000",
        path_from_volume_root=name,
        last_known_path=name,
        size_bytes=size,
        modified_at="2026-01-01T00:00:00Z",
        sha256=None,
    )
    return make_item(
        item_id=item_id,
        kind=kind,
        filename=name,
        captured_at=captured,
        captured_at_source="mtime",
        content_identifier=None,
        locations=[loc],
        renditions=renditions_for(kind, SRC, store="with-server"),
        faces=faces,
    )


class SizeSortAndPeopleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "library-data"
        self.root.mkdir()
        ensure_catalog_dirs(self.root)
        self.lib = Library(self.root)
        self.lib.ensure_settings()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _put(self, *items: dict, people: list[dict] | None = None) -> None:
        changes = [{"path": item_rel(item["id"]), "before": None, "after": item} for item in items]
        for person in people or []:
            changes.append({"path": person_rel(person["id"]), "before": None, "after": person})
        transact(self.root, changes)

    def test_size_sort_largest_first(self) -> None:
        small = _item("a" * 64, "small.jpg", size=10, captured="2026-01-03T00:00:00Z")
        big = _item("b" * 64, "big.jpg", size=5000, captured="2026-01-01T00:00:00Z")
        mid = _item("c" * 64, "mid.jpg", size=100, captured="2026-01-02T00:00:00Z")
        self._put(small, big, mid)
        ids = [item["id"] for item in self.lib.items_list({"sort": "size", "dir": "desc"})]
        self.assertEqual(ids, ["b" * 64, "c" * 64, "a" * 64])

    def test_size_sort_accepted_by_settings_and_query(self) -> None:
        _validate_item_query({"sort": "size", "dir": "desc"})
        after = self.lib.settings_set({"sort": "size", "dir": "desc"})
        self.assertEqual(after["sort"], "size")
        self.assertEqual(after["dir"], "desc")
        merged = merge_patch(defaults(), {"sort": "size"})
        self.assertEqual(merged["sort"], "size")
        with self.assertRaises(AppError) as raised:
            _validate_item_query({"sort": "bytes"})
        self.assertEqual(raised.exception.code, "invalid-argument")

    def test_has_people_keeps_linked_unnamed_and_drops_empty(self) -> None:
        person = ordered_person({"schemaVersion": 1, "id": PERSON, "name": None})
        with_face = _item(
            "d" * 64,
            "with.jpg",
            size=10,
            faces=[{"personId": PERSON}],
        )
        bare = _item("e" * 64, "bare.jpg", size=20)
        self._put(with_face, bare, people=[person])
        ids = [item["id"] for item in self.lib.items_list({"hasPeople": "1"})]
        self.assertEqual(ids, ["d" * 64])

    def test_has_people_with_kind_video(self) -> None:
        person = ordered_person({"schemaVersion": 1, "id": PERSON, "name": None})
        photo = _item(
            "f" * 64,
            "face.jpg",
            size=10,
            faces=[{"personId": PERSON}],
        )
        video = _item(
            "1" * 64,
            "face.mp4",
            size=50,
            kind="video",
            faces=[{"personId": PERSON}],
        )
        lone_video = _item("2" * 64, "alone.mp4", size=60, kind="video")
        self._put(photo, video, lone_video, people=[person])
        ids = [item["id"] for item in self.lib.items_list({"hasPeople": "1", "kind": "video"})]
        self.assertEqual(ids, ["1" * 64])


if __name__ == "__main__":
    unittest.main()
