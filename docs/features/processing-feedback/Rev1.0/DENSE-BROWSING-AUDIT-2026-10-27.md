# Dense browsing and intake audit — 2026-10-27

Scope: read-only review of the current working tree and existing measurements. No
feature Check was run or closed. The reported 10–15 seconds is the user's observation;
the particular device, network, and current workload have not been profiled here.
No listener on port 8785 was found during this review, so the running version and
end-to-end behavior could not be verified. Do not assume the pickup's earlier PID
or activation state is still current.

## Findings

1. **Viewport priority is incomplete.** `library.js` ranks visible image requests
   ahead of 24 nearby cells, but when the viewport changes it cancels active jobs
   only if the cell is disconnected or its URL changed. Old offscreen requests can
   occupy all 12 slots for up to 20 seconds. More importantly, the generator's
   wanted list is populated by the viewer, not by scrolling. Queued thumbnails
   are otherwise generated in catalog grid order. Thus download priority is not
   generation priority.
2. **Dense pending grids can miss readiness updates.** The once-per-second status
   poll takes only the first 80 intersecting IDs (intersection includes one viewport
   of margin). It does not rotate through the rest. A queued tile whose camera
   stand-in failed waits for its status to change; if it never enters the first 80,
   it can remain a placeholder even after generation until another refresh or
   viewport change. The 80-ID server limit needs batching or fair rotation, with
   visible tiles ahead of margin tiles.
3. **Ready thumbnails still have a costly per-image path.** Each URL is an
   individual HTTP request; the handler reads and parses that item's JSON, resolves
   the rendition and stats it, then reads the thumbnail. `private, no-cache` requires
   revalidation on reuse. The browser limits its own scheduler to 12, and the server
   uses HTTP/1.0 default `BaseHTTPRequestHandler` behavior. A 900-tile view means at
   least 75 scheduler waves even before connection, filesystem, network and decode
   costs. These are plausible costs, not a measurement attributing the user's delay.
4. **Filtering is not actually indexed or immediate.** A stream snapshots under
   the shared lock, then matches all catalog metadata, sorts, and computes stacks
   before sending even its start frame. Streaming accelerates later projection and
   painting but cannot bypass this upfront work. While scanning, the client also
   reloads the catalog every second; every arriving batch recomputes groups and
   updates grid/selection geometry. The earlier 400-item synthetic person filter
   measured about 41 ms, but this is not proof for a larger or busy live library.
5. **Face work is serial and deferred.** The drain waits for scanning and all
   rendition encoders to settle before face inference; it processes one photo per
   step with CPU-only ONNX and uses half the logical cores per session. Detection
   runs outside the shared lock, but clustering/publication runs inside it. Each
   step reads the face index and scans item order from the start; marking scanned
   rewrites the index. These are scaling and responsiveness risks needing profiling.
   Current still detection uses a 1920-pixel reduced frame and `single_window=True`;
   older tiled/full-resolution timings and the older combined-decode proposal do
   not measure the present algorithm or establish equivalent face recall.
6. **Intake has improved but remains separate from browse delivery.** The current
   scanner hashes and extracts metadata in one file read. A previous 40-file
   measurement reported 4.30 → 3.19 seconds for scanning, and 9.11 → 6.62 seconds
   for its preview drain; it is a historical small-sample result, not this user's
   current system or face throughput. Up to six rendition workers may compete for
   CPU and disk; more workers are not automatically faster or more responsive.

## Recommended order

1. Reproduce on the actual browsing device with a representative dense viewport.
   Record catalog size, device/network, processing stage, ready vs queued count,
   first paint and 50/90/100% visible paint after cold scroll, individual request
   latency/status and active slots, browser layout/decode time, and server disk,
   CPU and lock wait. Compare processing paused/running, cold/warm cache, and
   person-click-to-first-current-tile. Avoid recording personal images or names.
2. Fix viewport scheduling: cancel or demote stale offscreen in-flight requests,
   reserve slots for current visible tiles, batch/rotate status for every visible
   pending tile, and send a bounded, replaceable viewport hint to the generator.
   Viewer requests retain highest priority; debounce scroll hints, prevent stale
   clients from monopolizing the queue, and leave background progress fair. Test
   rapid scroll reversals, more than 80 pending cells, disconnected clients and
   multiple clients, plus pause/removal and existing source-safety rules.
3. Reduce cost of delivering ready thumbnails. Measure cached item lookup and
   safe versioned browser caching; use a real revision tied to rendition changes
   before allowing long-lived cache. Benchmark connection reuse and, if request and
   decode overhead remain dominant, bounded thumbnail batching/atlases or a
   smaller dense-grid derivative. Check stale replacement, relocation, offline
   previews, memory, quality and accessibility. A 900-tile first cold view cannot
   be promised instant without measuring network and device capacity.
4. For people clicks, instrument lock wait, snapshot, matching/sort/stacks, first
   stream byte and first tile. If upfront matching dominates, add a disposable
   person-to-item read index with the same AND, aliases, sort, stack and rebuild
   semantics, and avoid redundant scan-time full refreshes. If painting dominates,
   batch updates and virtualize offscreen cell DOM without breaking scroll anchor,
   grouping, selection or viewer navigation.
5. Profile present face detection, clustering, index reads/writes and lock holds on
   representative photos; measure recall as well as throughput. Consider batching
   index writes and a persistent work cursor first, then bounded concurrency or an
   available accelerated provider only after measuring contention and quality.
   If interleaving faces with rendition work, reserve browse capacity and preserve
   pause, rescan, revalidation and safe publication semantics.

Acceptance evidence should include the dense viewport on the intended device and
backend, repeated filter/clear, rapid scroll, queued-to-ready behavior beyond 80
tiles, and processing running versus paused. Record raw timings and correctness
artifacts; no existing feature Check is closed by this audit.
