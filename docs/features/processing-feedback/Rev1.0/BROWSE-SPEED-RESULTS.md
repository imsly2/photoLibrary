# Browse speed — 2026-10-20

Implemented within PRODUCT F7/F9/F11/F15. No stack or storage migration. No live
restart, real-disk scan, original write, or new feature Check closure. Existing
unrelated working-tree edits were preserved; these changes remain uncommitted.

## What changed

`library/web/assets/library.js` now starts the item request immediately, paints
its result independently of settings/sources/People/Tags, and derives groups from
those exact items. Changed queries abort/supersede older requests; obsolete success,
error and cleanup paths cannot replace current results. Same-query reloads remain
single-flight with one coalesced followup. Delayed settings cannot overwrite newer
user edits, and sort fetching no longer waits for settings persistence.

Grid lookup uses an id-to-array-index map. Thumbnail scheduling reads each cell's
rectangle once, prioritizes the current viewport, prefetches up to 64 nearby cells,
and recalculates on scroll/resize/collapse. Obsolete image sources are cancelled
before their slots are released. Changed filters and the open viewer free image
connections immediately. Up to 256 painted tile nodes are retained across filters,
including empty results; reused cells refresh badges and metadata. Local entity
groups use Python-compatible Unicode casefold/codepoint ordering.

`library/catalog_io.py`, `library/read_cache.py`, and `library/service.py` now match
stored metadata before projecting full browser records and checking original paths.
Each distinct referenced entity resolves once per response. Only matches receive
filesystem projection. Cache identity includes library root, raw object identity
and favorite state; the raw object is retained to prevent recycled-id collisions.
Entity names refresh on each query and stack decoration gets a separate response
dict, so cached results cannot carry another query's stack membership.

## Evidence

- Fresh independent browser verification: **22/22**, [result](assets/browse-speed/2026-10-20T14-04-08-723Z-after/result.json).
  Screenshots in that folder were inspected by verifier and lead. With all
  ancillary reads delayed 1.8 seconds, at 650 ms the page has 240 items / 84 painted
  thumbnails; [baseline](assets/browse-speed/2026-10-20T13-59-41-723Z-before/result.json)
  has 0 / 0. A new filter behind stalled images reaches the server in 8 ms and
  paints its three matches within 350 ms. Filter/clear retains the same painted
  cell and image nodes, including after an empty result. Sampled outstanding image
  reads stay at 12. Raw protocol events briefly overlap at 23 during cancellation;
  the raw trace is retained, not reported as a strict instantaneous network cap.
- Fresh independent backend verification: **60/60**, including 32 ordered full
  response comparisons, [result](assets/browse-speed/backend-synthetic-20261020T140547861113Z.json).
  Lead independently reran **60/60**:
  [result](assets/browse-speed/backend-synthetic-20261020T140606362931Z.json).
- Existing 400-photo scratch catalog, view-cache misses, same 13-query matrix:
  **13/13 complete payload hashes unchanged**, stable across three iterations.
  [Before](assets/browse-speed/query-before.json),
  [implementer after](assets/browse-speed/query-after.json),
  [independent lead timings](assets/browse-speed/query-lead-summary.json).
  Parent and implementer initially used the same after filename; the lead summary
  explicitly preserves the separate parent tool output instead of claiming two
  immutable runs at that shared path.
- Unicode group ordering: **992 cases match Python**,
  [lead result](assets/browse-speed/unicode-groups-lead.json). JavaScript syntax and
  changed Python module compilation also passed.

| Scratch query | Before | Lead after | Full browser projections before → after |
|---|---:|---:|---:|
| Empty tag | 242 ms | 46 ms | 400 → 0 |
| Person (2 matches) | 241 ms | 40 ms | 400 → 2 |
| Tag (4 matches) | 247 ms | 39 ms | 400 → 4 |
| Filename (1 match) | 315 ms | 41 ms | 400 → 1 |
| All, date sort | 242 ms | 153 ms | 400 → 400 |
| All, name sort | 234 ms | 102 ms | 400 → 400 |

Entity JSON opens fall from 873 to 140 distinct entities per query. These are
small scratch measurements, not a live-library end-to-end speed guarantee. The
read-only live observation is [live-before](assets/browse-speed/live-before.json).

## Indexing decision and limits

The current SQLite file stores basic item/source fields for rebuild parity; it
does not serve interactive searches. Filtering still scans cached metadata in
memory. The measured avoidable costs were repeated filesystem projection, duplicate
queries, quadratic frontend lookup, and loading work for obsolete/offscreen views.
There is no evidence here requiring a framework rewrite or a JSON storage migration.

The item response is still one complete JSON array. This work makes thumbnails and
independent UI sections progressive; it does not add streamed result metadata,
pagination, full-text SQLite search, or DOM virtualization. Those are separate next
steps if larger-catalog measurements show metadata/DOM work remaining on the
critical path. A future read index should stay disposable and preserve exact
Unicode/name/alias/substring/transcript/filter/sort semantics after edits and rebuild.

Browser fixtures use synthetic media. Existing scratch queries do not rewrite
photos. Full video hover/playback, the full feature Checks, cold physical-disk
behavior, and the changed code in the running live backend were not graded. No
additional feature is marked passed. Frontend changes load on browser refresh;
backend changes load on the next deliberate Library restart per the active handoff.

Repro commands: `node .qa/browse-speed-verify/verify.cjs after` and bundled Python
`.qa/browse-speed-verify/backend_verify.py`. The scratch matrix and preserved
pre-edit source files are under `.qa/browse-speed-before/`. The PLAN is
[BROWSE-SPEED-PLAN.md](BROWSE-SPEED-PLAN.md). Retain failed and intermediate evidence.
