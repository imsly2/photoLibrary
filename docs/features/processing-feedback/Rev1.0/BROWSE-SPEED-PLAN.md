# Browse responsiveness — 2026-10-20

Scope: existing PRODUCT F7/F9/F11/F15. Preserve the dirty working tree and running
live server. No original writes, scans, storage migration, new settings, or new
feature Check closure. Apply the active handoff's small bounded implementation /
fresh focused verification workflow; do not run broad acceptance suites.

## First slice

- Replace repeated linear item lookup in grid hot paths with an id map, kept in
  sync for item replacement and multi-person leftover records.
- Paint `/api/items` immediately, independently of sources/settings/sidebar and
  optional leftover requests. Derive groups from exactly those items; remove the
  redundant `/api/groups` round trip from this page.
- A changed query supersedes the previous request immediately; abort obsolete
  fetches where possible and guard all async result/error/cleanup paths by request
  identity. Same-query polling stays single-flight and coalesced.
- Schedule grid image reads by the current viewport plus a bounded nearby margin.
  Reprioritize on scroll/resize, cancel detached/obsolete jobs, keep concurrency
  bounded, and avoid a stalled retry multiplying still requests.
- Keep a bounded cache of painted tile nodes across filters, refreshing metadata,
  URL and badges when reused. Preserve video hover and viewer semantics.

## Focused verification

Use synthetic fixture API responses in a real headless browser or an existing
scratch library; never restart the live application. Capture before/after where
comparable and save immutable JSON plus a screenshot under assets/browse-speed/.
Verify first grid paints while ancillary reads are delayed, rapid filter reversal
cannot flash/commit stale results, multi-person extras arrive independently,
clearing filters reuses painted cells, newly visible images overtake offscreen
work, collapsed sections do not request images, failures retain the last grid,
bounded still concurrency/retry, and sort/group membership and viewer navigation
remain correct. Inspect screenshots and console/request errors. Focused evidence
does not close the full feature Checks.

## Query/index investigation

SQLite currently stores basic item identity fields for rebuild parity; interactive
search uses cached JSON item records and Python predicates, then sorts the result.
Measure request work before changing storage or replacing the stack. If significant
server cost remains after the frontend fix, optimize the measured read/filter path
in a second bounded slice and preserve entity rename, annotations, favorites,
rating, offline availability, JSON rebuild and query semantics.

Measured on the existing 400-item scratch library (no original changes): an empty
tag query after the two-second view-cache expiry spends 0.569 s in projection,
including 873 repeated entity JSON opens and 2,874 filesystem stats. The cold
projection was 1.853 s. The live HTTP observation (750 items) is recorded in
assets/browse-speed/live-before.json; it is observational, not an A/B benchmark.

## Second slice: metadata before filesystem projection

After the frontend implementation, resolve each distinct referenced entity only
once per item-query response. Match stored metadata, current entity names/aliases,
favorites, recent ids and effective ratings before computing original availability,
last-known path facts, and full browser reads. Only survivors need those filesystem
checks. Keep the same predicates, search hints, exact sort order and stack behavior;
unavailable visibility is still checked on survivors. Avoid a new long-lived query
cache or database schema in this slice. Entity renames and annotations must remain
visible, and favorite / root / item changes must not reuse an unrelated view.

Focused proof: identical ordered responses to baseline for date/name/location/
rating sorts; person AND, thing AND, place OR, source, favorite/recent, rating,
English/Chinese labels/names, filename/date/transcript and unavailable filters.
Use small synthetic records for correctness and the existing scratch catalog for
before/after latency and disk-read counts. Assert an empty selective filter does
not perform per-item availability projection, and a shared entity is loaded once
per query. This does not change the authoritative JSON/disposable SQLite contract.
