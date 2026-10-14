# Library — screen and interaction contract

2026-10-13. Target behavior, not running software. [PRODUCT.md](PRODUCT.md) owns
features; [CONTRACTS.md](CONTRACTS.md) owns data. No new screens or gestures may
be inferred from generated reference art. Windows desktop browser is the primary
taste surface; use a 1280×720 viewport for comparison and 1920×1080 for overflow.

**Windows Presentable Shell** below is first-class product, not a taste overlay.
Must-for-presentable items are locked there. The family-PC definition of done
is the 19-step checklist at the end of that section. Until that path is green,
deeper engine slices (S13 settings matrix, S14 whole-product audit) stay
secondary. Soon rows do not block it.

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
| Empty library | Library header and Add folder as the CTA; plain “No pictures yet” in grid. No fake sample pictures. Add opens named dialog. |
| Add folder | On Windows, Browse is the normal path: native folder picker fills the field. Cancel leaves the field unchanged. Typed or pasted paths still work; they are not required. `ask` starts with neither mode selected and Add disabled until path+mode exist. Other defaults preselect a mode, still require Add. Cancel/Esc closes without writes. No file-upload control. |
| Scanning | Close Add as soon as `POST /api/sources` returns 202 for **either** copy-here or serve-from-there. Never leave the dialog open on `busy` or a long scan; if the POST is `busy`, close and show scan status. Library shows a confirmation that the folder was added and a status line with added/skipped/error counts from sources. Poll every second while running. Previously indexed items remain browsable; newly indexed items appear as they become ready, with placeholders until renditions arrive. No percentage without a known denominator. An error leaves counts, readable error text, and **Retry**; never a blank page. The serve process prints scan progress on stdout during normal work. |
| Disconnected | Banner “Library is not responding”. Keep the last grid if any. Retry health then catalog every second. Clear the banner when health is 200. Never a blank crash and never a traceback. |
| Ready | Years/Months/Days/Off date grouping, search, sort Newest/Oldest/Name, filters All/Photos/Videos/Favorites, one Size density slider, hearts and open work on the same current item set. Date grouping (Years/Months/Days) and sort persist to settings; Off, selection, current filter, Size and Favorites collapse are transient. No localStorage truth. The page address is the live listen origin. |
| Live origin | History, Back, and links stay on `window.location.origin` (the process that served this page). Root-relative `/` and `/api/*` only. Never build `http://<host>:<settings.port>` or reuse a stored runtime URL from another listen (QA range 18765–18864 is a common stale port). Browser Back while the page is open closes the viewer or stays on the grid; it does not navigate to another host or port and does not call `history.back()`. |
| Update | Header `#update-library` is labeled Update Library. `#library-version` beside it shows this copy's short git SHA (or `local` when not a git checkout). Click runs `POST /api/update`. While the pull runs, `#update-status` says Updating… Then one sentence: updated / already current / git missing / not a git copy / pull failed / update-unavailable. A successful Update refreshes `#library-version` from the new tip in the response (the serve process does not restart). No command prompt. Does not switch branches. Launcher Update uses the same sentences. |
| Viewer | Show still preview first, then readable original with **no** “Showing original” control; video uses poster then **progressive** proxy→original (see Video playback and zoom). `#viewer-source` beside `#viewer-crumb` names Preview / Loading full… / Original / Full / Preview — full unavailable. Live uses still with motion playback. Back stays top-left. Previous/Next and Rotate sit on a **bottom** bar (`#viewer-nav` inside `#viewer-bottom`). ArrowLeft/ArrowRight still change photo and stop at ends. Zoom is a **vertical** `#viewer-zoom-slider` on the side of the stage (range 25–1600, 0.25×–16× fit) with a live percentage (`#viewer-zoom-pct`). **Plain wheel** is the primary zoom; the slider is secondary. Ctrl+wheel and Ctrl++/− stay. Ctrl+0 fits, Ctrl+1 is 100%. No Zoom in/Zoom out buttons. The slider does **not** sit in `#viewer-bottom` or over the picture. Click-hold pans while zoomed; stills also left-drag pan at fit; middle-drag pans stills and video. Rotate (button or Ctrl+R) turns the displayed still 90° and does not rewrite the original. F11 or F toggles fullscreen; Esc leaves fullscreen, then the viewer. F5 starts a slideshow of the current set (Space pauses; Esc stops; empty library: “Add photos first”). A heart toggles favorite (`catalog/favorites.json`); pressed/filled means favorited. Reveal in Explorer and Open (`#open-original`) sit side by side. Delete removes from the library (confirm; originals stay); Delete file is a second control with an extra confirm. Person/Place/Thing are **not** pills over the preview. Top-right `#viewer-info` opens a dropdown: EXIF/file facts first (date taken, camera, dimensions, size, path, GPS; empty “No camera info for this file.”), then people/places/things; a click on an entity filters the grid and closes the viewer. Type-in fields stay inside Info and stay labeled. Tooltips on chrome name the shortcut. Esc closes Info, then slideshow, then fullscreen, then the viewer. No box-drawing editor. `#viewer-scrub` lives in `#viewer-bottom` (the former zoom-slider slot) and seeks the playing video at any zoom or source; it does not overlay the picture. |
| Original absent, preview present | Exact banner “Original is not on this computer”. Cached preview remains; Open original disabled. Video/live Play preview enabled only if proxy exists. |
| Preview absent or failed | Stable placeholder with “Preview is not available”. If original exists the viewer may still load it. Missing-original banner also appears when both are absent. No broken image icon, endless spinner, or invented retry modal. Rescan is the existing retry operation. |
| Empty search | Query/chips remain; “No matches for …” including the query (or “No matches” when only a chip/filter is empty). Clearing query/chip returns matching broader grid, no catalog mutation. |
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

