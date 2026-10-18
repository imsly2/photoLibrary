from __future__ import annotations

import builtins
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from library import media
from library.media import ffprobe_json, read_source
from library.metadata import read_capture
from library.service import Library
from library.settings import defaults, write_settings_file


def _segment(marker: int, payload: bytes) -> bytes:
    return b"\xff" + bytes([marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def _jpeg_with_exif_date() -> bytes:
    # IFD0 -> ExifIFD with one DateTimeOriginal entry, so the scan has EXIF to parse.
    date = b"2020:01:02 03:04:05\x00"
    exif_at = 8 + 2 + 12 + 4
    ifd0 = b"\x00\x01" + (0x8769).to_bytes(2, "big") + b"\x00\x04\x00\x00\x00\x01" + exif_at.to_bytes(4, "big") + b"\x00\x00\x00\x00"
    value_at = exif_at + 2 + 12 + 4
    exif = b"\x00\x01" + (0x9003).to_bytes(2, "big") + b"\x00\x02" + len(date).to_bytes(4, "big") + value_at.to_bytes(4, "big") + b"\x00\x00\x00\x00"
    tiff = b"MM\x00\x2a\x00\x00\x00\x08" + ifd0 + exif + date
    sof = _segment(0xC0, b"\x08" + (120).to_bytes(2, "big") + (160).to_bytes(2, "big") + b"\x01\x01\x11\x00")
    # Bigger than the 128 KB head the folder-ordering pass reads, like a real photo.
    return b"\xff\xd8" + _segment(0xE1, b"Exif\x00\x00" + tiff) + sof + b"\xff\xda\x00\x02" + bytes(300 * 1024) + b"\xff\xd9"


class ScanOneReadTests(unittest.TestCase):
    def test_scan_reads_each_photo_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "library-data"
            root.mkdir()
            pictures = Path(temp) / "pictures"
            pictures.mkdir()
            photo = pictures / "IMG_0001.jpg"
            photo.write_bytes(_jpeg_with_exif_date())
            settings = defaults()
            settings.update(ratingMode="off", transcribeVideos=False, previewStore="with-source")
            write_settings_file(root, settings)
            lib = Library(root)
            lib.ensure_settings()

            # Bytes read from the photo per open. The folder ordering pass reads a
            # 128 KB head; indexing must then read the whole file exactly once.
            reads: list[int] = []
            real_open = builtins.open

            def counting_open(file, mode="r", *args, **kwargs):
                handle = real_open(file, mode, *args, **kwargs)
                if "b" in mode and "r" in mode and type(file) is not int and Path(str(file)) == photo:
                    reads.append(0)
                    slot = len(reads) - 1
                    real_read = handle.read

                    def read(n=-1):
                        data = real_read(n)
                        reads[slot] += len(data)
                        return data

                    handle.read = read
                return handle

            with patch.object(builtins, "open", counting_open), patch.object(io, "open", counting_open):
                lib.scan({"path": str(pictures), "mode": "serve-from-there", "previewStore": "with-source"})

            size = photo.stat().st_size
            full_reads = [n for n in reads if n >= size]
            self.assertEqual(len(full_reads), 1, reads)
            self.assertLessEqual(sum(reads), size + 128 * 1024, reads)
            items = lib.items_list({})
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["capturedAt"][:10], "2020-01-02")
            self.assertEqual(items[0]["capturedAtSource"], "exif")
            self.assertEqual(items[0]["id"], read_source(photo).sha256)

    def test_read_source_bytes_feed_the_parsers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            photo = Path(temp) / "a.jpg"
            photo.write_bytes(_jpeg_with_exif_date())
            source = read_source(photo)
            self.assertEqual(source.size, photo.stat().st_size)
            self.assertEqual(source.data, photo.read_bytes())
            with patch.object(Path, "read_bytes", side_effect=AssertionError("parser re-read the file")):
                captured, origin, meta = read_capture(photo, source.data)
            self.assertEqual((captured[:10], origin, meta["width"]), ("2020-01-02", "exif", 160))

    def test_ffprobe_is_run_once_per_unchanged_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clip = Path(temp) / "clip.mov"
            clip.write_bytes(b"not really a movie")
            runs: list[list[str]] = []

            def fake_run(cmd, **_kwargs):
                runs.append(cmd)
                import subprocess

                return subprocess.CompletedProcess(cmd, 0, '{"format": {"tags": {"a": "1"}}, "streams": []}', "")

            media._probe_memo.clear()
            with patch.object(media, "run_ffmpeg", fake_run):
                first = ffprobe_json(clip)
                first["format"]["tags"]["a"] = "changed by caller"
                second = ffprobe_json(clip)
                clip.write_bytes(b"a different movie now")
                third = ffprobe_json(clip)
            self.assertEqual(second["format"]["tags"]["a"], "1")
            self.assertEqual(third["format"]["tags"]["a"], "1")
            self.assertEqual(len(runs), 2, "one probe for the original file, one after it changed")


if __name__ == "__main__":
    unittest.main()
