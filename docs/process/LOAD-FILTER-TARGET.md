# Load and filter: the target

Steve, 2026-11-06: loading pictures and filtering them should be as fast
as this PC allows. Nothing in the current design is a requirement.

This file holds three things: what was measured on the live library,
the structure that gets there, and the benchmark that says whether a
change made it better or worse. How the page works today, line by line,
is [LOADING-PIPELINE.md](LOADING-PIPELINE.md). The implementation prompt
is [LOAD-FILTER-IMPLEMENT-HANDOFF.md](LOAD-FILTER-IMPLEMENT-HANDOFF.md).

## The library this is judged on

- The live library at [http://127.0.0.1:8785/](http://127.0.0.1:8785/),
  root `library-data/`, 28,135 pictures. It includes
  `K:\Photos\Iphone 2017-2026.10`, about 15,000 originals (116 GB) with
  38,000 sidecar files in `.library` folders.
- PC: i7-8700K (6 cores, 12 threads), 32 GB RAM. `K:` is a SATA SSD in a
  USB enclosure. `J:` is an NVMe in a USB enclosure. Python 3.13, numpy
  2.5 in `.venv`.
- A small test catalog can look fine while this one is slow. The
  benchmark refuses to run under 25,000 pictures.

## What was measured, 2026-11-06

All numbers are from the live server, read-only.

| What | Result |
|---|---|
| Full list, server alone | 28,135 rows, 57 MB, 2 KB per row, 8.5 s; first row at 0.7 s |
| Full list, with only the fields filters need | 2.1 MB (0.67 MB gzip), built in 0.17 s |
| Page count in a browser tab | 11,449 of 28,135 after 65 s; main thread 80% idle. Headless Edge: 267 s to know the count |
| One thumb, server idle | 2.3 ms median; 300 thumbs over 6 connections in 0.41 s |
| Catalog lock, idle library | held 6 to 11 s, every 30 s |
| People suggestions, one call | 230 to 264 s live; pure Python estimate 283 s; numpy 0.15 s |
| Server cold start, record load | 14.2 s for 28k record files |
| Chip click in memory | grid repaints in about 60 ms; no stream |

What those numbers mean:

1. **People suggestions holds Python's lock for minutes.** Every page
   open calls `loadPeople`, then `/api/people/suggestions`. That compares
   every pair of 1,631 face centroids (1.33 million pairs) in Python
   loops (`library/people_suggest.py`). It came in on 2026-10-16. The
   cost grows with the square of the number of people, so it got worse
   as Faces ran. This is the most likely cause of "it was instant, then
   it regressed." While it runs, the server sits at 100% of one core and
   the catalog stream and thumbnails wait.
2. **The missing-file sweep holds the catalog lock.**
   `requeue_missing_renditions` (`library/renditions.py`) runs every 30 s
   in the drain thread under the catalog lock. For each of 38,512
   renditions it reloads and resolves the source record: 115,000 `stat`
   calls and 77,000 path resolutions, with nothing cached between items.
   Any request that needs the lock in that window waits 6 to 11 s.
3. **The page cannot take the list in fast.** `readItemStream` commits
   24 rows, then waits for an animation frame and a timer. 28,135 rows
   need about 1,170 frames, at least about 19.5 s at 60 Hz even with an
   instant server. In a hidden tab, frames stop and so does the count.
4. **Most of the list is weight.** Each row is a full item view: paths,
   locations, metadata, renditions. Filtering and the grid need about a
   tenth of it.
5. **Blank tiles that never fill.** The 42-tile Favorites strip never
   gets an image `src`, while the status line says every thumbnail is on
   screen. This bug alone keeps every click from settling.
6. **Search clears the grid on every keystroke.** The `input` handler
   calls `clearCatalogForQuery` before its debounce.
7. **A video original is read whole to answer a range request.**
   `_send_media` reads the file into memory, then slices. The sample row
   was a 2.4 GB MOV.

Correction to the first advice: it said `/api/people` had not answered
after 11 minutes. That came from the browser's resource-timing buffer,
which was full. The benchmark measures `/api/people` directly: about
11 s, with the People panel filling about 6 s after open.

## The structure that gets there

The outcome, not a locked mechanism. The implementing agent owns the
design and may beat it.

1. **One compact catalog index, fetched once.** It holds only what
   filters, sort, grouping, and the grid need. Its address carries a
   catalog version, so the browser can cache it, and a change fetches
   only the rows that changed. The full record for one picture is
   fetched when its preview or inspector opens.
2. **Every filter, sort, group, and search happens in the page.** At
   28k items each is a few milliseconds. The server never answers a
   filter query, so no click waits on a list, and every control takes
   the same path.
3. **A filter changes the order of ids, not the grid.** Tiles are keyed
   by picture and reused when they survive the filter. No click clears
   the grid.
4. **A thumbnail fetched once is never fetched again.** Each thumb
   address names its version and is cached for good. A tile that comes
   back shows from browser memory. A whole screen of thumbs may arrive
   in one request.
5. **Processing cannot stall browsing.** Encoding, faces, suggestions,
   scans, and sweeps run where they cannot hold the lock or the Python
   interpreter that browsing needs. A separate process is the obvious
   shape.
6. **Cold start reads one index file.** The per-folder records stay the
   source of truth for F23. The index is a rebuildable copy.

What that throws out:

- The NDJSON stream and its frame-paced reader.
- Server-side filter queries, and the two paths in `loadCatalog`: the
  remembered wide list and the rule about whether its records carry
  people.
- `releaseGrid` and `clearCatalogForQuery` on a filter, sort, or search.
- The full item view per row.
- `private, no-cache` on files that never change.
- The 1,024-tile painted-cell map.
- The catalog lock as the coordinator for rendition threads, and the
  30-second sweep. Check for a missing file when a request finds it
  missing.
- Suggestions on page open. Compute them with vector math, cache them by
  face-index version, and only for the Review matches wizard.
- Reading a whole file to serve a range.

## What stays slow after that, and why

| Still slow | Why | Limit or structure |
|---|---|---|
| Thumbs the browser has never seen | 100 to 300 small files a screen at 1 to 2 ms each, plus about 1 ms decode each | Disk and decode. Near the floor |
| Very fast scrolling across 28k | Decoding new images | Decode. A tiny thumb for every picture, about 40 MB cached, is the way past it |
| New imports | HEIC decode and encode on the CPU | CPU. Browsing should not feel it |
| Rebuilding the index from nothing | About 14 s to read 28k files over USB | Disk. Should be rare |
| Six connections per host | HTTP/1.1 in Chromium | Browser. Caching and batched thumbs avoid it |

The disk is not the bottleneck today, even over USB. Python's lock is a
limit only when heavy work shares the process with browsing.

## The benchmark

One command, read-only against the running server. It refuses to run on
fewer than 25,000 pictures.

```
cd J:\slyOS\projects\photoLibrary
.\.venv\Scripts\python.exe -m tests.perf.live_load_filter            # full run, compare to baseline
.\.venv\Scripts\python.exe -m tests.perf.live_load_filter --quick    # about 8 min, skips the slow probes
.\.venv\Scripts\python.exe -m tests.perf.live_load_filter --save-baseline
```

- Code: `tests/perf/live_load_filter.py` (runner and server probes) and
  `tests/perf/live_load_filter.cjs` (headless Edge, 1600x900, Playwright).
  Goal numbers: `tests/perf/live_targets.json`.
- Each run writes `docs/process/assets/load-filter/runs/<stamp>.json`
  and a `.md` table: metric, baseline, now, change, target.
- Baseline: `docs/process/assets/load-filter/baseline.json`, the
  2026-11-06 run on the tree before any of this work.
- Exit 0 means no primary metric got worse. Exit 1 means one did: more
  than 25% worse and past a small absolute slack (50 ms, 0.25 s,
  2 tiles or requests). Exit 2 means it could not run.
- The browser never writes. Non-GET requests are answered inside the
  browser, so sort and settings never reach the server.
- Close other Library tabs first. The run records how many other
  connections were open, because a second tab changes the numbers.
- Before you compare, restart the server on the tree you want to
  measure. The running server is what gets measured, not the files on
  disk.
- After a redesign, keep the page hooks or update them in one place:
  `PAGE` at the top of the `.cjs`, and the route constants at the top of
  the `.py`. The count is known when `#grid` has
  `data-catalog-state="done"`, or else when `#library-chrome` shows
  "N pictures" without "still counting". A probe whose route is gone
  reports `absent`, not a pass.

### Every test it runs

Lower is better for every metric. Primary metrics decide the exit code.

| Test | What it does | Metrics |
|---|---|---|
| Preflight | Server up, other open connections, git revision, queue states | recorded only |
| Catalog | Fetch the full list the way the page does today, alone | `server.catalog.firstRowMs`, `totalSec`, `bytes` (primary) |
| Idle small requests | `/api/settings` twice a second for 65 s. It takes the catalog lock, so a lock hog shows as a slow sample | `server.settingsIdle.maxMs` (primary), `p90Ms` |
| Thumbs | 100 thumbs one at a time; the same 100 with `If-None-Match`; 300 over 6 connections; 300 over 5 connections while a full list downloads | `server.thumbs.serial200.p95Ms` (primary), `serial304.p95Ms`, `parallel300Sec`, `duringCatalog.p95Ms` (primary) |
| People | `/api/people` | `server.people.sec` (primary) |
| Server filter queries | Largest person, search `2019`, Recently added, sort by name, through the list route. Diagnostic: the target design has no such route | `server.filters.*.totalSec` |
| Suggestions | `/api/people/suggestions`, once | `server.suggestions.sec` (primary) |
| Internals | A fresh process: cold record load, the sweep's path build, suggestion math in Python against numpy. Each part reports `absent` once its code is gone | `internals.coldRecordLoad.sec`, `missingSweep.lockedBuildSec`, `suggestionMath.pythonEstimateSec` |
| Browser open | Open the page: first tile, first painted thumb, first full screen, count known, People rows, unpainted tiles at the end, long tasks, frame gaps | `browser.open.*`; time limit 600 s full, 300 s quick |
| Browser clicks | Photos, All, Videos, All, With people, Clear, largest person, Clear, search `2019`, Clear, sort other, sort back. Each is timed frame by frame inside the page. A step that never settles counts as 20,000 ms | `browser.click.<step>.readyMs` and `settledMs` (primary), `settledIgnoringNoSrcMs`, `maxBlank`, `redownloads` (primary), `catalogRequests` |
| Health during browser | `/api/health` 20 times a second for the whole browser run. It takes no lock, so a stall here means the Python interpreter itself is busy | `server.healthDuringBrowser.maxMs` (primary), `p99Ms`, `over1000` |

Definitions:

- **ready**: the count is known and the grid shows tiles.
- **settled**: every visible tile shows its picture, the Favorites strip
  included.
- **redownloads**: thumbnail requests, 304s included, for pictures that
  were already painted earlier in the run.
- **maxBlank**: the most visible tiles without a picture at once after
  ready.

### Goal numbers

From `tests/perf/live_targets.json`. A run says met or miss for each.

| Metric | Goal |
|---|---|
| Open to first painted thumb | 500 ms |
| Open to count known | 1,000 ms |
| Open to first screen fully painted | 1,500 ms |
| Open to People rows | 1,500 ms |
| Visible tiles still blank at the end of open | 0 |
| Any click, ready | 100 ms |
| Any click, settled | 250 ms |
| Any click, redownloads | 0 |
| `/api/health` worst sample during the browser run | 100 ms |
| `/api/settings` worst sample on an idle library | 100 ms |
| Bytes the page needs before it knows the list | 5 MB |
| One thumb, p95, idle and while a list downloads | 20 ms and 30 ms |
| `/api/people` | 0.5 s |
| Suggestions | 1 s |

Baseline table from 2026-11-06:
[baseline.md](assets/load-filter/baseline.md). It was taken on git
`a1bf370` plus the uncommitted tree that the live server was running.
Processing was paused except thumbnails, which had finished. Four other
connections were open: Steve's Chrome tab and an agent tab that was
closed during the run. Headlines from that run:

- Open: first painted thumb 2.2 s, count known 291 s, People rows
  2.9 s. 42 tiles were still blank at the end: the Favorites strip.
- Chip clicks and clears were ready in 36 to 113 ms. Apart from Videos,
  none settled within 20 s, because of the Favorites strip. Without it
  they settle in 56 to 527 ms (`settledIgnoringNoSrcMs`).
- Search `2019` and sort by name showed nothing within 20 s.
- `/api/settings` on an idle library: worst sample 11.2 s, the sweep.
  `/api/health` during the browser run: worst 530 ms.
- Suggestions: 202 s. The full list: 58 MB.
