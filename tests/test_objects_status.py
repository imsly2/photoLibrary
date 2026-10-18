from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from library import objects
from library.jobs import jobs_status


class ObjectsStatusTests(unittest.TestCase):
    def test_status_uses_recorded_identity_without_hashing_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "models").mkdir()
            (root / "models" / "objects-state.json").write_text(
                json.dumps({"schemaVersion": 1, "items": {"done-id": {"sha256": "legacy-digest", "names": []}}}),
                encoding="utf-8",
            )
            items = {
                "done-id": {"kind": "photo"},
                "pending-id": {"kind": "photo"},
            }
            with (
                patch.object(objects, "model_installed", return_value=True),
                patch.object(objects, "iter_item_ids", return_value=list(items)),
                patch.object(objects, "load_item", side_effect=lambda _root, item_id: items[item_id]),
                patch.object(objects, "_still_for_detect", return_value=Path("unused.jpg")),
                patch.object(objects, "sha256_file", side_effect=AssertionError("status hashed media")),
                patch("library.jobs._rendition_counts", return_value=(0, 0, 0)),
                patch("library.jobs._faces_counts", return_value=(0, 0, 0)),
                patch("library.jobs._analyze_counts", return_value=(0, 0, 0)),
                patch("library.jobs._module_available", return_value=False),
                patch("library.jobs.iter_item_ids", return_value=list(items)),
                patch("library.jobs.load_item", side_effect=lambda _root, item_id: items[item_id]),
            ):
                self.assertEqual(objects.analyze_status(root)["pending"], 1)
                status = jobs_status(root, paused=False)
                objects_queue = next(queue for queue in status["queues"] if queue["id"] == "objects")
                self.assertEqual(objects_queue["pending"], 1)
                self.assertEqual(objects_queue["done"], 1)


if __name__ == "__main__":
    unittest.main()
