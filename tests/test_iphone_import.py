"""Import iPhone finds tools/iphone and refuses a bad destination."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from library.iphone_import import _RollProgress, _destination, _file_mix, job, tool_root


def test_tool_root_uses_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = tmp_path / "ui-host" / "bin" / "Release" / "net10.0" / "win-x64" / "iphone-photos-host.exe"
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    match = tmp_path / "ui" / "match.py"
    match.parent.mkdir()
    match.write_text("# match\n", encoding="utf-8")
    monkeypatch.setenv("LIBRARY_IPHONE_TOOL", str(tmp_path))
    assert tool_root() == tmp_path


def test_destination_rejects_a_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        _destination(str(target))


def test_destination_creates_a_folder(tmp_path: Path) -> None:
    dest = _destination(str(tmp_path / "roll"))
    assert dest.is_dir()


def test_status_requires_the_explorer_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = tmp_path / "ui-host" / "bin" / "Release" / "net10.0" / "win-x64" / "iphone-photos-host.exe"
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    match = tmp_path / "ui" / "match.py"
    match.parent.mkdir()
    match.write_text("# match\n", encoding="utf-8")
    monkeypatch.setenv("LIBRARY_IPHONE_TOOL", str(tmp_path))
    assert tool_root() == tmp_path
    from library.iphone_import import status

    missing = status()
    assert missing["installed"] is False
    (tmp_path / "ExplorerLayout.ps1").write_text("# reader\n", encoding="utf-8")
    ready = status()
    assert ready["installed"] is True


def test_roll_counts_pictures_and_compares_before_the_walk_finishes() -> None:
    ready = threading.Event()
    ready.set()
    box = {"locals": {"201508_a/img_0519.jpg": ("201508_a/IMG_0519.JPG", 10)}}

    def action(rel, size, locals_by_path, name_sizes=None):
        found = locals_by_path.get(rel.replace("\\", "/").casefold())
        if found is not None and found[1] == size:
            return "skip"
        if found is not None:
            return "keep"
        return "copy"

    progress = _RollProgress(ready, box, action)
    progress.on_row({"reading": "201508_a", "found": 1})
    progress.on_row({"reading": "201508_a", "found": 2})
    progress.on_row({"rel": "201508_a/IMG_0519.JPG", "size": 10})
    progress.on_row({"rel": "201508_a/IMG_0002.JPG", "size": 4})
    snap = job()
    assert snap["onPhone"] == 2
    assert snap["bytes"] == 14
    assert snap["skip"] == 1
    assert snap["willCopy"] == 1
    assert snap["comparing"] is False
    assert "2 pictures" in snap["message"]
    assert "1 already here" in snap["message"]
    assert "This folder has 2 items so far." in snap["message"]


def test_roll_compares_pictures_that_arrived_before_the_folder_index() -> None:
    ready = threading.Event()
    box: dict = {}

    def action(rel, size, locals_by_path, name_sizes=None):
        found = locals_by_path.get(rel.replace("\\", "/").casefold())
        if found is not None and found[1] == size:
            return "skip"
        if found is not None:
            return "keep"
        return "copy"

    progress = _RollProgress(ready, box, action)
    progress.on_row({"rel": "201508_a/IMG_0002.JPG", "size": 4})
    assert job()["onPhone"] == 1
    assert job()["comparing"] is True
    assert "Checking this folder." in job()["message"]
    box["locals"] = {}
    ready.set()
    progress.flush()
    snap = job()
    assert snap["comparing"] is False
    assert snap["willCopy"] == 1
    assert "1 not here yet" in snap["message"]


def test_saved_look_is_only_the_folder_that_was_read(tmp_path: Path) -> None:
    from library import iphone_import as iphone

    dest = tmp_path / "roll"
    other = tmp_path / "other"
    dest.mkdir()
    other.mkdir()
    previous = iphone._last_look
    try:
        iphone._last_look = {
            "path": str(dest.resolve()),
            "name": "Apple iPhone",
            "files": [("201508_a/IMG_0001.JPG", 10)],
            "repeated": 0,
            "skipped": 0,
            "layout": "explorer",
        }
        assert iphone._saved_look(dest, "explorer")["name"] == "Apple iPhone"
        assert iphone._saved_look(dest, "month") is None
        assert iphone._saved_look(other, "explorer") is None
        iphone._last_look = {
            "path": str(dest.resolve()),
            "name": "Apple iPhone",
            "files": [],
            "repeated": 0,
            "skipped": 0,
            "layout": "explorer",
        }
        assert iphone._saved_look(dest, "explorer") is None
    finally:
        iphone._last_look = previous


def test_roll_wait_does_not_clear_the_pictures_already_found() -> None:
    ready = threading.Event()
    ready.set()
    box = {"locals": {}}

    def action(rel, size, locals_by_path, name_sizes=None):
        return "copy"

    progress = _RollProgress(ready, box, action)
    progress.on_row({"reading": "202512_a", "found": 40})
    progress.on_row({"rel": "202512_a/IMG_0001.JPG", "size": 8})
    progress._last_file = 0.0
    progress.on_row({"reading": "202512_a", "waitingMs": 12000})
    snap = job()
    assert snap["onPhone"] == 1
    assert snap["folderFound"] == 40
    assert snap["waitingMs"] == 12000
    assert snap["current"] == "202512_a"
    progress.on_row({"reading": "202512_a", "listMs": 18000, "files": 40, "sizeMs": 400})
    done = job()
    assert done["onPhone"] == 1
    assert done["folderFound"] == 40
    assert done["waitingMs"] == 0
    assert done["pace"]["listMs"] == 18000
    assert done["pace"]["sizeMs"] == 400
    assert done["pace"]["files"] == 40


def test_file_mix_separates_pictures_videos_and_edit_notes() -> None:
    text = _file_mix(
        [
            ("/DCIM/100APPLE/IMG_0001.HEIC", 2_000_000_000),
            ("/DCIM/100APPLE/IMG_0002.MOV", 500_000_000),
            ("/DCIM/100APPLE/IMG_0001.AAE", 1066),
        ]
    )
    assert text == "1 pictures, 1 videos, 1 edit notes, 2.5 GB"
