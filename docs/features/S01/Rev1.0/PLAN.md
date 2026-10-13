# S01 — Scan a linked fixture folder and keep its identity

Locked 2026-10-13 after recon. Depends on S00 at `662789d`. Closes no feature Check.
Foundations for F1, F3, F4, F5, F16, F20 only.

Read PRODUCT F5, CONTRACTS item/source/hash/history rules, FIXTURES, and this file.
Do not invent fields, errors, settings, or screens.

## In scope

- `scan <path> --serve-from-there` and `POST /api/sources` with mode `serve-from-there`.
- Source and item JSON, pending id then hash id, one history entry per scan.
- Disposable SQLite rebuilt from JSON. Schema stays private and is not an API.
- `GET /api/sources`, `GET /api/items`, `POST /api/rebuild-index`, matching CLI.
- `python -m tests.qa slice S01` on a fixture-owned root.

## Out of scope

`copy-here` (S05), rendition bytes (status `queued`, paths null), place matching and EXIF precedence proofs (S02), grid UI, annotate command, full F5/F16/F20 Checks. Do not generate thumbnails.

## Locked behavior

- Allowed extensions, case-insensitive: jpg, jpeg, png, gif, webp, heic, heif, tif, tiff, bmp, mp4, mov, m4v, avi, mkv, webm. Other files are ignored, not errors.
- Skip the real library-data directory, every `.library` directory, and do not follow symlinks or junctions.
- Linked files keep `destination: null` and `kind: volume`. Nothing is written inside the scanned folder except reads. Byte hashes of originals are unchanged.
- New file: write `pending-<sourceId>-<path-digest>`, hash bytes, publish one final item id = lowercase sha256, delete pending. Same bytes in a second path: one item, two locations, one primary.
- Rescan of the same volume identity and directory reuses the source id. Unchanged size and mtime: skipped. Second scan of an unchanged tree: `added` 0.
- One scan operation is one history entry.
- `broken.heic` is indexed from its bytes. Decode failure may be a source error. The item remains. Do not pretend a rendition exists.
- Live pair: if a still and a movie in the same source carry the same embedded content identifier, publish one `kind: live` item whose id is the still hash and whose locations use `component` still and motion. Filename equality does not pair. Orphans stay photo or video. Arrival-order and mismatch proofs stay S12; this slice only proves the committed pair scans as one item.
- `capturedAt` may be the file mtime with `capturedAtSource: mtime`. GPS and orientation may be null. Do not create place records. Read `contentIdentifier` because pairing needs it.
- Item `available` is computed. A location whose volume resolver returns null stays in the JSON and `available` is false. Do not delete it.
- POST returns 202 with the source record and finishes the scan before the response if the work is in-process. CLI waits and prints `{sourceId,added,skipped,errors}`.
- `copy-here` without this slice's implementation still returns the existing not-found error. Do not copy files.

## Interruptions and volume seam

Use the barrier names added to CONTRACTS Foundation locks. The slice kills at `hash-publication`, restarts, rescans, and asserts one item. It also deletes `catalog.sqlite`, runs rebuild, and asserts the same item ids.

`LIBRARY_TEST_VOLUMES` maps `windows:fixture-offline` to null. Seed one linked source and item that use that serial. After launch, the source is unavailable and the item JSON still contains the location.

## Gate

Fresh sandbox. Artifacts under `docs/features/S01/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `scan-first.log`, `scan-second.log`, catalog snapshots, `original-hashes.json`, `interruption.json`.

```powershell
python -m tests.qa slice S01 --root "$qaRoot/library-data" --artifacts $evidence
```

Exit 0 only when every proof above ran. Skipped assertions fail. The implementer may run it and must not call it the grade.

S00 `python -m tests.qa slice S00` must still exit 0.
