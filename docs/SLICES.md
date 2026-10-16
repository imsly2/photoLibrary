# Library — bounded build plan

2026-10-12. **Plan only. No command below exists yet. No Check has passed.**
Read [PRODUCT](PRODUCT.md), [CONTRACTS](CONTRACTS.md), [UI-SPEC](UI-SPEC.md),
[FIXTURES](FIXTURES.md), then [AGENT-BUILD-MODE](AGENT-BUILD-MODE.md).
This order replaces “next help-file section”: dependencies determine the build.

## Layers and milestone stops

| Layer | Slices | Runnable result |
|---|---|---|
| 0: durable foundation | S00 | Fixture runner, launch/health, settings, transaction/history and log foundations |
| 1: catalog | S01–S02 | Linked fixture scan, stable records, resume/dedup, dates and GPS places, disposable index |
| 2: first pictures | S03 | Small and medium stills served from local fixture library |
| 3: first browse | S04 | **M1 — Open the family box:** scan fixture folder, see small pictures, open one; first taste stop |
| 4: portable media | S05–S07 | Copy/link choices, portable originals, all formats/video proxies, preview locations and unavailable behavior |
| 5: names | S08–S09 | **M2 — Find it again:** annotate Ada/mug/Kitchen, search and inspect; evidence milestone, no required stop |
| 6: places | S10–S11 | **M3 — Travel through the pictures:** offline globe, cluster selection and looping tour; evidence milestone, no required stop |
| 7: finish | S12–S14 | Live pairs, full history/settings/keyboard, cross-platform launcher checks and whole-product verification; **M4 — Complete fixture library**, final taste stop |

Windows taste **Track A** (launch, Add folder, scan feedback, live-origin Back)
is a mid-queue product fix on already-shipped F2/F4 behavior. It does **not**
add a 23rd Check and does **not** start S13 or S14. Pin macOS/Linux F2.
Viewer/grid chrome is a separate track. Gate: `python -m tests.qa slice TASTE-WIN`
plus re-run `check F4`. See [taste-windows PLAN](features/taste-windows/Rev1.0/PLAN.md).

Optional local AI (2026-10-14) stacks on the People/Processing tip: offline
GPS city names (`setup-geo` / `analyze-places`), YOLO Things (`setup-ml
objects` / `analyze`; COCO person ignored), InsightFace unnamed
clusters (`setup-ml faces` / `infer-faces`), and Whisper video speech
(`setup-ml transcribe` / `transcribe`; extractive summary). Serve-time drains honor
`/api/jobs` Pause/Start. Models optional; browse does not crash when
they are missing. Gates: `slice GEO`, `slice TASTE-OBJECTS`,
`slice FACES`, `slice TASTE-TRANSCRIBE`, plus `slice TASTE-PEOPLE`. No 23rd Check. `Setup.bat`
composes `setup-geo` / `setup-ml objects` / `setup-ml faces` /
`setup-ml transcribe`.

**Presentable for family PC** (2026-10-13): [UI-SPEC](UI-SPEC.md#windows-presentable-shell)
is the North Star shell. Must items (fullscreen, slideshow, viewer keys,
EXIF Info, Open with, empty/error, remove vs delete-file, sort/filters,
search, Update UX) are on the 19-step checklist. Until that path is
green, do **not** start S13 or S14 to chase settings completeness, and do
not treat Soon rows (filmstrip, multi-select, Print, `?`) as the next
build. This combined merge includes PR #2 TASTE-VIEWER 72/72 (Win7 chrome
+ Update + Open) and PR #5 Presentable Shell docs. Pin macOS/Linux F2.
No 23rd Check.

Portable `Setup.bat` (2026-10-14) is a sibling of `Library.bat`: one-time
Python/ffmpeg/`.venv` plus `setup-geo` / `setup-ml objects` / `setup-ml
faces` / `setup-ml transcribe` when those CLIs exist. Missing modules tell Steve to Update
Library first. Gate: `python -m tests.qa slice TASTE-SETUP`. Does not
change serve. No 23rd Check.

