"""Match phone files to a destination folder. No phone, no tk."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOG_NAME = "iphone-photos-log.jsonl"
PARTIAL_SUFFIX = ".partial"

ACTION_SKIP = "skip"
ACTION_COPY = "copy"
ACTION_KEEP = "keep"

SKIP_TEXT = "Skipped, exact match"
KEEP_TEXT = "Left in place, size differs"
WILL_COPY_SIZE_TEXT = "Will copy, size differs"
WILL_COPY_MISSING_TEXT = "Will copy, not in folder"
WILL_COPY_PAIRED_TEXT = "Will copy, already paired"
COPYING_TEXT = "Copying"


class DestinationExists(Exception):
    """The final path was already there, so it was left untouched."""


class SizeMismatch(Exception):
    """The bytes written did not match the phone file's size."""


@dataclass(frozen=True)
class PhoneFile:
    source_path: str
    size: int
    mtime: datetime


@dataclass(frozen=True)
class PlanItem:
    source_path: str
    size: int
    mtime: datetime
    action: str
    dest_relative: str | None
    local_relative: str | None = None
    local_size: int | None = None
    stem_relative: str | None = None


@dataclass
class _LocalFile:
    path: Path
    size: int
    used: bool = False


def file_name(source_path: str) -> str:
    normalized = source_path.replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1]


def copied_text(dest_relative: str) -> str:
    return f"Copied, {dest_relative}"


def phone_text(source_path: str, size: int) -> str:
    return f"{source_path}  ({size:,})"


def folder_text(item: PlanItem) -> str:
    """What the destination scan found for this phone file."""
    if item.local_relative is not None and item.local_size is not None:
        if item.action == ACTION_SKIP and item.local_size == item.size:
            return f"{item.local_relative}  ({item.local_size:,})"
        return f"{item.local_relative}  folder {item.local_size:,}  phone {item.size:,}"
    text = "not in this folder"
    if item.stem_relative:
        text = f"{text}  also has {file_name(item.stem_relative)} at {item.stem_relative}"
    return text


def look_status(item: PlanItem) -> str:
    if item.action == ACTION_SKIP:
        return SKIP_TEXT
    if item.action == ACTION_KEEP:
        return KEEP_TEXT
    if item.local_relative is None or item.local_size is None:
        return WILL_COPY_MISSING_TEXT
    if item.local_size == item.size:
        return WILL_COPY_PAIRED_TEXT
    return WILL_COPY_SIZE_TEXT


def month_folder(mtime: datetime) -> str:
    if mtime.tzinfo is not None:
        mtime = mtime.astimezone()
    return f"{mtime.year:04d}-{mtime.month:02d}"


def _log_path(destination: Path) -> Path:
    return destination / LOG_NAME


def completed_pairs(destination: Path) -> set[tuple[str, int]]:
    """Source path + size already logged as copied or skipped_exact."""
    done: set[tuple[str, int]] = set()
    path = _log_path(destination)
    if not path.is_file():
        return done
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if row.get("status") not in ("copied", "skipped_exact"):
                continue
            source = row.get("source")
            size = row.get("source_size")
            if isinstance(source, str) and isinstance(size, int) and not isinstance(size, bool):
                done.add((source, size))
    return done


def _index_destination(
    destination: Path,
) -> tuple[dict[str, list[_LocalFile]], dict[str, list[_LocalFile]]]:
    by_name: dict[str, list[_LocalFile]] = {}
    by_stem: dict[str, list[_LocalFile]] = {}
    if not destination.is_dir():
        return by_name, by_stem
    log_key = os.path.normcase(str(_log_path(destination).resolve()))
    for dirpath, _dirnames, filenames in os.walk(destination):
        for name in filenames:
            if name.endswith(PARTIAL_SUFFIX):
                continue
            path = Path(dirpath) / name
            try:
                resolved = str(path.resolve())
                size = path.stat().st_size
            except OSError:
                continue
            if os.path.normcase(resolved) == log_key:
                continue
            local = _LocalFile(path, size)
            by_name.setdefault(name, []).append(local)
            by_stem.setdefault(Path(name).stem, []).append(local)
    for group in by_name.values():
        group.sort(key=lambda item: os.path.normcase(str(item.path)))
    for group in by_stem.values():
        group.sort(key=lambda item: os.path.normcase(str(item.path)))
    return by_name, by_stem


