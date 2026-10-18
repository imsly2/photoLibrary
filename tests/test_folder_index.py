"""Tests for library.folder_index.write_index."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from library.folder_index import write_index


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


if __name__ == "__main__":
    unittest.main()
