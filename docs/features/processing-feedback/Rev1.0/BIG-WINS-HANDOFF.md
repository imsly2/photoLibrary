# Big performance opportunities — active Cursor handoff

**Latest, 2026-10-20:** [BROWSE-SPEED-RESULTS](BROWSE-SPEED-RESULTS.md) records the
verified filter/render/thumbnail scheduling and metadata-query changes. Its
evidence supersedes the older next-action ledger below for browsing. Faces and
Objects inference already release the lock in the current tree. No live restart
or additional feature Check closure in this pass.

Updated 2026-10-18. User direction: prioritize large speed gains, use one smaller implementing agent, minimal focused verification, reversible commits. Do not spend remaining usage expanding benchmark infrastructure. This supersedes SCALE-PLAN's measurement-first emphasis for new work.

## Objective and order

1. **One decode for both photo sizes (ACTIVE).** Generate thumb.webp and preview.webp in one FFmpeg process whenever both are queued. Publish both promptly for that photo, including during scanning. Keep existing single-output behavior when only one needs work. Preserve sizes, source/original bytes, image orientation, errors, staged publication, source-change/removal revalidation and annotation edits. The first thumbnail may take slightly longer because its preview is generated too; measure that tradeoff rather than hiding it.
2. **Early large previews.** Step 1 should remove the all-thumbnails-first wait for newly processed photos. Keep viewer priority and ensure selecting a photo can still request a missing preview. Evaluate standalone scheduling changes only if this remains a measured issue.
3. **Release browsing lock during Rating, then Faces.** Select/snapshot while locked, compute outside lock, revalidate and publish under lock. Start with Rating only; retain settings changes, source removal/replacement, annotations and model semantics. This targets responsiveness; do not claim it accelerates model inference itself.
4. **Small bounded worker pool, only after the above.** Try two image workers if measured CPU/disk capacity allows. Keep publication serialized and pause/removal safe. This is deferred until the simpler gains are measured; not permission for an unbounded scheduler rewrite.

## Fast implementation loop

One smaller implementer (available gpt-6-luna in place of unavailable Cursor models), one bounded change, then fresh focused verification. Use the same small real-photo copies for before/after; record timings and output sizes/dimensions. Include only targeted safety checks for changed paths. No full 22-feature suite or another 400-file run per edit. Independent verification plus lead spot-check; no new feature Check closure without its full declared Check. Commit green bounded changes locally, never push. Do not change originals, restart the live app or migrate storage.

## Existing work and evidence

Cursor HEAD at start: 1121b35; prior app speed commits are documented in SPEED-LOOP-HANDOFF.md. Its 80 JPEG+1 MOV result measured previews, not all AI processing; 3/9 speed targets failed. Real server later reported previews1103 done0errors, Faces/Objects/Rating550 each done, transcription1error.

Current uncommitted benchmark work preserves Cursor's unfinished edit and repairs result serialization, false success on failed/missing derivatives, invalid not-applicable slots, unique safe scratch folders, fixture checksums, queue/mirror diagnostics, TCP port preflight, and unread subprocess output pipes. The old harness blocked a 400-photo run around191 items because scan progress filled stdout; that interrupted run is NOT app performance evidence. Eight focused harness tests passed independently and in lead rerun. Tests/perf/bench.py and tests/perf/test_bench_measurements.py are separate from product optimization work; preserve them.

The resumed400 run is being wrapped up by scale_verify. Evidence lives in assets/scale-audit and assets/perf-bench; add final values below when available. Scratch models differ from the real installation; AI processing is excluded from preview completion. Disk polling itself adds observer load. No known-good pre-portable baseline has yet been measured; c360c09 is the candidate, but viewer priority is absent there.

## Important corrected hypotheses

Rating does not inherently starve portable mirroring: rendition idle settlement runs before Rating. A pending batch can however be lost on a swallowed mirror exception; investigate separately if final evidence shows stale records. Current Rating decode and repeated catalog reads do run under the shared server lock. Paired FFmpeg generation is a hypothesis for a major gain, not an already measured improvement.

## Continuation ledger

- Paired still generation: **shipped** (Cursor, see "Paired stills + faster encoder" below).
- Faster WebP encode (bilinear scale, libwebp method 2): **shipped** in the same slice.
- Growing per-job overhead lead: **closed, bench artifact**. Serial stage profile at 80 photos measures 28.5 ms bookkeeping/job (assets/perf-1/paired-80-profile.json); the bench estimate subtracts a single-encode FFmpeg cost from paired jobs.
- Rating: **shipped** (see "Rating off the lock" below).
- Faces: **next**. `faces.infer_faces_step` has the same shape as old Rating: `iter_item_ids` + uncached `load_item` per step, `infer_faces` (decode + ONNX) called with no `io_context`, so it holds the server lock.
- Worker pool: deferred.
- Storage naming/layout: separate open proposal, no migration.
- Live server: leave running; fixes require a later deliberate restart to take effect.

## Cursor pickup

Read this file, git status/log, then the implementation/verification evidence appended below. Preserve unrelated untracked logs and prior artifacts. Continue the first incomplete opportunity; do not restart the broad benchmark repair project. Measure one small comparable batch and focus on the largest remaining cost. Be candid about gains, regressions and incomplete checks.

## Larger baseline now completed

The valid400 JPEG+1 MOV run finished before product edits: first thumbnail0.391s, scanDone29.422s, all grid109.625s, selected preview0.844s, all rendition files285.953s. 803 outputs nonempty, no rendition errors, no API failures. Eight of nine printed budgets passed; bookkeeping estimate259.704ms/job failed50ms. This estimate subtracts sampled FFmpeg costs from observed publication intervals; it is not direct stage profiling. Portable mirror failed to catch up in10s (400 records, final diagnostic228/401 matching); AI still unfinished/unavailable in scratch. Do not equate previews done with Processing done or portable data complete. Artifact: assets/perf-bench/bench-20261018-073207-rev1-scale-400-22850.json. Relative to the earlier80 run, 5x items took4.96x preview time: no clear superlinear preview collapse in this test, but the absolute cost is still substantial. Different revision/harness and filesystem caches limit that comparison.

