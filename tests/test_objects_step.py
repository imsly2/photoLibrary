from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from library import objects
from library.media import sha256_file


class ObjectsStepTests(unittest.TestCase):
    def test_settled_photos_are_not_hashed_again_and_inference_runs_unlocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "models").mkdir()
            legacy = root / "legacy.jpg"
            legacy.write_bytes(b"legacy bytes")
            fresh = root / "fresh.jpg"
            fresh.write_bytes(b"fresh bytes")
            # A record from before file signatures were stored: digest only.
            (root / "models" / "objects-state.json").write_text(
                json.dumps({"schemaVersion": 1, "items": {"legacy": {"sha256": sha256_file(legacy), "names": []}}}),
                encoding="utf-8",
            )
            items = {
                "legacy": {"id": "legacy", "kind": "photo", "locations": [{"current": True, "sizeBytes": 12}]},
                "fresh": {"id": "fresh", "kind": "photo", "locations": [{"current": True, "sizeBytes": 11}]},
            }
            stills = {"legacy": legacy, "fresh": fresh}
            detected: list[str] = []
            released: list[bool] = []

            @contextmanager
            def io_context():
                released.append(True)
                yield

            def detect(path, _model):
                detected.append(path.name)
                return []

            hashes: list[str] = []
            real_sha = objects.sha256_file

            def counting_sha(path):
                hashes.append(path.name)
                return real_sha(path)

            common = dict(
                model_installed=lambda _root: True,
                _ensure_runtime=lambda: None,
                load_item=lambda _root, item_id: items[item_id],
                _still_for_detect=lambda item, _root: stills[item["id"]],
                detect_objects=detect,
                _publish_detections=lambda _root, _id, _dets: [],
                model_path=lambda _root: root / "models" / "yolo.onnx",
            )
            with (
                patch.multiple(objects, **common),
                patch.object(objects, "sha256_file", counting_sha),
                patch("library.item_index.iter_items", lambda _root: list(items.values())),
                patch("library.item_index.root_key", lambda _root: str(root)),
            ):
                objects._settled.clear()
                # First tick: backfill the legacy record (one hash), analyze the fresh photo.
                self.assertTrue(objects.analyze_step(root, io_context=io_context))
                self.assertEqual(sorted(hashes), ["fresh.jpg", "legacy.jpg"])
                self.assertEqual(detected, ["fresh.jpg"])
                self.assertEqual(released, [True])
                state = json.loads((root / "models" / "objects-state.json").read_text(encoding="utf-8"))
                self.assertEqual(len(state["items"]["legacy"]["source"]), 2)
                self.assertEqual(len(state["items"]["fresh"]["source"]), 2)

                # Idle ticks: nothing hashed, nothing decoded, no disk read of originals.
                hashes.clear()
                detected.clear()
                with patch.object(objects, "sha256_file", side_effect=AssertionError("idle tick hashed media")):
                    self.assertFalse(objects.analyze_step(root, io_context=io_context))
                    self.assertFalse(objects.analyze_step(root, io_context=io_context))
                self.assertEqual(detected, [])

                # The photo changes on disk and the catalog notices (rescan): analyzed again.
                fresh.write_bytes(b"fresh bytes, edited")
                st = fresh.stat()
                os.utime(fresh, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
                items["fresh"] = dict(items["fresh"], locations=[{"current": True, "sizeBytes": 19}])
                self.assertTrue(objects.analyze_step(root, io_context=io_context))
                self.assertEqual(detected, ["fresh.jpg"])
                self.assertFalse(objects.analyze_step(root, io_context=io_context))


if __name__ == "__main__":
    unittest.main()
