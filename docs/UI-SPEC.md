# Library — screen and interaction contract

2026-10-13. Target behavior, not running software. [PRODUCT.md](PRODUCT.md) owns
features; [CONTRACTS.md](CONTRACTS.md) owns data. No new screens or gestures may
be inferred from generated reference art. Windows desktop browser is the primary
taste surface; use a 1280×720 viewport for comparison and 1920×1080 for overflow.

**Windows Presentable Shell** below is first-class product, not a taste overlay.
Steve's stated Windows requirements are locked there. The family-PC definition
of done is the checklist at the end of that section. Until that path is green,
deeper engine slices (S13 settings matrix, S14 whole-product audit) stay
secondary.

## Reference mapping

| Reference | State / retained composition |
|---|---|
| [years](reference/library-years.jpg) | Ready Years: dark background, Library heading, search, Add folder, settings, dated mosaic rows and four-level control |
| [grid](reference/library-grid.jpg) | Ready Days/All: day headings, picture-led dense grid, video duration/play cue and LIVE badge |
| [add folder](reference/library-add-folder.jpg) | The one named modal: editable server-local path, two choices, Cancel/Add |
| [settings](reference/library-settings.jpg) | Settings page: grouped radio choices and listen/port fields; remaining existing settings follow as labeled controls |
| [search](reference/library-search.jpg) | Search query, People/Places/Things chips, result grid and entity inspector |
| [unavailable](reference/library-unavailable.jpg) | Viewer: return control, amber banner, cached picture, entity labels, disabled Open original and video Play preview |

Reference styling is the baseline: dark surfaces, restrained borders, readable
labels, blue selection. Do not redesign layout as a build task. Do not implement
Albums, a storage meter, native window chrome, duplicate navigation, or
“Written by an agent into JSON” copy from these mockups. **Favorite** (viewer
heart, tile hearts ≥144, collapsible Favorites section) and **Reveal in
Explorer** (Windows, selected original or lastKnownPath) are authorized named
actions — not a 17th setting and not albums. Dates, photos, counts and names
in the art are illustrative. Actual fixture content determines results. Use
one consistent header across the views; the grid reference's unrelated sidebar
entries do not create another navigation system. Library and Globe are header
**buttons** with a visible idle border and a pressed fill when that view is
current; Settings is the third view destination. Search is the filtered
Library, Viewer is open media.

Library and Globe (`#view-library`, `#view-globe`) are toggle buttons. Idle
has a visible border. Hover fills a lighter surface and brightens the
border. `:active` insets. `aria-pressed="true"` uses the blue selected
fill. They must read as clickable toggles, not heading text.

## State transitions