The grid has **one** density slider: `#size-slider`, eight discrete stops
(72, 104, 144, 192, 256, 336, 420, 520 px). It only changes `--cell`. It
does not refetch or rebuild tiles, and it does not change date grouping.
Ctrl+wheel on the grid steps that same Size slider (coalesce an event
burst so one gesture moves one stop). Plain wheel on the grid scrolls the
wall. There is no Level slider and no second zoom rail.

Date grouping is a separate toolbar control `#date-group` (Years /
Months / Days / Off). It is not a second slider and not encoded as zoom.
Years is one mosaic card per year. Months is one mosaic card per month.
Days is a header per day and every photo from that day. Off (“one wall”
/ blob) cascades every matching thumb onto one continuous wall — one
flex wrap, 2 px gaps, no heading rows, no section margins. Changing
Dates does not move Size. Years/Months/Days persist as `zoomLevel`
(`all` remains a valid settings/API value and shows as Days). Off is a
session view option (`#grid` `data-date-group`, `data-group-dates`); it
is not a settings.json key. Size is also session-only (`#grid`
`data-size`).

Keep the hovered item's center/visible representative in view when Dates
changes; in the new layout it must be within the viewport, not
necessarily pixel-identical because a mosaic changes shape. The control
uses the central visible item as anchor when no pointer item exists. It
cannot jump to an unrelated year.

Already-decoded thumbnails stay painted through Size, Dates, and scroll.
The grid must not clear to an empty surface while zoom is in progress.

Tiles use one badge system. Video cells show a VIDEO badge (play mark plus
the word VIDEO, and duration when `metadata.durationSec` exists). Live
cells keep the existing LIVE badge (`.live-badge` text `LIVE`). Badges sit
on the tile and do not crop the media.

The toolbar All / Photos / Videos / Favorites controls are mutually
exclusive. All clears kind and favorite. Photos sends `kind=photo,live`.
Videos sends `kind=video`. Favorites sends `favorite=1`. Combined with
the presentable sort (Newest / Oldest / Name), this is how the library
is filtered. Location sort remains available.

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

