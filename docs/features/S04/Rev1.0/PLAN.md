# S04 — Browse and open the fixture pictures (M1)

Locked 2026-10-13 after S03 at `50c3ae6`. **Closes F9 and F11.** F10 stays open until S09. F21 and F22 stay open until S13/S14. This slice proves the browse subset only.

Read PRODUCT F9, F11, and the F10 open/arrows/Esc sentences; CONTRACTS groups and item sort; UI-SPEC grid/sort/viewer; FIXTURES date set; and this file. Do not invent fields, errors, settings, or screens.

## In scope

- `GET /api/groups?level=years|months|days|all` plus the existing item filters/sort.
- Toolbar sort by date, location, or name, both directions. Persist `sort`, `dir`, and `zoomLevel` through settings HTTP.
- A real Add folder dialog for a server-local path. S04 proves **serve-from-there** from that dialog. Copy-here stays unimplemented (`not-found` or disabled until S05).
- Library grid at four levels: Years, Months, Days, All. Slider and Ctrl+wheel step one level. The hovered item stays in view.
- Click a cell to open the still preview. ArrowLeft/ArrowRight move in the current sort. Esc restores the grid, level, and scroll.
- Viewer still zoom: Ctrl+wheel around the cursor; middle-drag pans 1:1. Fit on open. No crop on the opened still.
- `python -m tests.qa slice S04`, `check F9`, `check F11` on a fixture-owned root.
- S00, S01, S02, and S03 stay sequential and must not be weakened.

## Out of scope

Copy-here, video hover/proxy, globe, tour, search chips, annotate, settings page, relocate, Live badge playback. Do not close F10, F7, F21, or F22. Do not add a setting. Do not import Pillow from `library/`.

## Groups

`GET /api/groups` returns `{key,itemIds}[]`. Year `YYYY`, month `YYYY-MM`, day `YYYY-MM-DD`. Same item ids exactly once as `GET /api/items` with the same query. Groups ordered by first occurrence in the sorted items; contents keep that order. Days and All both list every matching item under day headings. No representative-photo algorithm.

A two-year fixture set (2024 and 2023 dates from IMG_1042 / far, plus pinned no-EXIF 2022) yields two year groups. Months one group per month that has items. Days and All one group per day.

## Sort

Default `sort=date`, `dir=desc`. Date then id. Name then date then id. Location: named places, unnamed GPS, then "No location", regardless of dir; dir orders names/coordinates and dates inside a category. Compare `capturedAt` as stored. The no-EXIF fixture `capturedAtSource` is `mtime` and sorts by that pinned 2022 time.

`GET /api/items?sort=date&dir=desc` on IMG_1042, far, and no-exif returns 2024, then 2023, then 2022.

## Page

When items exist, do not show “No pictures yet”. Add folder opens the named dialog: editable path, two choices, Cancel/Add. `ask` starts with neither mode selected and Add disabled until path and mode exist. Serve-from-there submits `POST /api/sources`. A small status line shows added/skipped/error from sources while scanning. Poll until idle. Cells use real thumbs. Placeholder text remains “Preview is not available” until the thumb loads.

Four-level control Years → Months → Days → All. Days cells ~240 px row height; All ~160 px. Years/Months are mosaics per group. Click opens preview. Esc from viewer returns to the same level and filter. No test-only controls.

## Gate

Fresh fixture-owned root. Artifacts under `docs/features/S04/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `years.png`, `all.png`, `viewer.png`, `input-trace.json`, `groups-years.json`, `groups-months.json`, `groups-days.json`, `groups-all.json`. Browser proofs at 1280×720 from the real page.

```powershell
python -m tests.qa slice S04 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F9 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F11 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Drive Add folder on the real page, submit serve-from-there on the fixture tree, and wait until items and thumbs exist.
2. Record the four `/api/groups` responses. Years has two groups. Months/days/all match the item set. Flattening the groups equals the item ids exactly once.
3. `check F9`: rendered Years and All screenshots; slider and Ctrl+wheel change level; hovered/anchor item stays in the viewport; `zoomLevel` persists after reload.
4. `check F11`: date desc puts 2024 first; no-EXIF is `mtime`; location and name sorts both directions; toolbar drives the same HTTP query the CLI uses.
5. Open the oriented still from the grid. Arrows stop at the ends. Esc restores scroll. Ctrl+wheel zoom and middle-drag pan are measured (anchor drift ≤2 px; pan equals drag ±2 px) in `input-trace.json` / `measurements.json`.
6. No console errors on valid actions. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