## Copy-paste prompt for Cursor

Work in J:\slyOS\projects\photoLibrary. Pick up from docs/features/processing-feedback/Rev1.0/BIG-WINS-HANDOFF.md and docs/PICKUP.md, then inspect git status and recent commits before changing anything. The handoff's latest ledger/evidence is authoritative about what actually finished; do not assume every planned opportunity shipped.

My priority is large practical speed improvements with low agent usage. Use one smaller implementing agent at a time. Finish or verify any in-progress paired thumbnail+preview generation, then tackle Rating's expensive work under the browsing lock; Faces follows, and only then consider two concurrent image workers. Measure a small identical photo sample before/after each substantial change. Include first-thumbnail/large-preview timing and output size where relevant. Use focused checks for the changed path, not repeated whole suites or benchmark-infrastructure rewrites. Keep fixes reversible and commit useful verified slices locally; never push.

The old400-photo harness stalled because unread output pipes filled; that was a test bug, since fixed. The valid400 JPEG+1MOV baseline was109.625s for grid thumbnails and285.953s for all preview files. AI work was excluded and portable records were still stale afterward. Do not treat that as total Processing completion or claim the earlier known-good speed has been restored. Read the new small-sample results in the handoff before choosing the next fix. Do not overwrite originals, migrate storage, or restart my live server casually. Preserve unrelated dirty files. Keep this handoff up to date with changes, measured gains/tradeoffs, commit IDs, pending work, and the exact next action so another agent can continue cheaply.

## Paired stills + faster encoder (Cursor, 2026-10-18 07:50)

Codex's uncommitted paired thumb+preview change in `library/renditions.py` was reviewed and re-verified: `tests.qa.processing_feedback` completed, 17 unit tests passed (relaxed recovery, objects status, volume lookup, bench measurements), and `assets/paired-stills/measure.py` reproduced 1.55x on the 11 small fixtures with identical output bytes and dimensions.

Encoder probe on 8 real 2592x1936 photos (`assets/paired-stills/encoder-probe.py`, `encoder-settings.json`): paired default 346 ms/photo; `flags=bilinear` + `-compression_level 2` 198 ms/photo, same dimensions, previews 14% smaller. `-lowres` rejected (would undershoot the 1600 px cap on these sources). Applied to every `_scale_filter`/WebP encode via `WEBP_ENCODE`.

Same 80 JPEG + 1 MOV bench, ui load, back to back:

| Run | first thumb | all thumbs | viewer preview | everything | artifact |
|---|---|---|---|---|---|
| HEAD 436a78e (unpaired) | 0.49 s | 21.0 s | 2.54 s | 56.6 s | perf-bench/bench-20261018-074231-head-unpaired-80.json |
| paired, default encoder | 0.74 s | 39.6 s | 1.13 s | 41.6 s | perf-bench/bench-20261018-074341-paired-80.json |
| paired + fast encoder | 0.48 s | 27.5 s | 1.62 s | **29.6 s** | perf-bench/bench-20261018-074616-paired-fastenc-80.json |

Net: all previews ~1.9x sooner; the grid finishes ~6 s later than unpaired because each thumb now waits for its preview (still inside the 30 s budget). 7/9 pass. `readingTenthRatio` (796374) is a bench bug, a near-zero first-tenth denominator; `bookkeeping` 207 ms is an estimate that assumes single encodes, but its samples climb steadily with item count, which is a real lead.

Exact next action: profile one post-scan drain step at 80 vs 400 items (`assets/perf-1/stage_profile.py --all-queues`) to find what per-publication work grows with N; then the Rating lock.

## Rating off the lock (Cursor, 2026-10-18 08:15)

Cause: `compute_basic` ran three pure-Python per-pixel loops over a 1024 px working image, about 1.17 s/photo, inside the server lock; each `rate_step` also re-read every item from disk and rebuilt best-of groups across the whole catalog.

Change (`library/rating.py`, `library/service.py`):
- `_NpLuma` does the same integer luma / Laplacian / histogram math with numpy; `_PyLuma` is the fallback. Metrics are bit-identical on 4 real photos either way (`assets/rating-speed/before.json` vs `after.json` / `after-py.json`). Compute 1170 -> 47 ms/photo.
- `rate_step(root, io_context=...)`: picks from the cached item index, skips photos whose score matches a current location's recorded size+mtime without a disk stat, decodes + scores inside `io_context` (lock released), then revalidates the item, still path and file signature before publishing.
- Best-of groups are recomputed once when the queue empties (and once per process), from cached items, instead of after every photo.

Evidence: serial drain of 40 real photos with all queues, Rating step mean 1.10 s -> 0.27 s (`assets/perf-1/rating-old-40.json` vs `rating-new-40.json`); whole drain 65.8 s -> 24.1 s including paired stills. `python -m tests.qa slice TASTE-RATING`: every behavior check PASS (scores, flags, best-of, rescan skip, stars/pick/reject, filters, smart mode, learn, HTTP); only `playwright-import` FAIL because no local Python has playwright, so the rating UI screenshot was not re-taken (UI untouched). Unit tests (17) OK.

Live server still runs old code until Steve restarts it.

Exact next action: apply the Rating pattern to `faces.infer_faces_step` (cached pick, decode + ONNX inside `io_context`, revalidate then publish), verify with the faces slice, then consider two image workers.
