# Library — status

Spec baseline: 2026-10-12. This is a planning result, not a software release.

## True now

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
  Check. F7 stays open until S06. F10 stays open until S09.
- S04 / M1 is green: Add folder (linked), four zoom levels, date/location/name
  sort, and open one still. Closes F9 and F11. F10 browse subset is present
  but the Check stays open until S09.
- S05 is green: copy onto this drive, collisions, interrupt resume, convert a
  linked source, move the library, undo leaves bytes. Closes F1 and F4.
  F9 and F11 stayed green after S05.
- Help file refined around Steve setting up a portable picture library for his
  mother-in-law to browse. No new product features added.
- [PRODUCT](PRODUCT.md) has F1–F22 and one Check each.
- [CONTRACTS](CONTRACTS.md), [UI-SPEC](UI-SPEC.md), [FIXTURES](FIXTURES.md),
  [SLICES](SLICES.md), and [AGENT-BUILD-MODE](AGENT-BUILD-MODE.md) specify the build.
- Six reference images exist; they are layout targets, not runtime evidence.

## Completion

**5 / 22 Checks = 22.7% tested.** F1, F4, F6, F9, and F11 have fresh-verifier artifacts.
M1 browse is recorded. The other commands remain pending.

| Check | Feature | State | Verifier / revision / platform | Command / evidence |
|---|---|---|---|---|
| F1 | Two folders | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `244771d` | `python -m tests.qa check F1` [verify-1](features/S05/Rev1.0/assets/verify-1/f1/result.json); orchestrator rerun [f1](features/S05/Rev1.0/assets/orchestrator-rerun/f1/result.json) |
| F2 | Launch | pending | — | Not run; no artifact |
| F3 | CLI / HTTP | pending | — | Not run; no artifact |
| F4 | Add folder | passed | Grok 4.7 verifier, Linux, Python 3.12.3, `244771d` | `python -m tests.qa check F4` [verify-1](features/S05/Rev1.0/assets/verify-1/f4/result.json); orchestrator rerun [f4](features/S05/Rev1.0/assets/orchestrator-rerun/f4/result.json) |
| F5 | Scan | pending | — | Not run; no artifact |
| F6 | Metadata | passed | Grok 4.7 verifier, Windows, Python 3.12.10 | `python -m tests.qa check F6` [verify-2](features/S02/Rev1.0/assets/verify-2/f6/result.json); orchestrator rerun [f6](features/S02/Rev1.0/assets/orchestrator-rerun/f6/result.json) |
| F7 | Previews | pending | — | Not run; no artifact |
| F8 | Preview storage | pending | — | Not run; no artifact |
| F9 | Zoom | passed | Grok 4.7 verifier, Linux, Python 3.12.3 | `python -m tests.qa check F9` [verify-1](features/S04/Rev1.0/assets/verify-1/f9/result.json); orchestrator rerun [f9](features/S04/Rev1.0/assets/orchestrator-rerun/f9/result.json) |
| F10 | Viewer | pending | — | Not run; no artifact |
| F11 | Sort | passed | Grok 4.7 verifier, Linux, Python 3.12.3 | `python -m tests.qa check F11` [verify-1](features/S04/Rev1.0/assets/verify-1/f11/result.json); orchestrator rerun [f11](features/S04/Rev1.0/assets/orchestrator-rerun/f11/result.json) |
| F12 | Globe | pending | — | Not run; no artifact |
| F13 | Tour | pending | — | Not run; no artifact |
| F14 | People / places / things | pending | — | Not run; no artifact |
| F15 | Search | pending | — | Not run; no artifact |
| F16 | Unavailable originals | pending | — | Not run; no artifact |
| F17 | Settings | pending | — | Not run; no artifact |
| F18 | Undo / Esc / clipboard / log | pending | — | Not run; no artifact |
| F19 | Live Photos | pending | — | Not run; no artifact |
| F20 | Rebuild | pending | — | Not run; no artifact |
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
