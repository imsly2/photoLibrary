# Speed loop handoff (2026-10-18, 03:00–06:50)

Continuation of [PERFORMANCE-AND-STORAGE-HANDOFF.md](PERFORMANCE-AND-STORAGE-HANDOFF.md).
Storage layout work has **not** started; it is still the open proposal there.

## Where it stands

Speed budgets now live in [PRODUCT.md F7 → Processing speed](../../../PRODUCT.md)
and are measured by one command:

```powershell
.\.venv\Scripts\python.exe -m tests.perf.bench --count 80 --label <name>   # or Bench.bat
.\.venv\Scripts\python.exe -m tests.perf.bench --app <worktree> --label <name>   # run another checkout
.\.venv\Scripts\python.exe -m tests.perf.bench --compare A.json B.json
```

It copies 80 of Steve's JPEGs + 1 MOV into `.qa/bench/`, starts a scratch server
on port 8797, adds the folder (serve-from-folder, previews in folder — the real
setup), opens one picture mid-run, polls the server like the UI does (1 Hz), and
times milestones from the scratch catalog on disk. PASS / FAIL / NO DATA per budget;
nonzero exit if anything is not PASS. Artifacts: `assets/perf-bench/`.
Serial stage profiler (where time goes, per stage): `assets/perf-1/stage_profile.py`.

Latest 80-photo bench at HEAD `3dbd34c`
([bench-…-combined-3.json](assets/perf-bench/bench-20261018-055115-combined-3.json)):

| Budget | Old code `48e1da5` | Now | |
|---|---|---|---|
| Reading ≥ 15 pictures/s | 1.8 | ~9 (all 81 on disk at 8.95 s; bench printed 7.9 from a coarse poll) | FAIL |
| Reading last/first tenth ≤ 1.25 | 3.6 | 0.89 | PASS |
| First thumb ≤ 3 s | 0.57 | 0.60 | PASS |
| All thumbs + poster ≤ 30 s | 52 | 23.3 | PASS |
| Viewer preview ≤ 2 s | 52 | 0.48 | PASS |
| Everything ≤ 90 s | 120 | 57.7 | PASS |
| Bookkeeping ≤ 50 ms/job | 541 | 149 | FAIL |
| `/api/jobs` p95 ≤ 300 ms | 565 | 1196 (p50 13) | FAIL |
| `/api/items` p95 ≤ 1 s | 530 | 99 | PASS |

Real library after Steve restarted at 06:03 on this code: 370 previews in 200 s
(06:03:14 → 06:06:34, **1.85 previews/s ≈ 0.54 s each**; ffmpeg alone ≈ 0.3 s).
All 1103 renditions done, faces 550/550, objects 550/550, rating 429/550 still
running at 06:50; `/api/jobs` took **1.95 s** during rating.
**Steve still reports previews feel far slower than the earlier known-good app** —
nobody has benchmarked the known-good build yet (see next step 1).

## What changed (commits, oldest first)

- `48e1da5` checkpoint of the GPT WIP + F7 budgets + `perf-1/baseline.json`.
- `085f527`, `e28970d`, `06ddcef` the bench (UI-cadence load, disk-timed
  milestones, NO DATA never passes, server-catalog only — never the portable mirror).
- `a946f58` scan: scan history appends small segments sealed at scan end;
  per-file source journals folded at scan end/recovery; relaxed durability on the
  scan thread only (manifests fsynced, payload fsync deferred to checkpoint);
  transaction ids sort in commit order (`tests/test_relaxed_recovery.py`).
  JSON per scanned file 1.46 MB → 41 KB. Serial scan 3.8 → 21 files/s, flat at 400.
