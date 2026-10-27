# Library — status

Spec baseline: 2026-10-12. This is a planning result, not a software release.

## True now

- 2026-10-27 — [iPhone mirror backup handoff](hand-offs/IPHONE-MIRROR-BACKUP-2026-10-27.md) consolidates corrected findings and next development steps. All 11 old-folder samples hash-verified; missing-file test demonstrates Explorer-mirror mismatch and preview/capture-metadata month disagreement. Earlier wrong-phone/DCIM-only whole-library and 38 GB storage-used inferences are superseded. Full backup remains on hold.

- 2026-10-27 — iPhone inventory diagnostic added at `tools/iphone/Inventory.ps1`, using the shipped GetAndSee.Core client. Live DCIM + CPLAssets scan: 17,468 files / 121,397,081,259 bytes, no scan errors. Five UUID-named source/local sample pairs match SHA-256. Offline diagnostic boundary/ambiguity/error checks pass (`tests/qa/iphone_inventory.ps1`). `Cli.ps1 --help` works under Windows PowerShell 5.1 with app-local bundle extraction; shipped `copy --dry-run` still lists only DCIM. Existing copy workflow is not expanded; no full backup or feature Check closed. Private reports remain outside Git in setup chat outputs.

- 2026-10-27 — Bundled importer interrupted-transfer and short-transfer cleanup regression tests pass; match suite 11/11. Synthetic checks only, no hardware disconnect was induced. Full existing-destination plan and private file inventories remain outside Git. No full backup authorized or performed.

- 2026-10-27 — Second PC hardware follow-up: trusted USB pairing validated; app-local .NET 10 runtime SHA-512 checked against Microsoft release metadata; bundled host starts and importer status is installed. Read-only DCIM inventory: 21,096 files / 150,123,360,560 bytes, including media and sidecars. Seven small real files (JPG/PNG/HEIC/MOV/MP4, including a same-stem still/motion pair) copied to a new test folder; all seven SHA-256 hashes match both the input stream and an independent second phone read. Repeat plan skips 7/7. Linked test-folder scan adds 7 with no errors; HTTP items lists 4 photos and 3 videos. This is a small hardware test, not a full backup or a proof of Live Photo grouping. No feature Check closed. ffmpeg preview decoding and GitHub authenticated push remain unverified. Private per-file evidence stays outside Git in the setup chat outputs.

- 2026-10-27 — Second Windows PC setup on branch `setup/second-windows-pc`: Python 3.14.5 isolated environment installed; local server returned HTTP 200 for home/settings/items (empty catalog). Missing .NET host message variants now map to an actionable runtime hint, and restricted Apple software inspection no longer aborts setup. Setup dry-run exits 0. Focused pytest checks: 18 passed (importer, folder index, item store); bundled match unittest suite: 9 passed. No feature Check closed. ffmpeg/.NET/Apple USB prerequisites and hardware testing remain pending; no real media imported, no backup completeness claim. See README second-PC troubleshooting.

- 2026-10-27 — Import iPhone is inside this repo at `tools/iphone` (267 files). With `LIBRARY_IPHONE_TOOL` unset, `tool_root()` is `J:\slyOS\projects\photoLibrary\tools\iphone` and `status()` reports `installed: true`. The helper exe starts and prints Usage. No file in that tree is over 100 MB. `J:\slyOS\projects\iphonePhotos` is still there and was not deleted. No phone was plugged in, so Look and Copy against a device were not run.

- 2026-10-27 — `Setup.bat -DryRun` on this PC finds Python, ffmpeg, git, the existing `.venv`, and all five local packs (places, objects, faces, transcribe, aesthetic). It does not download. A fresh PC was going to create `.venv` with the executable name `System.Object[]` because PowerShell wrapped the Python path three arrays deep. `setup.ps1` now unwraps that to the real `python.exe` before it prints or creates `.venv`. Those library commits and the Import iPhone button are on `origin/main` (`c852ec7`).

- 2026-10-20 — Browse responsiveness: item results paint without waiting for
  settings/folders/sidebar; newer filters supersede old work; visible thumbnails
  take priority on scroll; recently painted cells survive filter/clear. Metadata
  matches before original-path/full-browser projection, and shared entities resolve
  once per query. On the existing 400-photo scratch catalog, selective tag query
  247 → 39 ms, person query 241 → 40 ms; all 13 complete response hashes unchanged.
  Independent browser **22/22**, synthetic backend **60/60**, lead backend **60/60**.
  [Results and exact artifacts](features/processing-feedback/Rev1.0/BROWSE-SPEED-RESULTS.md).
  Item metadata still arrives as one JSON response; synthetic/scratch results are
  not a live-library speed guarantee. Full feature Checks were not rerun; no new
  Check closed. Live backend was not restarted. Existing unrelated edits preserved.

- 2026-10-20 — Suggested stars no longer sit at 5 for almost every photo.
  The mix is sharpness, exposure, face, rule of thirds, and gold. With a
  face, thirds is 0.35 and sharpness is 0.18. Without a face, gold is 0.40
  and sharpness is 0.35. A 5 needs that mix near the top. Re-rate of the
  live library (550 photos, 214 s, 0 errors): suggested stars 511 fives →
  14 fives, 77 fours, 225 threes, 217 twos, 17 ones. Nobody had set their
  own stars, so nothing personal was overwritten. Info on a photo lists
  sharpness, exposure, face, thirds, gold, and the mix as 0–100.
  [result.json](features/processing-feedback/Rev1.0/assets/rating-mix/result.json).

- 2026-10-19 — Face fingerprints stay on the photo, and the face index is no
  longer an undo step. Re-run on the live library (550 photos, threshold
  0.45, server restarted onto this code): 338 people → 56 (11 visible,
  37 on a single photo). The four biggest groups cover 227, 202, 109, and
  24 photos. Pace stayed flat, about 2.0 s/photo across 18.4 minutes
  (file timer around 1 s; last 20 sampled gaps 1.04 s, first 20 1.39 s).
  New undo is 500 files, 5.2 MB, mean 10 KB, max 67 KB. The previous 500
  entries, 4.41 GB, are still on disk. Every stored face has a 512-number
  fingerprint (658/658). Contact sheet:
  [sheet-045.png](features/processing-feedback/Rev1.0/assets/face-history-fix/live-rerun/sheet-045.png).
  Run log:
  [result.json](features/processing-feedback/Rev1.0/assets/face-history-fix/live-rerun/result.json).
  One ffmpeg now writes the thumbnail (or preview) and the upright frame
  face detection uses, so a new photo is decoded once. Measured on 16
  library JPEGs: full-frame RGB matched today's decode 16/16, mean
  0.757 s → 0.534 s. Detecting on the 1600 px preview missed 1 of 21
  faces and moved fingerprints (cosine mean 0.92), so that is not the
  path. This re-run still decoded originals; the thumbnails were already
  on disk.
  [measure-one-pass.json](features/processing-feedback/Rev1.0/assets/face-history-fix/measure-one-pass.json),
  [prove-shared-frame.json](features/processing-feedback/Rev1.0/assets/face-history-fix/prove-shared-frame.json).
  QA this tree: FACES 122/123 (`js-face-crop-url` only), TASTE-SETUP
  65/65, TASTE-PEOPLE 34/35 and TASTE-RATING 76/77 (playwright not
  installed), TASTE-SETTINGS 30/31 (`js-face-crop`, same missing
  `which=face&box=` literal).

