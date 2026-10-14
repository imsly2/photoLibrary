"""Taste proof: Reveal selects the real on-disk file, not Documents."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

from library.errors import AppError
from library.favorites import (
    existing_original,
    open_containing_folder,
    windows_reveal_command,
)
from library.service import Library
from tests.qa.s00 import (
    PRODUCT_ROOT,
    Checks,
    assert_no_pillow_in_server,
    copy_committed_fixtures,
)
from tests.qa.s03 import find_item
from tests.qa.s05 import pin_media_from_manifest
from tests.qa.s08 import fresh_root, write_result
from tests.qa.s09 import copy_s09_media

SELECT_PREFIX = 'explorer.exe /select,"'


def parse_select_path(command: str) -> str:
    if not command.startswith(SELECT_PREFIX) or not command.endswith('"'):
        return ""
    return command[len(SELECT_PREFIX) : -1]


def prove_command_form(checks: Checks) -> None:
    windows = Path(r"C:\Family Photos\Vacation 2024\IMG_1042.jpg")
    command = windows_reveal_command(windows)
    checks.check(
        "command-windows-spaces",
        command == r'explorer.exe /select,"C:\Family Photos\Vacation 2024\IMG_1042.jpg"',
        command,
    )
    posix = Path("/tmp/Family Photos/Vacation 2024/clip.mp4")
    posix_cmd = windows_reveal_command(posix)
    checks.check(
        "command-quoted-fullpath",
        posix_cmd.startswith(SELECT_PREFIX) and posix_cmd.endswith('"'),
        posix_cmd,
    )
    selected = parse_select_path(posix_cmd)
    checks.check(
        "command-selects-file-not-folder",
        selected.endswith("clip.mp4") and "Vacation 2024" in selected,
        selected,
    )
    checks.check(
        "command-not-documents",
        "Documents" not in selected,
        selected,
    )


def prove_existing_original(checks: Checks, workspace: Path) -> Path:
    folder = workspace / "Family Photos" / "Vacation 2024"
    folder.mkdir(parents=True)
    photo = folder / "IMG_1042.jpg"
    photo.write_bytes(b"jpeg-bytes")
    found = existing_original(photo)
    checks.check(
        "existing-absolute",
        found is not None and found.is_absolute() and found.is_file() and found.name == "IMG_1042.jpg",
        str(found),
    )
    checks.check(
        "existing-rejects-missing",
        existing_original(folder / "gone.jpg") is None,
    )
    checks.check(
        "existing-rejects-directory",
        existing_original(folder) is None,
    )
    checks.check(
        "existing-rejects-catalog-relative",
        existing_original(Path("originals/source/photo.jpg")) is None,
    )
    return photo


def prove_open_containing(checks: Checks, photo: Path) -> None:
    calls: list[Any] = []

    def fake_popen(*args: Any, **kwargs: Any) -> object:
        calls.append((args, kwargs))
        return object()

    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites.os.name", "nt"):
            opened = open_containing_folder(photo)
    checks.check("open-windows-returns-true", opened is True)
    checks.check("open-windows-one-launch", len(calls) == 1, str(calls))
    command = calls[0][0][0] if calls and calls[0][0] else ""
    selected = parse_select_path(str(command))
    checks.check(
        "open-windows-select-command",
        str(command).startswith(SELECT_PREFIX) and str(command).endswith('"'),
        str(command),
    )
    checks.check(
        "open-windows-selects-real-file",
        Path(selected) == photo.resolve() if selected else False,
        json.dumps({"command": str(command), "photo": str(photo.resolve())}),
    )
    checks.check(
        "open-windows-not-documents",
        "Documents" not in str(command) or "Documents" in str(photo),
        str(command),
    )

    calls.clear()
    missing = photo.parent / "missing-original.jpg"
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites.os.name", "nt"):
            opened_missing = open_containing_folder(missing)
    checks.check("open-missing-false", opened_missing is False)
    checks.check("open-missing-no-explorer", calls == [], str(calls))

    calls.clear()
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites.os.name", "nt"):
            opened_rel = open_containing_folder(Path("originals/src/photo.jpg"))
    checks.check("open-relative-false", opened_rel is False)
    checks.check("open-relative-no-explorer", calls == [], str(calls))


def _scan_folder(root: Path, folder: Path, commands: list[str], *, copy_here: bool) -> dict[str, Any]:
    flag = "--copy-here" if copy_here else "--serve-from-there"
    from tests.qa.s00 import run_library

    proc = run_library(root, ["scan", str(folder), flag], timeout=180)
    commands.append(f"python -m library scan <folder> {flag}")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return {"proc": proc}


def prove_library_reveal(checks: Checks, root: Path, artifacts: Path, commands: list[str]) -> None:
    sandbox = artifacts / "fixture-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    copy_committed_fixtures(sandbox)
    media_src = sandbox / "media"
    pin_media_from_manifest(media_src)

    spaced = artifacts / "Family Photos" / "Vacation 2024"
    if spaced.exists():
        shutil.rmtree(spaced)
    spaced.mkdir(parents=True)
    photo = spaced / "IMG_1042.jpg"
    shutil.copy2(media_src / "a" / "IMG_1042.jpg", photo)
    pin_media_from_manifest(spaced)

    linked_root = fresh_root(root)
    _scan_folder(linked_root, spaced, commands, copy_here=False)
    linked = Library(linked_root)
    items = linked.items_list({})
    item = find_item(items, "IMG_1042.jpg")
    checks.check("linked-item", item is not None, json.dumps(items)[:400])
    if item is None:
        return

    calls: list[Any] = []

    def fake_popen(*args: Any, **kwargs: Any) -> object:
        calls.append((args, kwargs))
        return object()

    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites.os.name", "nt"):
            body = linked.reveal(item["id"])
    checks.check("linked-reveal-opened", body.get("opened") is True, json.dumps(body))
    reveal_path = Path(body.get("path") or "")
    reveal_folder = Path(body.get("folder") or "")
    checks.check(
        "linked-reveal-absolute-file",
        reveal_path.is_absolute() and reveal_path.is_file() and reveal_path.resolve() == photo.resolve(),
        json.dumps(body),
    )
    checks.check(
        "linked-reveal-folder-is-parent",
        reveal_folder.resolve() == photo.parent.resolve(),
        json.dumps(body),
    )
    command = calls[0][0][0] if calls and calls[0][0] else ""
    selected = parse_select_path(str(command))
    checks.check(
        "linked-reveal-explorer-select",
        selected != "" and Path(selected).resolve() == photo.resolve(),
        str(command),
    )
    checks.check(
        "linked-reveal-not-documents",
        "Documents" not in str(reveal_folder) and "Documents" not in str(command),
        json.dumps({"folder": str(reveal_folder), "command": str(command)}),
    )

    photo.unlink()
    calls.clear()
    missing_error = None
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites.os.name", "nt"):
            try:
                linked.reveal(item["id"])
            except AppError as exc:
                missing_error = exc
    checks.check(
        "missing-raises-unavailable",
        missing_error is not None and missing_error.code == "unavailable",
        str(missing_error),
    )
    checks.check("missing-no-explorer", calls == [], str(calls))

    copy_media = artifacts / "copy-media"
    copy_s09_media(media_src, copy_media)
    copy_root = fresh_root(artifacts / "copy-root")
    _scan_folder(copy_root, copy_media / "a", commands, copy_here=True)
    copied = Library(copy_root)
    copy_items = copied.items_list({})
    copy_item = find_item(copy_items, "IMG_1042.jpg")
    checks.check("copy-item", copy_item is not None, json.dumps(copy_items)[:400])
    if copy_item is None:
        return
    calls.clear()
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites.os.name", "nt"):
            copy_body = copied.reveal(copy_item["id"])
    copy_path = Path(copy_body.get("path") or "")
    checks.check(
        "copy-reveal-absolute-under-originals",
        copy_path.is_absolute()
        and copy_path.is_file()
        and "originals" in copy_path.parts
        and copy_path.name == "IMG_1042.jpg",
        json.dumps(copy_body),
    )
    rel = None
    for loc in copy_item.get("locations") or []:
        if loc.get("libraryRelativePath"):
            rel = loc.get("libraryRelativePath")
            break
    checks.check(
        "copy-catalog-path-is-relative",
        type(rel) is str and not Path(rel).is_absolute(),
        str(rel),
    )
    checks.check(
        "copy-reveal-not-catalog-relative",
        str(copy_path) != rel and copy_path.is_absolute(),
        json.dumps({"path": str(copy_path), "catalog": rel}),
    )
    copy_command = calls[0][0][0] if calls and calls[0][0] else ""
    copy_selected = parse_select_path(str(copy_command))
    checks.check(
        "copy-reveal-explorer-selects-copy",
        copy_selected != "" and Path(copy_selected).resolve() == copy_path.resolve(),
        str(copy_command),
    )


def prove_static_source(checks: Checks) -> None:
    favorites = (PRODUCT_ROOT / "library" / "favorites.py").read_text(encoding="utf-8")
    page = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
    spec = (PRODUCT_ROOT / "docs" / "UI-SPEC.md").read_text(encoding="utf-8")
    checks.check(
        "source-uses-explorer-select-quoted",
        'explorer.exe /select,"' in favorites and 'f"/select,{path}"' not in favorites,
        "favorites.py command form",
    )
    checks.check(
        "source-no-list-form-explorer",
        '["explorer"' not in favorites and '["explorer.exe"' not in favorites,
        "favorites.py argv",
    )
    checks.check(
        "source-ui-shows-missing-error",
        "showRevealFailed" in page and "Original is not on this computer" in page,
        "library.js reveal error",
    )
    checks.check(
        "source-ui-does-not-swallow-reveal",
        "showRevealFailed();" in page and page.count("showRevealFailed") >= 2,
        "library.js reveal handler",
    )
    checks.check(
        "uispec-reveal-selects-file",
        'explorer.exe /select,"fullpath"' in spec and "never Documents" in spec,
        "UI-SPEC checklist 15",
    )


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    commands: list[str] = []
    artifacts.mkdir(parents=True, exist_ok=True)
    assert_no_pillow_in_server(checks)
    prove_command_form(checks)
    photo = prove_existing_original(checks, artifacts / "unit-files")
    prove_open_containing(checks, photo)
    prove_library_reveal(checks, root, artifacts, commands)
    prove_static_source(checks)
    extra = {
        "unit-files": str(artifacts / "unit-files"),
        "copy-root": str(artifacts / "copy-root"),
    }
    return write_result("TASTE-REVEAL", "slice", checks, artifacts, commands, extra)