| State | Visible behavior and exit |
|---|---|
| Empty library | Library header and Add folder; plain “No pictures yet” in grid. No fake sample pictures. Add opens named dialog. |
| Add folder | On Windows, Browse is the normal path: native folder picker fills the field. Cancel leaves the field unchanged. Typed or pasted paths still work; they are not required. `ask` starts with neither mode selected and Add disabled until path+mode exist. Other defaults preselect a mode, still require Add. Cancel/Esc closes without writes. No file-upload control. |
| Scanning | Close Add as soon as `POST /api/sources` returns 202 for **either** copy-here or serve-from-there. Never leave the dialog open on `busy` or a long scan; if the POST is `busy`, close and show scan status. Library shows a confirmation that the folder was added and a status line with added/skipped/error counts from sources. Poll every second while running. Previously indexed items remain browsable; newly indexed items appear as they become ready, with placeholders until renditions arrive. No percentage without a known denominator. An error leaves counts and readable error text, never a blank page. The serve process prints scan progress on stdout during normal work. |
| Disconnected | Banner “Library is not responding”. Keep the last grid if any. Retry health then catalog every second. Clear the banner when health is 200. Never a blank crash and never a traceback. |
| Ready | Years/Months/Days/All, search, sort, Videos, Size, Dates, hearts and open work on the same current item set. Level and sort persist to settings; selection, current filter, Size, Dates and Favorites collapse are transient. No localStorage truth. The page address is the live listen origin. |
| Live origin | History, Back, and links stay on `window.location.origin` (the process that served this page). Root-relative `/` and `/api/*` only. Never build `http://<host>:<settings.port>` or reuse a stored runtime URL from another listen (QA range 18765–18864 is a common stale port). Browser Back while the page is open closes the viewer or stays on the grid; it does not navigate to another host or port and does not call `history.back()`. |
| Update | Header `#update-library` is labeled Update. Click runs `POST /api/update` and writes a short sentence into `#update-status` (updated / already current / git missing / not a git copy / pull failed). No command prompt. Does not switch branches. |
| Viewer | Show still preview first, then readable original with **no** “Showing original” control; video uses poster then original/proxy, live uses still with motion playback. Back stays top-left. Previous/Next and Rotate sit on a **bottom** bar (`#viewer-nav`). ArrowLeft/ArrowRight still change photo and stop at ends. Zoom is `#viewer-zoom` (range slider) plus existing Ctrl+wheel; no Zoom in/Zoom out buttons. Click-and-drag pans while zoomed; stills also left-drag pan at fit; middle-drag pans stills and video. Rotate turns the displayed still 90° per click and does not rewrite the original. A heart toggles favorite (`catalog/favorites.json`); pressed/filled means favorited. Reveal in Explorer is always present and opens the original's folder when the file is on this computer; disabled with the missing-original banner otherwise. Open with default program is optional and launches that file. Play preview keeps click-to-pause. Person/Place/Thing are **not** pills over the preview. Top-right `#viewer-info` opens a dropdown that lists those entities; a click filters the grid to that entity and closes the viewer. Type-in fields stay inside Info and stay labeled. Esc closes Info first, then the viewer. No box-drawing editor. |
| Original absent, preview present | Exact banner “Original is not on this computer”. Cached preview remains; Open original disabled. Video/live Play preview enabled only if proxy exists. |
| Preview absent or failed | Stable placeholder with “Preview is not available”. If original exists the viewer may still load it. Missing-original banner also appears when both are absent. No broken image icon, endless spinner, or invented retry modal. Rescan is the existing retry operation. |
| Empty search | Query/chips remain; “No matching pictures”. Clearing query/chip returns matching broader grid, no catalog mutation. |
| Settings | Existing 16 settings only, grouped as the reference; change persists through HTTP immediately on valid commit. Inline validation preserves last valid value. Host/port label says “Applies next launch”. Esc returns to prior Library/Globe view. |
| Globe | Realistic local Earth texture (oceans, continents, ice — not abstract blobs) and clusters from visible located items; no-location items absent. Plain “No locations to show” if empty. WebGL unavailable produces inline error text, not another map provider. Horizontal drag yaws with the pointer (inverted from the first grab); vertical drag pitch is unchanged. |
| Tour | Existing globe motion plus media presentation, as specified below. Esc stops motion/playback at current globe position and leaves Globe. No new slideshow settings beyond the three existing tour settings. |

Settings and annotation text input keep normal editing keys: arrows, Space,
Ctrl+C, Ctrl+Z edit focused text rather than triggering viewer navigation or global
history. Global actions apply outside text inputs. Tab order follows visible order,
controls have names, focus is visible, and closing the Add dialog restores its
trigger focus. Error text explains the fixed API error without exposing a traceback.

## Grid, sort, and viewer

Years uses a mosaic per year; Months a mosaic per month. Days includes every
matching item under day headings at a medium cell size. All includes every
item under day headings at a closer default size. Nominal cell sizes at the
level defaults: Years 72 px, Months 104 px, Days 192 px, All 420 px. Those
four sizes must be visually distinct; Years and Months must not share a
pixel size. Fit cells within available width without cropping controls;
thumb crops are permitted in grid, the opened still starts fitted without crop.
Groups and contents follow current sort; date headings express each item's date.
For location/name sorts, group order follows the first occurrence in sorted items,
and within each group items retain that order. No item disappears on level change.

The level slider has four discrete stops, Years → Months → Days → All. Ctrl+wheel
steps one level per wheel event (coalesce an event burst to prevent skipped levels).
Keep the hovered item's center/visible representative in view on level change;
in the new layout it must be within the viewport, not necessarily pixel-identical
because a mosaic changes shape. The level control uses the central visible item
as anchor when no pointer item exists. It cannot jump to an unrelated year.

A Size slider has eight discrete stops (72, 104, 144, 192, 256, 336, 420,
520 px). Changing level sets Size to that level's default. Size only changes
`--cell`; it does not refetch or rebuild tiles. Already-decoded thumbnails
stay painted through Size, level, and scroll. The grid must not clear to an
empty surface while zoom is in progress.

