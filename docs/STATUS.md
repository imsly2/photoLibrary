# Library — status

Spec baseline: 2026-10-12. This is a planning result, not a software release.

## True now

- 2026-10-14 — **Docs audit** on tip `cursor/reveal-explorer-8d56`
  (PR #14 `1cac4c9`). PRODUCT / UI-SPEC / CONTRACTS / this file now
  carry every Steve taste lock, including sibling tips **#12 chrome**,
  **#13 places**, **#14 reveal/volume**, **#15 objects**, **#16 faces**,
  and pending **#17** Reveal-spaces / MOV / Years-Months hover / Preview
  badge notes. Honesty table: [UI-SPEC — Spec target vs current
  implementation](UI-SPEC.md#spec-target-vs-current-implementation).
  One-shot rebuild prompt: [ONE_SHOT_PROMPT.md](ONE_SHOT_PROMPT.md).
  **On this tip (shipped):** one Size slider; Dates Years/Months/Days/Off;
  side zoom %; bottom scrub; tile scrub; tile→viewer autoplay at time;
  mute/volume; header SHA + Update; Reveal string `/select,"path"` +
  missing-original 404; progressive proxy→original; hover at Days/Off
  and every Size; preserve originals; no cloud default. **Specified,
  not on this tip:** Reveal argv that survives spaces (PR #17);
  `#viewer-source` Preview/Original/Full + `playback.mp4` MOV sound
  (PR #17); hover in dated Years **and** Months (Steve lock; still a
  gap on #17); `setup-geo` / GEO 44/44 (PR #13); `setup-ml objects` /
  TASTE-OBJECTS 39/39 (PR #15); `setup-ml faces` / FACES 40/40 (PR #16);
  `Setup.bat` (intent only). No 23rd Check. **16/22 unchanged.**

- S00 is green on its Windows verifier: an empty fixture-owned library launches,
  persists the 16 default settings, reuses a matching-root server, refuses a
  foreign port without killing it, recovers a settings transaction, and undoes
  a settings change.
- S01 is green on its Windows verifier: a linked fixture folder scans in place,
  item ids match file bytes, a second scan adds nothing, originals are
  unchanged, and the embedded Live Photo pair is one item.
- F6 is closed: fixture dates follow EXIF, then filename, then modified time,
  and the three-JPEG set becomes two unnamed places 100 meters apart.
- S03 is green: JPEG thumb.webp and preview.webp are oriented, GET /api/media
  returns real bytes, and a minimal page opens the oriented still. Closes no
  Check. F10 stays open until S09.
- S04 / M1 is green: Add folder (linked), four zoom levels, date/location/name
  sort, and open one still. Closes F9 and F11. F10 browse subset is present
  but the Check stays open until S09.
- S05 is green: copy onto this drive, collisions, interrupt resume, convert a
  linked source, move the library, undo leaves bytes. Closes F1 and F4.
  F9 and F11 stayed green after S05.
- S06 is green: every fixture format is indexed; JPEG/PNG/GIF/WebP/TIFF/BMP
  stills and all video containers get ffmpeg renditions; `broken.heic` stays
  an error placeholder; `clip.mp4` proxy is silent H.264 ≤480 px and 2.000 s;
  hover respects off / days-and-all / always with one cell. Closes F5 and F7.
  This Linux ffmpeg cannot decode `quad.heic` / `quad.heif`; they stay error
  plus placeholder. F9 and F11 stayed green after S06.
- S07 is green: with-source thumbs land under `.library/renditions/`, relocate
  both directions with rollback, after-launch unplug, show/hide, and the
  missing-original / missing-preview screens. Closes F8 and F16. F5 and F7
  stayed green after S07.
- S08 is green: annotate Ada/mug with reuse, unnamed face naming, place
  rename, alias Cup→mug, people merge, pending annotate through hash, and
  rebuild-index search parity. Closes F14 and F20.
- S09 / M2 is green: viewer fields write Ada/mug/Kitchen, search chips,
  inspector unique-item counts, preview-then-original, and proxy fallback.
  Closes F10 and F15. Do not wait for taste.
- S10 / M3 globe is green: `GET /api/places` returns two GPS places and
  omits no-exif; local WebGL earth; 32 px cluster; click opens newest;
  Esc leaves the filtered grid. Closes F12.
- S11 / M3 tour is green: `GET /api/globe/tour` lists both GPS places and
  omits no-exif; Play orbits, eases, shows preview/proxy, wraps; Esc
  freezes the camera. Closes F13. Do not wait for taste.
- S12 is green: Live pair is one item on the still hash with two
  locations; LIVE badge; hover proxy; missing motion falls back to still.
  Closes F19. F5, F7, F10, F14, F16 stayed green.
- Windows taste Track A is on this branch for Steve: `Library.bat`,
  native Browse picker, 202-before-finish Add (dialog closes, scan
  progress, items as ready), live-origin Back (no jump to a stale
  18765 port), and non-fatal disconnect. Does not close F2. F4 stayed
  green. S13/S14 and macOS/Linux F2 are pinned. Viewer/grid chrome is
  a sibling track. Evidence:
  [TASTE-WIN](features/taste-windows/Rev1.0/assets/orchestrator-rerun/result.json),
  [F4 rerun](features/taste-windows/Rev1.0/assets/orchestrator-rerun/f4/result.json).
- Globe taste: local realistic `earth.png` (not blob continents);
  rightward drag increases yaw; up/down unchanged. Favorite star and
  Reveal in Explorer are specified for sibling tracks. F12 stays the
  Check; do not reopen S13/S14.
- Windows taste merge `taste/windows-abc` stacks Track A + globe, Track B
  viewer, and Track C grid. Shared `catalog/favorites.json`. Family
  Update Library (header, `POST /api/update`) and Win7-style viewer
  (Info, no Showing original, Prev/Rotate/Next bottom, zoom slider,
  click-hold pan, Reveal + Open) take the proven PR #2 chrome
  (`cursor/viewer-chrome-2bd1` at `192ca72`, TASTE-VIEWER 72/72,
  F10 29/29) while keeping Track A launcher/picker and Track C grid.
  Windows Presentable Shell Must/Soon/Later from PR #5
  (`cursor/windows-presentable-shell-bd24`) is the North Star. Does not
  start S13/S14.
- 2026-10-13 — **Windows Presentable Shell** locked in North Star docs
  (UI-SPEC primary). Must-for-presentable includes fullscreen,
  slideshow, viewer keyboard parity, EXIF-first Info, Open with, empty/
  error states, remove vs delete-file, Newest/Oldest/Name +
  All/Photos/Videos/Favorites, search, and Update UX finish — plus the
  earlier launch/grid/Win7/globe locks. Soon (filmstrip, multi-select,
  Print, `?`, …) does not block the 19-step family-PC checklist.
  This combined merge now includes PR #2 TASTE-VIEWER 72/72 chrome and
  PR #5 docs. No new Check; 16/22 unchanged. Pointer:
  [UI-SPEC — Windows Presentable Shell](UI-SPEC.md#windows-presentable-shell).
- Help file refined around Steve setting up a portable picture library for his
  mother-in-law to browse. No new product features added.
- [PRODUCT](PRODUCT.md) has F1–F22 and one Check each.
- [CONTRACTS](CONTRACTS.md), [UI-SPEC](UI-SPEC.md), [FIXTURES](FIXTURES.md),
  [SLICES](SLICES.md), and [AGENT-BUILD-MODE](AGENT-BUILD-MODE.md) specify the build.
- Six reference images exist; they are layout targets, not runtime evidence.
- 2026-10-13 — Windows taste Track B (viewer) is implemented on
  `cursor/viewer-chrome-2bd1`. Win7 Photo Viewer chrome: Back top-left,
  Previous/Next + Rotate at the bottom, zoom slider (no +/−), click-hold
  pan while zoomed, top-right Info dropdown (no overlay pills), Reveal
  in Explorer, Open in the default app (no “Showing original” button),
  viewer heart, and header Update Library (`POST /api/update`). Back
  stays on the live listen URL. Does not close a new Check. F10 stayed
  green. TASTE-VIEWER 72 assertions; F10 29.
  Evidence: [TASTE-VIEWER](features/taste-windows/Rev1.0/assets/viewer-chrome/result.json),
  [viewer-chrome.png](features/taste-windows/Rev1.0/assets/viewer-chrome/viewer-chrome.png),
  [F10](features/taste-windows/Rev1.0/assets/viewer-chrome/f10/result.json).
  No grid hearts, launcher, or Add-folder picker.
  **Superseded on `taste/windows-abc`:** “Showing original” and overlay-style
  Person/Place/Thing pills are retired. Spec target is the Win7-style
  viewer in UI-SPEC (Info dropdown, zoom slider, no highlight).
- 2026-10-13 — Windows Presentable Shell **viewer Must** rebased onto
  `cursor/merge-viewer-chrome-7726` (`d00addb`): fullscreen (F11 or F;
  Esc exits fullscreen then viewer), slideshow (F5 / Space / Esc; empty
  “Add photos first”), keyboard parity (Ctrl++/−, wheel, Ctrl+0 fit,
  Ctrl+1 100%, Ctrl+R, Space video when no slideshow, tooltips), Info
  file facts first then names (“No camera info for this file.”). Open +
  Reveal stay. Remove / sort / search / empty-library CTA stay with the
  parallel agent. Does not close a new Check.
  TASTE-VIEWER **103/103**, exit 0 on this merge tip.
  F10 **28/29**: same `browser-proof` timeout as `d00addb` (Info-first Esc
  after annotate; F10 still expects one Esc to close the viewer).
  Assertions not weakened.
  Evidence: [TASTE-VIEWER](features/taste-windows/Rev1.0/assets/viewer-shell/result.json),
  [viewer-chrome.png](features/taste-windows/Rev1.0/assets/viewer-shell/viewer-chrome.png),
  [F10](features/taste-windows/Rev1.0/assets/viewer-shell/f10/result.json).
  Pointer: [UI-SPEC — Windows Presentable Shell](UI-SPEC.md#windows-presentable-shell).
- 2026-10-13 — Windows Presentable Shell Must 6–10 (library grid/shell)
  on `cursor/windows-presentable-shell-must-806a` rebased onto PR #7
  (`cursor/viewer-shell-must-2e74`, `bd9746d`). Empty CTA + Add; scan
  Retry + path; reconnect Retry beside the exact banner; `remove` /
  `delete-file`; Newest/Oldest/Name + All/Photos/Videos/Favorites;
  search date + “No matches for …”; Update.bat / Updating…. Viewer
  fullscreen/slideshow/keys/EXIF Info stay from PR #7. Does not close a
  Check. 16/22 unchanged.
  Plan: [taste-shell](features/taste-shell/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-SHELL](features/taste-shell/Rev1.0/assets/verify-1/result.json)
  50/50, [shell.png](features/taste-shell/Rev1.0/assets/verify-1/shell.png).
- 2026-10-14 — Grid/viewer chrome taste on the video/zoom tip
  (`cursor/video-zoom-taste-1d0c`, PR #10). One `#size-slider`; Dates
  `#date-group` Years/Months/Days/Off (Off = one wall); Ctrl+wheel
  drives Size only; vertical side `#viewer-zoom-slider` with
  `#viewer-zoom-pct`; `#viewer-scrub` in `#viewer-bottom`, not over
  the picture. Clicking a video tile autoplays at the tile
  `currentTime`. `#library-version` SHA beside Update Library (PR #11).
  `launch.ps1` and `/api/update` unchanged. Does not close a Check.
  16/22 unchanged.
  Plan: [taste-video](features/taste-video/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-3/result.json)
  61/61 (tile autoplay + carry time),
  [video-viewer.png](features/taste-video/Rev1.0/assets/verify-3/video-viewer.png),
  [video-grid.png](features/taste-video/Rev1.0/assets/verify-3/video-grid.png).
- 2026-10-14 — Video + zoom taste on the Presentable Shell Must tip
  (`cursor/windows-presentable-shell-must-806a`). Viewer play stays
  fitted/centered across proxy→original; hover plays at every Size and
  on a Dates-off wall; plain-wheel zoom; `#viewer-scrub` + `.tile-scrub`.
  `launch.ps1` unwrap/reverse-slice fix from PR #9, `-Update` kept.
  Dual Level+Size sliders and overlay scrub were superseded by the
  chrome taste above. Does not close a Check. 16/22 unchanged.
  Plan: [taste-video](features/taste-video/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-1/result.json)
  45/45, [video-viewer.png](features/taste-video/Rev1.0/assets/verify-1/video-viewer.png),
  [launch-arglist](features/taste-windows/Rev1.0/assets/launch-arglist/result.json).
- 2026-10-14 — Visible checkout SHA next to **Update Library**
  (`#library-version`, `GET /api/version`, `git_sha` on
  `POST /api/update`). Short SHA only; no SemVer. Successful Update
  refreshes the label from the new tip; the serve process does not
  restart. Does not close a Check. 16/22 unchanged.
  Plan: [taste-version](features/taste-version/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-VERSION](features/taste-version/Rev1.0/assets/verify-1/result.json)
  23/23 on PR #11,
  [verify-2](features/taste-version/Rev1.0/assets/verify-2/result.json)
  23/23 after chrome+autoplay merge (SHA still beside Update Library),
  [version-header.png](features/taste-version/Rev1.0/assets/verify-2/version-header.png).
- 2026-10-14 — Reveal in Explorer selects the real on-disk file
  (`explorer.exe /select,"fullpath"`). Catalog-relative copy-here
  paths resolve to an absolute original; missing originals return
  404 `unavailable` and show “Original is not on this computer”
  instead of opening Documents. Viewer mute + volume sit beside
  `#viewer-scrub` (hover proxies stay silent). Does not close a
  Check. 16/22 unchanged. Plan:
  [taste-reveal](features/taste-reveal/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-REVEAL](features/taste-reveal/Rev1.0/assets/verify-1/result.json)
  37/37 reveal,
  [verify-2](features/taste-reveal/Rev1.0/assets/verify-2/result.json)
  40/40 after mute + volume beside scrub.

## Completion

**16 / 22 Checks = 72.7% tested.** F1, F4, F5, F6, F7, F8, F9, F10, F11, F12, F13, F14, F15, F16, F19, and F20 have fresh-verifier artifacts.
M1, M2, and M3 are recorded. Settings, keyboard, launch, and the full rerun remain pending.

| Check | Feature | State | Verifier / revision / platform | Command / evidence |
|---|---|---|---|---|
| F1 | Two folders | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `244771d` | `python -m tests.qa check F1` [verify-1](features/S05/Rev1.0/assets/verify-1/f1/result.json); orchestrator rerun [f1](features/S05/Rev1.0/assets/orchestrator-rerun/f1/result.json) |
| F2 | Launch | pending | — | Not run; no artifact |
| F3 | CLI / HTTP | pending | — | Not run; no artifact |
| F4 | Add folder | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `244771d`; Track A rerun `c4b953e` | `python -m tests.qa check F4` [verify-1](features/S05/Rev1.0/assets/verify-1/f4/result.json); orchestrator rerun [f4](features/S05/Rev1.0/assets/orchestrator-rerun/f4/result.json); Track A [f4](features/taste-windows/Rev1.0/assets/orchestrator-rerun/f4/result.json) |
| F5 | Scan | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `d55a569` | `python -m tests.qa check F5` [verify-1](features/S06/Rev1.0/assets/verify-1/f5/result.json); orchestrator rerun [f5](features/S06/Rev1.0/assets/orchestrator-rerun/f5/result.json) |
| F6 | Metadata | passed | Grok 4.7 verifier, Windows, Python 3.12.10 | `python -m tests.qa check F6` [verify-2](features/S02/Rev1.0/assets/verify-2/f6/result.json); orchestrator rerun [f6](features/S02/Rev1.0/assets/orchestrator-rerun/f6/result.json) |
| F7 | Previews | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `d55a569` | `python -m tests.qa check F7` [verify-1](features/S06/Rev1.0/assets/verify-1/f7/result.json); orchestrator rerun [f7](features/S06/Rev1.0/assets/orchestrator-rerun/f7/result.json) |
| F8 | Preview storage | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `a442e8f` | `python -m tests.qa check F8` [verify-1](features/S07/Rev1.0/assets/verify-1/f8/result.json); orchestrator rerun [f8](features/S07/Rev1.0/assets/orchestrator-rerun/f8/result.json) |
| F9 | Zoom | passed | Grok 4.7 verifier, Linux, Python 3.12.3 | `python -m tests.qa check F9` [verify-1](features/S04/Rev1.0/assets/verify-1/f9/result.json); orchestrator rerun [f9](features/S04/Rev1.0/assets/orchestrator-rerun/f9/result.json) |
| F10 | Viewer | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `b8e2663` | `python -m tests.qa check F10` [verify-1](features/S09/Rev1.0/assets/verify-1/f10/result.json); orchestrator rerun [f10](features/S09/Rev1.0/assets/orchestrator-rerun/f10/result.json) |
| F11 | Sort | passed | Grok 4.7 verifier, Linux, Python 3.12.3 | `python -m tests.qa check F11` [verify-1](features/S04/Rev1.0/assets/verify-1/f11/result.json); orchestrator rerun [f11](features/S04/Rev1.0/assets/orchestrator-rerun/f11/result.json) |
| F12 | Globe | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `9c2ab3a` + S10; taste rerun `e3a3439` | `python -m tests.qa check F12` [verify-1](features/S10/Rev1.0/assets/verify-1/f12/result.json); orchestrator rerun [f12](features/S10/Rev1.0/assets/orchestrator-rerun/f12/result.json); yaw/texture [f12-taste](features/S10/Rev1.0/assets/orchestrator-rerun/f12-taste/result.json) |
| F13 | Tour | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `01a28a5` + S11 | `python -m tests.qa check F13` [verify-2](features/S11/Rev1.0/assets/verify-2/f13/result.json); orchestrator rerun [f13](features/S11/Rev1.0/assets/orchestrator-rerun/f13/result.json) |
| F14 | People / places / things | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `59ab5ab` | `python -m tests.qa check F14` [verify-1](features/S08/Rev1.0/assets/verify-1/f14/result.json); orchestrator rerun [f14](features/S08/Rev1.0/assets/orchestrator-rerun/f14/result.json) |
| F15 | Search | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `b8e2663` | `python -m tests.qa check F15` [verify-1](features/S09/Rev1.0/assets/verify-1/f15/result.json); orchestrator rerun [f15](features/S09/Rev1.0/assets/orchestrator-rerun/f15/result.json) |
| F16 | Unavailable originals | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `a442e8f` | `python -m tests.qa check F16` [verify-1](features/S07/Rev1.0/assets/verify-1/f16/result.json); orchestrator rerun [f16](features/S07/Rev1.0/assets/orchestrator-rerun/f16/result.json) |
| F17 | Settings | pending | — | Not run; no artifact |
| F18 | Undo / Esc / clipboard / log | pending | — | Not run; no artifact |
| F19 | Live Photos | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `fccfbe6` + S12 | `python -m tests.qa check F19` [verify-1](features/S12/Rev1.0/assets/verify-1/f19/result.json); orchestrator rerun [f19](features/S12/Rev1.0/assets/orchestrator-rerun/f19/result.json) |
| F20 | Rebuild | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `59ab5ab` | `python -m tests.qa check F20` [verify-1](features/S08/Rev1.0/assets/verify-1/f20/result.json); orchestrator rerun [f20](features/S08/Rev1.0/assets/orchestrator-rerun/f20/result.json) |
| F21 | Keyboard | pending | — | Not run; no artifact |
| F22 | Web page states | pending | — | Not run; no artifact |

## Build handoff and prerequisites

Build is authorized. Follow SLICES dependency order from S00. Do not start from
the next heading in PRODUCT. M1 still means fixture scan → thumbnails → open a
photo, with a screenshot packet. Execution policy 2026-10-13: do not wait for
Steve to inspect M1, M2, or M3. Continue on the locked defaults. Target remains
22/22, with unavailable platform checks blocked rather than dropped.

On 2026-10-13 neither parent `J:\slyOS` nor this product was a Git repository.
This product alone was initialized. The specification baseline, ignore rules,
and the execution-policy edit are the first local commit. slyOS was not
initialized. No workflow-engine packet is claimed. macOS/Linux verification
environments must be supplied by the build or F2 remains pending; do not claim
100% while excluding that existing promise.

## Notes and spec evidence

- 2026-10-13 — Windows taste Track C (grid) locked and implemented on
  `cursor/s03-still-renditions-8e1d`: whole-tile video hover, VIDEO badge,
  `kind=video` filter, Size 72–520 with distinct level defaults (All 420),
  thumbs stay painted through zoom, Dates-off wall, tile hearts with
  collapsible Favorites (`catalog/favorites.json`), Library/Globe toggle
  chrome. No 17th setting. Does not close a Check. Plan:
  [taste-grid](features/taste-grid/Rev1.0/PLAN.md). Browser proof
  [verify-1](features/taste-grid/Rev1.0/assets/verify-1/result.json)
  26/26: whole-tile hover, VIDEO badge, kind=video, All 420 / Years 72 /
  Months 104, thumbs stay painted, wall, hearts + Favorites, view chrome.


- 2026-10-12 — Original help file and six layout references created; no code.
- 2026-10-12 baseline refinement — Added technical contracts, screen-state/input
  contract, fixed fixture specification, dependency plan and orchestrator handoff.
  Preserved original 18 Check examples, added four missing Checks (folder
  portability, CLI/HTTP parity, keyboard, complete web states), and extended gates
  to cover described visible behavior. Doc audit evidence is separate from the
  pending product checks: [spec validation](features/spec-plan/Rev1.0/assets/spec-validation.json).
- Independent specification review passed after six contract/dependency fixes:
  [review artifact](features/spec-plan/Rev1.0/assets/independent-review.md).
  This does not change the 0/22 software result.
- 2026-10-13 — Execution policy recorded in SLICES and AGENT-BUILD-MODE: prepare
  M1/M2/M3 evidence and continue without a taste pause. Product-only Git
  repository initialized. Software Checks remain 0/22.
- 2026-10-13 — S00 plan locked in `docs/features/S00/Rev1.0/PLAN.md`. Foundation
  and generator ambiguities are now in CONTRACTS and FIXTURES. No Check has run.
- 2026-10-13 — S00 green. Closes no Check (0/22 remains). Fresh verifier
  [verify-2](features/S00/Rev1.0/assets/verify-2/result.json) after one test
  correction: 251 assertions, exit 0. Orchestrator rerun
  [orchestrator-rerun](features/S00/Rev1.0/assets/orchestrator-rerun/result.json)
  also exit 0. Implementer model was Grok 4.6 because the documented 4.5 slug
  is not available; verifier was a fresh Grok 4.7. macOS/Linux was not run.
  No workflow-engine packet.
- 2026-10-13 — S01 green. Closes no Check (0/22 remains). Fresh verifier
  [verify-2](features/S01/Rev1.0/assets/verify-2/result.json): 179 assertions,
  exit 0, second scan added 0 / skipped 27. Orchestrator rerun
  [orchestrator-rerun](features/S01/Rev1.0/assets/orchestrator-rerun/result.json)
  also exit 0. S00 stayed green after the scan work
  [after-s01](features/S00/Rev1.0/assets/after-s01/result.json).
- 2026-10-13 — S02 plan locked in `docs/features/S02/Rev1.0/PLAN.md` after
  metadata recon.
- 2026-10-13 — F6 passed. Fresh verifier
  [verify-2](features/S02/Rev1.0/assets/verify-2/f6/result.json): 108
  assertions, exit 0. Orchestrator rerun
  [f6](features/S02/Rev1.0/assets/orchestrator-rerun/f6/result.json) also
  exit 0. S00 and S01 stayed green
  ([after-s02 S00](features/S00/Rev1.0/assets/after-s02/result.json),
  [after-s02 S01](features/S01/Rev1.0/assets/after-s02/result.json)).
  One test correction made the equal-timestamp tie sort by id rather than
  filename.
- 2026-10-13 — S03 plan locked in `docs/features/S03/Rev1.0/PLAN.md` after
  still-rendition recon. JPEG thumbs and previews only. F7 and F10 stay open.
- 2026-10-13 — S03 green. Closes no Check (1/22 remains). Fresh Grok 4.7
  verifier [verify-1](features/S03/Rev1.0/assets/verify-1/result.json): 59
  assertions, exit 0. Orchestrator rerun
  [orchestrator-rerun](features/S03/Rev1.0/assets/orchestrator-rerun/result.json)
  also exit 0. Thumb 240×320, preview 480×640, `first-still.png` is a real
  1280×720 viewer shot of the upright oriented JPEG. Implementer model was
  Grok 4.6 (`cursor-grok-4.6-high-fast`); the requested 4.5 slug is not
  available. Recon was Composer 2.5 Fast. Linux S00 after S03 failed two
  HEIC ffprobe metadata reads (`quad.heic` / `quad.heif`); hashes and ftyp
  brands still match
  ([orchestrator-after-s03](features/S00/Rev1.0/assets/orchestrator-after-s03/result.json)).
  Linux S01 aborted at the Windows `cmd /c mklink /J` junction helper
  ([after-s03 stdout](features/S01/Rev1.0/assets/after-s03/stdout.log)).
  Those are runner-platform facts, not S03 product failures. Windows S00/S01
  evidence remains the grade for those slices. After pinning checkout-rewritten
  fixture mtimes, S02 and F6 exited 0 on this Linux runner
  ([S02](features/S02/Rev1.0/assets/orchestrator-after-s03-mtime/result.json),
  [F6](features/S02/Rev1.0/assets/orchestrator-after-s03-mtime/f6/result.json)).
  Next action was S04 (closes F9, F11).
- 2026-10-13 — S04 / M1 green. Closes F9 and F11 (**3/22**). Fresh Grok 4.7
  verifier [S04](features/S04/Rev1.0/assets/verify-1/result.json) 86
  assertions, [F9](features/S04/Rev1.0/assets/verify-1/f9/result.json) 45,
  [F11](features/S04/Rev1.0/assets/verify-1/f11/result.json) 26, all exit 0.
  Orchestrator rerun [F9](features/S04/Rev1.0/assets/orchestrator-rerun/f9/result.json)
  and [F11](features/S04/Rev1.0/assets/orchestrator-rerun/f11/result.json)
  also exit 0. Years has two groups; date desc is 2024 then 2023 then pinned
  2022 mtime; zoom drift 0 px; pan error 0 px. M1 packet:
  [years](features/S04/Rev1.0/assets/verify-1/years.png),
  [all](features/S04/Rev1.0/assets/verify-1/all.png),
  [viewer](features/S04/Rev1.0/assets/verify-1/viewer.png).
  Do not wait for taste. Next action was S05 (closes F1, F4).
- 2026-10-13 — S05 green. Closes F1 and F4 (**5/22**). Fresh Grok 4.7
  verifier [S05](features/S05/Rev1.0/assets/verify-1/result.json) 114
  assertions, [F1](features/S05/Rev1.0/assets/verify-1/f1/result.json) 22,
  [F4](features/S05/Rev1.0/assets/verify-1/f4/result.json) 94, all exit 0
  at `244771d`. F9 and F11 stayed green after S05
  ([F9](features/S04/Rev1.0/assets/after-s05/f9/result.json) 45,
  [F11](features/S04/Rev1.0/assets/after-s05/f11/result.json) 26, exit 0).
  Committed fixture mtimes already matched the manifest, so none were pinned.
  Original hashes unchanged (26/26). Collisions wrote `photo_2.jpg` and
  `photo_3.jpg`. Moved library originals still open. Undo left copy bytes
  after the catalog records were removed. Orchestrator rerun
  [F1](features/S05/Rev1.0/assets/orchestrator-rerun/f1/result.json) and
  [F4](features/S05/Rev1.0/assets/orchestrator-rerun/f4/result.json) also
  exit 0. Next action is S06 (closes F5, F7).
- 2026-10-13 — S06 plan locked in `docs/features/S06/Rev1.0/PLAN.md` after
  S05. All fixture formats, HEIC failure placeholder, full-length silent
  ≤480 px H.264 proxy, and the three hover policies. F8 stays open until
  S07. F10 stays open until S09.
- 2026-10-13 — S06 green. Closes F5 and F7 (**7/22**). Fresh Grok 4.7
  verifier [S06](features/S06/Rev1.0/assets/verify-1/result.json) 89
  assertions, [F5](features/S06/Rev1.0/assets/verify-1/f5/result.json) 66,
  [F7](features/S06/Rev1.0/assets/verify-1/f7/result.json) 89, all exit 0
  at `d55a569`. F9 and F11 stayed green after S06
  ([F9](features/S04/Rev1.0/assets/after-s06/f9/result.json) 45,
  [F11](features/S04/Rev1.0/assets/after-s06/f11/result.json) 26, exit 0).
  Oriented JPEG 240×320 / 480×640. `clip.mp4` proxy 480×360 h264, 0 audio,
  2.000 s. Hover: one cell, off none, always at Years, leave restores poster.
  `broken.heic` error / no WebP. `quad.heic` / `quad.heif` stay error on this
  runner's ffmpeg. Original hashes unchanged. Orchestrator rerun
  [F5](features/S06/Rev1.0/assets/orchestrator-rerun/f5/result.json) and
  [F7](features/S06/Rev1.0/assets/orchestrator-rerun/f7/result.json) also
  exit 0. Implementer model was Grok 4.6 (`cursor-grok-4.6-high-fast`).
  Next action is S07 (closes F8, F16).
- 2026-10-13 — S07 green. Closes F8 and F16 (**9/22**). Fresh Grok 4.7
  verifier [S07](features/S07/Rev1.0/assets/verify-1/result.json) 83
  assertions, [F8](features/S07/Rev1.0/assets/verify-1/f8/result.json) 54,
  [F16](features/S07/Rev1.0/assets/verify-1/f16/result.json) 32, all exit 0
  at `a442e8f`. F5 and F7 stayed green after S07
  ([F5](features/S06/Rev1.0/assets/after-s07/f5/result.json) 66,
  [F7](features/S06/Rev1.0/assets/after-s07/f7/result.json) 89, exit 0).
  With-source thumb under `.library/renditions/`. Relocate both ways. Denied
  and interrupt leave old bytes. Banner exact. Placeholder exact. Orchestrator
  rerun [F8](features/S07/Rev1.0/assets/orchestrator-rerun/f8/result.json) and
  [F16](features/S07/Rev1.0/assets/orchestrator-rerun/f16/result.json) also
  exit 0. Next action is S08 (closes F14, F20).
- 2026-10-13 — S08 plan locked in `docs/features/S08/Rev1.0/PLAN.md` after
  S07. Annotate, merge, pending-during-hash, and rebuild-index. Viewer
  typing stays open until S09.
- 2026-10-13 — S08 green. Closes F14 and F20 (**11/22**). Fresh Grok 4.7
  verifier [S08](features/S08/Rev1.0/assets/verify-1/result.json) 104
  assertions, [F14](features/S08/Rev1.0/assets/verify-1/f14/result.json) 84,
  [F20](features/S08/Rev1.0/assets/verify-1/f20/result.json) 23, all exit 0
  at `59ab5ab`. Ada/mug reuse, `?thing=mug` both ids, pending annotate
  survives hash, rebuild search ids identical. Orchestrator rerun
  [F14](features/S08/Rev1.0/assets/orchestrator-rerun/f14/result.json) and
  [F20](features/S08/Rev1.0/assets/orchestrator-rerun/f20/result.json) also
  exit 0. Next action is S09 / M2 (closes F10, F15).
- 2026-10-13 — S09 plan locked in `docs/features/S09/Rev1.0/PLAN.md` after
  S08. Viewer annotation fields, search chips, and preview/original playback.
  This is M2. Do not wait for taste.
- 2026-10-13 — S09 / M2 green. Closes F10 and F15 (**13/22**). Fresh Grok
  4.7 verifier [S09](features/S09/Rev1.0/assets/verify-1/result.json) 91
  assertions, [F10](features/S09/Rev1.0/assets/verify-1/f10/result.json) 29,
  [F15](features/S09/Rev1.0/assets/verify-1/f15/result.json) 78, all exit 0
  at `b8e2663`. Viewer Ada/mug/Kitchen from real fields.
  [viewer](features/S09/Rev1.0/assets/verify-1/viewer-annotations.png),
  [search-mug](features/S09/Rev1.0/assets/verify-1/search-mug.png).
  Inspector mug count 2 unique ids. Orchestrator rerun
  [F10](features/S09/Rev1.0/assets/orchestrator-rerun/f10/result.json) and
  [F15](features/S09/Rev1.0/assets/orchestrator-rerun/f15/result.json) also
  exit 0. Next action is S10 (closes F12).
- 2026-10-13 — S10 plan locked in `docs/features/S10/Rev1.0/PLAN.md` after
  S09. Offline WebGL globe, clusters, click→newest viewer→Esc filtered grid.
- 2026-10-13 — S10 green. Closes F12 (**14/22**). Fresh Grok 4.7 verifier
  [S10](features/S10/Rev1.0/assets/verify-1/result.json) 56 assertions,
  [F12](features/S10/Rev1.0/assets/verify-1/f12/result.json) 51, both
  exit 0. Two GPS places; no-exif omitted; local `earth.png`; cluster
  count 3; drag 0.25 deg/px; zoom drift 0.13 px. Click opens near.jpg;
  Esc filtered grid (near, IMG_1042, far).
  [globe](features/S10/Rev1.0/assets/verify-1/globe.png),
  [cluster](features/S10/Rev1.0/assets/verify-1/cluster.png).
  Orchestrator rerun
  [F12](features/S10/Rev1.0/assets/orchestrator-rerun/f12/result.json)
  also exit 0. Implementer model was Grok 4.6
  (`cursor-grok-4.6-high-fast`). This Linux ffmpeg still cannot decode
  `quad.heic` / `quad.heif`. Next action is S11 (closes F13).
- 2026-10-13 — S11 / M3 green. Closes F13 (**15/22**). Fresh Grok 4.7
  verifier [S11](features/S11/Rev1.0/assets/verify-2/result.json) 85
  assertions, [F13](features/S11/Rev1.0/assets/verify-2/f13/result.json)
  85, both exit 0 after one Esc-orbit freeze correction. Tour JSON has
  both GPS places and omits no-exif; clip uses muted timed proxy.
  [tour](features/S11/Rev1.0/assets/verify-2/tour.mp4),
  [stopped](features/S11/Rev1.0/assets/verify-2/stopped-globe.png).
  Orchestrator rerun
  [F13](features/S11/Rev1.0/assets/orchestrator-rerun/f13/result.json)
  also exit 0. F12 stayed green after the S10 `page-no-play` retarget.
  Next action is S12 (closes F19).
- 2026-10-13 — S12 green. Closes F19 (**16/22**). Fresh Grok 4.7
  verifier [S12](features/S12/Rev1.0/assets/verify-1/result.json) 72
  assertions, [F19](features/S12/Rev1.0/assets/verify-1/f19/result.json)
  72, both exit 0. Live id is still hash `db41b641…`; LIVE badge;
  hover proxy; missing motion stays on the still.
  [live](features/S12/Rev1.0/assets/verify-1/live.png).
  F5/F7/F10/F14/F16 stayed green in
  [regression](features/S12/Rev1.0/assets/verify-1/regression.json).
  Orchestrator rerun
  [F19](features/S12/Rev1.0/assets/orchestrator-rerun/f19/result.json)
  also exit 0. `quad.heic` / `quad.heif` stay error + placeholder.
  Next action is S13 (closes F17, F18, F21).
- 2026-10-13 — S07 plan locked in `docs/features/S07/Rev1.0/PLAN.md` after
  S06. Preview store, relocate both ways, unavailable originals, and the
  missing-preview screen. F10 stays open until S09.
- 2026-10-13 — Windows taste Track B viewer chrome. Specs first
  (PRODUCT F10/F3, UI-SPEC Viewer, CONTRACTS favorite/reveal/open/update).
  Win7 chrome: Info dropdown, zoom slider, bottom Prev/Next/Rotate,
  click-hold pan, Reveal, default-app Open, Update Library hook.
  Browser proof TASTE-VIEWER 72 assertions exit 0; F10 29 assertions
  stayed green. No new Check closed (16/22).
- 2026-10-13 — Windows Presentable Shell North Star lock, then Must
  backlog folded in (PR #5). PRODUCT Must list + F3 remove/delete-file;
  UI-SPEC 19-step DoD; CONTRACTS `remove` / `delete-file` and
  `kind=photo,live`; SLICES: S13/S14 secondary. Combined with PR #2
  72/72 chrome on this merge. No new Check. 16/22 unchanged.
- 2026-10-13 — Viewer Presentable Shell Must (fullscreen, slideshow,
  keyboard parity, EXIF-first Info) rebased onto
  `cursor/merge-viewer-chrome-7726`. Open + Reveal + Win7 chrome stay.
  Remove/sort/search/empty shipped on this shell PR against that tip.
  TASTE-VIEWER 103 assertions exit 0 on the merge tip. F10 28/29:
  `browser-proof` times out on Info-first Esc, same as `d00addb`;
  assertions not weakened. No new Check. 16/22 unchanged.
- 2026-10-14 — Grid/viewer chrome taste after PR #10. One Size slider;
  Dates Years/Months/Days/Off; vertical side viewer zoom; scrub in
  `#viewer-bottom`. Clicking a video tile autoplays at the tile
  `currentTime`. TASTE-VIDEO 61/61. `#library-version` kept (PR #11
  merge); TASTE-VERSION 23/23 on this tip. `GET /api/update` 200. No
  new Check. 16/22 unchanged.
- 2026-10-14 — Reveal in Explorer selects the real on-disk file
  (`explorer.exe /select,"fullpath"`). Missing original is 404
  `unavailable` and the viewer banner, not Documents. TASTE-REVEAL
  37/37, then 40/40 with mute + volume. No new Check. 16/22 unchanged.
- 2026-10-14 — Docs-only North Star refresh (this file + PRODUCT /
  UI-SPEC / CONTRACTS / ONE_SHOT_PROMPT). Sibling code tips not
  merged here: #13 places, #15 objects, #16 faces, #17 spaces/MOV/badge.
  Hover-in-Years-and-Months remains a Steve lock and a code gap.
  16/22 unchanged.