- 2026-10-18 — Performance pass (perf-next): four areas measured, three fixed,
  all local commits `5a1279f`, `06fcb49`, `46a2206`. Ranked by what Steve feels,
  with before → after on the same fixture each time:
  1. **People filter and clicking around** (400 of Steve's JPEGs, 7 named people,
     headless Edge, idle server): click a person 16.7 s → 1.2 s; click a second
     person 10.4 s → 0.13 s; clear people 14.1 s → 0.5 s; first picture on screen
     9.3 s → 2.1 s; first load settled 11.8 s → 3.8 s; open original 3.3 s → 0.1 s.
     While faces re-run: person 4.2 s → 1.5 s, first picture 3.3 s → 1.6 s.
     Where the time went: a person click painted every face crop in the picker
     (294 crop requests, each a full-size ffmpeg decode of the original) ahead of
     `/api/items`; `/api/people`, `/api/tags` and `/api/sources` each read every
     item record from disk on every page load (7 calls serialised to 387 ms of
     server work, now 81 ms); an empty filter result re-fetched the whole catalog
     every 2 s. Fix: crops paint only when scrolled into view, the three lists
     read the in-memory item index, stack keys are memoised.
     Evidence: [ui-head](features/processing-feedback/Rev1.0/assets/perf-next/ui-head.json),
     [ui-after](features/processing-feedback/Rev1.0/assets/perf-next/ui-after.json),
     [api-cost-head](features/processing-feedback/Rev1.0/assets/perf-next/api-cost-head.json),
     [api-cost-after](features/processing-feedback/Rev1.0/assets/perf-next/api-cost-after.json);
     harness `ui_fixture.py` + `ui_timing.mjs` + `ui_compare.py` in the same folder.
  2. **AI queues** (40 JPEGs, faces + objects + rating): drain 98.5 s → 55.3 s;
     catalog lock held 88 s → 9 s (requests no longer wait behind models); idle
     drain tick 433 ms → 17 ms. Where the time went: the objects step re-hashed
     every original on every tick and built a fresh ONNX session per photo (the
     most likely source of the live `MemoryError`s — one session per model now,
     not reproduced on the fixture so not claimed fixed); faces and objects
     decoded and inferred while holding the lock. Every ffmpeg/ffprobe call now
     goes through one runner with `-nostdin`, a closed stdin and a hard timeout,
     so a hung decode (the live server has one, pid 39640) fails that item
     instead of stalling the whole drain — which matches the live "rating 0 done
     / 546 pending / running" symptom; rating itself completes 40/40 on the
     fixture at 0.28 s each.
     Evidence: [head-40-idle](features/processing-feedback/Rev1.0/assets/perf-next/head-40-idle.json),
     [after-40-idle](features/processing-feedback/Rev1.0/assets/perf-next/after-40-idle.json),
     py-spy [head](features/processing-feedback/Rev1.0/assets/perf-next/head-40-profile.profile.txt) /
     [after](features/processing-feedback/Rev1.0/assets/perf-next/after-ai-40-profile.profile.txt);
     tests `test_ffmpeg_runner.py`, `test_objects_step.py`.
  3. **Scan of a fresh folder** (40 JPEGs, 154 MB): bytes read per file 3.03× →
     1.03× the file size, 107.6 → 79.7 ms per file warm, binary opens 238 → 158.
     Hash, EXIF, content id and HEIF brand check now share one read; ffprobe is
     memoised per unchanged file. Evidence: [scan-head](features/processing-feedback/Rev1.0/assets/perf-next/scan-head.json),
     [scan-after](features/processing-feedback/Rev1.0/assets/perf-next/scan-after.json);
     test `test_scan_one_read.py`. On the USB-2-speed drive the cold read still
     dominates; the fix removes the two warm re-reads.
  4. **Thumb/preview encode — measured, not changed.** ffmpeg `-lowres 1` on 40
     JPEGs: median 216.4 → 214.8 ms, 37/40 same output size, SSIM min 0.95 — no
     gain, because the time is process start (~40 ms) + WebP encode (~100 ms at
     compression level 2), not the decode. Level 0 would be ~55 ms at +21 % bytes
     (taste call, left as is). Evidence: [lowres-1600-l1](features/processing-feedback/Rev1.0/assets/perf-next/lowres-1600-l1.json).
  Not done: shared decode across faces/objects/rating (each still decodes its own
  frame); `/api/items` is ~3.4 KB per item (face floats, quality metrics); face
  crops decode the original where the preview would be ~2× faster. The live 8785
  server still runs the old code. Unit suite 59 OK; FACES 117/1, TASTE-PEOPLE
  34/1, TASTE-FILTERS 25/1, TASTE-SIDEBAR 2/1 — the four FAILs are a missing
  `playwright` module and a `which=face&box=` literal check that went away in
  `470f11b`, both identical on the pre-pass worktree. No feature Check closed.

- 2026-10-18 — Fresh folders show pictures on every tile right away: JPEG tiles
  use the camera's embedded EXIF thumbnail (served from the original's first
  128 KB, turned upright) until the real thumb exists, and browser-ready JPEG/PNG/
  WebP/GIF up to 26 MP no longer get a 1600 px preview (the viewer shows the thumb,
  then the original). Same 120 of Steve's JPEGs, page open in headless Edge,
  before (24fa69b) → after: top 20 tiles all pictures 8.2 s → 3.3 s; tiles without
  a picture during the scan 19.8 → 1.3 on average; all processing 51.9 s → 16.9 s;
  previews made 120 → 0; viewer stand-in for a photo opened early 2.7 s → 31 ms,
  24 MP original in 80 ms with one download; no tile ever went blank. On Steve's
  550 JPEGs 454 carry a usable camera thumbnail (73 have none, 23 are letterboxed).
  Evidence: [after](features/processing-feedback/Rev1.0/assets/camera-tiles/after/result.json),
  [before](features/processing-feedback/Rev1.0/assets/camera-tiles/before/result.json).
  Perf bench at 80 ([after](features/processing-feedback/Rev1.0/assets/perf-bench/bench-20261018-120246-camera-tiles.json)):
  everything done 12.0 s → 7.8 s; reading-tenth ratio and `/api/jobs` p95 fail
  before and after alike; "bookkeeping" rose 42 → 196 ms because it is the gap
  between finished stills, which now includes encoders idling for the scan
  (all thumbs end 1.4 s after the last file is read) — the metric needs a
  server-side measure. No full F7 Check closed.