Dates (pressed by default) shows the current level's section headings.
Dates off flattens every matching item onto one continuous wall — one
flex wrap, 2 px gaps, no heading rows, no section margins. Date grouping
stays available; wall is the option for a dense thumbnail sheet at the
smallest sizes. Size and Dates are session view options (`#grid`
`data-size`, `data-group-dates`); they are not settings.json keys.

Tiles use one badge system. Video cells show a VIDEO badge (play mark plus
the word VIDEO, and duration when `metadata.durationSec` exists). Live
cells keep the existing LIVE badge (`.live-badge` text `LIVE`). Badges sit
on the tile and do not crop the media.

The toolbar Videos control sets the transient `kind=video` filter and
`aria-pressed`. Clearing it removes the kind filter. Combined with the
existing sort, this is how the library is filtered to videos.

Hearts: `#grid` `data-hearts=on` when `--cell` is 144 or larger, `off` at
72 and 104. The heart is a button `.heart` in the badge corner (top-left
stack, under the VIDEO/LIVE pill). `aria-pressed` follows the item’s
computed `favorite`. Click/Space on the heart sends
`PUT /api/items/<id>/favorite` and does not open the viewer. A
`#favorites` section is the first block in the grid when the current
result set has at least one hearted item; otherwise it is hidden. The
heading control `#favorites-toggle` starts `aria-expanded="true"` and
collapses only the favorites tiles, not the rest of the grid. Favorites
tiles use `data-slot="fav"` so the same id can also sit in its date/wall
row. Collapse is session-only.

Click a cell opens it. ArrowLeft/ArrowRight navigate. Ctrl+wheel zooms an opened
still or video around the cursor's image coordinate; the viewer zoom slider
maps the same 0.25×–16× fit range. Middle drag moves it 1:1, a still also
pans with a left drag, and any zoomed item pans with a left drag. No reflow
or automatic fit during a gesture. Images and video initially fit; each newly
opened item resets fit and rotation. A still click does nothing. Video/live
click or Space toggles playback. Normal scrolling does not seek. Unsupported
original codec falls back to proxy, not a silent freeze.

Proxy policy: `off` never autoplays; `days-and-all` plays only the hovered cell at
those levels; `always` also permits hover playback within Years/Months mosaics.
No policy autoplays all cells. Hover leave stops and restores still/poster; muted,
looped proxy never starts audio. Explicit viewer play is independent of hover setting.
The hover proxy is position-absolute over the still and `object-fit: cover`s the
entire cell. The still is not hidden by a `display` rule that would leave it
flex-sharing the tile. No split still+video.

## Search and annotation

Enter query or choose one entity-type chip; chips restrict name matching. Results
use the same grid/open/sort behavior. Clicking a displayed entity label sets its
id filter and inspector; inspector count and filenames come from matching unique
item ids, never the number of locations. Search matching multiple entities shows
the grid until a specific entity is selected, avoiding an invented entity chooser.
Viewer fields append names/associations on Enter or loss-of-focus commit; failed
requests retain text and show inline error. Person merge is the existing CLI/HTTP
operation; no merge wizard is authorized. Labels update after rename/merge.

## Globe and tour motion (no reference image exists)

Ship a realistic equirectangular Earth texture locally (`/assets/earth.png`),
record its license in the app. No network tiles. Drag rotates earth by 0.25
degrees per pixel; **rightward drag increases yaw** (eastward turn); upward
drag increases pitch. Clamp poles just before inversion. Wheel zooms by 1.1,
keeping the picked surface point within 2 screen pixels; use center anchoring if
pointer misses the globe. No network tiles, geocoder, analytics or coordinate upload.

Cluster projected pins deterministically: sort by place id; connected pins within
32 screen pixels form a cluster, centroid of their screen positions. Recompute
after camera movement ends; counts are distinct item counts. A single pin uses
the same interaction. Clicking sets place-id filter to cluster members and opens
the newest matching item (date then id). Esc leaves that filtered grid; opening
Globe again returns to globe state.