Click a cell opens it. ArrowLeft/ArrowRight navigate. Viewer zoom is a
**vertical side** slider (`#viewer-zoom-slider`) showing percentage, plus
**plain wheel** (primary) or Ctrl+wheel around the cursor's image
coordinate; middle drag moves it 1:1. Click-hold pans while the picture
is zoomed past fit (stills and video). A still also pans with a left
drag. No reflow or automatic fit during a gesture. Slider/wheel span
0.25× fit to 16× fit. Images and video initially fit; each newly opened
item resets fit and rotation. A still click does nothing. Video/live
click or Space toggles playback unless that pointer was a pan. The
viewer scrub bar sits in `#viewer-bottom` (not over the picture) and
seeks; wheel does not seek. Unsupported original codec stays on the
proxy after a progressive start, not a silent freeze.

Proxy policy: `off` never autoplays; `days-and-all` (default) and `always`
play only the hovered cell at every Dates grouping, including Years/Months
mosaics. No policy autoplays all cells. Hover leave stops and restores still/poster; muted,
looped proxy never starts audio. Explicit viewer play is independent of hover setting.
The hover proxy is position-absolute over the still and `object-fit: cover`s the
entire cell **at every Size stop** (72–520), not only on large tiles. The still
is not hidden by a `display` rule that would leave it flex-sharing the tile. No
split still+video. Dated Years/Months and a Dates-off wall all play the
hovered proxy. A catalog poll that
rebuilds the grid must resume the hovered proxy if the pointer is still
on that tile. A `.tile-scrub` on the hovered
video tile seeks that preview without opening the viewer.

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
the innermost active interaction: confirm dialog, Info, slideshow, fullscreen,
tour/gesture, Add dialog, Viewer, Settings, then selection. There is no modal
on top of a tour. Ctrl+F focuses search, Ctrl+, opens Settings. Ctrl+C copies
the primary path, with missing-path notice when needed. F is fullscreen, not
favorite. F5 starts the slideshow (5 s, no 17th setting). `?` cheat-sheet is
Soon. Do not add cut/paste filesystem mutations

Each browser gate must drive actual controls, assert resulting data/state, inspect
its saved PNG, and retain console/network diagnostics. Required proofs include:

- Grid has fixture ids and date groups; click opens the correct picture, arrows
  respect filter, Esc restores scroll; not merely endpoint returns 200.
- Dates/Size anchor remains visible; viewer and globe cursor anchor drift <=2 px;
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
albums, not an editor, not a cloud. PRODUCT F2 / F3 / F4 / F7 / F9 / F10 /
F11 / F12 / F15 / F18 / F21 / F22 name the operations; this section is the
presentable surface those Checks must look like.

Stolen from, then cut to this product: Windows Photo Viewer (prev/next/
rotate/slideshow/print/open-with), Windows Photos (shortcuts / F5 /
Alt+Enter / Esc / filters), Apple Photos chrome (heart / info / fit),
Google Photos (favorites strip / videos / search), IrfanView and XnView
(fullscreen / EXIF / filmstrip / portable). Ignore cloud, AI, burn, and
email.

Do not invent accounts, phone sync, editing suites, or albums-as-cloud.
Originals stay files on disk. New routes, settings, or errors still require
a CONTRACTS edit before code — except the Must remove / delete-file
commands already listed there.

### Locked Must-for-presentable (shell requirements)

These are the family-PC shell. They belong on the DoD checklist. They are
not Soon.

**1. Fullscreen / Esc dismiss.** F11 or F toggles viewer fullscreen. Esc
leaves fullscreen, then the viewer (then the rest of the Esc stack). Not
a native window rewrite. F means fullscreen, not favorite.
**Implemented on this PR:** app-level `data-fullscreen` plus Fullscreen API
on `document.documentElement`.

**2. Slideshow.** F5 starts a slideshow of the current filter/sort from
the open item (or the first item if started from the grid). Interval 5 s,
session-only — **no** 17th setting. Space pauses and resumes. Esc stops
and leaves the current item. Arrows still step. Videos play the proxy for
the interval. Empty library: “Add photos first”. Not the globe tour.
**Implemented on this PR.**

