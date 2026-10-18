"""Relaxed scan transactions replay in commit order, and only on the scan thread."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from library.atomic import (
    holding_open_transactions,
    recover_transactions,
    relaxed_durability,
    transact,
)
from library.history import (
    batching_history,
    extend_current_operation,
    history_batching,
    load_entry,
    make_history_entry,
    plan_append,
)


def _commit(root: Path, tid: str, changes: list[dict], mtime_ns: int) -> None:
    tdir = root / ".transactions" / tid
    tdir.mkdir(parents=True)
    manifest = {"schemaVersion": 1, "id": tid, "state": "committed", "changes": changes}
    path = tdir / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    os.utime(path, ns=(mtime_ns, mtime_ns))


class RelaxedRecoveryTests(unittest.TestCase):
    def test_replay_follows_commit_order_not_directory_name(self) -> None:
        """Old 12-hex ids sort backwards here: ffff... was committed first, 0000... last.

        Name order would restore v1 and resurrect the deleted file. Recovery must
        follow manifest mtime for those ids, and the latest transaction wins.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _commit(
                root,
                "ffffffffaaaa",
                [
                    {"path": "catalog/items/versioned.json", "before": None, "after": {"v": 1}},
                    {"path": "catalog/items/removed.json", "before": None, "after": {"ok": True}},
                ],
                mtime_ns=1_000_000_000,
            )
            _commit(
                root,
                "000000000001",
                [
                    {
                        "path": "catalog/items/versioned.json",
                        "before": {"v": 1},
                        "after": {"v": 2},
                    },
                    {"path": "catalog/items/removed.json", "before": {"ok": True}, "after": None},
                ],
                mtime_ns=2_000_000_000,
            )
            self.assertLess("000000000001", "ffffffffaaaa")

            recover_transactions(root)

            versioned = json.loads((root / "catalog" / "items" / "versioned.json").read_text(encoding="utf-8"))
            self.assertEqual(versioned, {"v": 2})
            self.assertFalse((root / "catalog" / "items" / "removed.json").exists())
            self.assertFalse((root / ".transactions").exists())

    def test_relaxed_transactions_replay_latest_after_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with relaxed_durability():
                first = transact(
                    root,
                    [{"path": "catalog/items/versioned.json", "before": None, "after": {"v": 1}}],
                )
                second = transact(
                    root,
                    [{"path": "catalog/items/versioned.json", "before": {"v": 1}, "after": {"v": 2}}],
                )
                transact(
                    root,
                    [{"path": "catalog/items/removed.json", "before": None, "after": {"ok": True}}],
                )
                transact(
                    root,
                    [{"path": "catalog/items/removed.json", "before": {"ok": True}, "after": None}],
                )
            self.assertLess(first, second)
            self.assertTrue((root / ".transactions" / first).is_dir())

            recover_transactions(root)

            versioned = json.loads((root / "catalog" / "items" / "versioned.json").read_text(encoding="utf-8"))
            self.assertEqual(versioned, {"v": 2})
            self.assertFalse((root / "catalog" / "items" / "removed.json").exists())
            self.assertFalse((root / ".transactions").exists())

    def test_batching_does_not_leak_to_other_threads(self) -> None:
        seen: list[bool] = []

        def other() -> None:
            seen.append(history_batching())

        with batching_history():
            thread = threading.Thread(target=other)
            thread.start()
            thread.join()
            self.assertTrue(history_batching())
        self.assertEqual(seen, [False])

    def test_annotate_during_scan_stays_its_own_undo_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan_change = {"path": "catalog/sources/src_scan.json", "before": None, "after": {"id": "src_scan"}}
            scan_entry = make_history_entry(root, "scan", [scan_change])
            transact(root, plan_append(root, scan_entry) + [scan_change])
            note = {"path": "catalog/items/noted.json", "before": None, "after": {"faces": [{"personId": "ada"}]}}

            def annotate() -> None:
                entry = make_history_entry(root, "annotate", [note])
                transact(root, plan_append(root, entry) + [note])

            with holding_open_transactions(root), batching_history():
                thread = threading.Thread(target=annotate)
                thread.start()
                thread.join()
                later = {"path": "catalog/items/later.json", "before": None, "after": {"n": 1}}
                self.assertEqual(extend_current_operation(root, [later]), [later])

            scan = load_entry(root, scan_entry["id"])
            self.assertEqual([change["path"] for change in scan["changes"]], ["catalog/sources/src_scan.json"])
            annotated = load_entry(root, json.loads((root / "undo" / "state.json").read_text(encoding="utf-8"))["entries"][-1])
            self.assertEqual(annotated["operation"], "annotate")
            self.assertEqual([change["path"] for change in annotated["changes"]], ["catalog/items/noted.json"])

    def test_other_thread_transaction_is_durable_while_scan_manifests_stay(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mirrored: list[str] = []

            def capture(_root: Path, changes: list[dict]) -> None:
                mirrored.extend(change["path"] for change in changes)

            from library import portable

            original = portable.mirror_changes
            portable.mirror_changes = capture
            try:
                with holding_open_transactions(root), batching_history(), relaxed_durability():
                    scan_id = transact(
                        root,
                        [{"path": "catalog/items/scan.json", "before": None, "after": {"from": "scan"}}],
                    )

                    def publish() -> None:
                        transact(
                            root,
                            [{"path": "catalog/items/thumb.json", "before": None, "after": {"slot": "thumb"}}],
                        )

                    thread = threading.Thread(target=publish)
                    thread.start()
                    thread.join()
                    self.assertIn("catalog/items/thumb.json", mirrored)
                    self.assertTrue((root / "catalog" / "items" / "thumb.json").is_file())
                    self.assertTrue((root / ".transactions" / scan_id).is_dir())
                    self.assertEqual(len(list((root / ".transactions").iterdir())), 1)
            finally:
                portable.mirror_changes = original

    def test_other_thread_recover_leaves_relaxed_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with holding_open_transactions(root), relaxed_durability():
                transact(
                    root,
                    [{"path": "catalog/items/scan.json", "before": None, "after": {"from": "scan"}}],
                )
                before = sorted(path.name for path in (root / ".transactions").iterdir())

                def recover() -> None:
                    recover_transactions(root)

                thread = threading.Thread(target=recover)
                thread.start()
                thread.join()
                after = sorted(path.name for path in (root / ".transactions").iterdir())
            self.assertEqual(after, before)
            self.assertEqual(
                json.loads((root / "catalog" / "items" / "scan.json").read_text(encoding="utf-8")),
                {"from": "scan"},
            )

    def test_annotate_follows_pending_id_after_publication(self) -> None:
        """The list can observe a pending id during the hash pause. Publication then
        deletes that file before the annotate request runs. The annotation lands
        on the hash item instead of 404.
        """
        from library.annotate import apply_annotate
        from library.catalog_io import iter_item_ids, load_item
        from library.scan import scan_serve_from_there

        fixture = Path(__file__).resolve().parent / "fixtures" / "media" / "a" / "IMG_1042.jpg"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "library"
            folder = Path(temp) / "photos"
            folder.mkdir()
            shutil.copy2(fixture, folder / "IMG_1042.jpg")
            seen: list[str] = []

            def between() -> None:
                for item_id in iter_item_ids(root):
                    if item_id.startswith("pending-") and item_id not in seen:
                        seen.append(item_id)

            scan_serve_from_there(root, folder, between=between)
            self.assertTrue(seen)
            pending_id = seen[0]
            self.assertFalse((root / "catalog" / "items" / f"{pending_id}.json").is_file())
            annotated = apply_annotate(root, pending_id, {"people": [{"name": "Ada"}]})
            self.assertFalse(annotated["id"].startswith("pending-"))
            stored = load_item(root, annotated["id"])
            self.assertTrue(stored.get("faces"))


if __name__ == "__main__":
    unittest.main()
