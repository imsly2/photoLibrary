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
    windows_reveal_select_arg,
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

SELECT_PREFIX = "/select,"
IPHONE_BACKUP = Path(r"J:\Iphone Backup\Another Rope Swing.MOV")


def parse_select_path(command: object) -> str:
    if isinstance(command, (list, tuple)) and len(command) >= 2:
        arg = str(command[1])
        if arg.startswith(SELECT_PREFIX):
            return arg[len(SELECT_PREFIX) :]
        return ""
    text = str(command)
    if text.startswith(SELECT_PREFIX):
        return text[len(SELECT_PREFIX) :]
    return ""


def prove_command_form(checks: Checks) -> None:
    windows = Path(r"C:\Family Photos\Vacation 2024\IMG_1042.jpg")
    command = windows_reveal_command(windows)
    checks.check(
        "command-is-argv-list",
        isinstance(command, list) and command[0] == "explorer.exe" and len(command) == 2,
        json.dumps(command) if isinstance(command, list) else str(command),
    )
    checks.check(
        "command-windows-spaces",
        command == ["explorer.exe", r"/select,C:\Family Photos\Vacation 2024\IMG_1042.jpg"],
        json.dumps(command) if isinstance(command, list) else str(command),
    )
    iphone = windows_reveal_command(IPHONE_BACKUP)
    iphone_arg = iphone[1] if isinstance(iphone, list) and len(iphone) > 1 else ""
    checks.check(
        "command-iphone-backup-spaces",
        iphone == ["explorer.exe", r"/select,J:\Iphone Backup\Another Rope Swing.MOV"],
        json.dumps(iphone) if isinstance(iphone, list) else str(iphone),
    )
    checks.check(
        "command-select-arg-has-no-quotes",
        '"' not in iphone_arg and "'" not in iphone_arg and " " in iphone_arg,
        iphone_arg,
    )
    checks.check(
        "command-comma-glued",
        iphone_arg.startswith("/select,J:") and "Iphone Backup" in iphone_arg,
        iphone_arg,
    )
    posix = Path("/tmp/Iphone Backup/Another Rope Swing.MOV")
    posix_cmd = windows_reveal_command(posix)
    checks.check(
        "command-posix-argv",
        isinstance(posix_cmd, list) and posix_cmd[0] == "explorer.exe" and posix_cmd[1].startswith(SELECT_PREFIX),
        json.dumps(posix_cmd) if isinstance(posix_cmd, list) else str(posix_cmd),
    )
    selected = parse_select_path(posix_cmd)
    checks.check(
        "command-selects-file-not-folder",
        selected.endswith("Another Rope Swing.MOV") and "Iphone Backup" in selected,
        selected,
    )
    checks.check(
        "command-not-documents",
        "Documents" not in selected and "Documents" not in json.dumps(posix_cmd),
        selected,
    )
    checks.check(
        "select-arg-helper",
        windows_reveal_select_arg(IPHONE_BACKUP) == r"/select,J:\Iphone Backup\Another Rope Swing.MOV",
        windows_reveal_select_arg(IPHONE_BACKUP),
    )


