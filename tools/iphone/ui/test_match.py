"""Match rules. Temp folders only. No phone, no E: drive."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ui.match import (
    DestinationExists,
    PhoneFile,
    PlanItem,
    copy_item,
    folder_text,
    look_status,
    phone_text,
    plan,
    write_stream,
)


class MatchTests(unittest.TestCase):
    def test_interrupted_transfer_cleans_partial(self) -> None:
        with TemporaryDirectory() as raw:
            final = Path(raw) / "IMG_0001.HEIC"
            def interrupted():
                yield b"abc"
                raise OSError("USB disconnected")
            with self.assertRaisesRegex(OSError, "USB disconnected"):
                write_stream(final, 6, interrupted())
            self.assertFalse(final.exists())
            self.assertFalse(final.with_name(final.name + ".partial").exists())

    def test_short_transfer_cleans_partial(self) -> None:
        from ui.match import SizeMismatch
        with TemporaryDirectory() as raw:
            final = Path(raw) / "IMG_0001.MOV"
            with self.assertRaises(SizeMismatch):
                write_stream(final, 6, [b"abc"])
            self.assertFalse(final.exists())
            self.assertFalse(final.with_name(final.name + ".partial").exists())

    def test_exact_match_skips(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            folder = dest / "2020-01"
            folder.mkdir()
            old = folder / "IMG_0140.JPG"
            old.write_bytes(b"abc")
            items = plan(
                [PhoneFile("/DCIM/100APPLE/IMG_0140.JPG", 3, datetime(2020, 1, 2))],
                dest,
            )
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].action, "skip")
            self.assertEqual(items[0].dest_relative, "2020-01/IMG_0140.JPG")
            self.assertEqual(items[0].local_relative, "2020-01/IMG_0140.JPG")
            self.assertEqual(items[0].local_size, 3)
            self.assertIsNone(items[0].stem_relative)
            self.assertEqual(folder_text(items[0]), "2020-01/IMG_0140.JPG  (3)")
            self.assertEqual(look_status(items[0]), "Skipped, exact match")
            self.assertEqual(
                phone_text(items[0].source_path, items[0].size),
                "/DCIM/100APPLE/IMG_0140.JPG  (3)",
            )
            self.assertEqual(old.read_bytes(), b"abc")
            self.assertEqual([path.name for path in folder.iterdir()], ["IMG_0140.JPG"])

    def test_second_same_name_and_size_copies(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            folder = dest / "2020-01"
            folder.mkdir()
            old = folder / "IMG_0140.JPG"
            old.write_bytes(b"abc")
            when = datetime(2020, 1, 2)
            items = plan(
                [
                    PhoneFile("/DCIM/100APPLE/IMG_0140.JPG", 3, when),
                    PhoneFile("/DCIM/101APPLE/IMG_0140.JPG", 3, when),
                ],
                dest,
            )
            self.assertEqual(items[0].action, "skip")
            self.assertEqual(items[0].local_relative, "2020-01/IMG_0140.JPG")
            self.assertEqual(items[0].local_size, 3)
            self.assertEqual(items[1].action, "copy")
            self.assertEqual(items[1].dest_relative, "2020-01/IMG_0140_2.JPG")
            self.assertEqual(items[1].local_relative, "2020-01/IMG_0140.JPG")
            self.assertEqual(items[1].local_size, 3)
            self.assertIsNone(items[1].stem_relative)
            self.assertEqual(
                folder_text(items[1]),
                "2020-01/IMG_0140.JPG  folder 3  phone 3",
            )
            self.assertEqual(look_status(items[1]), "Will copy, already paired")
            copy_item(dest, items[1], [b"abc"])
            self.assertEqual(old.read_bytes(), b"abc")
            self.assertEqual((folder / "IMG_0140_2.JPG").read_bytes(), b"abc")

    def test_size_mismatch_writes_suffix_beside_old_file(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            folder = dest / "pile"
            folder.mkdir()
            old = folder / "IMG_0140.JPG"
            old.write_bytes(b"OLD!")
            items = plan(
                [PhoneFile("/DCIM/100APPLE/IMG_0140.JPG", 7, datetime(2024, 8, 1))],
                dest,
            )
            self.assertEqual(items[0].action, "copy")
            self.assertEqual(items[0].dest_relative, "pile/IMG_0140_2.JPG")
            self.assertEqual(items[0].local_relative, "pile/IMG_0140.JPG")
            self.assertEqual(items[0].local_size, 4)
            self.assertIsNone(items[0].stem_relative)
            self.assertEqual(
                folder_text(items[0]),
                "pile/IMG_0140.JPG  folder 4  phone 7",
            )
            self.assertEqual(look_status(items[0]), "Will copy, size differs")
            copy_item(dest, items[0], [b"NEWDATA"])
            self.assertEqual(old.read_bytes(), b"OLD!")
            self.assertEqual((folder / "IMG_0140_2.JPG").read_bytes(), b"NEWDATA")
            self.assertFalse((folder / "IMG_0140_2.JPG.partial").exists())

    def test_missing_name_goes_to_month_folder(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            when = datetime(2024, 3, 15, 8, 30, 0)
            items = plan(
                [PhoneFile("/DCIM/100APPLE/IMG_0001.HEIC", 4, when)],
                dest,
            )
            self.assertEqual(items[0].action, "copy")
            self.assertEqual(items[0].dest_relative, "2024-03/IMG_0001.HEIC")
            self.assertIsNone(items[0].local_relative)
            self.assertIsNone(items[0].local_size)
            self.assertIsNone(items[0].stem_relative)
            self.assertEqual(folder_text(items[0]), "not in this folder")
            self.assertEqual(look_status(items[0]), "Will copy, not in folder")
            copy_item(dest, items[0], [b"data"])
            landed = dest / "2024-03" / "IMG_0001.HEIC"
            self.assertEqual(landed.read_bytes(), b"data")
            self.assertFalse(landed.with_name(landed.name + ".partial").exists())
            row = json.loads(
                (dest / "iphone-photos-log.jsonl").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(row["source"], "/DCIM/100APPLE/IMG_0001.HEIC")
            self.assertEqual(row["source_size"], 4)
            self.assertEqual(row["dest"], "2024-03/IMG_0001.HEIC")
            self.assertEqual(row["status"], "copied")
            self.assertIn("time", row)

    def test_existing_final_path_is_not_overwritten(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            final = dest / "2024-03" / "IMG_0001.HEIC"
            final.parent.mkdir(parents=True)
            final.write_bytes(b"KEEPME!!")
            with self.assertRaises(DestinationExists):
                write_stream(final, 3, [b"abc"])
            self.assertEqual(final.read_bytes(), b"KEEPME!!")
            self.assertFalse(final.with_name(final.name + ".partial").exists())

    def test_log_skips_before_disk_scan(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            row = {
                "source": "/DCIM/100APPLE/IMG_0001.HEIC",
                "source_size": 4,
                "dest": "2024-03/IMG_0001.HEIC",
                "status": "copied",
                "time": "2026-01-01T00:00:00",
            }
            (dest / "iphone-photos-log.jsonl").write_text(
                json.dumps(row) + "\n",
                encoding="utf-8",
            )
            items = plan(
                [PhoneFile("/DCIM/100APPLE/IMG_0001.HEIC", 4, datetime(2024, 3, 1))],
                dest,
            )
            self.assertEqual(items[0].action, "skip")
            self.assertIsNone(items[0].dest_relative)
            self.assertIsNone(items[0].local_relative)
            self.assertIsNone(items[0].local_size)
            self.assertEqual(look_status(items[0]), "Skipped, exact match")
            self.assertEqual(folder_text(items[0]), "not in this folder")
            self.assertFalse((dest / "2024-03").exists())

    def test_log_skip_does_not_consume_disk_match(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            folder = dest / "2020-01"
            folder.mkdir()
            (folder / "IMG_0140.JPG").write_bytes(b"abc")
            row = {
                "source": "/DCIM/100APPLE/IMG_0140.JPG",
                "source_size": 3,
                "dest": "2020-01/IMG_0140.JPG",
                "status": "copied",
                "time": "2026-01-01T00:00:00",
            }
            (dest / "iphone-photos-log.jsonl").write_text(
                json.dumps(row) + "\n",
                encoding="utf-8",
            )
            when = datetime(2020, 1, 2)
            items = plan(
                [
                    PhoneFile("/DCIM/100APPLE/IMG_0140.JPG", 3, when),
                    PhoneFile("/DCIM/101APPLE/IMG_0140.JPG", 3, when),
                ],
                dest,
            )
            self.assertEqual(items[0].action, "skip")
            self.assertIsNone(items[0].dest_relative)
            self.assertEqual(items[0].local_relative, "2020-01/IMG_0140.JPG")
            self.assertEqual(items[0].local_size, 3)
            self.assertEqual(items[1].action, "skip")
            self.assertEqual(items[1].dest_relative, "2020-01/IMG_0140.JPG")
            self.assertEqual(items[1].local_size, 3)

    def test_same_stem_different_extension_is_not_a_skip(self) -> None:
        with TemporaryDirectory() as raw:
            dest = Path(raw)
            folder = dest / "202311__"
            folder.mkdir()
            (folder / "IMG_0140.JPG").write_bytes(b"abc")
            (dest / "b").mkdir()
            (dest / "b" / "IMG_0140.MOV").write_bytes(b"zzzz")
            when = datetime(2020, 1, 2)
            items = plan(
                [PhoneFile("/DCIM/100APPLE/IMG_0140.HEIC", 3, when)],
                dest,
            )
            self.assertEqual(items[0].action, "copy")
            self.assertEqual(items[0].dest_relative, "2020-01/IMG_0140.HEIC")
            self.assertIsNone(items[0].local_relative)
            self.assertIsNone(items[0].local_size)
            self.assertEqual(items[0].stem_relative, "202311__/IMG_0140.JPG")
            self.assertEqual(
                folder_text(items[0]),
                "not in this folder  also has IMG_0140.JPG at 202311__/IMG_0140.JPG",
            )
            self.assertEqual(look_status(items[0]), "Will copy, not in folder")
            self.assertFalse((dest / "2020-01" / "IMG_0140.HEIC").exists())

    def test_readout_examples(self) -> None:
        phone = phone_text("/DCIM/100APPLE/IMG_0140.HEIC", 1_645_466)
        self.assertEqual(phone, "/DCIM/100APPLE/IMG_0140.HEIC  (1,645,466)")

        exact = PlanItem(
            "/DCIM/100APPLE/IMG_0150.MOV",
            3_375_767,
            datetime(2023, 11, 1),
            "skip",
            "202311__/IMG_0150.MOV",
            "202311__/IMG_0150.MOV",
            3_375_767,
            None,
        )
        self.assertEqual(folder_text(exact), "202311__/IMG_0150.MOV  (3,375,767)")
        self.assertEqual(look_status(exact), "Skipped, exact match")

        differs = PlanItem(
            "/DCIM/100APPLE/IMG_0140.MOV",
            4_331_820,
            datetime(2023, 11, 1),
            "copy",
            "IMG_0140_2.MOV",
            "IMG_0140.MOV",
            4_322_524,
            None,
        )
        self.assertEqual(
            folder_text(differs),
            "IMG_0140.MOV  folder 4,322,524  phone 4,331,820",
        )
        self.assertEqual(look_status(differs), "Will copy, size differs")

        missing = PlanItem(
            "/DCIM/100APPLE/IMG_0140.HEIC",
            1_645_466,
            datetime(2023, 11, 1),
            "copy",
            "2023-11/IMG_0140.HEIC",
            None,
            None,
            "202311__/IMG_0140.JPG",
        )
        self.assertEqual(
            folder_text(missing),
            "not in this folder  also has IMG_0140.JPG at 202311__/IMG_0140.JPG",
        )
        self.assertEqual(look_status(missing), "Will copy, not in folder")


if __name__ == "__main__":
    unittest.main()
