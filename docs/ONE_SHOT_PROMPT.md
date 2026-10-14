# Library — one-shot rebuild prompt

Copy everything below the line into an AI that can write a local app.
This file is the prompt, not a description of a prompt. Pair it with
[UI-SPEC.md](UI-SPEC.md) (screens and DoD) and [PRODUCT.md](PRODUCT.md)
(22 Checks) when those files are in reach. If they are not, this text
is enough to rebuild the product near one-shot.

---

Build **Library**: a portable, local photo-and-video library for a
Windows family PC. Steve copies one folder onto a USB drive or the
desktop, double-clicks `Library.bat`, and his mother-in-law browses
pictures and videos that are already on disk. An agent (or a person)
can then write who, where, and what is in them so they can be found
again. Rebuild the whole product. Do not invent a different app.

## Audience and how it is used

Steve sets it up once. His mother-in-law browses. Existing photos and
videos are already scattered through folders, often on external drives
and iPhone backups. In one sitting: launch the Library folder, point it
at those pictures, browse small pictures quickly, open one, play a
video with sound, Reveal the real file in Explorer, Update the app
from git without a command prompt.

The phone copier is a different tool (iphonePhotos). When that copy
has landed in a folder, add the folder here.

## Hard constraints

- **Windows first.** Double-click `Library.bat` (visible console →
  `launch.ps1`). Browser on `127.0.0.1:8765`. macOS/Linux `launch.sh`
  may exist; do not claim it is graded.
- **Portable folder, not an installer.** App folder + `library-data/`
  travel together. No MSI, no Electron, no Store package, no accounts.
- **Family Update is git.** Header **Update Library** and `Update.bat`
  / `launch.ps1 -Update` run `git fetch` then `git pull --ff-only` on
  the **current** branch. While it runs: Updating… Then one sentence:
  updated / already current / git missing / not a git copy / pull
  failed. Header `#library-version` shows the short checkout SHA (or
  `local`). A successful Update refreshes the SHA; the serve process
  does not restart. Never switch branches. Never ask anyone to type git.
- **Preserve originals.** Add folder asks: copy onto this drive, or
  serve that folder where it is. Default prompt is `ask`. Never
  overwrite or reorganize originals. Copy collisions write `name_2.ext`.
  Undo of a copy leaves the bytes. Delete key removes from the library
  (confirm; bytes stay). Delete file is a separate extra confirm +
  Recycle Bin.
- **No cloud default.** No accounts, cloud sync, share links, cloud AI,
  cloud geocoder, or uploaded faces/pixels. Optional local packs
  (`Setup.bat` / `setup-geo` / `setup-ml`) download into `library-data/`
  once; browse works without them. The globe ships its own Earth
  texture. Ordinary browsing works with the network blocked.
- **Python 3.12+ and ffmpeg.** Launcher installs them with winget on
  Windows if missing (`Python.Python.3.12`, `Gyan.FFmpeg`). One
  `library/` package, `library/web/` static assets, CLI `python -m
  library --root <library-data> <command>`. Same operations over HTTP.
- **JSON catalog is truth.** One JSON record per picture, person,
  place, thing. SQLite is a disposable search index rebuilt from those
  records. Relative local paths; volume identity (not drive letter) for
  linked drives. Runtime catalogs are never tracked in git.
- **22 feature Checks, no 23rd.** A feature is done when its Check has
  a STATUS artifact. Taste chrome is the UI-SPEC presentable checklist,
  not another Check. Synthetic/supplied test media only.

## What this is not

Not the phone copier. Not a cloud host. Not a bundled required image
model. Not a desktop-browser shell rewrite. Not an in-app editor (use
Open with the default app). Not albums, storage meters, keybinding
editors, ratings 1–5, contact sheets, filmstrip, multi-select, Print,
or a `?` cheat-sheet — those last items may exist later as Soon; they
do not block presentable. Do not restore overlay Person/Place/Thing
pills, a “Showing original” **control**, discrete Zoom in/out buttons,
or a second Level slider.

## Architecture sketch

```text
app-folder/                 # the thing you copy; git checkout
  Library.bat               # visible console → launch.ps1
  Update.bat                # same as header Update
  Setup.bat                 # optional: setup-geo + setup-ml objects + faces
  launch.ps1 / launch.sh
  library/                  # Python package
    __main__.py
    web/                    # index.html, library.js, style.css, globe.js
    web/assets/earth.png    # local realistic Earth; license beside it
  library-data/             # created on first launch; beside the launcher
    settings.json           # exactly 16 user keys + schemaVersion
    logs/server.log
    undo/
    catalog/
      sources/<id>.json
      items/<id>.json
      people/<id>.json
      places/<id>.json
      things/<id>.json
      favorites.json        # {schemaVersion:1,itemIds:[…]}
      catalog.sqlite        # rebuilt from JSON
    geo/                    # optional; setup-geo; not in git
    models/                 # optional; setup-ml; not in git
    renditions/<id>/        # thumb.webp preview.webp poster.webp
                            # proxy.mp4 (silent ≤480) playback.mp4 (full+sound)
    originals/<source>/     # only when a folder was copied here
```

