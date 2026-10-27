"""Import iPhone finds tools/iphone and refuses a bad destination."""

from __future__ import annotations

from pathlib import Path

import pytest

from library.iphone_import import _destination, tool_root


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