- `c45b3be` drain: process-level drive-letter cache (was 10,818 lookups / 73 s
  per 80 photos), stat-validated in-memory item index (`library/item_index.py`;
  job pick 0.23 s → 1 ms), viewer priority (`POST /api/items/<id>/want`, and a
  not-ready preview media GET also marks it), single-file fsynced rendition
  publish with portable mirror deferred to drain idle, snapshot-then-release
  catalog reads (`server._catalog_read`, `library/read_cache.py`, lock held ~5 ms;
  `GET /api/items` on 411 items ~35 ms warm). `LIBRARY_LOCK_TRACE=<file>` logs lock holds.
- `3dbd34c` HTTP scan batches like the CLI (it previously disabled batching
  whenever `between()` was passed), yields on a pending id ~2×/s;
  `LIBRARY_PROFILE_SCAN=<path>` profiles the scan thread.

Tests rerun by the lead: `unittest tests.test_relaxed_recovery tests.test_volume_lookup_scope
tests.test_objects_status` (9 OK), `tests.qa check F5` (pass). Agents reported S08 ×3,
processing_feedback, F7 (only `playwright-import` fails — Playwright not installed),
F8 (pre-existing chmod/busy failures, same at `48e1da5`).

## Not finished — known causes, in priority order

1. **Compare against the known-good build first.** Steve says it was much faster
   before. Make a worktree at the last commit before the portable-folder work
   (`c360c09`, before `10fb551`/`150a38e`) and run
   `tests.perf.bench --app .qa/known-good --label known-good` (check that the
   `/api/sources` body with `previewStore: with-source` is accepted there; if not,
   bench both with `with-server` too). That tells us whether the 0.54 s/preview
   live rate is the regression, and what "faster before" actually measured.
2. **Optional queues hold the global lock and rescan the catalog per step.**
   `rating.rate_step`, `faces.infer_faces_step`, `objects.analyze_step`,
   `transcribe.transcribe_step` loop `iter_item_ids` + uncached `load_item` over
   the whole catalog every step (the same O(N) pattern previews had), and
   `service.drain_step` calls them without `io_context`, so ffmpeg decode + ONNX
   inference run **inside** `handler.lock`. That is the likely cause of the slow
   Rating/Faces phases and of `/api/jobs` 1.2–2 s. Fix with the same pattern as
   renditions: pick from `item_index`, compute unlocked, revalidate, publish short.
3. **Drain loop sleeps 50 ms after every job** (`server.serve.drain_loop`:
   `drain_stop.wait(0.05 if worked else 0.25)`). Most of the 149 ms bookkeeping;
   in-process bookkeeping is ~30 ms. Remove the post-work wait.
4. **Scan holds the lock ~0.5 s between yields** after `3dbd34c`, which is the
   other half of the `/api/jobs` p95 spike and slows thumbs during a scan.
   Hash/EXIF/content-id must run under `io_context` (unlocked), locked sections
   < 100 ms. Also check end-of-scan `sync_bundles` on 400 files.
5. **Portable mirror lag**: 10+ s after the bench finished, the folder copy had
   all 81 items but only 11 with preview ready — the drain's idle flush does not
   reliably run/cover everything (check the case where optional queues keep the
   drain "working"). Requirement: folder copy current within 2 s of renditions idle.
6. **Decode-once for stills** not done: thumb and preview are two ffmpeg launches
   decoding the same 12 MP JPEG (thumb ~0.16 s, preview ~0.3 s). Pillow is not
   in the venv and the server must not import it (F5 check). Options: ffmpeg
   `split` producing both in one run once grid thumbs are done, or thumb from the
   written preview. Measure before choosing.
7. Uncommitted: `tests/perf/bench.py` has a half-finished round-3 edit (disk-based
   reading rate, stills-only tenth ratio, lock-trace summary). It compiles; not
   run. Finish it or `git checkout tests/perf/bench.py`.
8. Scaling run not done: `tests.perf.bench --count 400`.

## Rules that held

Never touch `library-data/` or `J:\Pictures` except reading originals for fixture
copies; scratch under `.qa/` (gitignored). Don't restart Steve's server
(port 8785) without asking. One agent per file set when running in parallel.
Commit each green slice locally. A budget with no data is not a pass.