CLI and HTTP call one application service. A running server is the sole
catalog writer. Bind `127.0.0.1:8765` unless settings say otherwise.
Binding every interface is a setting, off by default. Page, History,
Back, and fetches stay on the live origin (`window.location.origin` or
root-relative `/api/*`). Never embed `settings.port` or a leftover QA
port such as 18765.

Item id is SHA-256 of file bytes. Until hashed: `pending-<sourceId>-<path-digest>`,
then atomic merge. Two files with the same hash are one item. Live Photo
= still + motion sharing an Apple content identifier; id is the still
hash; grid badge LIVE.

Supported pictures: JPEG, PNG, GIF, WebP, HEIC, HEIF, TIFF, BMP.
Supported videos: MP4, MOV, M4V, AVI, MKV, WEBM. Date: EXIF
DateTimeOriginal, then CreateDate, then `YYYY-MM-DD` / `YYYYMMDD` in
the filename, then mtime. GPS from EXIF (JPEG/HEIC) or QuickTime
ISO6709 (MOV/MP4). Place name is not in the file.

`GET /api/media/<id>?which=thumb|preview|poster|proxy|playback|original`
returns bytes. `original` missing → 404 `unavailable`.

## How the features work

### Launch, Update, Setup

`Library.bat` starts `launch.ps1` in a visible console, checks
Python/ffmpeg, starts the server, opens the browser. Second launch
against the same library folder reuses the matching-root server; it
does not create a second catalog. Header **Update Library** calls
`POST /api/update`. `#library-version` reads `GET /api/version`.
`Setup.bat` is the portable one-click for optional local packs. It is
not required to browse. There is no MSI.

### Add a folder and scan

Add folder: path + two choices. On Windows, Browse is a native folder
picker (`POST /api/pick-folder`). Dialog closes on HTTP 202 for either
mode. Scan progress in the page and the console. Items appear as they
become ready.

**Copy onto this drive** → `library-data/originals/<safe-name>-<source-id>/`,
structure preserved; copies are primary and travel with the library.
**Serve from that folder** → remember volume serial + path from that
volume’s root; nothing copied. A later Copy onto this drive on a
linked source copies files, keeps the same item ids, leaves the old
folder untouched.

Scan walks recursively; skips `library-data/` and `.library/`; skips
unchanged size+mtime. Resumable. HEIC that fails to decode still gets
a record and an error placeholder.

### Grid: Size, Dates, hover, hearts

One density slider `#size-slider`: eight stops 72, 104, 144, 192, 256,
336, 420, 520. It only changes `--cell`. Ctrl+wheel on the grid steps
Size only. Plain wheel scrolls. There is no Level slider.

Separate `#date-group`: **Years / Months / Days / Off**. Years = one
mosaic card per year. Months = one card per month. Days = a header per
day and those photos. Off = one continuous wall (blob) — no date
sections. Years/Months/Days persist as `zoomLevel` (`all` displays as
Days). Off and Size are session-only. Changing Dates or Size keeps
already-loaded thumbs painted; the item under the cursor stays in view.