Filter bar / tags / arrange (2026-10-14) stacks on the People tip:
`#filter-bar` chips and Clear all, Group People/Places/Tags, collapse
any group, multi-person AND with fixture proof, user tags that survive
re-infer. Gate: `python -m tests.qa slice TASTE-FILTERS`. Keep
`Setup.bat` / `Library.bat` / ASCII `.ps1`. No 23rd Check.

Empty-grid / language / chrome (2026-10-14): catalog with photos and
people must paint the grid (never first-run “No pictures yet”); header
language English/中文 persists as `settings.language`; Search moves onto
`#filter-bar`; Group defaults to Date and no longer shares the header
with People/Places/Things search chips. Gates:
`slice TASTE-EMPTY-GRID`, `slice TASTE-I18N`, keep TASTE-FILTERS /
TASTE-PEOPLE / TASTE-SHELL. No 23rd Check.

Grid thumbs + People/Tags layout (2026-10-14): after the empty-grid
poll coalescing, catalog status can stay `queued` while files are
already on disk, and reused tile `<img>` error state is sticky across
person-filter / Clear. Tags in `#library-side` can paint over People.
Fix: serve a rendition file when it exists on disk (no re-encode);
`Cache-Control` on thumbs so a second load is cache-hit; drain must
not hold the HTTP lock across ffmpeg/faces; tile stills remember
painted URLs so filter/clear/refresh does not trickle; People and
Tags are session-collapsible (Tags start closed) with a horizontal
splitter and clipped flex panes. Face-crop picker is single-select.
Re-run Faces must drain the full remaining face queue (pending drops
each step; a failed item does not freeze the counter).
Gates: `slice TASTE-PREVIEWS`,
`slice TASTE-SIDEBAR`, keep TASTE-EMPTY-GRID / TASTE-FILTERS /
TASTE-PEOPLE / TASTE-SHELL. No 23rd Check.

Video rendition size (2026-10-14): proxies stay scrub-small (width ≤
`proxyWidth`, CRF 28, no audio). A stored `playback.mp4` is only for
originals that are not browser-safe MP4, and then only at ≤1280 / CRF
23 (remux only when already small). Orphan `*.tmp` is removed. Gate:
`slice TASTE-VIDEO` (size notes in `rendition-size.json`). No 23rd
Check. No new setting.

Copy/link identity, unavailable model, logging and history start before the first
scan. Their full UI/edge-case checks close later. This is deliberate: the suggested
late copy/undo layers would otherwise force rewrites of the early catalog.
SQLite rebuild plumbing starts S01; annotated-search equivalence closes F20 in S08.

**Execution policy (2026-10-13):** The earlier “stop at M1 for taste” rule is
suspended for this authorized build. Prepare the M1 screenshot and demo packet
(grid, one opened photo, fixture URL, evidence paths) and continue immediately,
using the existing reference images and locked defaults. Do not wait for Steve
to inspect M1, M2, or M3. M2 and M3 still produce their evidence packets while
the build continues. Stop for user input only for a genuine blocker or an
unresolved material product choice. M4 remains the single taste question, asked
once with the fixture demo after the Checks are recorded; do not pause the
queue waiting for that answer before continuing unrelated bookkeeping. Steve is
not routine QA. Failed measurable checks go back to agents.

M1 is still a capability milestone, not a misleading “mostly done” percentage:
it closes F6, F9, F11, **3/22 = 13.6%**. Other features have working subsets
then, but receive no credit until all their behavior passes. M2 is 13/22
(59.1%); M3 is 15/22 (68.2%); M4 is 22/22 (100%). These counts assume every
earlier closing gate passed and none regressed. A real family-drive trial is
separate future work, never silently substituted for fixture QA or required
for this plan.

## Common gate invocation and evidence

S00 implements the runner below; it is a build deliverable, not existing tooling.
Run from the product root. Set `$qaRoot` to a newly created fixture-owned temp
directory; never a user-selected photo folder. Set `$evidence` to
`docs/features/<S-id>/Rev1.0/assets/<run-id>/`. Artifacts are append-only per run.
The runner provisions its own marked library root and owns its server process.

