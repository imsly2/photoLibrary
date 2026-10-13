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
Favorites, Albums, a storage meter, native window chrome, duplicate navigation,
or “Written by an agent into JSON” copy from these mockups. Dates, photos, counts
and names in the art are illustrative. Actual fixture content determines results.
Use one consistent header across the views; the grid reference's unrelated sidebar
entries do not create another navigation system. Library, Globe and Settings are
the existing view destinations; Search is the filtered Library, Viewer is open media.

## State transitions

| State | Visible behavior and exit |
|---|---|
| Empty library | Library header and Add folder; plain “No pictures yet” in grid. No fake sample pictures. Add opens named dialog. |
| Add folder | Path is typed/pasted on the server computer, or filled by Browse. Browse on Windows opens the server computer's native folder picker and writes the chosen path into the field; cancel leaves the field unchanged. Typed paths still work. `ask` starts with neither mode selected and Add disabled until path+mode exist. Other defaults preselect a mode, still require Add. Cancel/Esc closes without writes. No file-upload control. |
| Scanning | Close Add as soon as `POST /api/sources` returns 202. Never leave the dialog open on `busy` or a long scan. Library shows a confirmation that the folder was added and a status line with added/skipped/error counts from sources. Poll every second while running. Previously indexed items remain browsable; newly indexed items appear as they become ready, with placeholders until renditions arrive. No percentage without a known denominator. An error leaves counts and readable error text, never a blank page. The serve process prints scan progress on stdout during normal work. |
| Disconnected | Banner “Library is not responding”. Keep the last grid if any. Retry health then catalog every second. Clear the banner when health is 200. Never a blank crash and never a traceback. |
| Ready | Years/Months/Days/All, search, sort and open work on the same current item set. Level and sort persist to settings; selection and current filter are transient. No localStorage truth. |
| Viewer | Show still preview first, then readable original; video uses poster then original/proxy, live uses still with motion playback. Visible Previous/Next and Back; arrows still move. Next/previous use the current filtered order, stop at ends without wrapping. Back/Esc restores the grid he came from (filter, level, scroll) on this same listen URL — never `history.back()` or a port change. Zoom in/out buttons plus existing Ctrl+wheel; stills also left-drag pan, middle-drag pans stills and video. Rotate turns the displayed still 90° per click and does not rewrite the original. A large heart toggles favorite; pressed/filled means favorited. Open original stays in this page and is pressed as “Showing original” when original bytes are on screen; click toggles back to the preview — it does not open another program. Reveal in Explorer is always present in the viewer and opens the original's folder when the file is on this computer; disabled with the missing-original banner otherwise. Play preview keeps click-to-pause. Person/Place/Thing fields are labeled; no unlabeled pills. Labels list existing annotations; typing a person/place/thing and committing sends annotate. No box-drawing editor. No grid-only favorite density in this slice. |
| Original absent, preview present | Exact banner “Original is not on this computer”. Cached preview remains; Open original disabled. Video/live Play preview enabled only if proxy exists. |
| Preview absent or failed | Stable placeholder with “Preview is not available”. If original exists the viewer may still load it. Missing-original banner also appears when both are absent. No broken image icon, endless spinner, or invented retry modal. Rescan is the existing retry operation. |
| Empty search | Query/chips remain; “No matching pictures”. Clearing query/chip returns matching broader grid, no catalog mutation. |
| Settings | Existing 16 settings only, grouped as the reference; change persists through HTTP immediately on valid commit. Inline validation preserves last valid value. Host/port label says “Applies next launch”. Esc returns to prior Library/Globe view. |
| Globe | Locally textured earth and clusters from visible located items; no-location items absent. Plain “No locations to show” if empty. WebGL unavailable produces inline error text, not another map provider. |
| Tour | Existing globe motion plus media presentation, as specified below. Esc stops motion/playback at current globe position and leaves Globe. No new slideshow settings beyond the three existing tour settings. |

Settings and annotation text input keep normal editing keys: arrows, Space,
Ctrl+C, Ctrl+Z edit focused text rather than triggering viewer navigation or global
history. Global actions apply outside text inputs. Tab order follows visible order,
controls have names, focus is visible, and closing the Add dialog restores its
trigger focus. Error text explains the fixed API error without exposing a traceback.

## Grid, sort, and viewer

Years uses a mosaic per year; Months a mosaic per month. Days includes every
matching item at nominal 240 px row height; All includes every item at nominal
160 px row height. Fit cells within available width without cropping controls;
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

Click a cell opens it. ArrowLeft/ArrowRight navigate. Ctrl+wheel zooms an opened
still or video around the cursor's image coordinate; middle drag moves it 1:1,
and a still also pans with a left drag. No reflow or automatic fit during a
gesture. Step factor 1.1 per wheel or button step, 0.25× fit minimum, 16× fit
maximum (zoom out from the opening fit is required). Images and video initially
fit; each newly opened item resets fit and rotation. A still click does
nothing. Video/live click or Space toggles playback. Normal scrolling does
not seek. Unsupported original codec falls back to proxy, not a silent freeze.

Proxy policy: `off` never autoplays; `days-and-all` plays only the hovered cell at
those levels; `always` also permits hover playback within Years/Months mosaics.
No policy autoplays all cells. Hover leave stops and restores still/poster; muted,
looped proxy never starts audio. Explicit viewer play is independent of hover setting.

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

Ship the earth texture locally, record its license in the app. Drag rotates earth
by 0.25 degrees per pixel; clamp poles just before inversion. Wheel zooms by 1.1,
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