- 2026-10-18 — Larger preview baseline: 400 JPEGs + 1 MOV completed in 285.953 s (grid109.625 s),803 nonempty outputs,0 rendition errors. Bookkeeping target failed; portable records were still stale after10 s. Eight focused harness checks passed independently and in lead rerun. No feature Check closed. See [active big-wins handoff](features/processing-feedback/Rev1.0/BIG-WINS-HANDOFF.md) and [baseline artifact](features/processing-feedback/Rev1.0/assets/perf-bench/bench-20261018-073207-rev1-scale-400-22850.json).


- 2026-10-18 — Live recovery after the follow-up report: backed up the existing
  catalog/undo/settings under `library-data/recovery/2026-10-18-processing-*`,
  replaced the old background server, and resumed the same 551-file source
  (`src_acda5625dae4`) without resetting its catalog. The real Chrome grid was
  observed with 135 cells / 15 painted thumbnails, then 29 completed preview
  jobs and zero rendition errors; processing continues. A catalog request fell
  from 33.50 s before the targeted fix to 1.76 s after it (live observations,
  not a controlled benchmark). Objects status no longer hashes image inputs;
  Windows mount lookup is cached only within each HTTP request, and worker
  exceptions are logged. Two focused regression tests pass. Evidence:
  [live recovery](features/processing-feedback/Rev1.0/assets/live-recovery-1/observations.json).
  No full F4/F7/F8 Check was closed; the working tree remains uncommitted.

- 2026-10-18 — Processing improvements are implemented but uncommitted; work
  stopped expanding at Steve's request to conserve usage. F5 and focused/browser
  checks pass; F4/F7/F8 remain unresolved. Exact evidence and a smaller-agent
  continuation prompt: [HANDOFF](features/processing-feedback/Rev1.0/HANDOFF.md).

- 2026-10-18 — Serve from that folder keeps the processed picture
  data in `<folder>/.library/`. Renditions stay under `renditions/`.
  The catalog copy is `catalog/` (items, people, places, things,
  hearts, face embeddings, object notes). Adding a folder that already
  has that catalog loads it and shows the finished pictures.
- 2026-10-18 — Serve from that folder keeps generated tiles, previews,
  and proxy videos in `<folder>/.library/renditions/<id>/`. The add
  dialog sends `previewStore: with-source`. A preview file already in
  that folder is served and not encoded again. Copy onto this drive
  still follows the global preview setting.
- 2026-10-18 — Processing names the file in hand. `GET /api/activity`
  is the current phase, filename, done/total for the folder read, and
  the time that file started. The panel ticks seconds on that file and
  shows this computer's listen address. Queue counts stay on
  `GET /api/jobs`.
- 2026-10-18 — Library and Photon Arena can both stay open. Factory
  listen port stays 8765. When another program already holds
  8765–8774, serve stores port 8785 (not an undo step) and the
  launcher opens that URL. It does not stop Photon and does not scan
  for a third port. A PC where 8765 is free stays on 8765.
- 2026-10-17 — Photo rating after PR #44 (`a82e556`) on
  `cursor/photo-rating-e3e7`. Settings **Rating** = Off / Basic /
  Smart (default Basic). Queue stage **Rating** after transcribe.
  Basic: Laplacian sharpness (normalized per resolution), histogram
  exposure, face size/sharpness from existing detections → suggested
  1–5 plus flags (blurry, too dark, too bright). Smart: local NIMA
  MobileNet ONNX via onnxruntime (CPU; GPU if present), blended with
  Basic. User 1–5 / P pick / X reject / 0 clear always wins. Reject
  hides from default views and never deletes. Filter chips: 4 stars
  and up, Picks, Hide rejects, Blurry. Sort by rating. Rescan skips
  same size+mtime. Optional reversible `ratingLearn`. Chinese strings
  included. ASCII launchers untouched. After Pull: rerun Setup.bat
  once for the aesthetic ONNX, restart Library, Start Processing.
  Does not close a Check. 16/22 unchanged.
  Plan:
  [taste-rating](features/taste-rating/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-RATING](features/taste-rating/Rev1.0/assets/verify-1/result.json)
  **82/82** (blur 3 < sharp 5; dark/bright/blurry flagged;
  burst_003 `bestOfGroup` on a BURST 3 stack; stars persist and
  override; reject hides, file stays; minStars/picks/hideRejects/
  blurry/sort=rating; rescan rated 0 skipped 9; Off `available`
  false; Smart CPU aesthetic colorful 0.41 > gray 0.15; zh 评分 /
  四星及以上 / 精选 / 隐藏排除 / 模糊),
  [grid](features/taste-rating/Rev1.0/assets/verify-1/rating-grid.png),
  [info](features/taste-rating/Rev1.0/assets/verify-1/rating-info.png),
  [chinese](features/taste-rating/Rev1.0/assets/verify-1/chinese-rating.png),
  [settings](features/taste-rating/Rev1.0/assets/verify-1/settings-rating-zh.png).
- 2026-10-16 — Local video transcription after PR #43 (`cba0ce3`) on
  `cursor/transcribe-videos-557d`. Queue stage **Transcribe** runs on
  videos with audio (faster-whisper `small`; CUDA float16 when
  present, else CPU int8). Timestamped segments/words live on the
  item. Summary is **extractive** (one or two sentences plus
  keywords; no local LLM, no cloud). Search matches spoken words
  with a **Said in video** hint and seeks. Info has a collapsible
  transcript; a line click seeks. Settings `transcribeVideos`
  (default On) turns the stage off. Same size+mtime is skipped.
  Chinese strings included. ASCII launchers untouched. After Pull:
  rerun Setup.bat once for Whisper `small`, restart Library, Start
  Processing. Does not close a Check. 16/22 unchanged.
  Plan:
  [taste-transcribe](features/taste-transcribe/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-TRANSCRIBE](features/taste-transcribe/Rev1.0/assets/verify-1/result.json)
  **88/88** (EN exact “The garden fountain is running today.”;
  ZH 今天天氣很好…; fountain `saidInVideo` seek 0.48s; rescan
  transcribed 0 skipped 3; setting off `available` false; zh
  视频里说到 / 逐字稿 / 转录视频),
  [search said](features/taste-transcribe/Rev1.0/assets/verify-1/search-said.png),
  [info](features/taste-transcribe/Rev1.0/assets/verify-1/info-transcript.png),
  [chinese](features/taste-transcribe/Rev1.0/assets/verify-1/chinese-transcribe.png),
  [settings](features/taste-transcribe/Rev1.0/assets/verify-1/settings-transcribe-zh.png).
