# F23 Folder library — build plan

Spec: [PRODUCT.md F23](../../../PRODUCT.md#f23--folder-library). Decisions (Steve, 2026-10-18):
the folder library is the only record for its pictures; files are flat and
named `<path-in-folder>.<suffix>` with the original extension kept.

## Architecture

One module owns every path: `library/folder_library.py`.

```python
fl = folder_library.for_source(root, source)   # None when unreachable
fl.dir                                          # <folder>/.library or library-data/folders/<name>-<id>
fl.record_path(rel)                             # .library/IMG_0456.JPG.json
fl.derived_path(rel, slot)                      # .library/IMG_0456.JPG.thumb.webp
fl.rel_for(item)                                # primary still (or motion) path inside the folder
fl.folder_file("people")                        # .library/people.json
```

Nothing else builds `.library/...`, `renditions/<id>/`, or `catalog/items/<id>.json`
strings. Item ids stay the SHA-256 (API URLs, undo, the speed index). The
on-disk address is derived from the item's location, never from its id.

Writers go through `atomic.transact` with a new path scheme
`source:<source-id>/<relative-to-folder-library>` so undo, recovery and
relaxed durability keep working for files outside `library-data/`.
`item_index` and `catalog.sqlite` become caches over all folder libraries.

## Slices (each: doc check first, scratch fixture only, commit when green)

1. **folder_library module + path scheme.** `for_source`, naming, escaping
   (Windows-reserved names, long paths), `source:` paths in transact and
   recovery. Unit tests: naming table, subfolders, Live pair, unreachable
   folder returns None, recovery replays a `source:` write.
2. **Renditions write/read new names.** `_job_destination`, `rendition_abs`,
   `requeue_missing_renditions`, media serving. Old layout still readable.
   Gate: `tests.qa.missing_previews`, processing_feedback, bench 80.
3. **Item record lives in the folder.** `catalog_io.load_item/items_dir`
   resolve through the index to `<name>.json`; readable denormalized fields
   (place name, people names) written beside ids. `library-data/catalog/items`
   no longer written for folder sources. Gate: TASTE-RATING, faces/places
   slices, annotate-during-scan (S08).

   Sub-steps:
   - **3a — record placement.** `catalog/items/<id>.json` stays the app's
     *logical* address (history, undo, overlays, transact all keep it).
     `library/item_store.py` maps it to the physical file: an item whose
     `renditions.store` is `folder-source` (the folder's own `.library/`) or
     `folder-server` (`library-data/folders/<name>-<id>/`) lives at
     `<that folder library>/<name>.json`. The store is recorded per item
     (like the old `with-source`/`with-server`) so a setting change never
     strands files and relocate + undo are plain before/after payloads;
     pending items and old-layout items stay in `library-data/catalog/items/`
     until migration (slice 6) moves their previews and record together.
     New scans create items in the store the F8 setting picks now. The id → file map is built
     from every reachable folder library's `*.json` records and kept current
     on each write. Writing a folder record removes any stale
     `library-data` copy. `item_index` reads both places. The old
     `.library/catalog/items` mirror skips folder-store items.
     Gate: unit tests, missing_previews, processing_feedback, TASTE-RATING,
     bench 80 (no slowdown). **Done** — [gates](assets/slice3a/gates.txt).
     Open: moving an item to another source re-queues its previews instead
     of moving them (slice 4).
   - **3b — readable fields.** `path`, `placeName`, `people[{id,name}]`
     written beside the ids, stripped on read; refreshed when a person or
     place is renamed.
   - **3c — folder files.** `folder.json` replaces `.library/source.json`;
     `people.json` / `places.json` / `favorites.json` per folder; the old
     `.library/catalog` mirror stops.
4. **Rename/move by fingerprint.** Scan matches a vanished name + new name
   with the same SHA-256 and renames generated files in one transaction.
   Gate: byte-identical rename test.
5. **Delete = reset.** Missing `.library/` (folder still reachable) drops that
   folder's items from the index and rescans it as new. Duplicates in other
   folders keep their own records. Gate: F23 Check reset part.
   Core landed with 3a (records in the folder made it necessary):
   `item_store.vanished_sources` notices a folder library that held records
   is gone while its parent folder exists; the server's idle drain loop starts
   the same background rescan as `POST /api/sources/<id>/rescan`; scan's
   "unchanged" test also requires the item record to exist, so every picture
   is read again. Gate: `tests.qa.missing_previews`. Still open: hearts in
   `favorites.json` and person links in `library-data` outlive the reset.
6. **Migration.** Old `.library/catalog` + `.library/renditions/<id>/` and
   `library-data/catalog/items` → new layout, rename-only, manifest-driven,
   resumable, verify-then-delete. Gate: old-layout fixture, hashes identical,
   zero encodes; kill mid-migration and resume. Real library only after
   Steve says go (back up `library-data/` and each `.library/` first).
7. **index.html.** Static grid + viewer + info from `index.js`
   (`window.LIBRARY = {...}`; `file://` cannot fetch JSON). Rewritten at idle.
   Gate: browser screenshot through `file://`.

## Open questions to settle inside slices (not taste)

- Path length: Windows MAX_PATH for deep subfolders; use `\\?\` long paths.
- Case-only renames on NTFS.
- People list: library-wide in `library-data/`; each folder's `people.json`
  carries the people it uses so a moved folder still shows names.
- Undo entries written before migration reference old paths; keep a mapping
  so undo of a pre-migration step still works or is clearly refused.
