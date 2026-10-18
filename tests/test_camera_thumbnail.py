from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.metadata import _jpeg_size_and_exif, _parse_tiff, camera_thumbnail, exif_orientation
from library.records import browser_ready_still, renditions_for


def _segment(marker: int, payload: bytes) -> bytes:
    return b"\xff" + bytes([marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def _sof(width: int, height: int) -> bytes:
    return _segment(0xC0, b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00")


def _entry(tag: int, typ: int, value: bytes) -> bytes:
    return tag.to_bytes(2, "big") + typ.to_bytes(2, "big") + b"\x00\x00\x00\x01" + value


def _photo(width: int, height: int, orientation: int, thumb: bytes | None) -> bytes:
    """A JPEG head: EXIF with an orientation and, optionally, an IFD1 thumbnail."""
    ifd1_at = 8 + 2 + 12 + 4
    ifd0 = b"\x00\x01" + _entry(0x0112, 3, orientation.to_bytes(2, "big") + b"\x00\x00")
    ifd0 += (ifd1_at if thumb else 0).to_bytes(4, "big")
    tiff = b"MM\x00\x2a\x00\x00\x00\x08" + ifd0
    if thumb:
        thumb_at = ifd1_at + 2 + 24 + 4
        tiff += b"\x00\x02" + _entry(0x0201, 4, thumb_at.to_bytes(4, "big"))
        tiff += _entry(0x0202, 4, len(thumb).to_bytes(4, "big")) + b"\x00\x00\x00\x00" + thumb
    return b"\xff\xd8" + _segment(0xE1, b"Exif\x00\x00" + tiff) + _sof(width, height) + b"\xff\xda\x00\x02\xff\xd9"


def _small_jpeg(width: int, height: int) -> bytes:
    return b"\xff\xd8" + _sof(width, height) + b"\xff\xd9"


class CameraThumbnailTests(unittest.TestCase):
    def _write(self, name: str, data: bytes) -> Path:
        path = Path(self._dir.name) / name
        path.write_bytes(data)
        return path

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_embedded_picture_comes_back_with_the_photo_orientation(self) -> None:
        path = self._write("a.jpg", _photo(2592, 1936, 6, _small_jpeg(160, 120)))
        data = camera_thumbnail(path)
        width, height, tiff = _jpeg_size_and_exif(data)
        self.assertEqual((width, height), (160, 120))
        self.assertEqual(_parse_tiff(tiff)["ifd0"][0x0112], 6)
        self.assertTrue(data.endswith(b"\xff\xd9"))

    def test_letterboxed_picture_is_not_used(self) -> None:
        path = self._write("wide.jpg", _photo(3456, 2304, 1, _small_jpeg(160, 120)))
        self.assertEqual(camera_thumbnail(path), b"")

    def test_photo_without_embedded_picture_has_none(self) -> None:
        path = self._write("plain.jpg", _photo(2592, 1936, 1, None))
        self.assertEqual(camera_thumbnail(path), b"")

    def test_only_jpegs_are_read(self) -> None:
        path = self._write("a.png", _photo(2592, 1936, 1, _small_jpeg(160, 120)))
        self.assertEqual(camera_thumbnail(path), b"")
        self.assertEqual(exif_orientation(path), 1)

    def test_exif_orientation_reads_the_head(self) -> None:
        self.assertEqual(exif_orientation(self._write("r.jpg", _photo(2592, 1936, 8, None))), 8)


class BrowserReadyStillTests(unittest.TestCase):
    def test_ordinary_jpeg_needs_no_preview(self) -> None:
        self.assertTrue(browser_ready_still(".JPG", {"width": 4032, "height": 3024}))
        self.assertTrue(browser_ready_still(".jpg", {"width": 5712, "height": 4284}))
        status = renditions_for("photo", "src_x", browser_still=True)["status"]
        self.assertEqual((status["thumb"], status["preview"]), ("queued", "not-applicable"))

    def test_other_formats_large_or_unknown_size_get_a_preview(self) -> None:
        self.assertFalse(browser_ready_still(".heic", {"width": 4032, "height": 3024}))
        self.assertFalse(browser_ready_still(".jpg", {"width": 8000, "height": 6000}))
        self.assertFalse(browser_ready_still(".jpg", {"width": None, "height": None}))
        self.assertFalse(browser_ready_still(".jpg", None))
        self.assertEqual(renditions_for("photo", "src_x")["status"]["preview"], "queued")


if __name__ == "__main__":
    unittest.main()