**3. Viewer keyboard parity.** Arrows prev/next and stop at the ends.
Ctrl++ / Ctrl+- or **plain wheel** zooms the open still or video
(Ctrl+wheel stays). Ctrl+0 fits. Ctrl+1 is 100% (one image pixel per
CSS pixel at rotation 0). Ctrl+R rotates the display 90°, same as the
Rotate button — does not rewrite the file. Space plays or pauses video
when a slideshow is not running. Tooltips on chrome name the shortcut
(Previous ←, Next →, Rotate Ctrl+R, Slideshow F5, Fullscreen F11).
Focused text fields keep their keys. Wheel over a range input (zoom
slider, scrub) keeps the native slider behavior.
**Implemented on this PR.**

**4. Info = file facts, then names.** `#viewer-info` is a top-right
dropdown, not overlay pills. First block: date taken, camera, dimensions,
size, path, GPS from the item record. Missing camera/EXIF: “No camera
info for this file.” Then people / places / things already on the record;
clicking one filters the grid and closes the viewer. Type-in fields stay
below that and stay labeled Person, Place, and Thing. No “Showing original”.
**Implemented on this PR.**

**5. Open with default app.** Sits beside Reveal in Explorer. Both always
visible in the viewer. Open launches the original (`POST /api/items/<id>/open`,
`os.startfile` on Windows). Disabled with the missing-original banner.
**Implemented on this merge:** [PR #2](https://github.com/imsly2/photoLibrary/pull/2)
(`cursor/viewer-chrome-2bd1`, TASTE-VIEWER 72/72) ships Open + Reveal +
Win7 chrome + Update Library. Grade that packet as the proof.

**6. Empty / first-run / error.** No folders: “No pictures yet” and Add
folder is the CTA. Scan failure: counts, readable error, **Retry** — never
a blank page or a stuck dialog. Missing file: existing “Preview is not
available” / “Original is not on this computer” placeholders. Reconnect:
“Library is not responding”; retry until health is 200.

**7. Remove vs Delete file.** Delete key (and a Remove control) **removes
from the library**: one confirm (“Remove from Library? The file stays on
disk.”). Catalog record and favorite drop; original bytes stay. Undo
restores the catalog. **Delete file** is a separate control with an extra
confirm (“Delete this file from disk?”). Windows sends the original to
the Recycle Bin when it can, then removes the catalog record. Undo
restores catalog only — not the bytes. Linked and copied files both
require that extra confirm. Never make Delete file the Delete-key
default. Commands: CONTRACTS `remove` and `delete-file`.

**8. Sort + filters.** Presentable sort labels: Newest, Oldest, Name
(`sort=date&dir=desc`, `sort=date&dir=asc`, `sort=name`). Location sort
stays available so F11 is not weakened. Filters are a mutually exclusive
toolbar: All (no kind, no favorite), Photos (`kind=photo,live`), Videos
(`kind=video`), Favorites (`favorite=1`). The Favorites strip still
appears when All is selected and any current result is hearted.

**9. Search.** The box matches filename, capturedAt date text (YYYY,
YYYY-MM, YYYY-MM-DD), and existing person/place/thing names (and thing
aliases). Chips still restrict to People / Places / Things. Empty:
“No matches for …” (query included). Clearing query/chip returns the broader grid.

**10. Update UX finish.** Launcher and in-app (`#update-library`, label
Update or Update Library). The shell shows build identity in
`#library-version` (short checkout SHA, or `local`). No command prompt.
While the pull runs: Updating… Then one sentence: updated / already
current / git missing / not a git copy / pull failed. A successful
Update refreshes that SHA from the new tip; the running server does not
restart. Does not switch branches. **Implemented on this merge** (PR #2
72/72 plus the abc Update commit). `Update.bat` / `launch.ps1 -Update`
is the launcher. Prove the progress sentence on a real git copy.

Also still locked from the earlier Windows notes (already on the DoD
path): `Library.bat`; native Add folder; 202-before-finish; live-origin
Back; non-fatal abort; full-tile video hover **at every Size**; VIDEO
badge; eight Size stops on **one** density slider; thumbs stay painted;
Dates Years/Months/Days/Off wall; Library/Globe buttons; viewer heart +
tile hearts + Favorites strip; bottom Prev/Next; **vertical side**
viewer zoom with percentage; `#viewer-scrub` in `#viewer-bottom`;
click-drag pan; no overlay pills; inverted globe yaw; local Earth.
macOS/Linux launch stays pinned later.

### Video playback and zoom (locked shell requirements)

Not Soon. Not one-off patches. These are presentable-shell rules for
video and the two zoom surfaces.

**Fit stays put.** Opening a video shows the poster fitted and centered
in the stage. Play, a proxy→original swap, or a higher-resolution source
must not jump the picture to a corner or change its fitted scale. Layout
uses the item’s catalog width/height (not the proxy’s 480 px) as the
stable box. `object-fit: contain` inside that box. After the first fit,
a source swap only reapplies the same transform.

**Progressive start.** Viewer play always begins with the silent proxy
as soon as it can, then swaps to the **original** when the browser can
decode it (MP4 H.264). iPhone `.MOV` / HEVC typically cannot play in
Chrome — do not wait forever on `canPlayType("maybe")`. Swap instead
to `which=playback` (`playback.mp4`: full-size H.264 + AAC, remux when
possible). The swap keeps `currentTime`, play/pause, and the current
scale/pan. No “Showing original” **control**. `#viewer-source` sits
beside the filename and must stay honest: **Preview** on the silent
proxy, **Loading full…** while original or playback is fetching,
**Original** only when the original file is playing, **Full** when the
library H.264/AAC derivative is playing, **Preview — full unavailable**
if both original and playback fail. Do not label a silent proxy as
Original. Slideshow still plays the proxy for the 5 s interval.
Clicking a video tile opens the viewer at that tile’s `currentTime`
(hover play or `.tile-scrub`) and autoplays; stills are unchanged.

**Hover at every tile size.** Grid preview playback is not reserved for
large cells. When the proxy policy allows the cell, the hovered video
fills that tile at Size 72 through 520. Dated Years/Months mosaics and a
Dates-off wall all play the hovered proxy; `.tile-scrub` seeks that
preview. `playProxies=off` is the only setting that leaves tiles still.
Leave restores the poster. A catalog rebuild
must resume the hovered proxy while the pointer stays on that tile.

**One grid Size, separate Dates, one viewer Zoom.** The rail
`#size-slider` is the only grid density control (eight Size stops).
`#date-group` is a toolbar dropdown: Years / Months / Days / Off.
Off is the one-wall cascade — no date sections. Dates is not a second
zoom slider; changing Size never changes Dates, and changing Dates never
moves Size. Viewer zoom lives only on the **vertical** side control
`#viewer-zoom-slider` with `#viewer-zoom-pct`. Do not put a picture-zoom
slider on the grid or in `#viewer-bottom`.

**Wheel parity.** In the viewer, plain wheel zooms the still or video
around the cursor (same as Ctrl+wheel / Ctrl++/−); the side slider is
secondary. Grid Ctrl+wheel steps **Size** only. Plain wheel on the grid
scrolls the wall. Wheel does not seek; `#viewer-scrub` and `.tile-scrub`
do.

**Scrub anywhere the video is playing.** `#viewer-scrub` (with a
mm:ss time label) sits in `#viewer-bottom` — the slot the zoom slider
used to occupy — and seeks the open viewer video at any zoom or source.
It must not overlay the picture. Mute (`#viewer-mute`) and a volume
slider (`#viewer-volume`) sit beside the scrub; hover proxies stay
silent. A compact `.tile-scrub` on the hovered grid tile seeks that
preview without opening the viewer. Originals stay on disk; no cloud.

### Spec target vs current implementation

Honesty rule: this combined taste merge includes **PR #2**
(`cursor/viewer-chrome-2bd1`) Win7 chrome + Update Library (TASTE-VIEWER
**72/72**) and **PR #5** Presentable Shell docs. Viewer Must (fullscreen,
slideshow, keyboard parity, EXIF-first Info) is **PR #7**. Mark those
chrome rows implemented. Do not revive retired chrome. Must 6–10
(empty/error, remove vs delete-file, sort/filters, search, Update
launcher) is this shell PR. F10’s one-Esc-from-Info close-viewer proof
still times out on this stack (same as `d00addb`); do not weaken that
Check to hide it.

