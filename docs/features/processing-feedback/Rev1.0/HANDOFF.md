> **Current performance and storage continuation:** read [PERFORMANCE-AND-STORAGE-HANDOFF.md](PERFORMANCE-AND-STORAGE-HANDOFF.md) first. It captures the user's current 2–5 sec/photo report, preview scheduling state, storage proposal, and measurement-first next steps without replacing the evidence below.

# Rev 1.0 handoff

## Live follow-up: 2026-10-18

The user reported an empty/stalled real library after relaunching. The old
backend PID 15540 was still scanning with the old code; browser relaunches
reused it. Catalog records were intact (164 indexed items), with most previews
still queued. Catalog/undo/settings/active transaction files were backed up
under `library-data/recovery/2026-10-18-processing-*` before replacement.

The latest checkout is now running on port 8785. The same source
`src_acda5625dae4` was resumed with `/rescan`; unchanged files are skipped.
Additional narrow fixes: object status uses recorded immutable item identities
instead of hashing every media input; HTTP requests share native Windows mount
lookups only within that request/thread and re-resolve on the next request;
background worker exceptions now reach logs. Actual inference checks and
scan/drain publication validation retain their original checks.

Focused tests: `python -m unittest tests.test_objects_status tests.test_volume_lookup_scope`.
Parent ran both successfully; fresh verifier evidence is under
`assets/live-recovery-1/`. The real Chrome grid was observed displaying
135 cells / 15 painted images, then 29 completed preview jobs with zero errors.
GET items improved from 33.50 s to 1.76 s in live observations. This is not a
full acceptance test or a controlled benchmark. Existing F4/F7/F8 gaps remain.

A temporary `.qa/trace-live-library.py` captured the request lock bottleneck;
that diagnostic process has exited. The final server uses the normal
`python -m library --root ... serve` command, with no repeating trace dump.
Logs: `library-data/logs/processing-live.out.log` and `.err.log`.
The older live-process instructions below are historical; do not restart again
just to pick up already-loaded fixes. Read `runtime.json` for the current PID.

## Current state

The implementation and focused QA are in progress on top of portable-folder commit `150a38e`. No commit was made for this work. The working tree contains the processing-feedback changes, `tests/qa/processing_feedback.py`, and unrelated untracked launch/setup/debug logs and `_proof` directories; preserve those files.

Implemented: scan activity runs independently of derivative generation and reports counts/loading labels with single-flight polling; thumbnails are prioritized and rendered into the grid during scans; file reads/encoding use unlocked pure computation with revalidation before publication; scan history compacts each path to its first-before/latest-after state; Windows copies use a writable, flushed partial followed by metadata preservation; relocation undo restores to the recorded target; idle settings refresh and HEIC decoder capability probing are included.

## Evidence so far

Core checks, undo/redo, pending-annotation rebasing, and read-only copy diagnostics passed in `assets/lead-final-1/result.json` and `assets/verify-1/final-focused/result.json`. These focused results do not establish that the full feature gates pass.

Source-only history measurement is in `assets/history-benchmark-1/results.json` and `assets/lead-history-benchmark-1/results.json`: 200 synthetic files / 32.77 MB compacted to 81 KB. This measures serialized history source size, not end-to-end runtime or storage.

Lead F4 and F5 passed (`assets/lead-f4-1/result.json`, `assets/lead-f5-1/result.json`). F7 failed only on a browser hover timeout (`assets/lead-f7-1/result.json`). F8 failed the denied-exit, denied-existing-error, denied-old-store, and denied-old-bytes cases, plus its runner's scan-409-busy condition (`assets/lead-f8-1/result.json`). The verifier's final F4 HTTP assertions failed while lead F4 passed; concurrent test-server port interference is a possibility, not a confirmed cause. Verifier F8 also failed in the runner. Do not report the feature as green.

`STATUS` and `PICKUP` now reopen F4/F7/F8 and record 13/22 passed; the older 16/22 claims are historical. F5 has current fresh-verifier evidence. Keep unresolved Checks pending/failed until their complete gates pass.

## Resume sequence

1. Inspect the verifier's immediate summary/report, then inspect current git diff and the relevant F7/F8 artifacts before changing code.
2. Resolve the F7 hover timeout and rerun the affected check alone. For F8, distinguish Windows chmod/permission assumptions from a product regression; rerun each denied case and the runner sequentially with fresh evidence.
3. Run required checks sequentially to avoid server/port interference. Keep the original failed evidence when correcting an obsolete decoder expectation. Do not run the whole suite as a shortcut.
4. Record passed checks and artifact paths in `docs/STATUS.md`; leave unresolved checks explicitly pending or failed. Do not claim a Check passed without running it.

Runtime: use `C:/Users/SLY2.0/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`, prepend `C:/ffmpeg/bin` to `PATH`, and set `PYTHONPATH` to `J:/slyOS/projects/photoLibrary/.qa/python-deps` (Playwright 1.49.1 is installed there). The default `.venv` Python currently fails with access denied.

The live app at port 8785 was last observed running older code with an active 551-file scan; it was not restarted. Coordinate before interrupting that scan. Optional AI and copy-phase work remain serialized; JSON source writes still grow with folder size. Standalone folder `index.html` remains deferred per the existing F4 scope.

## Fresh verifier report (2026-10-18)

The verifier completed its final run; no more tests are queued. `assets/verify-1/final-focused/result.json` passed, and `assets/verify-1/final-f5/result.json` passed 66/66. Browser evidence in `assets/verify-1/browser-final-3/browser-result.json` passed 8/8: English and Chinese activity fields, 3/3 tiles painted, pause/resume, single-flight polling (max in-flight 1), and zero console, network, or HTTP errors. Screenshots are in that same directory; the verifier inspected them.

Remaining verifier results: `assets/verify-1/final-f4` failed 89/94 on HTTP nonempty-sources and busy-409 assertions after the copy fix; `assets/verify-1/final-f7` failed 79/80 only on the first-hover 8-second timeout; `assets/verify-1/final-f8` failed 22/23 because the next fixture server port was already in use. The first F8 restore scenario passed. These precise outcomes supersede the earlier verifier summary above; lead F4/F5 pass results and lead F7/F8 outcomes remain as recorded. The demo processes were stopped cleanly. No additional tests were started after the request to conserve usage.

## Suggested smaller-agent prompt

Read this HANDOFF and PLAN. Continue the existing uncommitted processing-feedback
work. First diagnose the F7 hover timeout using its saved artifacts. Then run F4
and F8 separately on fresh fixture roots to resolve port interference and Windows
permission assumptions. Preserve unrelated work. Use targeted checks and do not
restart the real library or run the whole suite. Update STATUS with actual
evidence, and commit only once the required gates pass.