- 2026-10-16 — Flight burn fillers after PR #42 (`9a610ef`) on
  `cursor/flight-fillers-643d`. **Review matches** wizard suggests
  same-person pairs by face cosine; Merge / Not same / Skip; never
  merges without a click (builds on Merge into… #37). Live and burst
  stacks share one tile with a badge and expand in the viewer;
  originals stay. **Print** Ctrl+P fits the open still to the page.
  Chinese strings included. ASCII launchers untouched. Already on
  main (skipped): recently added, folder filter, `?`, Fit/Fill,
  missing-original badge (#42); multi-select / Move / duplicates
  (#39–#41). After Pull: restart Library. Does not close a Check.
  16/22 unchanged.
  Plan: [taste-burn](features/taste-burn/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-BURN](features/taste-burn/Rev1.0/assets/verify-1/result.json)
  **80/80** (Ada←Bob suggestion does not merge until Merge; Not same
  hides the pair; Skip/Esc leave Ada and Bob; burst is one `BURST 3`
  tile; live stack; item JSON has no stack rewrite; originals
  unchanged; Ctrl+P fills `#print-sheet`; zh 核对可能是同一人 /
  不是同一人 / 跳过 / 打印 / 连拍 3),
  [burst tile](features/taste-burn/Rev1.0/assets/verify-1/burst-tile.png),
  [burst viewer](features/taste-burn/Rev1.0/assets/verify-1/burst-viewer.png),
  [merge wizard](features/taste-burn/Rev1.0/assets/verify-1/merge-wizard.png),
  [chinese](features/taste-burn/Rev1.0/assets/verify-1/chinese-burn.png).
- 2026-10-16 — Flight fillers after Move PR #41 (`bd583a5`) on
  `cursor/flight-fillers-aef8`. **Recently added** plus per-folder
  browse (`source=` / Settings Show photos). `?` opens the shortcut
  cheat sheet; viewer **Fit/Fill** with `V`. Tiles and Info flag a
  missing original; Locate/Reveal if the last-known path still exists.
  No auto-delete. Chinese strings included. ASCII launchers untouched.
  After Pull: restart Library. Does not close a Check. 16/22 unchanged.
  Plan: [taste-fillers](features/taste-fillers/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-FILLERS](features/taste-fillers/Rev1.0/assets/verify-1/result.json)
  **75/75** (two-folder `source=` CLI/HTTP; session `recent=1` after
  scan A then B then late.jpg; invalid recent 400; missing original
  stays in catalog; locate mode+folder; `?` sheet; `V` Fit/Fill; I
  Info; tile Missing badge; zh 最近添加 / 定位 / 适合窗口 / 铺满),
  [recently added](features/taste-fillers/Rev1.0/assets/verify-1/recently-added.png),
  [folder](features/taste-fillers/Rev1.0/assets/verify-1/folder-filter.png),
  [keyboard](features/taste-fillers/Rev1.0/assets/verify-1/keyboard-help.png),
  [missing](features/taste-fillers/Rev1.0/assets/verify-1/missing-original.png),
  [chinese](features/taste-fillers/Rev1.0/assets/verify-1/chinese-fillers.png).
- 2026-10-16 — Multi-select Move to folder on
  `cursor/move-to-folder-6d43` after duplicate-compare PR #40
  (`72d9ab9`). `#selection-bar` **Move** opens `#move-folder`:
  pick a registered Settings folder and/or browse to a subfolder;
  confirm shows count + destination; cancel moves nothing.
  `move --to` / `POST /api/items/move` relocates originals
  (same-drive rename; cross-drive copy+verify+delete). Never
  overwrites (`name_2.ext`). Mid-item failure rolls that item's
  bytes back so the catalog matches disk. Thumbs/proxies stay
  ready (no reprocess). Faces, favorites, tags, and people stay.
  Reveal opens the new path. Rescan adds no duplicate items.
  Chinese chrome included. ASCII launchers untouched. After Pull:
  restart Library. Does not close a Check. 16/22 unchanged.
  Plan: [taste-move](features/taste-move/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-MOVE](features/taste-move/Rev1.0/assets/verify-1/result.json)
  **74/74** (move N to another folder; files at new path not old;
  catalog paths updated; thumbs served without re-encode;
  favorites/faces kept; collision `near_2.jpg` no overwrite;
  cancel moves nothing; simulated failure stays consistent;
  rescan no dupes; zh 移动 / 移动到文件夹 / 将 N 项移动到),
  [selection](features/taste-move/Rev1.0/assets/verify-1/selection-move.png),
  [chinese bar](features/taste-move/Rev1.0/assets/verify-1/selection-move-zh.png),
  [chinese dialog](features/taste-move/Rev1.0/assets/verify-1/move-zh.png),
  [confirm](features/taste-move/Rev1.0/assets/verify-1/move-confirm.png),
  [after](features/taste-move/Rev1.0/assets/verify-1/after-move.png).
- 2026-10-16 — Duplicate compare UI on
  `cursor/duplicate-compare-6d12` after batch-remove PR #39
  (`79daf9a`). `#filter-duplicates`, selection **Compare** (2+),
  and Info **Compare copies** open `#duplicate-compare`: both
  sides plus dimensions / size / path / folder / date / hash.
  Each distinct item has Keep / Remove (default Keep). Same-item
  hash sides use one radio group per side so both can stay Keep.
  Apply with any Remove uses the existing confirm +
  `POST /api/items/remove`. Cancel and confirm-cancel leave both.
  Same-hash copies stay one item with Info **Also at**. Never
  auto-deletes on hash match. Originals stay. Chinese chrome
  included. ASCII launchers untouched. After Pull: restart
  Library. Does not close a Check. 16/22 unchanged.
  Plan: [taste-duplicates](features/taste-duplicates/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-DUPLICATES](features/taste-duplicates/Rev1.0/assets/verify-1/result.json)
  **60/60** (compare shows both sides + stats; unique radio
  groups; keep A / remove B drops B and keeps A; cancel and
  confirm-cancel keep both; no removal without confirm; zh
  重复项 / 比较重复项 / 保留 / 移出图库 / 应用选择 / 也在),
  [compare](features/taste-duplicates/Rev1.0/assets/verify-1/compare-sides.png),
  [chinese](features/taste-duplicates/Rev1.0/assets/verify-1/compare-zh.png),
  [confirm](features/taste-duplicates/Rev1.0/assets/verify-1/compare-confirm.png),
  [after](features/taste-duplicates/Rev1.0/assets/verify-1/after-keep-remove.png),
  [also-at](features/taste-duplicates/Rev1.0/assets/verify-1/info-also-at.png).
- 2026-10-16 — Multi-select batch favorite / remove on
  `cursor/batch-favorite-remove-4d93` after video UX PR #38
  (`89c1104`). `#selection-bar` on the existing Ctrl/Shift grid
  selection: count, Favorite / Unfavorite (same toggle as one item),
  Remove with confirm, Clear. `POST /api/items/favorite` and
  `POST /api/items/remove` reuse `catalog/favorites.json` and the
  catalog-only drop (item JSON, favorite entry, source file pointers,
  index) in one undo step. Original bytes stay. Generated
  thumbs/proxies are not wiped (same as one-item Remove). Cancel
  leaves the selection. Esc clears it. Chinese strings included.
  Never auto-deletes on hash match. No batch Delete file, export, or
  move-to-folder. ASCII launchers untouched. After Pull: restart
  Library. Does not close a Check. 16/22 unchanged.
  Plan: [taste-select](features/taste-select/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-SELECT](features/taste-select/Rev1.0/assets/verify-1/result.json)
  59/59 (select N → batch favorite all true; confirm cancel leaves
  them; confirm OK drops catalog/grid; originals stay; 已选 / 收藏 /
  移出图库 / 清除选择),
  [selection-bar](features/taste-select/Rev1.0/assets/verify-1/selection-bar.png),
  [chinese](features/taste-select/Rev1.0/assets/verify-1/selection-bar-zh.png),
  [confirm](features/taste-select/Rev1.0/assets/verify-1/batch-remove-confirm.png),
  [after remove](features/taste-select/Rev1.0/assets/verify-1/after-batch-remove.png).
- 2026-10-16 — Video UX leftovers on
  `cursor/video-ux-taste-9a03` after faces PR #37 (`b71e85d`).
  Viewer play/swap keep the fitted box (stage-local wheel/slider
  zoom; catalog-sized layout box). Small grid tiles hover-play with
  `.tile-scrub`. Size slider ↔ Ctrl+wheel and zoom slider ↔ percent
  stay in sync both ways. Progressive proxy→original/playback keeps
  time and fit. Chinese `预览进度` on tile scrub. Encode policy from
  PR #34 unchanged. After Pull: restart Library. Do **not** delete
  `playback.mp4` unless encode defaults change (they did not).
  Does not close a Check. 16/22 unchanged.
  Plan: [taste-video](features/taste-video/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-ux-3/result.json)
  **132/132** (play stays centered; Size 72 hover-play + `.tile-scrub`;
  Size ↔ Ctrl+wheel and zoom slider ↔ percent both ways; plain
  wheel zoom keeps the picture center; garden proxy→original keeps
  fit/time; Chinese `预览进度`),
  [grid](features/taste-video/Rev1.0/assets/verify-ux-3/video-grid.png),
  [viewer](features/taste-video/Rev1.0/assets/verify-ux-3/video-viewer.png),
  [mov](features/taste-video/Rev1.0/assets/verify-ux-3/video-mov.png),
  [zoom](features/taste-video/Rev1.0/assets/verify-ux-3/video-zoom.json),
  [rendition-size](features/taste-video/Rev1.0/assets/verify-ux-3/rendition-size.json).
- 2026-10-16 — Faces burn slice #1 on
  `cursor/faces-split-merge-together-ee3f` after Settings PR #36
  (`28cfd93`). **Not this person** / `people split` /
  `POST /api/people/split` takes one boxed face off a person into a new
  Unnamed person (Ada stays). **Merge into…** confirm keeps the first
  selected person (Ada←Bob). **Photos together (N)** is a Favorites-style
  collapse of the AND set, then leftover per-person groups. Chinese
  strings included. ASCII launchers untouched. After Pull: restart
  Library; Re-run Faces only if a cluster still needs a fresh detect.
  Does not close a Check. 16/22 unchanged.
  Plan: [taste-faces-burn](features/taste-faces-burn/Rev1.0/PLAN.md).
  Evidence:
  [FACES](features/faces/Rev1.0/assets/verify-4/result.json)
  118/118 (split CLI/HTTP; Ada remains),
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-8/result.json)
  63/63 (merge UI Ada←Bob),
  [TASTE-FILTERS](features/taste-filters/Rev1.0/assets/verify-6/result.json)
  50/50 (Photos together + Ada/Bob leftovers),
  [photos-together](features/taste-filters/Rev1.0/assets/verify-6/photos-together.png).
- 2026-10-16 — Settings folders + face match on
  `cursor/settings-sources-reveal-f272`. `#settings-view` (Ctrl+, /
  header): Folders first with lastKnown path, available, mode, counts,
  rendition done/queued/error, last scan; Add / Refresh (`rescan`,
  skip unchanged) / catalog-only Remove. Remaining settings.json keys
  as controls. `faceMatchThreshold` default **0.80** (slider 0.35–0.95)
  plus Re-run Faces note; `faceMinSidePx` stays 80. Detect remains
  full-frame 640 → original 112 ArcFace; large stills add overlapping
  1280 tiles (NMS) so small faces in phone photos get a usable box.
  Weak/small detections need a clearer score to join a **named**
  person. People picker uses square `which=face&box=` crops. Reveal
  argv + lastKnown fallback stay. Does not close F17. 16/22 unchanged.
  Plans: [taste-settings](features/taste-settings/Rev1.0/PLAN.md),
  [faces](features/faces/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-SETTINGS](features/taste-settings/Rev1.0/assets/verify-1/result.json)
  31/31,
  [folders](features/taste-settings/Rev1.0/assets/verify-1/settings-folders.png),
  [slider](features/taste-settings/Rev1.0/assets/verify-1/settings-faces-slider.png),
  [FACES](features/faces/Rev1.0/assets/verify-3/result.json)
  93/93 (200 px face on 4032×3024 is 32 px on the 640 canvas vs 100 px
  on a 1280 tile; named-weak stays Unnamed),
  [TASTE-REVEAL](features/taste-reveal/Rev1.0/assets/verify-6/result.json)
  57/57 (spaces + lastKnown fallback).
- 2026-10-14 — Lean deploy zip for USB / family PCs: double-click
  `PackDeploy.bat` (thin `pack-deploy.ps1` + `pack-deploy.py`). Writes
  `dist/photoLibrary-deploy.zip` and overwrites that file on re-run.
  Includes Setup / Library / Update launchers and `library/`. Excludes
  `.venv`, `library-data`, `.git`, `docs`, `tests`, `.qa`, `__pycache__`,
  egg-info, CaptureRegion screenshots, and other fat/dev trees. ASCII
  `.bat` / `.ps1` (PowerShell 5.1). README Quick start has one paragraph.
  Does not close a Check. 16/22 unchanged.
  Plan: [taste-pack](features/taste-pack/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-PACK](features/taste-pack/Rev1.0/assets/verify-1/result.json)
  57/57 (sandbox excludes planted fat trees; real zip has Setup.bat +
  library/, about 275 KB),
  [dry-run](features/taste-pack/Rev1.0/assets/verify-1/dry-run.txt),
  [repo names](features/taste-pack/Rev1.0/assets/verify-1/repo-names.json).
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
- 2026-10-14 — Follow-up on PR #14 tip `1cac4c9`: Explorer argv is
  now `["explorer.exe", "/select," + path]` so spaces
  (`Iphone Backup`, `Another Rope Swing.MOV`) select the file.
  Missing originals still 404, never Documents. Grid hover resumes
  after a catalog rebuild; dated Years/Months stay stills unless
  Dates=Off or `playProxies=always`. `#viewer-source` names Preview /
  Loading full… / Original / Preview — full unavailable. Does not
  close a Check. 16/22 unchanged. Evidence:
  [TASTE-REVEAL](features/taste-reveal/Rev1.0/assets/verify-3/result.json)
  53/53 argv + Iphone Backup spaces,
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-4/result.json)
  65/65 hover at Size 72, dated Years still, Dates-off wall play,
  `#viewer-source` Original,
  [video-viewer](features/taste-video/Rev1.0/assets/verify-4/video-viewer.png).
- 2026-10-14 — iPhone `.MOV` no longer stays on the silent 480px
  proxy. Viewer starts Preview, then swaps to `playback.mp4`
  (full-size H.264 + AAC; remux when the bitstream allows) and
  labels **Full**. Browser-safe MP4 still becomes **Original**.
  Both failing is **Preview — full unavailable**. Preserve
  Originals keeps the MOV. Reveal argv + grid hover stay.
  Does not close a Check. 16/22 unchanged. Evidence:
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-5/result.json)
  89/89 clip.mov Full + audio, clip.mp4 Original,
  [video-mov](features/taste-video/Rev1.0/assets/verify-5/video-mov.png),
  [TASTE-REVEAL](features/taste-reveal/Rev1.0/assets/verify-4/result.json)
  52/52 Iphone Backup argv + Full in UI-SPEC.