```powershell
python -m tests.qa fixtures --output $qaRoot
python -m tests.qa slice S00 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F1 --root "$qaRoot/library-data" --artifacts $evidence
```

For each row substitute its S-id. For each **closes** id run the last command with
that F-id; full Check assertions are in the coverage table below. A slice may pass
without closing a feature, but cannot call that feature complete. Exit 0 requires
all declared assertions and artifacts; missing prerequisites/skipped cases are
nonzero, not an empty green report. Gate captures must include actual CLI/HTTP
calls from PRODUCT, not only direct service calls. Use isolated fresh roots per
scenario, immutable fixture manifest, and record revision + platform.

Default artifacts for every row: `result.json`, `stdout.log`, relevant JSON records
and API response bodies. Browser rows also require inspected PNGs, `console.json`,
`network.json`, `measurements.json`; video/tour add `playback.json` and a short
recording. A fresh verifier runs these; orchestrator re-runs closing Checks and
checks the artifacts. Implementer logs cannot close a Check.

## Slice cards (strict dependency order)

Each row's dependencies must already be green. Earlier gates stay green; future
unbuilt features are explicitly pending, never replaced with fake successful data.

| Id / one-line result | Depends on | Features / closes | Gate: expected assertions beyond common command | Evidence additions | Steve |
|---|---|---|---|---|---|
| S00 — Start an empty durable library | None; Git prerequisite below | F2,F3,F17,F18 foundations; closes none | `slice S00`: generate/validate fixed fixtures; launch isolated root, health 200; settings defaults persisted; second launch same root reuses server; occupied port does not kill service; root lock, atomic write recovery, settings undo/redo and forced error log work | health.json, settings.json, recovery.json, dependency-probe.log, fixture-manifest.json | No |
| S01 — Scan a linked fixture folder and keep its identity | S00 | F1,F3,F4,F5,F16,F20 foundations; closes none | `slice S01`: scan serve-from-there, enumerate allowed formats, skip excluded trees; pending→hash, same-byte duplicate locations, repeated scan skipped/added=0, stop/resume; missing volume retained; JSON→SQLite rebuild; no writes to originals except explicit future with-source previews | scan-first.log, scan-second.log, catalog snapshots, original-hashes.json, interruption.json | No |
| S02 — Put pictures on dates and GPS places | S01 | closes F6 | `slice S02`, `check F6`: exact EXIF/CreateDate/filename/mtime precedence, orientation/media metadata, JPEG+QuickTime GPS, 50m reuse/5km separation, null names without geo pack, no-GPS exclusion, deterministic ties | metadata.json, items/, places/, extraction-dumps/ | No |
| S03 — Produce and open still renditions | S02 | F7,F10 media subset; closes none | `slice S03`: JPEG thumb/preview oriented and within bounds, byte responses and range/errors; placeholder while queued; decoder failure preserves record; fixed missing-preview state. Serve a minimal real page, not mock responses | sizes.json, media-responses.json, first-still.png | No |
| S04 — Browse and open the fixture pictures (M1) | S03 | closes F9,F11; F10/F21/F22 browse subset | `slice S04`, `check F9`, `check F11`: Add linked fixture from real dialog, scan status→grid, four levels, date/location/name directions, open correct still, next/previous/Esc, cursor zoom/pan measurements and no console errors. Date fixture has pinned no-EXIF mtime | years.png, all.png, viewer.png, input-trace.json, groups-*.json | Evidence packet; do not wait |
| S05 — Copy a source and move the library intact | S04 | closes F1,F4 | `slice S05`, `check F1`, `check F4`: both Add choices and defaults/CLI override; file structure preserved, collisions suffix, interrupted copy resumes without extra copies; convert linked source after seeded annotations, ids persist; move app/data and remap volume; original byte hashes unchanged; copy undo retains originals | paths-before-after.json, copied-items/, collision.json, original-hashes.json | No |
| S06 — Finish scan formats and video renditions | S05 | closes F5,F7 | `slice S06`, `check F5`, `check F7`: all fixture extensions indexed; valid formats decode with declared dependencies, failed HEIC placeholder retained; full-length <=480px H.264 silent proxy, 2s duration within 1 frame; hover policy including always/off, only one hovered cell; original/proxy fallback | ffprobe.json, scan-resume.json, hover-playback.json, format-matrix.json | No |
| S07 — Keep previews useful when originals are away | S06 | closes F8,F16 | `slice S07`, `check F8`, `check F16`: global/per-source preview store, dedup ownership; relocate both directions, interrupted/unwritable destination rollback; source disappears after launch; show/hide + explicit override; missing original, missing preview and both missing states; available alternate used | relocation-before-after.json, source-resolution.json, unavailable.png, no-preview.png | No |
| S08 — Store people, places and things; rebuild search | S07 | closes F14,F20 | `slice S08`, `check F14`, `check F20`: CLI/HTTP annotate, normalized boxes, names/aliases reused, unnamed face/name assignment, place rename, merge rewrites all faces atomically; real pending annotate before hashing; restart/undo survives hash merge; delete index and compare results | annotation-records/, merge.json, pending-migration.json, rebuild-before-after.json | No |
| S09 — Find and open annotated pictures (M2) | S08 | closes F10,F15 | `slice S09`, `check F10`, `check F15`: viewer fields write via real controls, labels refresh; substring/name/id/chip queries and inspector count/filenames, empty search, filtered arrows/Esc; preview→original and proxy fallback exercised on all current media | search-mug.png, viewer-annotations.png, inspector.json, playback.json | No; archive milestone |
| S10 — Spin the offline globe and open a place | S09 | closes F12 | `slice S10`, `check F12`: places API counts exclude no-GPS; texture local; geometry/cluster counts, rotation/zoom anchor measurement; cluster filters and opens newest; Esc filtered grid; WebGL failure inline | globe.png, cluster.png, cluster-members.json, offline-network.json | No |
| S11 — Tour the places (M3) | S10 | closes F13 | `slice S11`, `check F13`: eligible items only; full motion sequence, durations, cap, place wrap, absent preview skip, video timed proxy, no-GPS/empty no-op; Esc every phase cancels timers; manual gesture stops tour | tour.json, tour-trace.json, tour.mp4, stopped-globe.png | No; archive milestone |
| S12 — Pair still and motion as Live Photos | S11 | closes F19; re-run F5,F7,F10,F14,F16 | `slice S12`, `check F19`: embedded identifier pair, reversed arrival/restart/orphan/mismatch, still hash one item, two component locations, annotations/history preserved, LIVE badge, hover/explicit play, missing motion falls back to still | live-item.json, live.png, live-playback.json, regression.json | No |
| GEO — Offline GPS city names | S02 | extends F6; no new F-id | `slice GEO` / `check GEO`: `setup-geo --from` fixture pack, Chicago-area GPS JPEGs named, search finds Chicago, human Kitchen name never overwritten, analyze-places backfill, missing pack leaves name null | result.json, info-chicago.png, search-chicago.png, named-places/ | No |
| TASTE-OBJECTS — Optional local YOLO Things | S08 | extends F14; no new F-id | `slice TASTE-OBJECTS`: missing model is `model-unavailable`; `setup-ml objects` + `analyze --item` writes Things; human mug kept; COCO person ignored | result.json, analyze.json, info-things.png, search.json | No |
| TASTE-TRANSCRIBE — Optional local video speech | S06 | extends F15; no new F-id | `slice TASTE-TRANSCRIBE`: spoken EN/ZH clips; Whisper `small`; skip same size+mtime; setting off skips the queue; search Said in video seeks | result.json, item-en.json, item-zh.json, search-said.png, info-transcript.png | No |
| FACES — Optional local face inference | S08 | extends F14; no new F-id | `slice FACES`: `setup-ml faces` (fixture backend under `LIBRARY_TEST=1`), detect → embed → two unnamed people, reuse across photos, boxes in range, no guessed name, Info/annotate names one person, `person=` / `q=` search, merge reassigns faces + embeddings, missing models → `models-missing`. | result.json, people/, infer.json, search.json, merge.json | No |
| S13 — Complete settings, history and keyboard across views | S12 | closes F17,F18,F21 | `slice S13`, `check F17`, `check F18`, `check F21`: all 16 settings validation+reload; host/port next launch; 500 history cap, branch, restart, merge/copy/relocate undo; original hashes preserved; focused input keys, clipboard available/lastKnownPath, log time/path, Esc priorities everywhere | settings-roundtrip.json, history.json, clipboard.txt, input-trace.json, server.log | No |
| S14 — Audit the whole fixture library (M4) | S13 | closes F2,F3,F22; re-run F1–F22 | `slice S14`, `check F2`, `check F3`, `check F22`, then `all`: Windows default launch/install path, same-root reopen, explicit port conflict; macOS/Linux launch+volume identity with platform artifacts; CLI/HTTP parity/error matrix; five views/every UI state, no external browsing requests. All 22 complete Checks green on final revision | parity.json, errors.json, platform-results/, state-gallery/, all-checks.json | **Final taste at 100%** |