def prove_existing_original(checks: Checks, workspace: Path) -> Path:
    if workspace.exists():
        shutil.rmtree(workspace)
    folder = workspace / "Iphone Backup"
    folder.mkdir(parents=True)
    photo = folder / "Another Rope Swing.MOV"
    photo.write_bytes(b"mov-bytes")
    found = existing_original(photo)
    checks.check(
        "existing-absolute",
        found is not None and found.is_absolute() and found.is_file() and found.name == "Another Rope Swing.MOV",
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
        with patch("library.favorites._windows", return_value=True):
            opened = open_containing_folder(photo)
    checks.check("open-windows-returns-true", opened is True)
    checks.check("open-windows-one-launch", len(calls) == 1, str(calls))
    command = calls[0][0][0] if calls and calls[0][0] else ""
    selected = parse_select_path(command)
    checks.check(
        "open-windows-select-command",
        isinstance(command, list)
        and command[0] == "explorer.exe"
        and str(command[1]).startswith(SELECT_PREFIX)
        and '"' not in str(command[1]),
        json.dumps(command) if isinstance(command, list) else str(command),
    )
    checks.check(
        "open-windows-selects-real-file",
        Path(selected) == photo.resolve() if selected else False,
        json.dumps({"command": command, "photo": str(photo.resolve())}, default=str),
    )
    checks.check(
        "open-windows-spaces-in-arg",
        "Iphone Backup" in selected and "Another Rope Swing.MOV" in selected,
        selected,
    )
    checks.check(
        "open-windows-not-documents",
        "Documents" not in selected and "Documents" not in json.dumps(command, default=str),
        json.dumps(command, default=str),
    )

    calls.clear()
    missing = photo.parent / "missing-original.jpg"
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites._windows", return_value=True):
            opened_missing = open_containing_folder(missing)
    checks.check("open-missing-false", opened_missing is False)
    checks.check("open-missing-no-explorer", calls == [], str(calls))

    calls.clear()
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites._windows", return_value=True):
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

    spaced = artifacts / "Iphone Backup"
    if spaced.exists():
        shutil.rmtree(spaced)
    spaced.mkdir(parents=True)
    photo = spaced / "Another Rope Swing.MOV"
    shutil.copy2(media_src / "a" / "clip.mp4", photo)
    pin_media_from_manifest(spaced)

    linked_root = fresh_root(root)
    _scan_folder(linked_root, spaced, commands, copy_here=False)
    linked = Library(linked_root)
    items = linked.items_list({})
    item = find_item(items, "Another Rope Swing.MOV")
    checks.check("linked-item", item is not None, json.dumps(items)[:400])
    if item is None:
        return

    calls: list[Any] = []

    def fake_popen(*args: Any, **kwargs: Any) -> object:
        calls.append((args, kwargs))
        return object()

    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites._windows", return_value=True):
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
    selected = parse_select_path(command)
    checks.check(
        "linked-reveal-explorer-select",
        selected != "" and Path(selected).resolve() == photo.resolve(),
        json.dumps(command, default=str),
    )
    checks.check(
        "linked-reveal-argv-no-quotes",
        isinstance(command, list) and command[0] == "explorer.exe" and '"' not in str(command[1]),
        json.dumps(command, default=str),
    )
    checks.check(
        "linked-reveal-iphone-backup-spaces",
        "Iphone Backup" in selected and "Another Rope Swing.MOV" in selected,
        selected,
    )
    checks.check(
        "linked-reveal-not-documents",
        "Documents" not in str(reveal_folder) and "Documents" not in json.dumps(command, default=str),
        json.dumps({"folder": str(reveal_folder), "command": command}, default=str),
    )

    photo.unlink()
    calls.clear()
    missing_error = None
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites._windows", return_value=True):
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

    copy_media = artifacts / "copy-media" / "a"
    if copy_media.exists():
        shutil.rmtree(copy_media)
    copy_media.mkdir(parents=True)
    shutil.copy2(media_src / "a" / "IMG_1042.jpg", copy_media / "IMG_1042.jpg")
    pin_media_from_manifest(copy_media.parent)
    copy_root = fresh_root(artifacts / "copy-root")
    _scan_folder(copy_root, copy_media, commands, copy_here=True)
    copied = Library(copy_root)
    copy_items = copied.items_list({})
    copy_item = find_item(copy_items, "IMG_1042.jpg")
    checks.check("copy-item", copy_item is not None, json.dumps(copy_items)[:400])
    if copy_item is None:
        return
    calls.clear()
    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites._windows", return_value=True):
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
    copy_selected = parse_select_path(copy_command)
    checks.check(
        "copy-reveal-explorer-selects-copy",
        copy_selected != "" and Path(copy_selected).resolve() == copy_path.resolve(),
        json.dumps(copy_command, default=str),
    )
    checks.check(
        "copy-reveal-argv-list",
        isinstance(copy_command, list) and copy_command[0] == "explorer.exe" and '"' not in str(copy_command[1]),
        json.dumps(copy_command, default=str),
    )


def prove_last_known_fallback(checks: Checks, artifacts: Path, commands: list[str]) -> None:
    from library.atomic import atomic_write_json
    from library.catalog_io import load_item
    from library.records import ordered_item

    sandbox = artifacts / "fixture-sandbox" / "media" / "a"
    src = sandbox / "IMG_1042.jpg"
    if not src.is_file():
        checks.check("last-known-source-photo", False, str(src))
        return
    folder = artifacts / "last-known-folder"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    photo = folder / "Keep Me.jpg"
    shutil.copy2(src, photo)
    pin_media_from_manifest(folder)
    lib_root = fresh_root(artifacts / "last-known-root")
    _scan_folder(lib_root, folder, commands, copy_here=False)
    lib = Library(lib_root)
    item = find_item(lib.items_list({}), "Keep Me.jpg")
    checks.check("last-known-item", item is not None, "Keep Me.jpg")
    if item is None:
        return
    rec = load_item(lib_root, item["id"])
    for loc in rec.get("locations") or []:
        loc["volumeSerial"] = "linux:/not-mounted-here"
        loc["lastKnownPath"] = str(photo.resolve())
    atomic_write_json(lib_root / "catalog" / "items" / f"{item['id']}.json", ordered_item(rec))
    calls: list[Any] = []

    def fake_popen(*args: Any, **kwargs: Any) -> object:
        calls.append((args, kwargs))
        return object()

    with patch("library.favorites.subprocess.Popen", fake_popen):
        with patch("library.favorites._windows", return_value=True):
            body = lib.reveal(item["id"])
    reveal_path = Path(body.get("path") or "")
    checks.check("last-known-opened", body.get("opened") is True, json.dumps(body))
    checks.check(
        "last-known-selects-file",
        reveal_path.is_file() and reveal_path.resolve() == photo.resolve(),
        json.dumps(body),
    )
    command = calls[0][0][0] if calls and calls[0][0] else ""
    selected = parse_select_path(command)
    checks.check(
        "last-known-explorer-select",
        selected != "" and Path(selected).resolve() == photo.resolve(),
        json.dumps(command, default=str),
    )
    checks.check(
        "last-known-not-documents",
        "Documents" not in selected and "Documents" not in json.dumps(body),
        selected,
    )


def prove_static_source(checks: Checks) -> None:
    favorites = (PRODUCT_ROOT / "library" / "favorites.py").read_text(encoding="utf-8")
    page = (PRODUCT_ROOT / "library" / "web" / "assets" / "library.js").read_text(encoding="utf-8")
    html = (PRODUCT_ROOT / "library" / "web" / "index.html").read_text(encoding="utf-8")
    spec = (PRODUCT_ROOT / "docs" / "UI-SPEC.md").read_text(encoding="utf-8")
    checks.check(
        "source-uses-explorer-select-argv",
        '["explorer.exe"' in favorites
        and "/select," in favorites
        and 'explorer.exe /select,"' not in favorites,
        "favorites.py command form",
    )
    checks.check(
        "source-list-form-glued-select",
        'f"/select,{text}"' in favorites or 'f"/select,{path}"' in favorites or 'windows_reveal_select_arg' in favorites,
        "favorites.py glued select arg",
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
        ("/select,fullpath" in spec or "/select,fullpath" in spec.replace(" ", ""))
        and "never Documents" in spec
        and "argv" in spec,
        "UI-SPEC checklist 15",
    )
    checks.check(
        "source-volume-chrome",
        'id="viewer-mute"' in html and 'id="viewer-volume"' in html and "applyViewerVolume" in page,
        "mute + volume beside scrub",
    )
    checks.check(
        "source-hover-stays-muted",
        "video.muted = true" in page and "video.volume = 0" in page,
        "grid hover proxy stays silent",
    )
    checks.check(
        "uispec-volume-beside-scrub",
        "#viewer-mute" in spec and "#viewer-volume" in spec and "hover proxies stay" in spec,
        "UI-SPEC scrub volume",
    )
    checks.check(
        "source-viewer-source-chrome",
        'id="viewer-source"' in html
        and "setVideoSourceState" in page
        and "Loading full…" in page
        and 'full: "Full"' in page
        and "Preview — full unavailable" in page
        and "resumeHoverIfNeeded" in page,
        "viewer source + hover resume",
    )
    checks.check(
        "source-hover-allows-years-months",
        "function hoverAllowed" in page
        and 'policy === "off"' in page
        and 'return level === "days" || level === "all"' not in page
        and "playProxies" in page,
        "dated Years/Months hover-play under the default",
    )
    checks.check(
        "uispec-viewer-source",
        "#viewer-source" in spec
        and "Loading full" in spec
        and "Original / Full" in spec
        and "Preview — full unavailable" in spec,
        "UI-SPEC source chrome",
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
    prove_last_known_fallback(checks, artifacts, commands)
    prove_static_source(checks)
    extra = {
        "unit-files": str(artifacts / "unit-files"),
        "copy-root": str(artifacts / "copy-root"),
    }
    return write_result("TASTE-REVEAL", "slice", checks, artifacts, commands, extra)
