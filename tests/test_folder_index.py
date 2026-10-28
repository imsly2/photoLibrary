"""Tests for library.folder_index.write_index and stale scan settle on recover."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from library.atomic import transact
from library.catalog_io import ensure_catalog_dirs, fold_source_changes, source_rel, try_load_source
from library.folder_index import write_index
from library.records import make_source
from library.service import Library

SRC = "src_0123456789ab"


def _parse_index_js(text: str) -> dict:
    prefix = "window.LIBRARY = "
    assert text.startswith(prefix)
    body = text[len(prefix) :].rstrip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


class WriteIndex(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.lib = self.tmp / ".library"
        self.lib.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_html_and_js(self) -> None:
        write_index(
            self.lib,
            [{"path": "a.jpg", "id": "x", "kind": "photo", "filename": "a.jpg"}],
            folder_name="Test Folder",
        )
        self.assertTrue((self.lib / "index.html").is_file())
        self.assertTrue((self.lib / "index.js").is_file())
        data = _parse_index_js((self.lib / "index.js").read_text(encoding="utf-8"))
        self.assertEqual(data["folderName"], "Test Folder")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["path"], "a.jpg")

    def test_script_injection_safe(self) -> None:
        evil = '</script><img src=x onerror=alert(1)>'
        write_index(
            self.lib,
            [{"path": evil, "kind": "photo", "filename": evil}],
            folder_name="X",
        )
        js = (self.lib / "index.js").read_text(encoding="utf-8")
        self.assertNotIn("</script>", js.replace(r"<\/", ""))
        data = _parse_index_js(js)
        self.assertEqual(data["items"][0]["path"], evil)

    def test_special_path_segments(self) -> None:
        path = "sub/旅行 #50%.jpg"
        write_index(
            self.lib,
            [{"path": path, "kind": "photo", "filename": "旅行 #50%.jpg"}],
            folder_name="F",
        )
        data = _parse_index_js((self.lib / "index.js").read_text(encoding="utf-8"))
        self.assertEqual(data["items"][0]["path"], path)
        html = (self.lib / "index.html").read_text(encoding="utf-8")
        self.assertIn("encodeURIComponent", html)

    def test_garbage_fields_do_not_crash(self) -> None:
        write_index(
            self.lib,
            [
                None,
                "nope",
                {
                    "path": "ok.jpg",
                    "kind": 99,
                    "people": "x",
                    "things": [None, {"label": 1}, "tag"],
                    "quality": "bad",
                    "renditions": [],
                    "capturedAt": 123,
                },
            ],
            folder_name=123,
        )
        data = _parse_index_js((self.lib / "index.js").read_text(encoding="utf-8"))
        self.assertEqual(data["folderName"], "Photos")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["kind"], "photo")
        self.assertEqual(data["items"][0]["tags"], ["tag"])

    def test_unchanged_skips_mtime(self) -> None:
        records = [
            {
                "path": "b.jpg",
                "kind": "photo",
                "capturedAt": "2024-01-02T12:00:00",
                "quality": {"stars": 3},
            }
        ]
        write_index(self.lib, records, folder_name="Stable")
        js_path = self.lib / "index.js"
        html_path = self.lib / "index.html"
        mtime_js = js_path.stat().st_mtime_ns
        mtime_html = html_path.stat().st_mtime_ns
        time.sleep(0.05)
        write_index(self.lib, records, folder_name="Stable")
        self.assertEqual(js_path.stat().st_mtime_ns, mtime_js)
        self.assertEqual(html_path.stat().st_mtime_ns, mtime_html)


class SettleInterruptedScans(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.root = (self.tmp / "library-data").resolve()
        self.root.mkdir()
        ensure_catalog_dirs(self.root)
        source = make_source(
            source_id=SRC,
            name="Favorites",
            mode="serve-from-there",
            preview_store="with-server",
            origin={
                "volumeSerial": "windows:00000000",
                "pathFromVolumeRoot": "Pictures/Favorites",
                "lastKnownPath": str(self.tmp / "Pictures" / "Favorites"),
            },
            scan={"state": "running", "added": 3, "skipped": 4, "errors": []},
        )
        transact(self.root, [{"path": source_rel(SRC), "before": None, "after": source}])

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recover_marks_stale_running_interrupted(self) -> None:
        lib = Library(self.root)
        self.assertFalse(lib._scanning)
        lib.recover()
        reloaded = try_load_source(self.root, SRC)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded["scan"]["state"], "interrupted")
        self.assertEqual(reloaded["scan"]["added"], 3)
        self.assertEqual(reloaded["scan"]["skipped"], 4)
        self.assertEqual(reloaded["scan"]["errors"], [])

        lib._scanning = True
        running = dict(reloaded)
        running["scan"] = {"state": "running", "added": 3, "skipped": 4, "errors": []}
        transact(self.root, fold_source_changes(self.root, running))
        lib.recover()
        again = try_load_source(self.root, SRC)
        self.assertIsNotNone(again)
        self.assertEqual(again["scan"]["state"], "running")
        self.assertEqual(again["scan"]["added"], 3)
        self.assertEqual(again["scan"]["skipped"], 4)


if __name__ == "__main__":
    unittest.main()
