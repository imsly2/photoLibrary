from __future__ import annotations

import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from library import media


class FfmpegRunnerTests(unittest.TestCase):
    def test_hung_child_is_killed_and_reported_as_failure(self) -> None:
        # A child that never writes and never exits: what the live server's
        # rating decode turned into when ffmpeg blocked on an unread pipe.
        started = time.perf_counter()
        proc = media.run_ffmpeg([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.5)
        took = time.perf_counter() - started
        self.assertEqual(proc.returncode, media.TIMEOUT_RETURNCODE)
        self.assertEqual(proc.stdout, b"")
        self.assertLess(took, 10.0)

    def test_output_is_captured_and_returncode_passed_through(self) -> None:
        proc = media.run_ffmpeg(
            [sys.executable, "-c", "import sys; sys.stdout.write('hi'); sys.exit(3)"],
            text=True,
        )
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "hi")

    def test_ffmpeg_gets_nostdin_and_a_closed_stdin(self) -> None:
        seen: dict = {}

        class FakeProc:
            returncode = 0

            def communicate(self, timeout=None):
                return b"", b""

        def fake_popen(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs
            return FakeProc()

        with patch.object(subprocess, "Popen", fake_popen):
            media.run_ffmpeg(["ffmpeg", "-y", "-i", "in.jpg", "out.webp"])
        self.assertEqual(seen["cmd"][:2], ["ffmpeg", "-nostdin"])
        self.assertEqual(seen["kwargs"]["stdin"], subprocess.DEVNULL)
        with patch.object(subprocess, "Popen", fake_popen):
            media.run_ffmpeg(["ffprobe", "-v", "error", "in.jpg"])
        self.assertNotIn("-nostdin", seen["cmd"])


if __name__ == "__main__":
    unittest.main()
