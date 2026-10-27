# Browse speed regression floor — 2026-10-20

Frozen measurement of the **current working tree** on the existing 400-photo
scratch catalog. Future filter or query work compares against this file.
A slower median, a changed payload hash, or a higher disk-read count is a
regression. This is not a live-library guarantee and it does not close a
feature Check.

## What this measures

In-process `items_from_snapshot` on `.qa/ui-400/library-data` (400 items).
Each query is warmed once, then timed three times with the view cache
cleared. The median of those three is the number. Payload identity is the
SHA-256 of the ordered JSON. Entity JSON opens and browser projections are
counted on the last sample.

The scratch catalog is read-only. Do not point this harness at `library-data`.

Rerun, from the repo root:

```text
.venv\Scripts\python.exe .qa\browse-speed-before\query_bench.py regression-floor
```

Any label other than `before` loads the current `library` package and writes
`assets/browse-speed/query-<label>.json`, with a `parity` map against
[query-before.json](assets/browse-speed/query-before.json). `before` loads the
preserved pre-edit copy under `.qa/browse-speed-before/` and must not be
overwritten.

## Floor (2026-10-20, current tree)

Artifact: [query-regression-floor.json](assets/browse-speed/query-regression-floor.json).

All 13 payload hashes match the pre-speed-fix baseline. Every query is
stable across its three timed samples. Entity opens are 140 (was 873).
Selective filters project only the matches (was 400 projections even for
an empty result).

| Query | Before | Floor now | Count | Projections before → now |
|---|---:|---:|---:|---:|
| Tag (4 matches) | 247 ms | 41 ms | 4 | 400 → 4 |
| Person (2 matches) | 241 ms | 41 ms | 2 | 400 → 2 |
| Filename (1 match) | 315 ms | 39 ms | 1 | 400 → 1 |
| Empty tag | 242 ms | 39 ms | 0 | 400 → 0 |
| Chinese, no match | 245 ms | 41 ms | 0 | 400 → 0 |
| Favorites (none) | 246 ms | 41 ms | 0 | 400 → 0 |
| Date search (2024) | 271 ms | 74 ms | 188 | 400 → 188 |
| All, name sort | 234 ms | 89 ms | 400 | 400 → 400 |
| All, rating sort | 297 ms | 90 ms | 400 | 400 → 400 |
| All, location sort | 241 ms | 89 ms | 400 | 400 → 400 |
| Four stars | 294 ms | 88 ms | 400 | 400 → 400 |
| Recent | 257 ms | 85 ms | 400 | 400 → 400 |
| All, date sort | 242 ms | 95 ms | 400 | 400 → 400 |

Milliseconds are rounded from the artifact medians. Compare new runs to the
JSON, not to this rounded table. Machine noise of a few milliseconds is
expected; a return toward the Before column is not.

History, same catalog and same hashes:

- [query-before.json](assets/browse-speed/query-before.json) — pre-fix tree
- [query-lead-summary.json](assets/browse-speed/query-lead-summary.json) — after the metadata-before-disk fix
- [query-progressive-lead.json](assets/browse-speed/query-progressive-lead.json) — after streamed results were added

## What else already passed, and what it is not

Browse-speed behavior checks (synthetic browser, not this latency floor):
22/22 in
[2026-10-20T14-04-08-723Z-after](assets/browse-speed/2026-10-20T14-04-08-723Z-after/result.json).
Backend predicate parity: 60/60 in
[backend-synthetic-20261020T140606362931Z.json](assets/browse-speed/backend-synthetic-20261020T140606362931Z.json).
Narrative: [BROWSE-SPEED-RESULTS.md](BROWSE-SPEED-RESULTS.md).

Streamed results, still on this tree: browser 106/106 in
[2026-10-20T14-35-37-367Z-after](assets/progressive-results/2026-10-20T14-35-37-367Z-after/result.json);
HTTP 31/31 in
[backend-http-20261020T143238184538Z.json](assets/progressive-results/backend-http-20261020T143238184538Z.json).
Plan: [PROGRESSIVE-RESULTS-PLAN.md](PROGRESSIVE-RESULTS-PLAN.md).

The live Library process was **not** restarted. Refresh picks up
`library.js`. `/api/items/stream` is in the working tree and is not served
until that matching-root process is deliberately reloaded. No activation
JSON exists. Do not treat the running server as this floor.