- 2026-10-14 — Dated Years/Months hover play + tile scrub (Steve).
  Default `playProxies` no longer leaves those mosaics still. Days,
  Dates=Off, Reveal argv, Preview/Original/Full, and MOV
  `playback.mp4` stay. Does not close a Check. 16/22 unchanged.
  Evidence:
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-8/result.json)
  92/92 Years + Months play and scrub,
  [TASTE-REVEAL](features/taste-reveal/Rev1.0/assets/verify-5/result.json)
  52/52.
- 2026-10-14 — Library chrome taste on the reveal/hover tip
  (`cursor/reveal-spaces-hover-proxy-c876`). Size + Dates sit in
  `#library-chrome` at the **bottom-left** of the grid. Right People
  splitter: named always, unnamed at ≥3 photos, click / Ctrl-click
  AND, rename + thumbnail. `#jobs-panel` Pause / Start talks to
  `/api/jobs` (rendition drain is live; analyze / infer-faces /
  objects honor the same pause). Grid and viewer stay. Does not
  close a Check. 16/22 unchanged.
  Plan: [taste-people](features/taste-people/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-1/result.json)
  52/52,
  [library-chrome](features/taste-people/Rev1.0/assets/verify-1/library-chrome.png),
  [people-panel](features/taste-people/Rev1.0/assets/verify-1/people-panel.png).
