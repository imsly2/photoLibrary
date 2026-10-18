"""Focused checks for benchmark measurement completion and JSON schema."""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock

from tests.perf import bench


class BenchMeasurementTests(unittest.TestCase):
    def _photo(self, item_id: str, preview_status: str = "ready") -> dict:
        renditions = {
            "store": "with-server",
            "status": {
                "thumb": "ready",
                "preview": preview_status,
                "poster": "not-applicable",
                "proxy": "not-applicable",
                "playback": "not-applicable",
            },
            "thumb": f"renditions/{item_id}/thumb.webp",
            "preview": f"renditions/{item_id}/preview.webp",
        }
        return {"id": item_id, "kind": "photo", "renditions": renditions}

    def test_ready_completion_requires_nonempty_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library-data"
            fixture = root / "fixture"
            (library / "renditions" / "one").mkdir(parents=True)
            fixture.mkdir()
            item = self._photo("one")
            (library / item["renditions"]["thumb"]).write_bytes(b"thumb")
            (library / item["renditions"]["preview"]).write_bytes(b"preview")
            result = bench._rendition_completion([item], 1, library, fixture)
            self.assertTrue(result["terminal"])
            self.assertTrue(result["successful"])
            self.assertEqual(result["slotCounts"]["notApplicable"], 3)

            (library / item["renditions"]["preview"]).unlink()
            result = bench._rendition_completion([item], 1, library, fixture)
            self.assertTrue(result["terminal"])
            self.assertFalse(result["successful"])
            self.assertEqual(result["nonemptyFileFailures"], [{"itemId": "one", "slot": "preview"}])

    def test_error_is_terminal_but_never_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library-data"
            fixture = root / "fixture"
            thumb = library / "renditions" / "one" / "thumb.webp"
            thumb.parent.mkdir(parents=True)
            fixture.mkdir()
            thumb.write_bytes(b"thumb")
            result = bench._rendition_completion(
                [self._photo("one", preview_status="error")], 1, library, fixture
            )
            self.assertTrue(result["terminal"])
            self.assertFalse(result["successful"])
            self.assertEqual(result["slotCounts"]["error"], 1)

    def test_required_photo_slot_cannot_be_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library-data"
            fixture = root / "fixture"
            output_dir = library / "renditions" / "one"
            output_dir.mkdir(parents=True)
            fixture.mkdir()
            item = self._photo("one")
            item["renditions"]["status"]["thumb"] = "not-applicable"
            (output_dir / "thumb.webp").write_bytes(b"thumb")
            (output_dir / "preview.webp").write_bytes(b"preview")

            result = bench._rendition_completion([item], 1, library, fixture)
            self.assertTrue(result["terminal"])
            self.assertFalse(result["successful"])
            self.assertEqual(result["invalidNotApplicable"], [{"itemId": "one", "slot": "thumb"}])

    def test_video_playback_not_applicable_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library-data"
            fixture = root / "fixture"
            output_dir = library / "renditions" / "clip"
            output_dir.mkdir(parents=True)
            fixture.mkdir()
            item = {
                "id": "clip",
                "kind": "video",
                "renditions": {
                    "poster": "renditions/clip/poster.webp",
                    "proxy": "renditions/clip/proxy.mp4",
                    "status": {
                        "thumb": "not-applicable",
                        "preview": "not-applicable",
                        "poster": "ready",
                        "proxy": "ready",
                        "playback": "not-applicable",
                    },
                },
            }
            (output_dir / "poster.webp").write_bytes(b"poster")
            (output_dir / "proxy.mp4").write_bytes(b"proxy")

            result = bench._rendition_completion([item], 1, library, fixture)
            self.assertTrue(result["terminal"])
            self.assertTrue(result["successful"])
            self.assertEqual(result["invalidNotApplicable"], [])

    def test_measurement_schema_serializes_latency_and_reading_fields(self) -> None:
        state = bench.RunState()
        state.milestones.t0 = 100.0
        state.file_read_at = {"a.jpg": 101.0}
        state.file_read_bytes = {"a.jpg": 123}
        state.job_latency_samples = [{"tRelSec": 1.0, "ms": 12.5}]
        state.items_latency_samples = [{"tRelSec": 1.0, "ms": 30.0}]
        state.api_counts = {"/api/jobs": {"samples": 1, "successes": 1, "failures": 0, "statuses": {"200": 1}}}
        state.rendition_completion = {"terminal": True, "successful": False}
        encoded = json.dumps(bench._measurement_schema(state))
        schema = json.loads(encoded)
        self.assertEqual(schema["latencyMs"]["jobs"]["n"], 1)
        self.assertEqual(schema["latencyMs"]["jobs"]["p95"], 12.5)
        self.assertEqual(schema["reading"]["files"], 1)
        self.assertEqual(schema["apiCounts"]["/api/jobs"]["failures"], 0)
        self.assertFalse(schema["renditionCompletion"]["successful"])

    def test_item_read_identity_keeps_same_named_files_distinct(self) -> None:
        a = {"filename": "IMG_1.JPG", "locations": [{"current": True, "pathFromVolumeRoot": "photos/a/IMG_1.JPG"}]}
        b = {"filename": "IMG_1.JPG", "locations": [{"current": True, "pathFromVolumeRoot": "photos/b/IMG_1.JPG"}]}
        self.assertNotEqual(bench._item_rel_key(a), bench._item_rel_key(b))

    def test_logged_child_can_write_beyond_pipe_capacity(self) -> None:
        with tempfile.TemporaryDirectory(dir=bench.BENCH_ROOT) as tmp:
            root = Path(tmp)
            stdout_path = root / "server.stdout.log"
            stderr_path = root / "server.stderr.log"
            child_code = (
                "import sys; sys.stdout.write('x' * 262144); sys.stdout.flush(); "
                "sys.stderr.write('child diagnostic\\n'); sys.stderr.flush()"
            )
            proc = bench._popen_logged(
                [sys.executable, "-c", child_code],
                cwd=Path.cwd(),
                env=os.environ.copy(),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            self.assertEqual(proc.wait(timeout=10), 0)
            self.assertEqual(stdout_path.stat().st_size, 262144)
            self.assertIn("child diagnostic", stderr_path.read_text(encoding="utf-8"))

    def test_tcp_listener_rejected_before_fixture_copy_without_http_check(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            with mock.patch.object(bench, "_ensure_fixture") as ensure_fixture:
                with redirect_stderr(StringIO()):
                    result = bench.run_bench(
                        1, "port-check", Path.cwd(), port, keep=False, load="ui"
                    )
                self.assertEqual(result, 2)
                ensure_fixture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
