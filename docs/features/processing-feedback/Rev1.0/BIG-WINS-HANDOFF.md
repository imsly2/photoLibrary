# Big performance opportunities — active Cursor handoff

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

- Paired still generation: implementer being assigned; no product change yet.
- Rating lock: pending.
- Worker pool: deferred.
- Storage naming/layout: separate open proposal, no migration.
- Live server: leave running; fixes require a later deliberate restart to take effect.

## Cursor pickup

Read this file, git status/log, then the implementation/verification evidence appended below. Preserve unrelated untracked logs and prior artifacts. Continue the first incomplete opportunity; do not restart the broad benchmark repair project. Measure one small comparable batch and focus on the largest remaining cost. Be candid about gains, regressions and incomplete checks.

## Larger baseline now completed

The valid400 JPEG+1 MOV run finished before product edits: first thumbnail0.391s, scanDone29.422s, all grid109.625s, selected preview0.844s, all rendition files285.953s. 803 outputs nonempty, no rendition errors, no API failures. Eight of nine printed budgets passed; bookkeeping estimate259.704ms/job failed50ms. This estimate subtracts sampled FFmpeg costs from observed publication intervals; it is not direct stage profiling. Portable mirror failed to catch up in10s (400 records, final diagnostic228/401 matching); AI still unfinished/unavailable in scratch. Do not equate previews done with Processing done or portable data complete. Artifact: assets/perf-bench/bench-20261018-073207-rev1-scale-400-22850.json. Relative to the earlier80 run, 5x items took4.96x preview time: no clear superlinear preview collapse in this test, but the absolute cost is still substantial. Different revision/harness and filesystem caches limit that comparison.