- 2026-10-14 — Optional local AI stacked on the People/Processing tip:
  offline GPS city names (`setup-geo` / `analyze-places`), YOLO Things
  (`setup-ml objects` / `analyze`; COCO person ignored), InsightFace
  unnamed clusters (`setup-ml faces` / `infer-faces`). Serve-time
  `drain_step` runs those workers when jobs are not paused and the
  pack/models are installed. Missing models stay idle (`available`
  false) and browse does not crash. People panel reads real face
  clusters. Tip chrome (bottom Size/Dates, right People+Processing)
  stays. `Setup.bat` now composes those CLIs (sibling below). Does not close
  a Check. 16/22 unchanged. Fresh on this stack:
  [GEO](features/places-geo/Rev1.0/assets/verify-2/result.json) 44/44,
  [TASTE-OBJECTS](features/taste-objects/Rev1.0/assets/verify-2/result.json) 39/39,
  [FACES](features/faces/Rev1.0/assets/verify-2/result.json) 40/40,
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-2/result.json) 52/52.
  Processing `available=true` + People after infer:
  [jobs](features/stack-local-ai/Rev1.0/assets/verify-1/jobs-available.png),
  [people](features/stack-local-ai/Rev1.0/assets/verify-1/people-after-infer.png),
  [library](features/stack-local-ai/Rev1.0/assets/verify-1/library-stack.png).

- 2026-10-14 — Portable `Setup.bat` on the reveal/hover tip
  (`cursor/reveal-spaces-hover-proxy-c876`). One-time Windows install:
  Python 3.12+ / ffmpeg (same winget ids as `launch.ps1`), `.venv`,
  then `setup-geo` + `setup-ml objects` + `setup-ml faces` when those
  CLIs exist. Missing modules print that Update Library must pull them
  and exit non-zero. `Library.bat` / `launch.ps1` serve path unchanged.
  Story: Setup once → Library daily → Update for code. No MSI. First
  model download needs the internet. Does not close a Check. 16/22
  unchanged.
  Plan: [taste-setup](features/taste-setup/Rev1.0/PLAN.md).
  After rebase onto the #21 stack tip, the probe finds
  `setup-geo` / `setup-ml objects` / `setup-ml faces`.
  Evidence:
  [TASTE-SETUP](features/taste-setup/Rev1.0/assets/verify-2/result.json)
  21/21 (all three CLIs present),
  [dry-run](features/taste-setup/Rev1.0/assets/verify-2/dry-run.txt),
  earlier missing-module path
  [verify-1](features/taste-setup/Rev1.0/assets/verify-1/result.json).
- 2026-10-14 — Filter bar, chips, arrange, and user tags on
  `cursor/filter-bar-tags-5ac4`. Search stays in the header. All
  filters live on `#filter-bar` (All/Photos/Videos/Favorites,
  Person/Place/Tag chips, Clear all, Group Dates/People/Places/Tags).
  One `filter` object; click a selected person deselects. Group
  People/Places/Tags with Unknown / No place / Untagged; collapse any
  header for the session. User tags (Things) create/apply/remove on
  one or many selected items, persist, and survive re-annotate.
  Multi-person AND proven with Ada/Bob/Cam. Does not close a Check.
  16/22 unchanged. Setup.bat / Library.bat / `.ps1` untouched.
  Plan: [taste-filters](features/taste-filters/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-FILTERS](features/taste-filters/Rev1.0/assets/verify-1/result.json)
  41/41,
  [filter-bar](features/taste-filters/Rev1.0/assets/verify-1/filter-bar.png),
  [group-people](features/taste-filters/Rev1.0/assets/verify-1/group-people.png).
  Stayed green: TASTE-PEOPLE 52/52, TASTE-SHELL 50/50, F9 46/46,
  F11 26/26, F14 84/84. F15 HTTP search stayed green; browser-proof
  is the same Info-first Esc as F10 28/29.
