# Library — status

Spec baseline: 2026-10-12. Pickup: [PICKUP.md](PICKUP.md).
Private remote: https://github.com/imsly2/photoLibrary `main`.
This is not a finished release.

## True now

- S00 is green: an empty fixture-owned library launches, persists the 16 default
  settings, reuses a matching-root server, refuses a foreign port without
  killing it, recovers a settings transaction, and undoes a settings change.
- S01 is green: a linked fixture folder scans in place, item ids match file
  bytes, a second scan adds nothing, originals are unchanged, and the embedded
  Live Photo pair is one item.
- F6 is closed: fixture dates follow EXIF, then filename, then modified time,
  and the three-JPEG set becomes two unnamed places 100 meters apart.
- Help file refined around Steve setting up a portable picture library for his
  mother-in-law to browse. No new product features added.
- [PRODUCT](PRODUCT.md) has F1–F22 and one Check each.
- [CONTRACTS](CONTRACTS.md), [UI-SPEC](UI-SPEC.md), [FIXTURES](FIXTURES.md),
  [SLICES](SLICES.md), and [AGENT-BUILD-MODE](AGENT-BUILD-MODE.md) specify the build.
- Six reference images exist; they are layout targets, not runtime evidence.
- On `main` at `9f6094c`: the Python server, linked scan, metadata, fixture
  media, and QA runner exist. The web page is still the empty-library shell.
  Rendition bytes are not implemented. No personal photo disk has been scanned.

## Completion

**1 / 22 Checks = 4.5% tested.** Only F6 has a fresh-verifier artifact.
The other commands remain pending.

| Check | Feature | State | Verifier / revision / platform | Command / evidence |
|---|---|---|---|---|
| F1 | Two folders | pending | — | Not run; no artifact |
| F2 | Launch | pending | — | Not run; no artifact |
| F3 | CLI / HTTP | pending | — | Not run; no artifact |
| F4 | Add folder | pending | — | Not run; no artifact |
| F5 | Scan | pending | — | Not run; no artifact |
| F6 | Metadata | passed | Grok 4.7 verifier, Windows, Python 3.12.10 | `python -m tests.qa check F6` [verify-2](features/S02/Rev1.0/assets/verify-2/f6/result.json); orchestrator rerun [f6](features/S02/Rev1.0/assets/orchestrator-rerun/f6/result.json) |
| F7 | Previews | pending | — | Not run; no artifact |
| F8 | Preview storage | pending | — | Not run; no artifact |
| F9 | Zoom | pending | — | Not run; no artifact |
| F10 | Viewer | pending | — | Not run; no artifact |
| F11 | Sort | pending | — | Not run; no artifact |
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
  Next action is the S03 implementation from that plan.
- 2026-10-13 — Pickup index added at [PICKUP.md](PICKUP.md). Steve authorized
  the private GitHub remote so a cloud clone can continue. Unpublished local
  S03 edits are not on `main` and are not the baseline.
