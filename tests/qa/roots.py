"""Fixture-owned library-data roots."""

from __future__ import annotations

import json
from pathlib import Path

MARKER = {"schemaVersion": 1, "owner": "tests.qa"}


class UnmarkedRootError(RuntimeError):
    pass


def write_marker(root: Path) -> None:
    path = root / ".fixture-root"
    path.write_text(json.dumps(MARKER, indent=2) + "\n", encoding="utf-8")


def prepare_root(root: Path) -> Path:
    """Create a missing root, refuse a nonempty root without the QA marker."""
    root = Path(root)
    marker = root / ".fixture-root"
    if root.exists():
        children = [p for p in root.iterdir() if p.name != ".fixture-root"]
        if children and not marker.is_file():
            raise UnmarkedRootError(
                f"refusing nonempty root without library-data/.fixture-root: {root}"
            )
        root.mkdir(parents=True, exist_ok=True)
        if not marker.is_file():
            write_marker(root)
        return root
    root.mkdir(parents=True)
    write_marker(root)
    return root