Play follows the ordered tour list from CONTRACTS. Orbit around the vertical
axis at 6 degrees/second for tourOrbitSec; ease camera to next place over 1 second;
present up to tourPictures at tourPictureSec per item; ease out over 1 second;
orbit and advance, wrapping at end. Stills/live show preview, videos play muted
proxy for the allotted time. Never require original availability. Query eligibility
again each cycle; skip unreadable/missing previews. Empty list leaves camera still
and says “No locations to show”. Esc at any phase cancels timers/media and stays
at current position. While touring, user drag/wheel first stops the tour and then
applies that same gesture, so playback does not fight the user.

## Keyboard and proof

Use PRODUCT's keyboard table, plus the focused-text exception above. Esc cancels
the innermost active interaction: tour/gesture, Add dialog, Viewer, Settings,
then selection. There is no modal on top of a tour. Ctrl+F focuses search, Ctrl+,
opens Settings. Ctrl+C copies the primary path, with missing-path notice when
needed. Do not add cut/paste filesystem mutations to satisfy a general baseline.
Anticipated Soon keys (F, I, F11, `?`, Home/End) are listed in Windows
Presentable Shell; they are not required of F21 until that backlog row is built.

Each browser gate must drive actual controls, assert resulting data/state, inspect
its saved PNG, and retain console/network diagnostics. Required proofs include:

- Grid has fixture ids and date groups; click opens the correct picture, arrows
  respect filter, Esc restores scroll; not merely endpoint returns 200.
- Level anchor remains visible; viewer and globe cursor anchor drift <=2 px;
  pan displacement equals drag within 2 px. Record numeric measurements.
- Hover plays only the permitted cell and stops on exit, live badge identifies
  paired media, original failure falls back visibly, missing preview never spins.
- Tour traces orbit → zoom-in → media → zoom-out → orbit; settings change durations
  within one rendered frame plus 100 ms; Esc cancels in every phase. Use virtual
  clock in automated checks and one ordinary-time recording for visual proof.
- Settings survive reload/restart, typing does not trigger global shortcuts,
  entity inspector matches data, every named state has a screenshot.
- Block outbound network while globe/browsing runs and retain the request log.

These assertions extend each feature's existing Check; they are not separately
counted features. Passing only an API half never closes a UI feature.

## Windows Presentable Shell

First-class shell contract for the family Windows PC. Not a 23rd Check, not
albums, not an editor, not a cloud. PRODUCT F2 / F4 / F7 / F9 / F10 / F11 /
F12 / F18 / F21 / F22 already name the operations; this section is the
presentable surface those Checks must look like.

Do not invent accounts, phone sync, editing suites, or albums-as-cloud.
Originals stay files on disk. New routes, settings, or errors still require
a CONTRACTS edit before code.

### Locked from Steve (stated requirements)

**Launch and update.** Double-click `Library.bat` in the app folder. It runs
`launch.ps1` in a visible console so scan progress is readable. Nobody types
a command prompt. Header **Update** (`#update-library`) pulls the current git
branch (`git fetch` then `git pull --ff-only`) and writes one sentence into
`#update-status`: updated / already current / git missing / not a git copy /
pull failed. It does not switch branches or open GitHub Desktop. A copy that
is not a git folder, or a PC without git, says so in that same line.
macOS/Linux launch stays `launch.sh` and is **pinned later** — not graded on
this family-PC path.

**Add folder.** Browse opens the native folder picker on this computer and
fills the path. Typed or pasted paths still work; they are not required.
After Add, the dialog closes on the 202 (or on `busy`). The library confirms
the folder. Scan progress appears in `#scan-status` and the server console.
Pictures show as they become ready. The dialog never stays open on a dead
`busy` wait. No upload control.

**Reliability.** Back (in-app or the browser button) stays on the live
`window.location.origin` and port. It must not jump to a leftover QA listen
such as `127.0.0.1:18765`. History, links, and fetches use the current origin
or root-relative paths. A client abort (`BrokenPipeError`,
`ConnectionResetError`, `ConnectionAbortedError`, WinError 10053) is
non-fatal: no 500, no `internal-error`, server keeps serving. Normal scan
progress prints on stdout, not only failures. Disconnected banner:
“Library is not responding”; retry until health is 200.

