# Live dense browsing measurement — 2026-10-27

This is an incomplete performance iteration, not a feature Check. Live Library
on port 8785 was processing faces throughout. The tests did not modify media,
stop processing, or persist UI settings. `tests/perf/live_browse.cjs` launches a
fresh headless Edge on the server PC at 1600 × 900, samples loaded visible image
elements after animation frames, and clicks an actual People row and Name sort.
Non-GET requests are blocked. For the dense scroll, Dates is Off and Size is 36px
in that isolated page. It uses the existing live backend and overrides only the
browser script with the requested baseline or candidate. The sampling itself
walks the DOM and adds overhead; concurrent face work, streaming, selection of
the scroll position, cache state, and changing catalog contents add variability.
These are single observations, not controlled device-independent statistics.

| Scenario | Before | Retained code | Interpretation |
|---|---:|---:|---|
| Dense scroll, half visible | 8.06 s | 8.76 s | No demonstrated improvement |
| Dense scroll, all visible | 13.94 s, 576 tiles | 542/576 after 14.90 s | No demonstrated improvement |
| Person, half visible | 2.68 s | 9.03 s | Variable; no improvement shown |
| Person, all visible | 11.18 s, 451 tiles | 11.38 s, 486 tiles | Similar full-grid delay |
| Name sort, all visible | 15.59 s, 451 tiles | 20.93 s, 486 tiles | Variable; no improvement shown |

The result samples and all timestamps are in [baseline](assets/live-dense-before-v3.json)
and [retained code](assets/live-dense-final.json). During the retained-code run the
face queue increased from 2,192 to 2,205 completed in 70.7 seconds, including the
time spent running the browser test. This is an observed queue rate, not an
isolated face inference benchmark or a measured improvement.
In a separate roughly one-minute [observation](assets/live-face-observation.json)
after the browser benchmark stopped, the queue advanced by 33. The concurrent
run and the separate observation use different photos and system conditions;
they suggest contention is worth investigating but do not prove its cause.

Changes retained in the browser: status polling rotates through dense sets rather
than repeatedly asking for the first 80 IDs, and streaming reuses its layout map
instead of collecting all cells for every batch. Synthetic
[status proof](assets/viewport-dense-final.json) shows more than 80 IDs checked;
it also records that offscreen network requests remain a known gap. The existing
progressive browser suite passed 106/106 ([artifact](assets/progressive-results/2026-10-27T23-25-51-368Z-dense-final/result.json));
`tests.test_light_thumbs` passed 9/9. No full product Check was run.

An explicit fetch/abort experiment was removed after the live scroll loaded only
244 of 608 tiles in 15 seconds ([artifact](assets/live-dense-after-v4.json)). It
did abort the synthetic stalled requests, but its end-to-end result was worse; do
not claim a cancellation fix or a browsing speedup from it. The retained code
does not prioritize generation for the current viewport. Face processing was not
changed, and the people-filter backend was not changed.

Next: instrument per-request and server snapshot/matching/lock time without
exposing photo details; reduce ready-thumbnail delivery cost and retest on a
fixed dense viewport with repeated runs, then address person filter preparation
and face throughput with the same before/after discipline. The live server was
not restarted during active processing. Browser code is served from the working
tree on a page refresh; the raw live runs loaded their specified script directly.

## Where the time was going

Read-only timings on the live process (pid 42516, `tests.perf.serve_profile`,
root `library-data`, faces running, renditions idle at 15,207 done) and a
separate process that did not recover or write:

| Work | Live server, last samples | Same code, items already in memory, no face thread |
|---|---:|---:|
| Catalog prepare before the first streamed record | p50 16.6 s, max 31.7 s | 0.97 s for 14,608 items |
| One ready thumbnail, handler included | p50 10.5 ms | not remeasured outside the server |
| Face step | p50 955 ms | — |
| Face index read | p50 125 ms | — |
| Face index write | p50 322 ms | — |

The index file was 7.6 MB. Every photo re-read and rewrote it. That work held
the interpreter while the catalog scan waited, which is why a one-second
prepare became 16–32 seconds. Thumbnail generation was not the dense-scroll
cost: renditions were idle, and a ready thumb was about 10 ms. The earlier
scroll sample was also still in `loading` at 14.9 seconds, with animation
frames about 400 ms apart, so the page was still building the grid.

A read-only compare of the new prepare against the old full entity scan
matched id, stack id, and representative for date+hide-rejects (14,608),
name+hide-rejects (14,608), and one real person plus name sort (1,214).
Artifact: the command below, run against `library-data`. Standalone prepare
went from 0.96 s / 0.86 s / 0.42 s to 0.46 s / 0.46 s / 0.12 s. Projecting
every browser record afterward is still several seconds because each record
still checks the original file.

```text
.\.venv\Scripts\python.exe .qa\prepare_parity.py
```

## What changed

- Catalog prepare no longer builds entity records for every item on a
  date, name, or rating query. A person click matches face ids and names
  from the person files, then projects only the matches. Order and stacks
  matched the previous scan on the three queries above.
- The face index stays parsed in memory. The drain rewrites the file every
  24 photos or 3 seconds, and on pause, idle, and process exit. A crash can
  redo the photos not flushed yet. Clustering and the per-photo catalog
  record are unchanged. A manual write still hits disk immediately.
