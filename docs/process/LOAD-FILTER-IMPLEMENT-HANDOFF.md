# Handoff: build load and filter as fast as this PC allows

Paste the prompt below into the next agent.

---

You lead this. You may orchestrate subagents. You choose the approach. The
bar is a local photo browser where opening the library and changing a
filter feel instant on a 28,000-picture library: the grid answers the
click in the next frame and pictures already seen come straight back.
Lightroom's grid and Apple Photos set that feel. Do not clone either.

## North star

The photo library at `J:\slyOS\projects\photoLibrary` should load pictures
and filter them as fast as this PC allows. That is the whole goal.
Nothing in the current design is a requirement because it is already
built. Before you build, write that goal into `docs/PRODUCT.md` in your
own words, in the feature sections that own browsing (F9 Zoom, F11 Sort,
F14 People, places, and things, F15 Search, F23 Folder library, or a new
section if none fits). Describe the outcome there, not the mechanism. The
repo rule is to build only what a PRODUCT.md feature describes, and a
feature is done only when its Check has run and the artifact path is in
`docs/STATUS.md`.

## Problem

Steve, on the live library: opening the page counts pictures for a long
time. Thumbnails fill part of the screen, then stop. The page is hard to
use until the count finishes. Filtering was almost instant for a moment,
including turning filters off and on, then it regressed. A filter, a
person, and clearing that filter wait while a list comes in. Tiles that
had pictures go blank, and the thumbnails build again slowly. It feels
like more than one loader is competing. Making one path faster has left
the same stall on another path.

That has been measured. Read `docs/process/LOAD-FILTER-TARGET.md` first.
In short:

- `/api/people/suggestions` compares every pair of 1,631 face centroids
  in Python loops, 230 to 264 s per call. Every page open triggers it.
  It holds the Python interpreter, so the stream and thumbnails starve.
- A missing-file sweep in `library/renditions.py` holds the catalog lock
  for 6 to 11 s every 30 s.
- The page takes the 57 MB list in 24 rows per frame. Headless Edge
  needed 267 s to know the count.
- The 42-tile Favorites strip never gets an image `src`, so no click
  ever settles.
- Search clears the grid on every keystroke.
- When nothing competes, one thumb takes 2.3 ms. The disk is not the
  limit.

The earlier line of work, keeping a remembered wide list in the page so
chips answer from memory, made chips fast for a while. He still sees the
wait on person, search, sort, and clear, and blank tiles on every path.

## Goal

On this library: the page knows the count within about a second of
opening. Any filter, person, search, sort, or clear shows the right
pictures within a frame or two. Pictures already seen never go blank and
never download again. Nothing running in the background (thumbnails,
faces, people suggestions, scans) can make browsing wait. The target
numbers are in `tests/perf/live_targets.json`. They are a floor to beat,
not a cap.

`docs/process/LOAD-FILTER-TARGET.md` has a proposed structure: one
compact index fetched once, all filtering in the page, ids reordered
instead of the grid rebuilt, permanent thumbnail addresses, and
processing kept away from browsing. Use it, change it, or beat it. Say
which in PRODUCT.md and why.

## Already decided

- The per-folder `.library/` records stay the source of truth (F23). Any
  index you add is a rebuildable copy.
- Everything stays local. No cloud, no accounts.
- The controls Steve has locked in `docs/UI-SPEC.md` keep working: the
  chips, People, Places, Tags, folder, search, sort, Group, Dates, Size.
  Make them faster. Do not remove them.
- The benchmark is the judge. Do not loosen a target or the regression
  rule to make a run pass.

## Pickup

- Door: `AGENTS.md`, then `docs/PICKUP.md`.
- Live page: [http://127.0.0.1:8785/](http://127.0.0.1:8785/). The server
  is `python -m library serve` from this repo with `.venv`, root
  `library-data/`, 28,135 pictures. The iPhone folder
  `K:\Photos\Iphone 2017-2026.10` is part of it.
- PC: i7-8700K (6 cores, 12 threads), 32 GB RAM. `K:` is an SSD in a USB
  enclosure. Python 3.13, numpy 2.5, and py-spy are in `.venv`. To see
  what the live server is doing:
  `.\.venv\Scripts\py-spy.exe dump --pid <pid>`.
- Files that own this: `library/web/assets/library.js` (page),
  `library/server.py` (routes, cache headers, threads),
  `library/service.py` (list build), `library/item_index.py` (records in
  memory), `library/renditions.py` (encode pool, sweep),
  `library/people_suggest.py` (suggestions).
- How the page works today: `docs/process/LOADING-PIPELINE.md`. This is
  history, not a design to keep.
- Earlier speed notes, also history: `docs/PICKUP.md` "Active
  performance work" and
  `docs/features/processing-feedback/Rev1.0/BROWSE-SPEED-BASELINE.md`.
- The working tree already has many uncommitted changes that are not
  yours. Do not revert them.

## Prove it

The benchmark measures this library through the running server and a
headless browser. It never writes to the catalog.

```
cd J:\slyOS\projects\photoLibrary
.\.venv\Scripts\python.exe -m tests.perf.live_load_filter --quick   # about 8 min today
.\.venv\Scripts\python.exe -m tests.perf.live_load_filter           # full, 15 to 25 min today
```

- It measures the running server, so restart `python -m library serve`
  on your tree before each measurement, and close other Library tabs.
- Every run writes `docs/process/assets/load-filter/runs/<stamp>.json`
  and `.md`. The table shows each metric against the 2026-11-06 baseline
  (`docs/process/assets/load-filter/baseline.json`, readable as
  `baseline.md`) as better, same, or WORSE, and against its target as
  met or miss. Exit 1 means a primary metric got worse.
- Run it after each change that could move speed. Report the run file
  and the lines that moved. A change that improves one path and makes
  another WORSE is not done.
- If your design removes a route or renames a page hook the benchmark
  uses, update the one place it lives: `PAGE` at the top of
  `tests/perf/live_load_filter.cjs`, and the route constants at the top
  of `tests/perf/live_load_filter.py`. Every test must still measure what
  its row in `LOAD-FILTER-TARGET.md` says. A probe that reports `absent`
  is not a pass. Do not move the baseline to make a run look better.
  Only Steve's accepted result becomes the next baseline
  (`--save-baseline`).
- Write the passing run's path into `docs/STATUS.md` for the feature it
  closes. Update `docs/PICKUP.md` and `LOADING-PIPELINE.md` to match what
  the page now does.
- Steve's eyes are the last check. When the numbers are green, restart
  the live server and ask him to open the page, click a person, clear
  it, and search. A green table he still feels as slow is not success.
- When you finish, leave a short report in `J:\slyOS\inbox` named
  `YYYY-MM-DD_HHMM_photoLibrary_<topic>.md`.

## Hands off

- Not in scope: new features, the Globe, iPhone import, export, and
  restyling the grid. Speed only, plus the bugs above that block it.
- Do not commit, push, or rewrite history unless Steve asks.
- Do not delete or move originals, `.library/` folders, or
  `library-data/` records to make a measurement easier.