**Grid.** Hovered video proxy fills the whole tile; the still stays underneath
as the poster. No split still-on-one-side / video-on-the-other. Every video
cell shows a VIDEO badge (play mark + VIDEO + duration when known); live
cells keep LIVE. Toolbar **Videos** is a transient `kind=video` filter, not
a setting. Size has eight discrete stops (72, 104, 144, 192, 256, 336, 420,
520). Already-decoded thumbs stay painted through Size, level, and scroll —
the grid does not blank. Dates off is one continuous wall (2 px gaps, no
heading rows). Library and Globe in the header are pressed/unpressed
**buttons**: idle border, hover fill, `:active` inset, `aria-pressed`
selected fill. They must not read as heading text.

**Favorites.** Viewer heart marks or clears the item in `catalog/favorites.json`.
Tile hearts appear at Size 144 and up, same badge-corner language, and do
not open the viewer. At 72 and 104 the tile heart hides. A Favorites strip
sits at the top of the Library grid whenever any current result is hearted;
it starts expanded and can collapse to its heading. Hearted items also stay
in their date or wall positions. Ctrl+Z undoes a heart. This is not an
album system.

**Viewer (Windows Photo Viewer–ish).** Bottom bar holds Previous, Rotate,
zoom **slider**, Next. Left/Right arrows change photo and stop at the ends.
Back (and Esc) returns to the grid he came from on the same live origin.
Zoom is the slider (`#viewer-zoom`, 0.25×–16×) plus existing Ctrl+wheel —
not Zoom in / Zoom out buttons. Click-and-drag pans while zoomed; a still
also left-drags at fit; middle-drag pans stills and video. Rotate turns the
displayed still 90° and does not rewrite the file. No “Showing original”
button, badge, or highlight — preview loads first, then the original when
it is here. Person / Place / Thing are **not** pills painted over the
preview. Top-right **Info** (`#viewer-info`) opens a dropdown of those
entities; clicking one filters the grid to that entity and closes the
viewer. Type-in fields stay inside Info and stay labeled Person, Place,
and Thing. **Reveal in Explorer** opens the original's folder
(`explorer /select` on Windows) when the file is here; disabled with the
missing-original banner otherwise. **Open with default program** is
optional and launches that file. Play preview still toggles pause/play on
click. Space plays or pauses video.

**Globe.** Shipped realistic local Earth texture (`/assets/earth.png`), no
network tiles. Drag right yaws east (inverted from the first grab); up/down
pitch is unchanged. Cluster click already opens the newest item and leaves
a filtered grid on Esc.

**Pinned later.** macOS/Linux `launch.sh` and those platforms' volume
identity. Do not block the family-PC path on them.

### Spec target vs current implementation

`taste/windows-abc` (merged Track A + globe + Track B viewer + Track C grid)
already carries most of the locked chrome. This table is so the next
implementer changes the remaining gaps and does **not** revive retired
chrome.

| Surface | Spec target | On `taste/windows-abc` | Gap |
|---|---|---|---|
| Launch | Double-click `Library.bat` → visible console + browser | `Library.bat` present | F2 Check still pending; family-PC pull not graded |
| Update | Header Update; one status sentence; no CMD | `#update-library` / `#update-status` | Prove on a real git copy; fail sentences must stay family-readable |
| Add folder | Native Browse; close on 202; confirm; progress; items as ready | Picker + 202-before-finish + `#scan-status` | Linux QA gets `picker-unavailable` (expected). Busy-limbo must stay gone |
| Back / origin | Stay on live origin/port | Track A live-origin | Do not reintroduce `settings.port` URLs |
| Disconnect | Non-fatal abort; banner + retry | Non-fatal + banner | — |
| Video tile | Full-tile hover; VIDEO badge | Track C | — |
| Videos filter | Transient `kind=video` | `#filter-videos` | — |
| Size / zoom | ≥8 stops; thumbs stay painted | 8 stops 72–520 | — |
| Dates off | Dense wall, no section gaps | `data-group-dates` | — |
| Library / Globe | Button affordances | `aria-pressed` toggles | — |
| Hearts | Viewer + tile ≥144 + Favorites strip | Shared `favorites.json` | — |
| Prev / Next | Bottom bar; arrow keys; stop at ends | `#viewer-nav` / `#viewer-bottom` | — |
| Zoom | Slider + Ctrl+wheel; **no** zoom buttons | `#viewer-zoom` range | Do not bring back Zoom in / Zoom out |
| Pan / rotate | Click-drag pan; Rotate beside Prev/Next | Present | — |
| Overlay pills | **Forbidden** — Info dropdown only | Info dropdown; labels are buttons inside it | Do not paint Person/Place/Thing over the preview |
| “Showing original” | **Forbidden** — no control, no highlight | Control removed; leftover JS only deletes `dataset.showingOriginal` | Do not restore a highlight or button |
| Reveal / open | Reveal in Explorer; optional default app | Both buttons | — |
| Info filter | Click entity → filtered grid, viewer closes | `filterByEntity` | Keep type-in fields inside Info |
| Globe | Invert yaw; realistic local Earth | `earth.png` + inverted yaw | Cluster hover polish is Soon, not a gap in this lock |
| macOS / Linux launch | Pinned later | `launch.sh` exists; not graded | Do not claim F2 from Windows alone |

