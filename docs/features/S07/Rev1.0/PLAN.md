# S07 — Keep previews useful when originals are away

Locked 2026-10-13 after S06 at `d55a569`. **Closes F8 and F16.** F10 stays open until S09. Relocate undo history is proved here; the full F18 history Check stays open until S13.

Read PRODUCT F8 and F16, CONTRACTS rendition store/relocate/unavailable, UI-SPEC missing-original and missing-preview states, FIXTURES absent-source and preview-missing, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- Global `previewStore`: `with-server` (default) writes `library-data/renditions/<id>/`. `with-source` writes `<selected-folder>/.library/renditions/<id>/`.
- Source `previewStore` override when not null. Inherit is null. For a copied source, with-source means the copied folder, never the old disk.
- Dedup ownership: the existing primary source remains the rendition owner. A second location does not move or duplicate the files.
- `renditions relocate` / `POST /api/renditions/relocate` moves existing preview files to match current settings and updates each item's `renditions` object. Originals are not moved.
- Relocate both directions. Interrupted or unwritable destination rolls back: old files and references survive. An unavailable source fails relocate and preserves old files/references. Response 200 `{"ok":true}` only after completion.
- Relocate is a history `relocate` operation. Undo restores references when the referenced renditions are recoverable (`undo/files/<entry-id>/...`). Never point history at deleted bytes.
- Launch resolves sources. A test-volume serial mapped to null is not mounted. After-launch unplug uses the same seam; do not unplug a real disk.
- `unavailableItems` `show` (default) keeps unavailable items; `hide` omits them from the grid and `GET /api/items` unless `unavailable=1`.
- `GET /api/media/<id>?which=original` is 404 `unavailable` when the original is gone. Ready preview/proxy still serve. Missing rendition is 404 `preview-unavailable`.
- Real page: exact banner “Original is not on this computer”; Open original disabled; Play preview only if a proxy exists. Missing preview uses “Preview is not available”. Both-missing shows banner and placeholder. An available alternate location is used.
- `python -m tests.qa slice S07`, `check F8`, `check F16` on fixture-owned roots.
- Original byte hashes unchanged. `library/` must not import Pillow.

## Out of scope

Annotate command, globe, tour, search chips, Live pairing, settings page as F17, full F10 viewer Check, F18 history cap. Do not add a setting. Do not add test-only UI.

## Store and paths

`renditions.store` is `with-server|with-source`. `renditions.sourceId` is the owning source. Paths:

- with-server: `renditions/<id>/thumb.webp` (relative to library-data).
- with-source: `.library/renditions/<id>/thumb.webp` (relative to the selected source root). Same for preview, poster, `proxy.mp4`.

New drain jobs follow the snapshot of settings + source override at job start. Relocate is the only command that moves existing files. Changing `previewStore` without relocate leaves old bytes where they are.

A duplicate hash item keeps one rendition directory. Do not write a second copy under the other source.

## Relocate

`python -m library --root <root> renditions relocate` and `POST /api/renditions/relocate` with `{}`.

1. Snapshot current global and per-source store.
2. For each item with ready rendition files, copy/move to the destination store, then update the item JSON, then remove the old files only after the new files exist and are non-empty.
3. If the destination cannot be written, or the process is killed at the test barrier, leave the old files and the old references. Do not publish a half-moved set.
4. If the owning source is unavailable (with-source files not readable), fail that item, keep old files, continue others, and surface the failure. CLI exit 1 when any item fails. HTTP `200 {"ok":true}` only when every item completed. Any failure uses an existing error (`io-error` or `unavailable`), never a new code.
5. History entry `operation: relocate`. Undo copies verified bytes back when stored under `undo/files/`.

Use `LIBRARY_TEST=1` plus an existing or documented relocate barrier only if CONTRACTS already names it. Do not invent a new barrier name. An OS-level kill during the write plus restart is enough if no named barrier exists. Unwritable destination can be a chmod-denied folder in the sandbox.

## Unavailable

Resolve only current locations whose stored size/mtime still match. A `volume` location needs a mounted serial via the OS or `LIBRARY_TEST_VOLUMES`. Null mount = not here.

After launch, remap the serial to null and reload items/sources without restarting the machine. Same letter/wrong volume must not resolve (use two test serials). An alternate current location that still matches is used.

Grid and `GET /api/items` follow `unavailableItems`. `unavailable=1` includes both. `GET /api/sources` marks the source unavailable when its origin is not mounted.

Viewer proofs on the real page at 1280×720:

- Original gone, preview present: banner exact, preview visible, Open original disabled. Save `unavailable.png`.
- Preview gone, original present: placeholder “Preview is not available”. Save `no-preview.png`.
- Both gone: banner and placeholder.
- Video: Play preview enabled only if `proxy` is ready and readable.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts under `docs/features/S07/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `relocation-before-after.json`, `source-resolution.json`, `unavailable.png`, `no-preview.png`.

```powershell
python -m tests.qa slice S07 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F8 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F16 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. `check F8`: set `previewStore` to `with-source`, scan a fixture folder, assert thumb under that folder's `.library/renditions/`. Set `with-server`, run `renditions relocate`, assert thumb beside the server and gone from the source tree. Record both directory listings in `relocation-before-after.json`. Repeat the reverse direction. Per-source override wins over global. Duplicate item has one owner.
2. Interrupted and unwritable relocate leave old bytes and old references. Original hashes unchanged.
3. `check F16`: a source JSON with a test-volume serial that is not mounted. `GET /api/sources` marks it unavailable. `show` includes the item; original GET is 404 `unavailable`; `hide` omits it until `unavailable=1`. After-launch unplug, wrong-volume serial, and an available alternate are recorded in `source-resolution.json`.
4. Real-page `unavailable.png` and `no-preview.png` at 1280×720 from the running page, not drawings. Banner text is exact. Placeholder text is exact.
5. Exit 0 only when every proof ran. Never weaken an assertion or change expected fixture values.

The implementer may run these gates and must not call that log the grade.