- 2026-10-14 — Empty-grid regression after PR #26, Simplified Chinese,
  and Group/Search chrome on `cursor/empty-grid-chinese-chrome-0c42`.
  Root cause: 1s poll overlapped `loadCatalog`; `/api/items` +
  `/api/groups` full-scans raced; newer `loadGen` discarded items so
  the grid painted first-run empty while People/Tags still filled.
  Fix: coalesce catalog loads; poll jobs/health only unless scanning
  or the first items have not landed; groups 400 falls back to client
  grouping; `catalogReady` after items land so a truly empty library
  still shows “No pictures yet” (not stuck Loading). Header Language
  English / 中文 writes `settings.language` (`en` | `zh-Hans`);
  fill_missing_defaults accepts pre-language files. Search is on
  `#filter-bar`; Group defaults to Date; People/Places/Things search
  chips dropped. Zero new deps. Setup.bat / Library.bat / `.ps1`
  untouched. Does not close a Check. 16/22 unchanged.
  Plans: [taste-empty-grid](features/taste-empty-grid/Rev1.0/PLAN.md),
  [taste-i18n](features/taste-i18n/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-EMPTY-GRID](features/taste-empty-grid/Rev1.0/assets/verify-1/result.json)
  19/19,
  [grid-with-people](features/taste-empty-grid/Rev1.0/assets/verify-1/grid-with-people.png),
  [TASTE-I18N](features/taste-i18n/Rev1.0/assets/verify-1/result.json)
  25/25,
  [chinese-chrome](features/taste-i18n/Rev1.0/assets/verify-1/chinese-chrome.png),
  [TASTE-FILTERS](features/taste-filters/Rev1.0/assets/verify-2/result.json)
  44/44,
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-3/result.json)
  57/57,
  [TASTE-SHELL](features/taste-shell/Rev1.0/assets/verify-2/result.json)
  50/50.
- 2026-10-14 — Grid thumbs + People/Tags layout on
  `cursor/grid-previews-sidebar-e8d3` (PR #28). Person-filter chip X
  and full reload were wiping tiles or stalling mid-batch: a second
  still job for the same cell leaked the concurrency slot, so the
  rest of the grid stayed **Preview not available**. One live job
  per cell; the stall watchdog always releases; a 1s recover pass
  re-queues hung thumbs; skip `/api/media` until rendition status is
  ready or error. People and Tags are session-collapsible (People
  open, Tags collapsed) with `#side-vsplit` so Tags never covers a
  face. Setup.bat / Library.bat / `.ps1` untouched. Does not close a
  Check. 16/22 unchanged.
  Plans: [taste-previews](features/taste-previews/Rev1.0/PLAN.md),
  [taste-sidebar](features/taste-sidebar/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-PREVIEWS](features/taste-previews/Rev1.0/assets/verify-3/result.json)
  20/20 (chip X twice, overlapping paints, two reloads stay painted),
  [grid-thumbs](features/taste-previews/Rev1.0/assets/verify-3/grid-thumbs.png),
  [TASTE-SIDEBAR](features/taste-sidebar/Rev1.0/assets/verify-3/result.json)
  26/26,
  [sidebar](features/taste-sidebar/Rev1.0/assets/verify-3/sidebar-people-tags.png),
  [TASTE-EMPTY-GRID](features/taste-empty-grid/Rev1.0/assets/verify-3/result.json)
  19/19,
  [TASTE-FILTERS](features/taste-filters/Rev1.0/assets/verify-3/result.json)
  44/44,
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-4/result.json)
  57/57,
  [TASTE-SHELL](features/taste-shell/Rev1.0/assets/verify-3/result.json)
  50/50.