Retired chrome (do not ship, do not treat reference art as permission to
return): overlay Person/Place/Thing pills, “Showing original”, discrete
Zoom in / Zoom out buttons, Albums, storage meter, keybinding editor.

### Anticipated shell backlog

Studied, then filtered to this product (portable USB library, no accounts,
preserve originals, no editing suite): Windows Photo Viewer, Windows Photos,
Apple Photos browse/viewer chrome only, Google Photos local-feel browse,
Lightroom/Bridge-lite, Digikam, XnView-class browsers. Each row is a
feature Steve has not yet named and will almost certainly want. **Must**
means the family-PC path feels unfinished without it. **Soon** is the next
obvious ask after that path is green. **Later** waits, or conflicts with a
locked boundary.

Do **not** add: cloud accounts, phone sync, editing, albums-as-cloud,
ratings-as-albums, compare/survey modules, a keybinding editor, or map
tile networks.

A Soon/Later row that needs a new route, setting, or error is **not**
authorized to start until CONTRACTS lists it. Slideshow, fullscreen,
cheat-sheet, multi-select, and window title are page chrome on existing
APIs.

| Pri | Feature | Why it belongs (and the bound) |
|---|---|---|
| Must | First-run empty library | Header + Add folder + plain “No pictures yet”. Add is the obvious next click. No fake samples. Already named in Empty library; this row forbids shipping a dead empty page. |
| Must | Scan / add empty states | After Add: confirmation + counts. An error leaves counts and readable error text, never a blank page or a stuck dialog. Already named in Scanning. |
| Must | Window title / taskbar identity | Document title stays `Library` (optionally `Library — N pictures` when N is known). The tab and taskbar must not look like a raw `file://` or a random localhost mystery. No Electron chrome. Favicon may be a small mark later; a blank `data:,` icon is acceptable until then. |
| Soon | Slideshow | Every family viewer has this (Photo Viewer F11, Photos F5, Apple Photos slideshow, XnView). Play from the viewer (and optionally the grid). Default interval 5 s, session-only — **no** 17th setting. Esc stops and leaves the current item. Space pauses/resumes the slideshow; arrows still step. Videos play the proxy for the interval, not the whole file. Reuse the current filter/sort. |
| Soon | Fullscreen / F11 | Photo Viewer and Photos both fullscreen the picture. F11 toggles viewer fullscreen; Esc leaves fullscreen first, then the viewer (existing Esc stack). Double-click the still may toggle fullscreen. Not a native window chrome rewrite. |
| Soon | Keyboard cheat-sheet | In-app `?` or F1 overlay listing the locked keys. Not an editor. Proposed additions once this row is built: Space play/pause video (already locked); F favorite; I toggle Info; `+` / `-` or wheel zoom (Ctrl+wheel already locked); F11 fullscreen; Home/End first/last in the current set. Do not steal those letters from focused text fields. |
| Soon | Copy path (already F18) + copy file | Ctrl+C already copies the primary path. A named **Copy file** that writes bytes somewhere else is a copy-originals operation — promote in CONTRACTS first, never silently duplicate a folder. Until then, Reveal and Copy path are enough. |
| Soon | Multi-select | Shift+click range and Ctrl+click toggle on the grid, Lightroom/XnView/Explorer-style. Batch favorite or batch Reveal only. No batch delete, no batch export. Selection is session-only. Esc clears selection after other innermost layers. |
| Soon | Right-click on a tile / open item | Favorite, Reveal in Explorer, Copy path. Same actions as the buttons. No “Send to”, no cloud share. |
| Soon | Viewer “n of N” and filename | Photo Viewer showed where you are. A quiet `3 of 128` plus the filename on the viewer bar. Not a metadata editor. |
| Soon | Filmstrip under the viewer | XnView / Lightroom / several local viewers keep neighbors visible. Optional strip of nearby thumbs; click jumps. Session-only; hide in fullscreen if chrome is hidden. |
| Soon | Cluster UX polish | Pin → viewer already exists. Hover shows count; overlapping pins stay one cluster; after Esc the filtered grid names the place if it has one. No geocoder. |
| Soon | Remember last view | Last Library vs Globe, and last entity filter, for the browser session. Zoom level and sort already persist in settings.json. Size and Dates stay session (locked). Do not persist browser window size — this is a tab, not Electron. |
| Soon | Remove from library | Apple Photos distinguishes “remove from library” vs “delete photo”. Here: drop the catalog records / source registration and **leave original bytes**. Confirm. Undo restores catalog, not a recycle-bin dance. Needs a CONTRACTS command before code. This is not Delete. |
| Later | Delete / trash originals | Conflicts with “never overwrite or reorganize originals” unless it is an explicit, confirmed send-to-Recycle-Bin of a **copied** original, never a linked one. Default is off the family path. Do not add a toolbar Delete until Steve asks. |
| Later | Print | Photos/Photo Viewer have Ctrl+P. Browser print of the current still is enough if anyone asks. No print layout suite. |
| Later | Share / export | USB copy-here is already the product. A share sheet or cloud export fights “no accounts”. A later “copy these files to a folder” may be the same as Copy file. |
| Later | Face / people browser | Info already lists people and filters the grid. A People view that groups faces is a later F14 surface, not tonight’s shell. No on-device model. |
| Later | macOS / Linux launch | Already pinned. F2 stays pending until those runners exist. |
| Later | Compare, ratings 1–5, contact sheets | Lightroom/Digikam features. Hearts cover “keep this one”. Out of scope. |

