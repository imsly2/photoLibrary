"""Application service shared by CLI and HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from library.atomic import recover_transactions, transact
from library.errors import AppError, fail
from library.history import (
    load_entry,
    load_state,
    make_settings_entry,
    plan_append,
    plan_cursor_move,
)
from library.lock import WriteLock
from library.settings import (
    defaults,
    dumps_settings,
    load_settings_file,
    merge_patch,
    ordered,
    parse_cli_value,
    settings_path,
    write_settings_file,
)


class Library:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def recover(self) -> dict[str, Any]:
        return recover_transactions(self.root)

    def ensure_settings(self) -> dict[str, Any]:
        path = settings_path(self.root)
        if not path.exists():
            write_settings_file(self.root, defaults())
            return defaults()
        return load_settings_file(self.root)

    def settings_get(self) -> dict[str, Any]:
        self.recover()
        return ordered(self.ensure_settings())

    def settings_set(self, patch: dict[str, Any]) -> dict[str, Any]:
        self.recover()
        before = self.ensure_settings()
        after = merge_patch(before, patch)
        if dumps_settings(before) == dumps_settings(after):
            return after
        entry = make_settings_entry(self.root, before, after)
        changes = [
            {
                "path": "settings.json",
                "before": ordered(before),
                "after": ordered(after),
            }
        ]
        changes.extend(plan_append(self.root, entry))
        transact(self.root, changes, use_settings_barriers=True)
        return after

    def settings_set_cli(self, key: str, raw: str) -> dict[str, Any]:
        return self.settings_set({key: parse_cli_value(key, raw)})

    def undo(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        state = load_state(self.root)
        if state["cursor"] == 0:
            return {"ok": True}
        entry_id = state["entries"][state["cursor"] - 1]
        entry = load_entry(self.root, entry_id)
        file_changes = [
            {
                "path": change["path"],
                "before": _read_relative_json(self.root, change["path"]),
                "after": change["before"],
            }
            for change in entry["changes"]
        ]
        transact(
            self.root,
            plan_cursor_move(self.root, state["cursor"] - 1, file_changes),
        )
        return {"ok": True}

    def redo(self) -> dict[str, bool]:
        self.recover()
        self.ensure_settings()
        state = load_state(self.root)
        if state["cursor"] >= len(state["entries"]):
            return {"ok": True}
        entry_id = state["entries"][state["cursor"]]
        entry = load_entry(self.root, entry_id)
        file_changes = [
            {
                "path": change["path"],
                "before": _read_relative_json(self.root, change["path"]),
                "after": change["after"],
            }
            for change in entry["changes"]
        ]
        transact(
            self.root,
            plan_cursor_move(self.root, state["cursor"] + 1, file_changes),
        )
        return {"ok": True}

    def history_len(self) -> int:
        return len(load_state(self.root)["entries"])


def _read_relative_json(root: Path, relative: str) -> Any:
    from library.paths import library_path

    path = library_path(root, relative)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def with_write_lock(root: Path) -> WriteLock:
    return WriteLock(root)


def error_payload(code: str) -> bytes:
    return json.dumps({"error": code}, separators=(",", ":")).encode("utf-8")
