# Consistent progressive filter results — 2026-10-20

User steering supersedes the previous keep-old-grid behavior: every changed
person/filter/sort/clear empties the grid immediately, then draws current matches
in order as results arrive, on every repeat visit. Existing snapshots/evidence for
the prior browse-speed pass remain historical. Scope PRODUCT F7/F9/F11/F15 and
the new CONTRACTS `/api/items/stream` protocol; no new feature Check closure.

## Bounded implementation

1. Preserve current dirty files in `.qa/progressive-results-before/`. No original
   writes, storage migration, broad benchmark work, or dependency installation.
2. Service prepares lightweight metadata matches in exact sort order and computes
   final stacks from that result. For hidden unavailable items, precheck basic
   availability before stacks. Lazily project/yield the next browser item. Preserve
   normal JSON responses, query errors, entity/name/alias/transcript/rating behavior,
   search hints, and complete ordered payload/stack parity.
3. New NDJSON endpoint snapshots under the lock and streams outside it. Flush start,
   every item and completion. Catch midstream failure in the stream writer; never
   write a second response. Disconnect/cancellation stops further projection.
4. The page clears synchronously on user query changes, cancels older network,
   image and queued paint work, resets scroll to the start, and shows loading.
   Read stream incrementally with a streaming TextDecoder (split lines and Chinese
   text may cross chunks). Draw the first record promptly. Bounded batches yield
   to actual browser paints even if all records arrive in one network chunk/cache.
   Avoid a completion-time full re-render. Keep node/image reuse per arriving item.
   Same-query polling must not clear or replay the current grid. Only committed
   current records may drive selection/viewer navigation; do not prune selections
   prematurely on a same-query partial refresh. Per-person extras remain secondary.
5. No silent full-array fallback on the normal supported runtime. If endpoint is
   unavailable, expose failure with current origin; deployment must load the new
   backend before claiming the behavior is active.

## Focused verification

Fresh verifier, isolated synthetic fixtures, no real-disk scan. Save immutable
JSON and inspected screenshots under `assets/progressive-results/`.

- Real HTTP stream: deliberately slow per-item projection; read the first item
  before the final projection/completion. Normal JSON and streamed ordered payloads
  must match for sort/filter/stacks and unavailable policies. Invalid arguments,
  empty stream, midstream failure and disconnect are explicit.
- Real browser: person → clear → person repeated at least three times; each action
  immediately removes all old cells, first current record paints before done, and
  successive prefixes preserve requested ordering. Both slow-chunk and all-in-one
  cached responses yield intermediate paints. Final arrival must not blank/rebuild
  already-painted nodes. Test name/date/rating sorts, loading vs completed empty,
  stale delayed chunks/EOF/errors, split UTF-8/lines, same-query refresh stability,
  viewer/selection integrity and secondary person extras.
- Keep the previous viewport thumbnail scheduling and bounded cache/concurrency.
  Run existing narrow backend parity diagnostics if shared service code changes.
  No broad suite and no treating focused checks as full feature completion.

## Activation

Once verified, deliberately reload only this matching-root Library backend so the
new endpoint is actually available for this user request. First verify the runtime
root/PID and that no scan/inference/manual transaction is active; preserve persisted
data and pending work, keep the same port/root, and verify health/runtime/stream.
Do not update/pull code or touch another service. Record activation evidence and
any interruption limits; never claim a live deployment while old code is serving.
