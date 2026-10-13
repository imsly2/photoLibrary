# Library — orchestrator handoff

2026-10-12. This document is the handoff for a later authorized build. The current
request ends with specifications. Do not start S00, launch the server, install
dependencies, or scan real pictures during this spec task.

## Read order

README/AGENTS → PRODUCT → CONTRACTS → UI-SPEC → FIXTURES → SLICES → STATUS.
Then read the shared [ORCHESTRATION](../../slyAI/shared/ORCHESTRATION.md),
[WORKING-ORDER](../../slyAI/shared/WORKING-ORDER.md),
[VERIFY-TOOLBOX](../../slyAI/shared/VERIFY-TOOLBOX.md), and
[WORKFLOW-MEMORY](../../slyAI/shared/WORKFLOW-MEMORY.md).
These links are relative from docs; the shared files are the existing workflow,
not permission to create a competing engine. PRODUCT defines scope; other specs
cannot silently expand it. Reference art is a target, never a passing artifact.

## One bounded loop

1. Pick the next SLICES row whose dependencies have verifier artifacts. Re-check
   working directory, Git prerequisite and any existing unrelated edits. Freeze
   that slice's feature ids, command gates and fixture manifest in its PLAN.
2. Spawn read-only recon with file:line map, current vs target behavior, applicable
   contract clauses, and exact gap list. Use the shared minimum-capable model rule.
   If Composer/Grok slugs are absent, use a supported worker and disclose the
   substitution; do not invent a model slug or become the coder.
3. Orchestrator resolves doc-only gaps before implementation. A missing field,
   error, fixture, setting or screen is a stop **for that slice**: record the gap
   in STATUS, edit the governing spec deliberately, then resume only after it is
   locked. Scope/taste forks go to at most one question, not implementer invention.
4. Spawn implementer with the slice PLAN, contract links, exact test assertions,
   “edit in place, no whole-file regeneration”, original safety rules, and required
   report of files/deviations. It may run diagnostics; it does not grade itself.
5. Spawn a **fresh verifier**, not the implementer. It may not edit product code or
   weaken tests/fixtures. It runs the slice and every closing Check, saves immutable
   evidence, opens screenshots, and returns pass/fail with paths. The orchestrator
   independently re-runs closing Checks and audits data/measurements/pixels.
6. Failure returns to a bounded correction implementer. Maximum **three correction
   loops after the initial attempt**, then stop with failure artifacts and what
   was tried. Do not take over the code, ask Steve to debug, or mark a failed Check
   green to unblock the queue.
7. When green, record evidence in STATUS, update packet notes/engine phase using
   the existing workflow where registered, and make one **local** commit named
   `slice(Snn): <result>`. Never push, rebase or amend somebody else's work.
   Keep earlier unrelated changes separate; never blindly checkpoint the workspace.
8. Continue by dependencies. Prepare M1, M2, and M3 evidence packets (screenshots,
   fixture URL, artifact paths) and continue without waiting for inspection.
   This 2026-10-13 execution policy replaces the earlier M1 pause: use the
   existing references and locked defaults. Stop for Steve only at a hard block
   or unresolved material product choice, and ask one taste question at M4.
   Do not pause the queue for that answer. Elapsed time and silence are not
   approval. Do not ask Steve to run acceptance scripts.

The orchestrator writes help/STATUS/PLAN, spawns workers, audits evidence and
commits. It does not write product code. During a docs-only refinement it may
author these specification documents directly, then use an independent doc audit.

## What counts as tested

The denominator is the **22 `**Check:**` paragraphs associated with F1–F22** in
PRODUCT. A complete Check covers its original example and its SLICES coverage
row/UI assertions. Multiple assertions/PNGs are still one Check. Intermediate
slice success is not feature credit. If a spec edit changes the denominator,
update STATUS and SLICES openly; never exclude difficult checks from the count.

STATUS rows record feature id, status (`pending|passed|failed|blocked`), verifier,
tested revision/platform, command, evidence path. Passed requires an existing
result artifact from a fresh verifier. Orchestrator re-run evidence is additional.
If later code invalidates a prior Check, mark it pending/failed until rerun; do not
leave stale green. Final S14 runs all Checks against one final revision and records
the aggregate manifest. Cross-platform launch evidence may be from that revision
on separate machines; unsupported environments are blocked, not skipped green.

Completion percentage = passed / 22 × 100. M1 expected 3/22; M2 13/22;
M3 15/22; final stop **22/22**. Report artifact paths and limitations, never a vibe
percentage. “Most functioning” can be described as capabilities at a milestone,
but cannot replace the requested whole-north-star percentage.

## Worker prompt shapes

Recon: “Read these specs and Snn. Return current file:line map, differences,
dependencies and missing contracts. Do not edit or scan non-fixture folders.”

Implement: “Implement only Snn against locked PLAN/CONTRACTS/UI-SPEC/FIXTURES.
Use fixture-owned temporary data. Preserve original bytes. Stop on unlisted fields,
errors, settings or screens. Report files, changes, diagnostics and deviations.
You are not the verifier.”

Verify: “You did not implement Snn. Do not repair code. Run its declared gates and
closing F Checks on fresh fixtures, inspect images, retain actual API/CLI outputs,
test negative/recovery paths, and report pass/fail with paths and revision. Missing
test cases are failures. No real disks, no treating mockups as screenshots.”

## Boundaries

No phone USB code, cloud hosting, accounts, image model, geocoder, remote photo
uploads, albums/favorites, photo editing, automatic original rearrangement, new
gestures, or user-facing debugging panels. Never scan a real photo disk under
this plan. Runtime libraries are agent choices inside the frozen behavior; no new
dependency that requires a changed user workflow without a contract edit.

Progress updates name what works, the evidence, and the next slice. A taste
question is reserved for M4 or a genuine blocker, with the fixture URL and
artifacts. At a block, name the blocked gate and the smallest next action,
with evidence. Do not hand Steve worker prompts to paste.