**Hover lock (shipped, PR #17):** muted looped `proxy.mp4` plays on the
cell under the pointer in **Years, Months, Days, and Off** at every
Size 72–520. Still stays underneath as a poster. No split still+video.
`playProxies=off` disables. `days-and-all` (default) and `always` both
hover-play at every Dates grouping. Leave restores the poster. A
catalog rebuild must resume the hovered proxy. Every video cell shows
a VIDEO badge; live cells show LIVE. `.tile-scrub` seeks the hover
preview without opening the viewer. Clicking a video tile opens the
viewer at that tile `currentTime` and autoplays.

Hearts: tile heart at Size ≥144; hidden at 72/104. Viewer heart.
`catalog/favorites.json`. Collapsible Favorites strip at the top of
the grid when any current result is hearted. Hearted items also stay
in their date/wall positions. Ctrl+Z undoes a heart.

Toolbar: sort Newest / Oldest / Name (`sort=date&dir=desc`,
`sort=date&dir=asc`, `sort=name`). Filters All / Photos
(`kind=photo,live`) / Videos (`kind=video`) / Favorites
(`favorite=1`), mutually exclusive. Search matches filename,
`YYYY` / `YYYY-MM` / `YYYY-MM-DD`, and person/place/thing names.
Empty: “No matches for …”. Chips limit to People / Places / Things.

Library and Globe in the header are pressed/unpressed buttons, not
labels.

### Viewer

Click a cell. Back top-left (same live origin). Bottom bar:
Previous / Rotate / Next (Windows Photo Viewer). Arrows change photo
and stop at the ends. Zoom is a **vertical side** `#viewer-zoom-slider`
with live `#viewer-zoom-pct` (25–1600 = 0.25×–16× fit). **Plain wheel**
is the primary zoom (cursor-anchored). Ctrl+wheel and Ctrl++/− stay.
Ctrl+0 fit; Ctrl+1 100%; Ctrl+R rotate display 90° (does not rewrite
the file). Click-hold pans while zoomed; stills also left-drag; middle
drag pans. F11 or F fullscreen; Esc leaves fullscreen, then the
viewer. F5 slideshow (5 s, session-only); Space pauses; Esc stops;
empty “Add photos first”. Space plays/pauses video when no slideshow.

Photo: `preview.webp` first, then original. **No** “Showing original”
control. Video: poster, then silent proxy immediately (**Preview**),
then swap to the original if the browser can decode it (**Original**),
else to `playback.mp4` (**Full**) — full pixel size, H.264 + AAC,
remux when the bitstream allows. iPhone `.MOV` / HEVC must not stay
on the silent 480 px proxy forever. `#viewer-source` beside the
filename stays honest: Preview, Loading full…, Original, Full, or
Preview — full unavailable. Never label a silent proxy Original. The
swap keeps `currentTime`, play/pause, and the current scale/pan.
Layout uses catalog width/height, not the proxy’s 480 px.
`#viewer-scrub` + `#viewer-mute` + `#viewer-volume` sit in
`#viewer-bottom`, not over the picture. Hover proxies stay silent.

Reveal in Explorer and Open sit side by side. Reveal launches
`explorer.exe` as argv `["explorer.exe", "/select," + absolutePath]`
— comma glued to the path, **no extra quotes** — so
`J:\Iphone Backup\Another Rope Swing.MOV` selects that file. **Shipped
on PR #17** (TASTE-REVEAL 52/52). The older string
`explorer.exe /select,"fullpath"` opens Documents on spaces; do not
restore it. Missing original → 404 `unavailable`, banner
“Original is not on this computer”, never Documents. Open is
`os.startfile` on Windows.

Info is a top-right dropdown, not overlay pills. File facts first
(date, camera, dimensions, size, path, GPS; empty “No camera info for
this file.”), then people / places / things. Unnamed face clusters
show as **Unnamed**; type a name in Person. Clicking a name filters
the grid. Person / Place / Thing type-in fields stay inside Info.

Remove: Delete key + confirm (“Remove from Library? The file stays on
disk.”). Delete file: extra confirm + Recycle Bin. Undo restores
catalog only for delete-file.

### Offline, globe, names

Unavailable linked originals stay in the grid by default (thumb if
present) with the missing-original banner. Hide is a setting.

Globe: local WebGL Earth (`/assets/earth.png`), no map tiles, no
network. Drag right yaws east (inverted from the first grab). Wheel
zooms about the cursor. Overlapping pins cluster (32 px). Click
cluster → filter to those places and open the newest. Esc leaves the
filtered grid. Play starts a tour: orbit, zoom into a place, show up
to `tourPictures` (default 5) for `tourPictureSec` (default 3), zoom
out, repeat. Esc stops and stays.

People / places / things are JSON files. Search reads ids, not pixels.
`annotate` is the write path. Optional **local** packs, after Setup:

- `setup-geo` / `analyze-places` — GeoNames-class cities in
  `library-data/geo/`. Fills null GPS `place.name` (`Chicago, Illinois`).
  Never overwrites a human/agent name. No cloud geocoder.
- `setup-ml objects` / `analyze` — YOLOv8n ONNX CPU. Writes Things
  through annotate. Human tags stay. Ignore COCO `person`.
- `setup-ml faces` / `infer-faces` — InsightFace buffalo_s ONNX.
  Detect, embed, cluster **unnamed** people. Never upload faces. Never
  guess a real name. `people merge` reassigns faces and embeddings.

Browse works with no models (`models-missing` / `model-unavailable`).

### Settings, undo, keyboard

Exactly 16 settings (plus `schemaVersion`): `previewStore`,
`unavailableItems`, `addFolderDefault`, `playProxies`, `listenHost`,
`port`, `thumbPx`, `previewPx`, `proxyWidth`, `placeMatchMeters`,
`tourOrbitSec`, `tourPictures`, `tourPictureSec`, `sort`, `dir`,
`zoomLevel`. Defaults: with-server, show, ask, days-and-all,
127.0.0.1, 8765, 320, 1600, 480, 100, 8, 5, 3, date, desc, years.
`days-and-all` and `always` both hover-play in Years/Months/Days/Off
(PR #17). Only `off` leaves tiles still.

Ctrl+Z / Ctrl+Shift+Z undo/redo catalog and settings (~500 file
steps). Esc cancels the innermost: confirm, Info, slideshow,
fullscreen, tour/gesture, Add dialog, viewer, settings, then
selection. Ctrl+F search. Ctrl+, settings. Ctrl+C copies the primary
path. Focused text fields keep their keys.

## Presentable for family PC — definition of done

One path on a real Windows family PC (double-click, not a developer
shell). Until every row is green, do not start S13 settings completeness
or Soon rows (filmstrip, multi-select, Print, `?`, recently added).

1. Double-click `Library.bat` — visible console; browser on the live
   URL; title Library.
2. Empty / first-run — “No pictures yet”; Add folder is the CTA; no
   fake samples.
3. Update — Updating… then a sentence; header shows the checkout SHA;
   no CMD; no branch switch.
4. Add folder — native picker; copy-or-link; dialog closes on 202.
5. Progress / scan error — status + console; items as ready; Retry,
   never a blank page.
6. Wall + sort + filters — Dates Off = one wall; Years/Months/Days
   separate from Size; ≥8 sizes; thumbs stay; **hover in Years and
   Months**; Newest/Oldest/Name; All / Photos / Videos / Favorites.
7. Search — filename, date, or a tag; empty “No matches for …”.
8. Open — preview then original or `playback`; no “Showing original”
   control; `#viewer-source` Preview / Loading full… / Original / Full
   / Preview — full unavailable; no overlay pills; missing-file
   placeholder. **MOV reaches Full with sound**, not silent forever.
9. Next / Prev / arrows — bottom Previous and Next; stop at ends;
   Back stays on this origin.
10. Keyboard parity — Ctrl++/− or plain wheel zoom; Ctrl+0 fit;
    Ctrl+1 100%; Ctrl+R rotate; Space play/pause video; tooltips.
11. Zoom / pan / rotate — vertical side zoom with %; click-drag pan;
    Rotate beside Prev/Next; Size ≠ Dates; scrub + mute/volume in
    `#viewer-bottom`.
12. Fullscreen — F11 or F; Esc exits fullscreen, then the viewer.
13. Slideshow — F5; Space pauses; Esc stops; empty “Add photos first”.
14. Favorite — viewer heart; tile heart at large Size; Favorites strip
    can collapse.
15. Reveal + Open — side by side; Reveal argv survives spaces
    (`Iphone Backup`); missing original = banner, never Documents.
16. Info — file facts first (or “No camera info”), then names; click
    filters the grid.
17. Remove / Delete file — Delete key removes from library (confirm,
    bytes stay). Delete file extra-confirms and Recycle-Bins.
18. Reconnect — “Library is not responding”; health 200 clears it.
19. Globe basics — local Earth; drag right yaws east; cluster opens
    newest; Esc leaves the filtered grid.

All 19 green ⇒ presentable. Optional Setup / geo / objects / faces do
not block this gate. A missing Must row does, even if an F-id already
has an API artifact.

## Non-goals

Accounts, cloud sync, share links, cloud AI, cloud geocoder, uploaded
faces, in-app edit, cloud albums, MSI, Electron, light-table/compare,
batch convert, burn, email, ratings 1–5, contact sheets, keybinding
editor, albums-as-product, storage meter. Do not add a 17th setting
or a 23rd Check. macOS/Linux launch stays pinned until verified.

## Build order and proof

Foundation (settings, lock, undo, log) → linked scan + identity →
dates/GPS → still renditions → browse/open (M1) → copy/link + all
formats + video proxy → preview store + unavailable → annotate +
rebuild → viewer fields + search (M2) → globe + tour (M3) → Live
Photos → settings/keyboard/whole-page Checks. Taste chrome (this
prompt’s presentable path) sits on that engine; close Must gaps
before S13/S14.

There are 22 Checks (F1–F22). Fresh verifier evidence in STATUS
closes a Check. API 200 alone never closes a screen feature. Use
fixture-owned temp libraries, never a real photo disk, for Checks.

When this prompt and a live tree disagree, the honesty table in
UI-SPEC (“Spec target vs current implementation”) wins for *what is
already shipped*. This prompt wins for *what to build*.

**Shipped on PR #17** (`cursor/reveal-spaces-hover-proxy-c876`,
TASTE-VIDEO 92/92, TASTE-REVEAL 52/52): Reveal argv that survives
spaces; hover play + tile scrub in dated Years **and** Months;
`#viewer-source` Preview / Loading full… / Original / Full; MOV
`playback.mp4` with sound. Do not reopen those.

**Still specified, not required to browse:** `Setup.bat` and the
optional local packs (places / objects / faces on sibling PRs #13
#15 #16). Do not call an unmerged pack shipped.
