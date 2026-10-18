# Scale verification plan — 2026-10-18

User requests independent verification of Cursor speed claims against a larger workload. Scope is F7 performance measurement, not storage migration or broad product optimization.

1. Preserve and finish the existing uncommitted benchmark edit in place. Repair stale RunState attribute references and reading-metric arguments, wire intended diagnostics, preserve prior work.
2. Use a unique resolved scratch directory below repo .qa/bench for each run; check containment before cleanup. Never modify original media or production library-data/server. Record fixture SHA256/size/path manifest and app revision/dirty diff identity.
3. Define renditions complete only when every expected item/slot is ready or contractually not-applicable; errors are explicit failures, never successful completion. Retain separate queue-terminal vs successful completion if useful. Verify derivative files nonempty at completion.
4. Report portable mirror completion separately and honestly, including timeout and matched/expected counts. Do not claim fully portable until records match. Keep AI completion separate/excluded; record available queues and final queue state. Do not install models.
5. Preserve F7 budgets; no weakening thresholds. Validate metric serialization with focused inexpensive tests before long run. Add API failure/sample counts so successful requests alone cannot disguise failures.
6. Fresh verifier runs one 400 JPEG + 1 MOV test with UI cadence, retaining immutable JSON/logs and exact composition. If insufficient JPEGs, use maximum available and record deviation. Run only one test at a time. Inspect result and surviving outputs, compare normalized 80-photo prior report with stated limitations. No broad suite, no production restart, no old-revision benchmark without a known-good baseline identity.
7. Lead audits artifacts, writes conclusions in STATUS and scale report. This diagnostic does not close F7 or other feature Checks. Product fixes follow measured evidence in a subsequent bounded slice.
