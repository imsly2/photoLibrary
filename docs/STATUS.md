# Library — status

Spec baseline: 2026-10-12. This is a planning result, not a software release.

## True now

- Help file refined around Steve setting up a portable picture library for his
  mother-in-law to browse. No new product features added.
- [PRODUCT](PRODUCT.md) has F1–F22 and one Check each.
- [CONTRACTS](CONTRACTS.md), [UI-SPEC](UI-SPEC.md), [FIXTURES](FIXTURES.md),
  [SLICES](SLICES.md), and [AGENT-BUILD-MODE](AGENT-BUILD-MODE.md) specify the build.
- Six reference images exist; they are layout targets, not runtime evidence.
- No server, scanner, web page, fixture media, Python package or QA runner exists.
  No server was launched and no real photo disk was scanned for this task.

## Completion

**0 / 22 Checks = 0% tested.** The commands in the plan are future deliverables.
No implementation Check has been run; a reviewed specification is not a pass.

| Check | Feature | State | Verifier / revision / platform | Command / evidence |
|---|---|---|---|---|
| F1 | Two folders | pending | — | Not run; no artifact |
| F2 | Launch | pending | — | Not run; no artifact |
| F3 | CLI / HTTP | pending | — | Not run; no artifact |
| F4 | Add folder | pending | — | Not run; no artifact |
| F5 | Scan | pending | — | Not run; no artifact |
| F6 | Metadata | pending | — | Not run; no artifact |
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
