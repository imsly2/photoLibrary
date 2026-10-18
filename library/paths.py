"""Root and library-relative path helpers."""

from __future__ import annotations

import os
from pathlib import Path

APP_FOLDER = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = APP_FOLDER / "library-data"


class PathError(ValueError):
    """Relative path failed containment or shape checks."""


def normalize_root(root: str | Path) -> Path:
    return Path(root).expanduser().resolve()


def roots_equal(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(str(normalize_root(a))) == os.path.normcase(
        str(normalize_root(b))
    )


def root_text(root: str | Path) -> str:
    return str(normalize_root(root))


def default_root() -> Path:
    return normalize_root(DEFAULT_ROOT)


def library_path(root: Path, relative: str) -> Path:
    """Resolve a library-relative path using `/` separators.

    ``source:<id>/<name>`` addresses a file in that source's folder library.
    """
    if relative.startswith("source:"):
        from library.folder_library import resolve_logical

        return resolve_logical(root, relative)
    rel = relative.replace("\\", "/")
    if rel.startswith("/") or ".." in Path(rel).parts:
        raise PathError("path-outside-root")
    root = normalize_root(root)
    out = (root / Path(*rel.split("/"))).resolve()
    try:
        out.relative_to(root)
    except ValueError as exc:
        raise PathError("path-outside-root") from exc
    return out