- Processing threads run below normal priority, same idea as the encoder
  processes.
- Thumbnail responses use HTTP/1.1 so the browser can reuse connections.
  The item stream still closes its connection.
- The grid asks the intersection observer which cells are on screen and
  which are within 240 px, and orders those by stream rank. It no longer
  reads every cell's position for that decision when the cells have ranks.

## Live browser, one run each

Same harness: `node tests/perf/live_browse.cjs <out> library/web/assets/library.js`.
Headless Edge on this PC, 1600×900, fresh cache, non-GET blocked, faces
running. One observation each. Not a tablet and not a repeated trial.

| | Earlier retained run | Client changes, old server | After one restart onto this code |
|---|---:|---:|---:|
| Open, first painted tile | 10.4 s | 12.4 s | 1.1 s |
| Dense scroll, half of 576 | 8.8 s | 5.9 s | 4.7 s |
| Dense scroll, all visible | 542/576 at 14.9 s, still loading | 576/576 at 10.5 s | 576/576 at 8.0 s |
| Person, first painted tile | 8.9 s | 20.3 s | 3.2 s |
| Name sort, first painted tile | 20.2 s | did not finish a full grid in 25 s | 0.8 s, then the grid kept growing |

Server-Timing on the restarted server: lock 158 ms, snapshot 132 ms,
prepare 376 ms, headers at 763 ms. In-process prepare samples after the
restart were p50 591 ms (was 16.6 s). Face index reads in those samples
were under 1 ms; writes were under 1 ms except the periodic flush. Face
step p50 663 ms (was 955 ms). During the 125 s browser run the face queue
moved from 5,972 done to 5,986 done. That is one observation while the
browser was also running, not an isolated face benchmark.

The restarted process is pid 57080, root
`J:\slyOS\projects\photoLibrary\library-data`, `http://127.0.0.1:8785/`.
The previous listener was pid 42516. It was stopped at 20:37 local and the
new process answered runtime about 14 seconds later. Faces were running
before (5,943 done, 8,662 pending) and after (5,955 done, 8,650 pending).
Renditions stayed idle. Refresh a tab that was open before the restart.

Raw artifacts:
[client-only](file:///J:/slyOS/projects/photoLibrary/docs/features/processing-feedback/Rev1.0/assets/live-dense-client-only.json),
[after restart](file:///J:/slyOS/projects/photoLibrary/docs/features/processing-feedback/Rev1.0/assets/live-dense-after-restart.json),
profile [before](file:///J:/slyOS/projects/photoLibrary/.qa/dense-live-profile.json) and
[after](file:///J:/slyOS/projects/photoLibrary/.qa/dense-live-profile-after.json).
The profile files are local diagnostics and are not a feature Check.

## Still open

Eight seconds for 576 ready thumbnails is not the scrolling experience we
want. Each thumb is about 6 ms at the server in the later samples, and the
browser's frame gap during that scroll was still about 250 ms. The page
had 12,855 grid cells. The next measurement should remove off-screen cell
DOM, or otherwise stop the main thread from laying out the whole library
between image waves, and repeat this same scroll. No feature Check is closed.

## Windowed grid, 2026-10-27

The slow start was the page creating a placeholder for every photo, then
trying to load thumbnails into that same pass. Clearing a filter threw
those placeholders away and kept at most 256 pictures that had already
been decoded. Thumbnails on disk were already made. The wait was the
browser building the grid and decoding pictures into it.

The grid now keeps a placeholder only for the rows on screen. While any
of those pictures is still loading, it does not fetch pictures above or
below. After the screen is full it prefetches two more rows. Pictures
that already decoded are kept, up to 1,024, and reused when that photo
comes back. A filter clear still empties the grid immediately. It does
not put the previous grid back. The bottom bar says how many on-screen
tiles have a picture, how many are in memory, and how many are still to
load. The largest folder row names the file processing is on.

Same headless Edge test, faces still running, no server restart. The
open years view had 78 grid cells in the page, not 11,964. One of those
78 never painted (77/78 at 60s, state done), the same class as the known
unavailable preview. A jump into the dense 36 px wall, dates off:

| | Before this window | This run |
| --- | --- | --- |
| First painted tiles | 24 of 576 at 1.3s | 30 of 576 at 0.24s |
| Half of the screen | 4.7s | 1.0s |
| All 576 visible tiles | 8.0s | 1.7s |
| Frame gap, median | 255ms | 128ms |

Artifact: `assets/live-dense-windowed-v2.json`. An earlier run of the
same scroll, before year groups were included in the window, was 1.9s
(`assets/live-dense-windowed.json`) and still built 11,964 cells on the
years view.

A person filter filled its on-screen tiles at 3.5s (78/78) while later
records were still arriving; at 25s the screen was 132/132 and the
stream had not finished. Name sort in that same run had 16 tiles on
screen after 25s, first tiles at 10s, stream still open. Faces moved
7,323 to 7,335 in the 122s run, about one photo every 10s while the
browse test was also loading pictures. The folder row can now say which
file that is. Detection itself is still one photo at a time. No feature
Check is closed.