Forbidden even as Later flavor: accounts, Immich-style remote hosting, phone
sync, destructive auto-organize, albums, storage meters.

### Presentable for family PC — definition of done

One path. Until every row is green on a Windows family PC (double-click,
not a developer shell), S13-class settings/keyboard matrix work is
secondary. Fixture Checks stay the grade for F-ids; this checklist is the
taste gate that tells Steve the box is presentable.

| # | Step | Pass |
|---|---|---|
| 1 | Double-click `Library.bat` | Visible console; browser opens on this PC at the live listen URL; title reads Library; empty library shows “No pictures yet” and Add folder |
| 2 | Update | Header Update runs without a command prompt. Status sentence is readable (updated / already current / git missing / not a git copy / pull failed). Does not switch branches |
| 3 | Add folder | Browse opens the native picker; path fills; copy-or-link confirmed; Add closes the dialog |
| 4 | Progress | `#scan-status` and the console show work; no busy-limbo dialog; items appear as they become ready |
| 5 | Wall | Dates off is a dense thumbnail wall; Size has ≥8 stops; thumbs stay painted while zooming; Library/Globe look like buttons |
| 6 | Open | Click a cell; preview then original; no “Showing original”; no overlay pills |
| 7 | Next / Prev / arrows | Bottom Previous and Next; Left/Right arrows; stop at the ends; Back returns to the same origin/port |
| 8 | Zoom / pan / rotate | Slider zooms; click-drag pans; Rotate beside Prev/Next turns the display only |
| 9 | Favorite | Viewer heart writes `catalog/favorites.json`; tile heart at large Size; Favorites strip can collapse |
| 10 | Reveal in Explorer | Opens the original's folder with the file selected when the file is here |
| 11 | Info filter | Info dropdown; click a person/place/thing; grid filters to that entity; viewer closes |
| 12 | Videos filter | Toolbar Videos keeps only videos; hover fills the tile; VIDEO badge visible |
| 13 | Globe basics | Realistic local Earth; drag right yaws east; cluster opens the newest item; Esc leaves the filtered grid |

All 13 green ⇒ presentable for the family PC. Slideshow, fullscreen,
cheat-sheet, multi-select, and remove-from-library are Soon — they do not
block this gate. Deeper settings, F3 parity, and macOS/Linux launch do not
block this gate. A missing row on this path **does** block calling the
shell presentable, even if an F-id already has an API artifact.
