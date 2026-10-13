# S02 — Put pictures on dates and GPS places

Locked 2026-10-13 after recon [S02 metadata](9edf9814-50a6-43f5-adc9-7a119844aae9).
Depends on S01 at `977af0b`. **Closes F6.**

Read PRODUCT F6, CONTRACTS date/GPS/place rules, FIXTURES, and this file.
Do not invent fields, errors, settings, or screens. Do not add an altitude field.

## In scope

- Library-owned metadata reader. Do not call `tests/qa/probe.py` from the server.
- On scan and on rescan of changed bytes, fill `capturedAt`, `capturedAtSource`, `metadata`, and `placeId`. Unchanged size+mtime stays skipped and keeps its record.
- Create `catalog/places/<id>.json` with `place_` plus 12 lowercase hex digits.
- `python -m tests.qa slice S02` and `python -m tests.qa check F6`.
- S00 and S01 gates still exit 0.

## Out of scope

Rendition bytes, grid, copy-here, annotate, globe, `/api/places`, tour. HEIC GPS is not an F6 assertion. No geocoder and no place names from coordinates.

## Date and metadata

Precedence: DateTimeOriginal, then CreateDate (both `capturedAtSource: exif`), then the leftmost valid `YYYY-MM-DD` or `YYYYMMDD` in the filename (`filename`), then mtime (`mtime`). Invalid candidates are skipped.

Spellings:

- Floating EXIF, no offset: `2024-06-12T15:04:00` (no `Z`).
- Date-only filename: midnight with no zone, `2020-01-02T00:00:00`.
- mtime: UTC with `Z`, `2022-02-03T04:05:06Z`.
- Explicit offset: normalize to UTC with `Z`. A sandbox JPEG with DateTimeOriginal `2024:06:12 15:04:00` and OffsetTimeOriginal `-05:00` becomes `2024-06-12T20:04:00Z`.
- QuickTime `2024-06-12T15:07:00Z` stays that instant.

Store raw pixel width and height plus EXIF orientation 1–8. `oriented.jpg` is 640×480, orientation 6. Video `durationSec` is 2.0 within one frame. GPS latitude/longitude as stored numbers. `camera` and `lens` stay null when the file has none. No GPS means `placeId` null.

## Places

Haversine distance. Reuse an existing place when the fix is within `placeMatchMeters` (default 100). Nearest wins. Equal distance breaks by lexical place id. A match keeps that place's existing coordinates and name. A new place gets `name: null` and the seeding fix's coordinates. Enumerate files by normalized relative path so the seed is stable.

The three-JPEG subset `a/IMG_1042.jpg`, `a/near.jpg`, `b/far.jpg` produces exactly two place files. IMG_1042 and near share one id. far has the other. The shared place keeps 41.88, -87.63 because `a/IMG_1042.jpg` sorts first. Do not assert that count against the whole media tree. `a/clip.mp4` joins the IMG_1042 place when it is in the same scan. `b/no-exif.jpg`, `b/created.jpg`, both holiday files, and `b/oriented.jpg` have null `placeId`.

## Ties

Sort by date, then id. Build a sandbox pair with the same `capturedAt` and assert the lower id sorts first. A filename containing two valid dates uses the leftmost. An invalid date token falls back to mtime.

## Gate

Fresh fixture-owned root. Artifacts under `docs/features/S02/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `metadata.json`, `items/`, `places/`, `extraction-dumps/`.

```powershell
python -m tests.qa slice S02 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F6 --root "$qaRoot/library-data" --artifacts $evidence
```

Exit 0 only when every proof ran. Skipped assertions fail. The implementer may run these and must not call them the grade.
