#!/usr/bin/env python3
"""Build a lean photoLibrary zip for USB / family PCs.

Keep this file ASCII. The Windows wrapper (pack-deploy.ps1) may be read
as the system ANSI code page; this script is run by Python 3.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ZIP_ROOT = "photoLibrary"
ZIP_NAME = "photoLibrary-deploy.zip"

# Directory names skipped anywhere in the path (case-insensitive).
EXCLUDE_DIR_NAMES = frozenset(
    {
        ".venv",
        "venv",
        "library-data",
        ".git",
        "docs",
        "tests",
        ".qa",
        "tmp",
        "dist",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".cursor",
        ".github",
        "node_modules",
        "captureregion",
        ".claude",
        ".idea",
        ".vscode",
        ".agent",
    }
)

EXCLUDE_DIR_SUFFIXES = (".egg-info",)

EXCLUDE_FILE_NAMES = frozenset(
    {
        "thumbs.db",
        "desktop.ini",
        ".ds_store",
        ".library-revision.json",
        "agents.md",
        "claude.md",
    }
)

EXCLUDE_FILE_PREFIXES = ("captureregion",)
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo", ".pyd")

# Root launchers and metadata needed to extract and run Setup / Library / Update.
ROOT_ALWAYS = frozenset(
    {
        "setup.bat",
        "setup.ps1",
        "library.bat",
        "update.bat",
        "createshortcut.bat",
        "create-shortcut.ps1",
        "launch.bat",
        "launch.ps1",
        "launch.sh",
        "setup-geo.bat",
        "packdeploy.bat",
        "pack-deploy.ps1",
        "pack-deploy.py",
        "pyproject.toml",
        "readme.md",
        "library.ico",
    }
)

ROOT_EXTRA_SUFFIXES = (".bat", ".ps1", ".sh", ".ico")
INCLUDE_DIRS = ("library",)


def _norm(name: str) -> str:
    return name.replace("\\", "/").strip().lower()


def is_excluded_dir_name(name: str) -> bool:
    lowered = _norm(name)
    if lowered in EXCLUDE_DIR_NAMES:
        return True
    return any(lowered.endswith(suffix) for suffix in EXCLUDE_DIR_SUFFIXES)


def is_excluded_file_name(name: str) -> bool:
    lowered = _norm(name)
    if lowered in EXCLUDE_FILE_NAMES:
        return True
    if any(lowered.startswith(prefix) for prefix in EXCLUDE_FILE_PREFIXES):
        return True
    return any(lowered.endswith(suffix) for suffix in EXCLUDE_FILE_SUFFIXES)


def present_excludes(app_folder: Path) -> list[str]:
    found: list[str] = []
    try:
        names = list(app_folder.iterdir())
    except OSError:
        return found
    seen = set()
    for item in names:
        label = item.name
        key = _norm(label)
        if key in seen:
            continue
        if item.is_dir() and is_excluded_dir_name(label):
            found.append(label + "/")
            seen.add(key)
        elif item.is_file() and is_excluded_file_name(label):
            found.append(label)
            seen.add(key)
    found.sort(key=lambda text: text.lower())
    return found


def _rel_parts_ok(rel: Path) -> bool:
    for part in rel.parts:
        if part in (".", ".."):
            continue
        if is_excluded_dir_name(part):
            return False
    return True


def is_root_include(name: str) -> bool:
    lowered = _norm(name)
    if lowered in ROOT_ALWAYS:
        return True
    if lowered.startswith("license"):
        return True
    return any(lowered.endswith(suffix) for suffix in ROOT_EXTRA_SUFFIXES)


def collect_files(app_folder: Path) -> list[Path]:
    chosen: list[Path] = []
    for child in sorted(app_folder.iterdir(), key=lambda item: item.name.lower()):
        if child.is_file() and is_root_include(child.name) and not is_excluded_file_name(child.name):
            chosen.append(Path(child.name))

    for folder_name in INCLUDE_DIRS:
        root = app_folder / folder_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(app_folder)
            if not _rel_parts_ok(rel):
                continue
            if is_excluded_file_name(path.name):
                continue
            chosen.append(rel)
    return chosen


def zip_entry_name(rel: Path) -> str:
    return ZIP_ROOT + "/" + rel.as_posix()


def default_zip_path(app_folder: Path) -> Path:
    return app_folder / "dist" / ZIP_NAME


def format_size(byte_count: int) -> str:
    if byte_count < 1024:
        return str(byte_count) + " bytes"
    kb = byte_count / 1024.0
    if kb < 1024:
        return ("%.1f KB" % kb)
    mb = kb / 1024.0
    return ("%.1f MB" % mb)


def write_zip(app_folder: Path, files: list[Path], dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(app_folder / rel, zip_entry_name(rel))
    if dest.exists():
        dest.unlink()
    tmp.replace(dest)
    return dest.stat().st_size


def print_plan(app_folder: Path, files: list[Path], skipped: list[str], dest: Path, dry_run: bool) -> None:
    print("")
    print("Library deploy zip")
    print("------------------")
    print("Folder: " + str(app_folder))
    print("")
    print("Skipped (present, not packed):")
    if skipped:
        for name in skipped:
            print("  " + name)
    else:
        print("  (none of the fat / dev folders are in this copy)")
    print("")
    print("Packed:")
    roots = [rel.as_posix() for rel in files if len(rel.parts) == 1]
    lib_count = sum(1 for rel in files if rel.parts and rel.parts[0] == "library")
    for name in roots:
        print("  " + name)
    if lib_count:
        print("  library/  (" + str(lib_count) + " files)")
    print("  " + str(len(files)) + " files total")
    print("")
    raw = 0
    for rel in files:
        try:
            raw += (app_folder / rel).stat().st_size
        except OSError:
            pass
    print("Uncompressed about " + format_size(raw))
    if dry_run:
        print("Dry-run -- not writing a zip.")
        print("Would write (overwrite if present):")
        print("  " + str(dest))
    else:
        if dest.exists():
            print("Overwriting existing zip:")
        else:
            print("Writing:")
        print("  " + str(dest))


def print_done(dest: Path, size: int) -> None:
    print("")
    print("Zip ready: " + str(dest))
    print("Size: about " + format_size(size))
    print("Safe to run again -- it overwrites this same file.")
    print("")
    print("Next step: copy the zip to a USB or family PC, extract it,")
    print("then double-click Setup.bat.")
    print("")


def resolve_app_folder(hint: str | None) -> Path | None:
    candidates: list[Path] = []
    if hint:
        candidates.append(Path(hint))
    candidates.append(Path(__file__).resolve().parent)
    try:
        candidates.append(Path.cwd())
    except OSError:
        pass
    markers = ("Setup.bat", "Library.bat", "pack-deploy.py", "setup.ps1")
    for item in candidates:
        try:
            folder = item.resolve()
        except OSError:
            continue
        if not folder.is_dir():
            continue
        if any((folder / name).is_file() for name in markers):
            return folder
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write dist/photoLibrary-deploy.zip -- a lean copy for USB / family PCs.",
    )
    parser.add_argument("--app-folder", default="", help="Library folder (folder with Setup.bat)")
    parser.add_argument(
        "--output",
        default="",
        help="Zip path (default: <app-folder>/dist/photoLibrary-deploy.zip)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List includes and excludes; do not write the zip",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = resolve_app_folder(args.app_folder or None)
    if app is None:
        print("Could not find the Library folder (the folder with Setup.bat).")
        print("Open that folder and run PackDeploy.bat again.")
        return 1
    dest = Path(args.output) if args.output else default_zip_path(app)
    dest = dest.resolve()
    files = collect_files(app)
    skipped = present_excludes(app)
    if not any(rel.as_posix().lower() == "setup.bat" for rel in files):
        print("Setup.bat is missing -- this is not a Library folder.")
        return 1
    if not any(rel.parts and rel.parts[0] == "library" for rel in files):
        print("library/ is missing -- this is not a Library folder.")
        return 1
    print_plan(app, files, skipped, dest, args.dry_run)
    if args.dry_run:
        print("")
        print("Next step after a real run: copy the zip, extract it, Setup.bat.")
        print("")
        return 0
    size = write_zip(app, files, dest)
    print_done(dest, size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