- 2026-10-14 — Family install polish on `cursor/mil-install-update-a762`
  (rebased on `8ede708` / PR #30, includes PR #28). Desktop + Start Menu Library
  shortcut (`CreateShortcut.bat`, `library.ico`). Update always
  tracks `main` over anonymous HTTPS git (no `gh`, no GitHub login;
  credential helper off). If git is missing, overlays a public zip of
  `main` and never replaces `library-data/`. Setup progress + failure
  next-steps; optional `Git.Git`. Auto-restart only this app's serve
  after a real update. In-app Update strings through i18n. Does not
  close a Check. 16/22 unchanged.
  Plan: [taste-install](features/taste-install/Rev1.0/PLAN.md).
  Evidence:
  [TASTE-SETUP](features/taste-setup/Rev1.0/assets/verify-4/result.json)
  40/40 (shortcut script, Update tracks main, optional git/zip),
  [TASTE-INSTALL](features/taste-install/Rev1.0/assets/verify-2/result.json)
  51/51 (isolated checkout of main, zip preserves library-data, no gh).
- 2026-10-14 — Cached thumbs + face-crop picker on
  `cursor/thumb-cache-face-picker-e8d3` (PR #29), after Steve pulled
  #28 and refresh still trickled. Cause: `Cache-Control: no-store`
  on `/api/media`, drain holding the HTTP lock across ffmpeg/faces,
  and queued catalog status skipping files already under
  `renditions/`. Fix: serve the existing file (no re-encode);
  `private, max-age=604800` + ETag/304 on thumbs; media GET is
  lock-free; client remembers painted still URLs; face picker is
  single-select with an immediate ring. Re-run Faces does not reset
  grid rendition status. Setup.bat / Library.bat / `.ps1` untouched.
  Does not close a Check. 16/22 unchanged.
  Evidence:
  [TASTE-PREVIEWS](features/taste-previews/Rev1.0/assets/verify-4/result.json)
  27/27 (cached thumbs 10 ms, reload 16 ms, picker single-select),
  [grid-thumbs](features/taste-previews/Rev1.0/assets/verify-4/grid-thumbs.png),
  [TASTE-EMPTY-GRID](features/taste-empty-grid/Rev1.0/assets/verify-5/result.json)
  19/19,
  [TASTE-SIDEBAR](features/taste-sidebar/Rev1.0/assets/verify-4/result.json)
  26/26,
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-6/result.json)
  57/57,
  [TASTE-FILTERS](features/taste-filters/Rev1.0/assets/verify-4/result.json)
  44/44,
  [TASTE-SHELL](features/taste-shell/Rev1.0/assets/verify-4/result.json)
  50/50.
- 2026-10-14 — Re-run Faces drain + picker + cached thumbs on
  `cursor/faces-progress-thumbs-e8d3` (PR #32), rebased on `449f248`
  / PR #31. Steve: Faces pending after Re-run Faces ticked once
  (37→36) then stalled; picker still unclear / multi-select / laggy.
  Cause: `infer_faces_step` with `forceRescan` re-inferred the first
  item forever and `except: return False` froze the queue; picker
  rebuild + itemId-only match. Fix: skip already-scanned even when
  force; mark failed/unreadable items scanned; drain faces first
  during force rescan; picker is pointerdown single-box with a
  visible outline. Cache-instant thumbs from the unmerged #29 stack
  stay. Setup.bat / Library.bat / ASCII `.ps1` untouched on this
  branch (install files come from #31). Does not close a Check.
  16/22 unchanged.
  Evidence:
  [TASTE-PREVIEWS](features/taste-previews/Rev1.0/assets/verify-5/result.json)
  41/41 (faces queue 6→0 including planted failure; cached thumbs
  11 ms; picker immediate + rapid single-select),
  [faces-progress](features/taste-previews/Rev1.0/assets/verify-5/faces-progress.json),
  [grid-thumbs](features/taste-previews/Rev1.0/assets/verify-5/grid-thumbs.png),
  [TASTE-EMPTY-GRID](features/taste-empty-grid/Rev1.0/assets/verify-6/result.json)
  19/19,
  [TASTE-SIDEBAR](features/taste-sidebar/Rev1.0/assets/verify-5/result.json)
  26/26,
  [TASTE-PEOPLE](features/taste-people/Rev1.0/assets/verify-7/result.json)
  57/57,
  [TASTE-FILTERS](features/taste-filters/Rev1.0/assets/verify-5/result.json)
  44/44,
  [TASTE-SHELL](features/taste-shell/Rev1.0/assets/verify-5/result.json)
  50/50.
- 2026-10-14 — Setup.bat on a flash-drive copy printed Ready after
  `Set-Location` failed because the app-folder path was null
  (`setup.ps1:15`). `$AppFolder` now resolves from `-AppFolder`
  (Setup.bat / Library.bat / Update.bat / CreateShortcut.bat pass
  `%~dp0`), then `$PSScriptRoot`, then `$MyInvocation.MyCommand.Path`,
  then a cwd that contains those launch files. If the folder still
  cannot be resolved, the script exits 1 and the batch failure
  branch runs (no Ready). Same resolver in `launch.ps1` and
  `create-shortcut.ps1`. ASCII `.bat` / `.ps1`. Does not close a
  Check. 16/22 unchanged. Restart not required; re-copy or Update
  then run Setup.bat again.
  Evidence:
  [TASTE-SETUP](features/taste-setup/Rev1.0/assets/verify-5/result.json)
  63/63 (empty `$PSScriptRoot` uses bat hint / MyCommand.Path /
  cwd marker; all-empty is null; Ready only after errorlevel 0),
  [app-folder-probe](features/taste-setup/Rev1.0/assets/verify-5/app-folder-probe.json).
- 2026-10-14 — Video rendition size on `cursor/rendition-disk-13ad`.
  Proxies stay scrub-small (≤`proxyWidth`, CRF 28, no audio). Stored
  `playback.mp4` is only for originals that are not browser-safe MP4,
  and then only at ≤1280 / CRF 23 (remux only when already small).
  Orphan `*.tmp` is removed on the next drain. `#viewer-source` names
  the file that is playing. Existing huge playback files are not
  rewritten; delete them and restart Library.bat to rebuild. Does not
  close a Check. 16/22 unchanged.
  Evidence:
  [TASTE-VIDEO](features/taste-video/Rev1.0/assets/verify-size-5/result.json)
  114/114,
  [rendition-size](features/taste-video/Rev1.0/assets/verify-size-5/rendition-size.json)
  (2s 4K MOV: old CRF 18 full-frame 225 KB → policy 58 KB at 1280;
  browser-safe MP4 writes no playback file; fixture proxy 3.4 KB).

## Completion

**13 / 22 Checks = 59.1% recorded passed.** The processing-feedback working tree reopens F4, F7, and F8 below. Earlier 16/22 claims are historical; this is not a full final-revision rerun.
M1, M2, and M3 are recorded. Settings, keyboard, launch, and the full rerun remain pending.

| Check | Feature | State | Verifier / revision / platform | Command / evidence |
|---|---|---|---|---|
| F1 | Two folders | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `244771d` | `python -m tests.qa check F1` [verify-1](features/S05/Rev1.0/assets/verify-1/f1/result.json); orchestrator rerun [f1](features/S05/Rev1.0/assets/orchestrator-rerun/f1/result.json) |
| F2 | Launch | pending | — | Not run; no artifact |
| F3 | CLI / HTTP | pending | — | Not run; no artifact |
| F4 | Add folder | pending | Fresh Codex verifier, Windows/Python 3.12.14, processing-feedback working tree | Conflicting runs: lead passed, fresh verifier 89/94 (HTTP busy/nonempty-source). Resolve possible test-port interference; no full credit. [Verifier](features/processing-feedback/Rev1.0/assets/verify-1/final-f4/result.json), [lead](features/processing-feedback/Rev1.0/assets/lead-f4-1/result.json) |
| F5 | Scan | passed | Fresh Codex verifier, Windows/Python 3.12.14, processing-feedback working tree | `python -m tests.qa check F5`, 66/66. [Verifier](features/processing-feedback/Rev1.0/assets/verify-1/final-f5/result.json), [lead rerun](features/processing-feedback/Rev1.0/assets/lead-f5-1/result.json) |
| F6 | Metadata | passed | Grok 4.7 verifier, Windows, Python 3.12.10 | `python -m tests.qa check F6` [verify-2](features/S02/Rev1.0/assets/verify-2/f6/result.json); orchestrator rerun [f6](features/S02/Rev1.0/assets/orchestrator-rerun/f6/result.json) |
| F7 | Previews | failed | Fresh Codex verifier, Windows/Python 3.12.14, processing-feedback working tree | 79/80; hover-browser timeout remains. HEIC codec probes and generated media pass. [Verifier](features/processing-feedback/Rev1.0/assets/verify-1/final-f7/result.json), [lead](features/processing-feedback/Rev1.0/assets/lead-f7-1/result.json) |
| F8 | Preview storage | failed | Fresh Codex verifier, Windows/Python 3.12.14, processing-feedback working tree | 22/23 then fixture server port-in-use; lead additionally exposes permission-denial assumptions and busy 409. Undo destination correction passes; full Check unresolved. [Verifier](features/processing-feedback/Rev1.0/assets/verify-1/final-f8/result.json), [lead](features/processing-feedback/Rev1.0/assets/lead-f8-1/result.json) |
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
- 2026-10-14 — Follow-up: argv `/select,path` for spaced
  `Iphone Backup` paths; hover resume; `#viewer-source`. TASTE-REVEAL
  53/53, TASTE-VIDEO 65/65. No new Check. 16/22 unchanged.
- 2026-10-14 — MOV `playback.mp4` + honest Full badge. TASTE-VIDEO
  89/89, TASTE-REVEAL 52/52. No new Check. 16/22 unchanged.
- 2026-10-14 — Rendition size policy (proxy CRF 28; playback ≤1280 /
  CRF 23; no playback for browser-safe MP4; tmp sweep). TASTE-VIDEO
  114/114. No new Check. 16/22 unchanged.

