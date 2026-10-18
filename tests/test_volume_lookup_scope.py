from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from library import volumes


class VolumeLookupScopeTests(unittest.TestCase):
    def test_native_mount_is_cached_only_inside_one_scope(self) -> None:
        serial = "windows:12345678"
        first = Path("M:/")
        with (
            patch.object(volumes.os, "name", "nt"),
            patch.object(volumes, "load_test_volumes", return_value=None),
            patch.object(volumes, "_windows_mount_for_serial", side_effect=[first, None]) as lookup,
        ):
            with volumes.volume_lookup_scope():
                self.assertEqual(volumes.resolve_volume_mount(serial), first)
                self.assertEqual(volumes.resolve_volume_mount(serial), first)
                self.assertEqual(lookup.call_count, 1)
            with volumes.volume_lookup_scope():
                self.assertIsNone(volumes.resolve_volume_mount(serial))
                self.assertIsNone(volumes.resolve_volume_mount(serial))
                self.assertEqual(lookup.call_count, 2)


if __name__ == "__main__":
    unittest.main()
