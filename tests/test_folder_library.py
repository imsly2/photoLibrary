"""F23 folder library: naming, where each source's library lives, source: paths."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import folder_library as fl
from library.atomic import recover_transactions, transact
from library.paths import library_path

SRC = "src_0123456789ab"


class Naming(unittest.TestCase):
    def test_table(self) -> None:
        self.assertEqual(fl.record_name("IMG_0456.JPG"), "IMG_0456.JPG.json")
        self.assertEqual(fl.derived_name("IMG_0456.JPG", "thumb"), "IMG_0456.JPG.thumb.webp")
        self.assertEqual(fl.derived_name("IMG_0456.JPG", "preview"), "IMG_0456.JPG.preview.webp")
        self.assertEqual(fl.derived_name("clip.MOV", "poster"), "clip.MOV.poster.webp")
        self.assertEqual(fl.derived_name("clip.MOV", "proxy"), "clip.MOV.proxy.mp4")
        self.assertEqual(fl.derived_name("clip.MOV", "playback"), "clip.MOV.playback.mp4")
        self.assertEqual(fl.derived_name("2023\\trip\\a b.jpg", "thumb"), "2023/trip/a b.jpg.thumb.webp")

    def test_same_stem_different_extension_do_not_clash(self) -> None:
        self.assertNotEqual(fl.derived_name("IMG_0001.JPG", "poster"), fl.derived_name("IMG_0001.MOV", "poster"))

    def test_parse_round_trip(self) -> None:
        for rel in ("IMG_0456.JPG", "2023/x.y.jpeg", "旅行 photo.jpg"):
            for slot in fl.SUFFIXES:
                self.assertEqual(fl.parse_name(fl.derived_name(rel, slot)), (rel, slot))

    def test_folder_files_never_parse_as_pictures(self) -> None:
        for kind in fl.FOLDER_FILES:
            self.assertIsNone(fl.parse_name(fl.folder_file_name(kind)))
        for name in fl.INDEX_FILES:
            self.assertIsNone(fl.parse_name(name))

    def test_rejects_escape(self) -> None:
        for bad in ("../x.jpg", "a/../../x.jpg", ""):
            with self.assertRaises(ValueError):
                fl.record_name(bad)


class Locations(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "library-data"
        self.root.mkdir()
        self.folder = self.tmp / "Pictures" / "Favorites"
        self.folder.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _serve(self, store: str) -> dict:
        return {
            "id": SRC, "name": "Favorites", "mode": "serve-from-there", "previewStore": store, "copyRoot": None,
            "origin": {"volumeSerial": "windows:00000000", "pathFromVolumeRoot": "Pictures/Favorites",
                       "lastKnownPath": str(self.folder)},
            "files": {},
        }

    def test_serve_with_source_is_inside_the_folder(self) -> None:
        lib = fl.for_source(self.root, self._serve("with-source"))
        self.assertEqual(lib.dir, self.folder / ".library")
        self.assertEqual(lib.record_path("IMG_1.JPG"), self.folder / ".library" / "IMG_1.JPG.json")

    def test_serve_with_server_is_under_library_data(self) -> None:
        lib = fl.for_source(self.root, self._serve("with-server"))
        self.assertEqual(lib.dir, self.root.resolve() / "folders" / f"Favorites-{SRC}")

    def test_copy_here_is_inside_the_copy(self) -> None:
        source = {"id": SRC, "name": "Trip", "mode": "copy-here", "copyRoot": "originals/Trip-x", "origin": {}}
        lib = fl.for_source(self.root, source)
        self.assertEqual(lib.dir, self.root.resolve() / "originals" / "Trip-x" / ".library")

    def test_unreachable_folder_is_none(self) -> None:
        source = self._serve("with-source")
        shutil.rmtree(self.folder)
        with mock.patch("library.renditions.source_preview_root", return_value=None):
            self.assertIsNone(fl.for_source(self.root, source))

    def test_item_rel_names_live_pair_after_still_and_keeps_subfolders(self) -> None:
        source = self._serve("with-source")
        source["files"] = {
            "2023/IMG_9.MOV": {"itemId": "abc", "component": "motion"},
            "2023/IMG_9.HEIC": {"itemId": "abc", "component": "still"},
            "clip.mp4": {"itemId": "vid", "component": "motion"},
        }
        live = {"id": "abc", "locations": [
            {"sourceId": SRC, "current": True, "component": "motion", "role": "primary", "pathFromVolumeRoot": "Pictures/Favorites/2023/IMG_9.MOV"},
            {"sourceId": SRC, "current": True, "component": "still", "role": "primary", "pathFromVolumeRoot": "Pictures/Favorites/2023/IMG_9.HEIC"},
        ]}
        video = {"id": "vid", "locations": [
            {"sourceId": SRC, "current": True, "component": "motion", "role": "primary", "pathFromVolumeRoot": "Pictures/Favorites/clip.mp4"},
        ]}
        self.assertEqual(fl.item_rel(source, live), "2023/IMG_9.HEIC")
        self.assertEqual(fl.item_rel(source, video), "clip.mp4")


class LogicalPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "library-data"
        self.root.mkdir()
        self.lib = fl.FolderLibrary(SRC, self.tmp / "Favorites" / ".library")
        self.available = True
        patcher = mock.patch.object(fl, "for_source_id", side_effect=lambda _root, sid: self.lib if self.available and sid == SRC else None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_library_path_resolves_source_paths(self) -> None:
        self.assertEqual(library_path(self.root, f"source:{SRC}/2023/a.jpg.json"), self.lib.dir / "2023" / "a.jpg.json")
        with self.assertRaises(Exception):
            library_path(self.root, "source:not-an-id/a.jpg.json")
        with self.assertRaises(Exception):
            library_path(self.root, f"source:{SRC}/../escape.json")

    def test_transact_writes_into_the_folder_library(self) -> None:
        rel = self.lib.logical(fl.record_name("IMG_1.JPG"))
        transact(self.root, [{"path": rel, "before": None, "after": {"filename": "IMG_1.JPG"}}])
        self.assertEqual(json.loads((self.lib.dir / "IMG_1.JPG.json").read_text(encoding="utf-8")), {"filename": "IMG_1.JPG"})

    def test_recovery_waits_for_an_unplugged_folder_then_rolls_forward(self) -> None:
        rel = self.lib.logical(fl.record_name("IMG_2.JPG"))
        tdir = self.root / ".transactions" / "01790000000000000000-00000001-aaaaaaaa"
        tdir.mkdir(parents=True)
        manifest = {"schemaVersion": 1, "id": tdir.name, "state": "committed",
                    "changes": [{"path": rel, "before": None, "after": {"filename": "IMG_2.JPG"}}]}
        (tdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.available = False
        recover_transactions(self.root)
        self.assertTrue(tdir.is_dir(), "manifest must survive while the folder is unreachable")
        self.available = True
        recover_transactions(self.root)
        self.assertFalse(tdir.exists())
        self.assertTrue((self.lib.dir / "IMG_2.JPG.json").is_file())


if __name__ == "__main__":
    unittest.main()