S05 uses valid fixture-seeded annotations to prove copying preserves data before
the annotation command exists; S08 repeats through actual commands. S01/S06 use a
hash barrier with seeded pending annotations; S08 repeats through actual annotate.
Seeds must follow CONTRACTS exactly; they do not count as proof of user commands.
The first runnable subsets may expose only implemented controls. F22 at S14 rejects
unimplemented controls, “coming soon” stubs or required hidden manual setup.

## One complete Check per feature

These are the acceptance assertions invoked by `python -m tests.qa check F<n>`.
Each includes the original PRODUCT Check verbatim in intent plus its described
behavior not previously proved. No standalone UI/API subtest is a numerator unit.

| Check | Complete acceptance / slice that closes it |
|---|---|
| F1 | Data outside tracked source; relocation with relative originals, volume remount and missing files; no drive-letter identity. S05. |
| F2 | Windows health/default URL, prerequisites present/missing/install failure, matching-root relaunch and port conflict; macOS/Linux shell launch with stable volume identity. S14. Windows double-click `Library.bat` is required product (not a new Check); macOS/Linux launch stays pinned. Family Update is presentable-shell (UI-SPEC), not a 23rd Check. |
| F3 | Every listed mutation CLI/HTTP equivalent; read filters/media/parity, content types/ranges; unknown ids/fields/errors, success/empty/failure/argument exits. Normalize only generated ids/root prefixes, never names/values/relations. S14. Presentable `remove` / `delete-file` and `kind=photo,live` are the same matrix — do not invent a 23rd Check. |
| F4 | Original two-file copy/link example plus Add choice/default, source override, conversion id+annotation preservation, collision and interruption. S05. Windows Browse picker, 202-before-finish for both modes, close-on-busy, scan progress, and live-origin Back are the same feature — re-prove with TASTE-WIN, do not weaken this Check. |
| F5 | Original second-scan skipped/added=0 plus exclusions, formats, pending hash+annotations, duplicates, changed path, restart and HEIC failure. S06, refreshed S08/S12. |
| F6 | Original two places from three JPEGs plus all date fallbacks, orientation, dimensions/duration, EXIF/QuickTime GPS, absent GPS, tie behavior. Without the geo pack, place names stay null. Named-city proof is `check GEO` / `slice GEO`. S02. |
| F7 | Original rendition bytes and ffprobe plus oriented dimensions, full duration/audio absent, queued/error states and all three hover policies. S06, refreshed S12. |
| F8 | Original with-source→server relocation plus reverse, overrides, dedup owner, unavailable/unwritable destination and interruption; originals unchanged. S07. |
| F9 | Original four groups responses plus rendered levels, all items retained, slider/Ctrl+wheel anchors and saved level. S04. |
| F10 | Original media responses plus preview/original display, filtered arrows/Esc, zoom/pan, playback/fallback, annotations shown, absent source behavior. S09, refreshed S12. Presentable chrome (slider, Info facts-then-names, fullscreen, slideshow, Open beside Reveal, remove/delete-file) is UI-SPEC Windows Presentable Shell — do not weaken this Check. PR #2 72/72 covers Win7 chrome + Open + Update. |
| F11 | Original known-date sorting plus all three sorts/directions, pinned no-EXIF fallback, deterministic ties and toolbar. S04. Presentable labels Newest/Oldest/Name and All/Photos/Videos/Favorites are the same Check, not a new one. |
| F12 | Original places/filter responses plus offline globe, visible pins/clusters/counts, drag/zoom, clicked cluster→newest viewer→Esc filtered grid. S10. Taste refresh: realistic local `earth.png`, rightward drag increases yaw; do not weaken this Check. |
| F13 | Original tour membership plus eligible previews, complete timed motion, settings, looping/no-location behavior, Esc in every phase and offline requests. S11. |
| F14 | Original Ada/mug reuse/search plus explicit-id naming, aliases/boxes, place handling, people merge, pending/hash preservation and viewer writes in S09 regression. Close after S08 service checks; the viewer interaction belongs F10. |
| F15 | Original filename query plus typed entity search/chips, casefold/aliases, empty results, inspector ids/count/filenames, no duplicate locations in results. S09. |
| F16 | Original offline show/hide/404 plus after-launch unplug, same letter/wrong volume, available alternate and both missing-preview screen cases. S07, refreshed S12. |
| F17 | Original settings file match plus each key/default, source override precedence, invalid values, restart behavior and page edits; no localStorage authority. S13. |
| F18 | Original port undo+404 log plus redo, 500 cap, branch, restart, every mutation's undo semantics, preserved original bytes, Esc priorities and clipboard. S13. Presentable remove undo restores catalog; delete-file undo does not restore bytes. |
| F19 | Original one live item/two locations plus real identifiers, arrival order/restart/orphans/mismatch, identity/annotation retention, LIVE badge/proxy and missing motion. S12. |
| F20 | Original annotated thing after deleting index plus all filter/group/merge ids before/after rebuild, startup auto-rebuild and interrupted rebuild; JSON byte hashes unchanged. S08. |
| F21 | Every documented key/gesture works in correct context; measured cursor anchors/pan, no text-field hijacking, tour Esc. S13. Presentable Must keys (F11/F, F5, Ctrl+0/1/R, Delete) are this table; `?` / Ctrl+P stay Soon. |
| F22 | All five views and UI state gallery; reference-scope fidelity, responsive usable 1280×720/1920×1080, no blank/error loops, console/network clean on valid actions. S14. Presentable Must states (fullscreen, slideshow, empty/error, Info facts) belong here once built. Soon states (filmstrip, `?`) do not. The family-PC checklist is the taste gate, not a 23rd F-id. |

## Readiness and blocking prerequisites

On 2026-10-12 both `J:\slyOS` and this product directory returned “not a git
repository”. No commits can be made today. Before S00, initialize **only this
product** as a local Git repository, add ignores for runtime data and temporary
artifacts, then commit the reviewed spec baseline separately from S00. The fixtures
are created and committed in S00; they do not exist at the baseline prerequisite.
The build authorization covers that local prerequisite; no remote or push. Never
initialize all of slyOS or sweep unrelated work into a checkpoint. Re-check for an
existing repository first, since another session may have established one.

The workflow engine registration is also not established by this plan. Use
WORKFLOW-MEMORY's `feature-help`/registry discovery before creating machine-managed
packets. Do not fabricate BACKLOG/feature.yaml phase state. The artifact paths here
are a proposed packet convention; docs-only evidence may use those paths without
claiming engine registration. Resolve integration in S00 or record it as blocked.

No macOS/Linux runner available means F2 remains pending and the truthful maximum
is 21/22, never “100% on Windows therefore done everywhere”. A spec change can
narrow that promise only explicitly. A missing decoder, fixture, contract or QA
capability is a named blocked gate; do not replace it with Steve's manual QA.
