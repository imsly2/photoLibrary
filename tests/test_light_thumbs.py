"""F7 light thumbs: JPEG lowres choice, encode path isolation, rendition-status."""

from __future__ import annotations

import inspect
import struct
import tempfile
import unittest
from pathlib import Path

from library.catalog_io import ensure_catalog_dirs, item_rel
from library.errors import AppError
from library.atomic import transact
from library.records import make_item, make_location, renditions_for
from library.renditions import _encode_job, jpeg_lowres_for_cap, jpeg_sof_dimensions
from library.service import Library, parse_rendition_status_ids


def _minimal_jpeg(width: int, height: int) -> bytes:
    """Hand-built JPEG with SOF0 carrying ``width`` x ``height`` (no real image data)."""
    # SOI + APP0(JFIF) + SOF0 + EOI — enough for jpeg_sof_dimensions.
    app0 = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = bytes(
        [
            8,  # precision
            (height >> 8) & 0xFF,
            height & 0xFF,
            (width >> 8) & 0xFF,
            width & 0xFF,
            1,  # components
            1,
            0x11,
            0,  # Y component
        ]
    )
    return b"".join(
        [
            b"\xff\xd8",
            b"\xff\xe0",
            struct.pack(">H", len(app0) + 2),
            app0,
            b"\xff\xc0",
            struct.pack(">H", len(sof) + 2),
            sof,
            b"\xff\xd9",
        ]
    )


class JpegLowresTests(unittest.TestCase):
    def test_decision_large_image_uses_lowres_3(self) -> None:
        self.assertEqual(jpeg_lowres_for_cap(4000, 3000, 320), 3)

    def test_decision_small_image_omits_lowres(self) -> None:
        self.assertIsNone(jpeg_lowres_for_cap(400, 300, 320))

    def test_decision_1080p_landscape_uses_lowres_2(self) -> None:
        self.assertEqual(jpeg_lowres_for_cap(1920, 1080, 320), 2)

    def test_decision_phone_preview_cap_uses_lowres_1(self) -> None:
        self.assertEqual(jpeg_lowres_for_cap(4032, 3024, 1600), 1)

    def test_sof_parser_reads_crafted_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "big.jpg"
            path.write_bytes(_minimal_jpeg(4032, 3024))
            self.assertEqual(jpeg_sof_dimensions(path), (4032, 3024))
            self.assertEqual(jpeg_lowres_for_cap(4032, 3024, 320), 3)

    def test_sof_parser_small_file_omits_lowres(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "small.jpg"
            path.write_bytes(_minimal_jpeg(400, 300))
            size = jpeg_sof_dimensions(path)
            self.assertEqual(size, (400, 300))
            assert size is not None
            self.assertIsNone(jpeg_lowres_for_cap(size[0], size[1], 320))


class EncodeJobIsolationTests(unittest.TestCase):
    def test_encode_job_source_has_no_shared_face_path(self) -> None:
        source = inspect.getsource(_encode_job)
        self.assertNotIn("detect_shared_frame", source)
        self.assertNotIn("encode_webp_and_rgb", source)
        self.assertNotIn("_share_face_decode", source)
        self.assertNotIn("_publish_shared_faces", source)


class RenditionStatusTests(unittest.TestCase):
    def test_parser_rejects_empty_and_oversize_and_slash(self) -> None:
        with self.assertRaises(AppError) as empty:
            parse_rendition_status_ids({"ids": ""})
        self.assertEqual(empty.exception.code, "invalid-argument")

        with self.assertRaises(AppError) as missing:
            parse_rendition_status_ids({})
        self.assertEqual(missing.exception.code, "invalid-argument")

        with self.assertRaises(AppError) as too_many:
            parse_rendition_status_ids({"ids": ",".join(f"id{i}" for i in range(81))})
        self.assertEqual(too_many.exception.code, "invalid-argument")

        with self.assertRaises(AppError) as slash:
            parse_rendition_status_ids({"ids": "ab/cd"})
        self.assertEqual(slash.exception.code, "invalid-argument")

        with self.assertRaises(AppError) as extras:
            parse_rendition_status_ids({"ids": "a", "extra": "1"})
        self.assertEqual(extras.exception.code, "invalid-argument")

    def test_status_returns_only_requested_known_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "library-data"
            root.mkdir()
            ensure_catalog_dirs(root)
            src = "src_0123456789ab"
            a = "a" * 64
            b = "b" * 64
            c = "c" * 64

            def put(item_id: str, name: str, thumb: str) -> None:
                loc = make_location(
                    source_id=src,
                    role="primary",
                    component="still",
                    volume_serial="windows:00000000",
                    path_from_volume_root=name,
                    last_known_path=name,
                    size_bytes=1,
                    modified_at="2026-01-01T00:00:00Z",
                    sha256=None,
                )
                item = make_item(
                    item_id=item_id,
                    kind="photo",
                    filename=name,
                    captured_at="2026-01-01T00:00:00Z",
                    captured_at_source="mtime",
                    content_identifier=None,
                    locations=[loc],
                    renditions=renditions_for("photo", src, store="with-server"),
                )
                item["renditions"]["status"]["thumb"] = thumb
                transact(root, [{"path": item_rel(item_id), "before": None, "after": item}])

            put(a, "one.jpg", "ready")
            put(b, "two.jpg", "queued")
            put(c, "three.jpg", "error")

            library = Library(root)
            body = library.rendition_status({"ids": f"{a},{c},missing-id"})
            self.assertEqual(
                body,
                {
                    "items": [
                        {
                            "id": a,
                            "status": {
                                "thumb": "ready",
                                "preview": "queued",
                                "poster": "not-applicable",
                                "proxy": "not-applicable",
                                "playback": "not-applicable",
                            },
                        },
                        {
                            "id": c,
                            "status": {
                                "thumb": "error",
                                "preview": "queued",
                                "poster": "not-applicable",
                                "proxy": "not-applicable",
                                "playback": "not-applicable",
                            },
                        },
                    ]
                },
            )
            # Request order preserved; unknown omitted; b not requested.
            self.assertEqual([row["id"] for row in body["items"]], [a, c])


if __name__ == "__main__":
    unittest.main()