def _observe_same_name(
    locals_for_name: list[_LocalFile],
    phone_size: int,
    destination: Path,
) -> tuple[str | None, int | None]:
    """Relative path and size of one same-name file, or (None, None).

    Prefers an unused exact-size file, then any same-size file, then the
    first different-size file. Does not mark anything used.
    """
    if not locals_for_name:
        return None, None
    exact_free = next(
        (local for local in locals_for_name if local.size == phone_size and not local.used),
        None,
    )
    if exact_free is not None:
        return _relative(destination, exact_free.path), exact_free.size
    same_size = next((local for local in locals_for_name if local.size == phone_size), None)
    chosen = same_size if same_size is not None else locals_for_name[0]
    return _relative(destination, chosen.path), chosen.size


def _stem_relative(
    by_stem: dict[str, list[_LocalFile]],
    filename: str,
    destination: Path,
) -> str | None:
    """One different filename whose stem matches. Not a match."""
    for local in by_stem.get(Path(filename).stem, []):
        if local.path.name == filename:
            continue
        return _relative(destination, local.path)
    return None


def _relative(destination: Path, path: Path) -> str:
    return path.resolve().relative_to(destination.resolve()).as_posix()


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path))


def _allocate(directory: Path, filename: str, reserved: set[str], *, allow_plain: bool) -> Path:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    if allow_plain:
        plain = directory / filename
        if not plain.exists() and _path_key(plain) not in reserved:
            reserved.add(_path_key(plain))
            return plain
    number = 2
    while number <= 100000:
        candidate = directory / f"{stem}_{number}{suffix}"
        if not candidate.exists() and _path_key(candidate) not in reserved:
            reserved.add(_path_key(candidate))
            return candidate
        number += 1
    raise RuntimeError(f"No free name for {filename} in {directory}")


def plan(phone_files: list[PhoneFile], destination: Path) -> list[PlanItem]:
    """Decide skip vs copy for each phone file. Does not write anything."""
    done = completed_pairs(destination)
    by_name, by_stem = _index_destination(destination)
    reserved: set[str] = set()
    items: list[PlanItem] = []

    for phone in phone_files:
        name = file_name(phone.source_path)
        locals_for_name = by_name.get(name, [])
        if (phone.source_path, phone.size) in done:
            local_relative, local_size = _observe_same_name(
                locals_for_name, phone.size, destination
            )
            stem_relative = (
                None
                if local_relative is not None
                else _stem_relative(by_stem, name, destination)
            )
            items.append(
                PlanItem(
                    phone.source_path,
                    phone.size,
                    phone.mtime,
                    ACTION_SKIP,
                    None,
                    local_relative,
                    local_size,
                    stem_relative,
                )
            )
            continue

        exact = next(
            (
                local
                for local in locals_for_name
                if local.size == phone.size and not local.used
            ),
            None,
        )
        if exact is not None:
            exact.used = True
            relative = _relative(destination, exact.path)
            items.append(
                PlanItem(
                    phone.source_path,
                    phone.size,
                    phone.mtime,
                    ACTION_SKIP,
                    relative,
                    relative,
                    exact.size,
                    None,
                )
            )
            continue

        local_relative, local_size = _observe_same_name(
            locals_for_name, phone.size, destination
        )
        if locals_for_name:
            directory = locals_for_name[0].path.parent
            dest = _allocate(directory, name, reserved, allow_plain=False)
            stem_relative = None
        else:
            directory = destination / month_folder(phone.mtime)
            dest = _allocate(directory, name, reserved, allow_plain=True)
            stem_relative = _stem_relative(by_stem, name, destination)
        items.append(
            PlanItem(
                phone.source_path,
                phone.size,
                phone.mtime,
                ACTION_COPY,
                _relative(destination, dest),
                local_relative,
                local_size,
                stem_relative,
            )
        )
    return items


