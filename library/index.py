"""Disposable SQLite index rebuilt from catalog JSON. Schema is private."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from library.atomic import maybe_test_barrier
from library.catalog_io import iter_item_ids, iter_source_ids, load_item, load_source


def sqlite_path(root: Path) -> Path:
    return root / "catalog" / "catalog.sqlite"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            filename TEXT NOT NULL,
            captured_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    return conn


def fill_index(root: Path, conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM items")
    conn.execute("DELETE FROM sources")
    for source_id in iter_source_ids(root):
        source = load_source(root, source_id)
        conn.execute(
            "INSERT INTO sources(id, mode, name) VALUES (?, ?, ?)",
            (source["id"], source["mode"], source["name"]),
        )
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        conn.execute(
            "INSERT INTO items(id, kind, filename, captured_at) VALUES (?, ?, ?, ?)",
            (item["id"], item["kind"], item["filename"], item["capturedAt"]),
        )
    conn.commit()


def rebuild_sqlite(root: Path, *, use_barrier: bool = False) -> None:
    db_path = sqlite_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    if use_barrier:
        maybe_test_barrier("sqlite-rebuild")
    conn = _connect(db_path)
    try:
        fill_index(root, conn)
    finally:
        conn.close()


def maybe_rebuild_missing(root: Path) -> None:
    catalog = root / "catalog"
    if not catalog.exists():
        return
    db_path = sqlite_path(root)
    has_json = any(iter_source_ids(root)) or any(iter_item_ids(root))
    if has_json and not db_path.exists():
        rebuild_sqlite(root, use_barrier=False)


def item_ids_from_sqlite(root: Path) -> list[str]:
    db_path = sqlite_path(root)
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT id FROM items ORDER BY id").fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()
