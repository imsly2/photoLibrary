# Library — screen and interaction contract

2026-10-12. Target behavior, not running software. [PRODUCT.md](PRODUCT.md) owns
features; [CONTRACTS.md](CONTRACTS.md) owns data. No new screens or gestures may
be inferred from generated reference art. Windows desktop browser is the primary
taste surface; use a 1280×720 viewport for comparison and 1920×1080 for overflow.

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