def _safe_mirror_relative(source_path: str) -> str:
    rel = source_path.replace("\\", "/").strip("/")
    parts = tuple(Path(rel).parts)
    if (
        not rel
        or rel.startswith(("/", "\\"))
        or ".." in parts
        or any(part.endswith(":") for part in parts)
    ):
        raise ValueError(f"Not an Internal Storage path: {source_path}")
    return rel


def _mirror_locals(destination: Path) -> dict[str, tuple[str, int]]:
    found: dict[str, tuple[str, int]] = {}
    for dirpath, dirnames, filenames in os.walk(destination):
        dirnames[:] = [name for name in dirnames if name != ".library"]
        for name in filenames:
            if name == LOG_NAME or name.endswith(PARTIAL_SUFFIX):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(destination).as_posix()
            found[rel.casefold()] = (rel, path.stat().st_size)
    return found


def plan_mirror(phone_files: list[PhoneFile], destination: Path) -> list[PlanItem]:
    """Match Explorer's Internal Storage paths. Never invent a date folder.

    Same folder, name, and size is a skip. A different size at that path is
    left untouched. A missing file is copied to that same relative path.
    """
    locals_by_path = _mirror_locals(destination)
    items: list[PlanItem] = []
    for phone in phone_files:
        rel = _safe_mirror_relative(phone.source_path)
        found = locals_by_path.get(rel.casefold())
        if found is not None and found[1] == phone.size:
            items.append(
                PlanItem(
                    rel,
                    phone.size,
                    phone.mtime,
                    ACTION_SKIP,
                    found[0],
                    found[0],
                    found[1],
                    None,
                )
            )
            continue
        if found is not None:
            items.append(
                PlanItem(
                    rel,
                    phone.size,
                    phone.mtime,
                    ACTION_KEEP,
                    None,
                    found[0],
                    found[1],
                    None,
                )
            )
            continue
        items.append(
            PlanItem(
                rel,
                phone.size,
                phone.mtime,
                ACTION_COPY,
                rel,
                None,
                None,
                None,
            )
        )
    return items


def append_log(
    destination: Path,
    source_path: str,
    source_size: int,
    dest_relative: str,
    status: str,
    when: datetime | None = None,
) -> None:
    moment = when or datetime.now().astimezone()
    row = {
        "source": source_path,
        "source_size": source_size,
        "dest": dest_relative,
        "status": status,
        "time": moment.isoformat(timespec="seconds"),
    }
    path = _log_path(destination)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def log_skip_if_new(
    destination: Path,
    item: PlanItem,
    done: set[tuple[str, int]],
) -> None:
    key = (item.source_path, item.size)
    if key in done:
        return
    append_log(
        destination,
        item.source_path,
        item.size,
        item.dest_relative or "",
        "skipped_exact",
    )
    done.add(key)


def write_stream(final: Path, expected_size: int, chunks) -> None:
    """Write chunks to a .partial file, then replace onto final if it is absent."""
    final.parent.mkdir(parents=True, exist_ok=True)
    partial = final.with_name(final.name + PARTIAL_SUFFIX)
    replaced = False
    try:
        with partial.open("wb") as handle:
            for chunk in chunks:
                if chunk:
                    handle.write(chunk)
        actual = partial.stat().st_size
        if actual != expected_size:
            raise SizeMismatch(
                f"{final.name} wrote {actual} bytes, phone file is {expected_size}"
            )
        if final.exists():
            raise DestinationExists(str(final))
        os.replace(partial, final)
        replaced = True
    finally:
        if not replaced and partial.exists():
            partial.unlink()


def copy_item(destination: Path, item: PlanItem, chunks) -> None:
    if item.action != ACTION_COPY or not item.dest_relative:
        raise ValueError("copy_item was given a file that is not a copy")
    final = destination / item.dest_relative
    write_stream(final, item.size, chunks)
    append_log(destination, item.source_path, item.size, item.dest_relative, "copied")
