# S04 — Browse and open the fixture pictures

Locked 2026-10-13 after recon [S04 browse](d67824d6-a356-4042-b57b-60b82f206a0f).
Depends on S03 at `08e4e77`. **Closes F9 and F11.** F10, F21, and F22 stay open; this slice proves only their browse subset.

Read PRODUCT F9, F10, and F11, CONTRACTS `/api/groups` and sort rules, UI-SPEC grid and viewer, FIXTURES, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- `GET /api/groups` and location sort on `GET /api/items`.
- Add folder dialog that links a fixture folder, then the grid.
- Four zoom levels, sort toolbar, viewer arrows, zoom, and pan.
- `python -m tests.qa slice S04`, `check F9`, and `check F11`.
- S00, S01, S02, and S03 gates still exit 0 when run one at a time.

## Out of scope

copy-here, search, settings page, globe, tour, annotate, video playback, hover, original-over-preview upgrade, and missing-original banners. Do not close F10, F21, or F22.

## Add folder

The empty library shows Add folder enabled. The dialog title is Add folder. The path is a text field. The two choices are labeled "Copy onto this drive" and "Serve from that folder". Cancel and Add are the only buttons. Esc and Cancel close the dialog and write nothing.

`addFolderDefault` is `ask`, so neither choice starts selected and Add stays disabled until both a path and a choice exist. The gate chooses "Serve from that folder" and posts `serve-from-there`. Choosing "Copy onto this drive" posts `copy-here` and shows the existing not-found error. It does not copy files.

The scan still finishes inside that POST, as S01 locked. The status line then shows the returned added, skipped, and error counts. There is no new job API and no percentage. After that, the grid loads real items.

## Groups and zoom

`GET /api/groups?level=years|months|days|all` accepts the same sort, dir, and filters as items. Each element is `{key, itemIds}`. The same ids appear once, in item-sort order inside the group. Groups are ordered by the first item's position in that sort. No cover photo is chosen.

Keys come from `capturedAt`, using the calendar date before `T`:

- years: `YYYY`
- months: `YYYY-MM`
- days and all: `YYYY-MM-DD`

`level=days` and `level=all` return the same keys. The page differs. Days uses a day header and a nominal 240 px row. All uses a day header and a nominal 160 px row. Years is one card per year and Months is one card per month. Each card is a mosaic of that group's thumbs. Switching level keeps every item represented.

The slider has four stops, Years, Months, Days, All. Ctrl+wheel on the grid moves one stop. A burst of wheel events is one step. The item under the pointer stays in view. With no pointer item, anchor the central visible item. Changing level writes `zoomLevel` through the settings API. Default remains `years`.

## Sort

The toolbar sets date, location, or name, and asc or desc. Default is date descending. A change writes `sort` and `dir` through the settings API.

- Date key: `capturedAt`, then id. `dir=desc` reverses that pair.
- Name key: filename casefolded, then `capturedAt`, then id. `dir` reverses that triple.
- Location categories stay in this order for both directions: a place whose name is non-empty, then a place with coordinates and no name, then no `placeId`. `dir` does not swap those categories.
- Inside the named category, `dir` reverses name casefold, then `capturedAt`, then id.
- Inside unnamed GPS, `dir` reverses latitude, then longitude, then `capturedAt`, then id. The numbers are the place's stored coordinates.
- Inside no location, `dir` reverses `capturedAt`, then id.

The location group label is the place name, or `lat,lon` with two digits after the decimal, or the exact text `No location`. Calendar group keys do not change when the sort changes. Their order follows the first sorted item.

F11 uses `a/IMG_1042.jpg`, `b/far.jpg`, and `b/no-exif.jpg`. `no-exif.jpg` keeps `capturedAtSource` `mtime` and `capturedAt` `2022-02-03T04:05:06Z`. Date descending puts the newest `capturedAt` first. Do not edit that fixture's mtime.

F9 uses a fixture-owned library that spans exactly two calendar years. `level=years` returns two groups. Do not require the full media tree to have exactly two years.

## Viewer

Clicking a cell opens `GET /api/media/<id>?which=preview`. ArrowLeft and ArrowRight move through `GET /api/items` for the current sort, not through mosaic geometry. They stop at the ends. Esc closes the viewer and restores the grid scroll position and zoom level. A newly opened item starts fitted. Ctrl+wheel on the open still zooms by 1.1 around the cursor, from fit scale to 16 times fit, with no reflow during the gesture. Middle-button drag pans 1:1. Record the pointer anchor and the pan: the image point under the cursor stays within 2 px, and pan displacement matches the drag within 2 px.

## Gate

Fresh fixture-owned roots. Viewport 1280×720. Artifacts under `docs/features/S04/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `years.png`, `all.png`, `viewer.png`, `groups-years.json`, `groups-months.json`, `groups-days.json`, `groups-all.json`, `input-trace.json`, `measurements.json`, `console.json`, `network.json`.

```powershell
python -m tests.qa slice S04 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F9 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F11 --root "$qaRoot/library-data" --artifacts $evidence
```

The browser starts from an empty library, types the fixture path, chooses Serve from that folder, and waits until the oriented JPEG is visible. Screenshots come from that page. A console error fails the gate. Playwright may stay in the gitignored `.venv`. `library/` must not import it.

The implementer may run these gates and must not call that log the grade. Run S00 through S03 only one at a time.