| Surface | Spec target | Where it lives | Gap |
|---|---|---|---|
| Launch | Double-click `Library.bat` | abc Track A | F2 Check pending |
| Update | In-app + launcher; Updating… then a sentence; header shows checkout SHA | **This merge** (PR #2 72/72 + abc) + `Update.bat` + `#library-version` | Progress sentence on a real git copy |
| Add folder | Native Browse; close on 202; items as ready | abc Track A | Linux QA `picker-unavailable` (expected) |
| Back / origin | Stay on live origin/port | abc Track A | Do not reintroduce `settings.port` URLs |
| Disconnect / reconnect | Banner + Retry | abc Track A + this shell | `#reconnect-retry` beside exact banner text |
| Video tile / Videos | Full-tile hover; VIDEO badge; `kind=video` | abc Track C | Photos / All / Favorites filters still Must |
| Size / wall | ≥8 stops; thumbs stay; Dates-off wall | abc Track C | — |
| Library / Globe | Button affordances | abc Track C | — |
| Hearts / Favorites strip | Viewer + tile ≥144 + strip | abc B+C | — |
| Prev / Next / slider / pan / rotate | Bottom bar; vertical side zoom; no zoom buttons | **This merge** (PR #2 72/72) + **this PR** keys | Ctrl+0 / Ctrl+1 / Ctrl+R / tooltips shipped |
| Grid Size vs Dates | One `#size-slider`; `#date-group` Years/Months/Days/Off | This chrome tip | Ctrl+wheel drives Size only; Off is one wall |
| Viewer wheel | Plain wheel zooms still/video | This video/zoom tip | Ctrl+wheel stays; wheel does not seek |
| Progressive video | Proxy first, then original or full-sound `playback`; same fit/time | This video/zoom tip | Catalog width/height is the layout box. `#viewer-source` names Preview / Loading full… / Original / Full / Preview — full unavailable |
| Scrub | `#viewer-scrub` in `#viewer-bottom` + `.tile-scrub` | This chrome tip | Scrub is not over the picture; tile scrub does not open the viewer |
| Overlay pills / “Showing original” | **Forbidden** | **This merge** removed them | Do not restore |
| Reveal + Open | Side by side | **This merge** Open + Reveal | Keep beside each other |
| Info | File facts first, then names | **This PR** facts + names | Empty camera: “No camera info for this file.” |
| Fullscreen / slideshow | F11 or F; F5; Esc stack | **This PR** | Esc: Info, then slideshow, then fullscreen, then viewer |
| Remove / Delete file | Delete key vs extra confirm | This shell PR | CONTRACTS `remove` / `delete-file`; toolbar + dialogs |
| Sort Newest/Oldest/Name | Presentable labels | This shell PR | Hidden `#sort`/`#dir` stay for F11 |
| Filters All/Photos/Videos/Favorites | Mutually exclusive toolbar | This shell PR | Videos id kept; Photos is `kind=photo,live` |
| Search | Filename + date + tags; “No matches for …” | This shell PR | Date `YYYY` / `YYYY-MM` / `YYYY-MM-DD` |
| Globe basics | Invert yaw; local Earth | abc globe taste | Polish is Later |
| macOS / Linux launch | Pinned later | `launch.sh` exists | Do not claim F2 |

Retired chrome: overlay Person/Place/Thing pills, “Showing original”,
discrete Zoom in / Zoom out buttons, Albums, storage meter, keybinding
editor.

### Soon (backlog — does not block presentable DoD)

| Feature | Bound |
|---|---|
| Filmstrip under the viewer | Neighbors; click jumps; hide in fullscreen if chrome hides. XnView / Lightroom. |
| Multi-select + batch favorite / remove | Shift+click range, Ctrl+click toggle. Batch favorite or batch **remove-from-library** only. No batch Delete file, no batch export. |
| Print Ctrl+P | Browser print of the current still. No print suite. Photo Viewer had this. |
| Copy path / copy file | Ctrl+C already copies the path (F18). Copy file (bytes to a folder) needs a CONTRACTS promotion first. |
| Fit / Fill / 100% near the zoom slider | Visible twins of Ctrl+0 / Ctrl+1. Fill is Soon; Fit and 100% keys are already Must. |
| Tile badges LIVE / ♥ / missing | LIVE and heart already exist. Missing-original badge on the tile is Soon polish. |
| Recently added + per-folder browse | Session “Recently added” after a scan; filter to one source. Not albums. |
| Keyboard help `?` | Overlay of locked keys. Not an editor. I / Alt+Enter may toggle Info here. |
| Remember window / last view | Last Library vs Globe and last filter for the session. Zoom/sort already persist. This is a browser tab — do not persist OS window size via Electron. |
| Missing-original polish | Stronger banner / disabled Open+Reveal+Delete-file. Core placeholders are already Must. |

### Later / non-goals

Accounts, cloud sync, share links, cloud AI, in-app edit (use Open with),
cloud albums, light-table / compare, batch convert, burn, email.
macOS/Linux launch stays pinned. Globe polish beyond F12 waits until this
shell path is green. Ratings 1–5 and contact sheets stay out; hearts cover
“keep this one”.

### Presentable for family PC — definition of done

One path. Until every row is green on a Windows family PC (double-click,
not a developer shell), S13-class settings work and Soon rows are
secondary. Fixture Checks stay the grade for F-ids; this checklist is the
taste gate.

| # | Step | Pass |
|---|---|---|
| 1 | Double-click `Library.bat` | Visible console; browser opens on the live listen URL; title reads Library |
| 2 | Empty / first-run | “No pictures yet”; Add folder is the CTA; no fake samples |
| 3 | Update | Launcher or header Update; Updating… then updated / already current / failed / git missing. Header shows the checkout SHA. No CMD. No branch switch |
| 4 | Add folder | Native picker; copy-or-link; dialog closes on 202 |
| 5 | Progress / scan error | Status + console; items as ready; failure shows Retry, never a blank page |
| 6 | Wall + sort + filters | Dates Off = one wall; Years/Months/Days separate from Size; ≥8 sizes; thumbs stay; Newest/Oldest/Name; All / Photos / Videos / Favorites |
| 7 | Search | Filename, date, or a tag; empty “No matches for …” |
| 8 | Open | Preview then original or `playback`; no “Showing original” control; `#viewer-source` names Preview / Loading full… / Original / Full / Preview — full unavailable; no overlay pills; missing-file placeholder |
| 9 | Next / Prev / arrows | Bottom Previous and Next; arrows; stop at ends; Back stays on this origin |
| 10 | Keyboard parity | Ctrl++/− or **plain wheel** zoom; Ctrl+0 fit; Ctrl+1 100%; Ctrl+R rotate; Space play/pause video; tooltips show shortcuts |
| 11 | Zoom slider / pan / rotate | Vertical side viewer zoom with %; click-drag pan; Rotate beside Prev/Next. Grid Size ≠ Dates. Scrub in `#viewer-bottom` |
| 12 | Fullscreen | F11 or F; Esc exits fullscreen, then the viewer |
| 13 | Slideshow | F5 starts; Space pauses; Esc stops; empty “Add photos first” |
| 14 | Favorite | Viewer heart; tile heart at large Size; Favorites strip can collapse |
| 15 | Reveal + Open | Side by side; Reveal uses argv `explorer.exe` + `/select,fullpath` (comma glued, no extra quotes) so paths with spaces (e.g. `Iphone Backup`) select the file; missing original shows the banner, never Documents |
| 16 | Info | File facts first (or “No camera info”), then people/places/things; click filters the grid |
| 17 | Remove / Delete file | Delete key removes from library (confirm, bytes stay). Delete file extra-confirms and Recycle-Bins |
| 18 | Reconnect | Kill the server: “Library is not responding”; restore health clears it |
| 19 | Globe basics | Local Earth; drag right yaws east; cluster opens newest; Esc leaves the filtered grid |

All 19 green ⇒ presentable. Soon rows (filmstrip, multi-select, Print,
copy file, `?`, recently added) do **not** block this gate. Deeper
settings, F3 parity, globe polish, and macOS/Linux launch do not block
it. A missing Must row **does**, even if an F-id already has an API
artifact.
