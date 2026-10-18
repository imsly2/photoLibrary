# Handoff — make processing, AI checks, filtering and first load fast

## Result (2026-10-18, commits `5a1279f` `06fcb49` `46a2206`)

Ranked by what Steve feels. Every row is before → after on the same fixture;
artifacts live in `assets/perf-next/`.

| # | Area | Fixture | Before → after | Where the time went | Evidence |
|---|------|---------|----------------|---------------------|----------|
| 1 | People filter, clicks, first load | 400 JPEGs, 7 named people, headless Edge, idle | person click 16.7 s → 1.2 s; 2nd person 10.4 s → 0.13 s; clear 14.1 s → 0.5 s; first picture 9.3 s → 2.1 s; settled 11.8 s → 3.8 s; open original 3.3 s → 0.1 s | picker painted 294 face crops (ffmpeg decode of each original) ahead of `/api/items`; people/tags/sources read every record file per load (387 ms server work → 81 ms); empty filter re-fetched the catalog every 2 s | `ui-head.json`, `ui-after.json`, `api-cost-{head,after}.json` |
| 1b | Same, while faces re-run | same | person 4.2 s → 1.5 s; first picture 3.3 s → 1.6 s; server `/api/tags` 1.4 s → 13 ms | lock held by models (see 2) | `ui-{head,after}.json` → `processing` |
| 2 | AI queues (faces, objects, rating) | 40 JPEGs | drain 98.5 s → 55.3 s; lock held 88 s → 9 s; idle tick 433 → 17 ms | objects re-hashed every original each tick and built a new ONNX session per photo; faces/objects inferred under the lock; no ffmpeg timeout | `head-40-idle.json`, `after-40-idle.json`, `*-profile.profile.txt` |
| 3 | Scan a fresh folder | 40 JPEGs, 154 MB | 3.03× → 1.03× bytes per file; 107.6 → 79.7 ms/file warm; 238 → 158 opens | hash, content id, EXIF each re-read the file | `scan-head.json`, `scan-after.json` |
| 4 | Thumb/preview encode | 40 JPEGs, `-lowres 1` | 216.4 → 214.8 ms median (no gain) | process start ~40 ms + WebP encode ~100 ms; decode is not the cost | `lowres-1600-l1.json` |

Not done, in order of likely payoff: one shared decode for faces/objects/rating;
smaller `/api/items` (~3.4 KB/item: face floats, quality metrics); face crops
from the preview instead of the original (~2× faster); WebP compression level
0 for thumbs (~55 ms vs ~100 ms, +21 % bytes — taste call).

Harness: `ui_fixture.py` builds `.qa/ui-400` (copies 400 of Steve's JPEGs,
names the top clusters), `ui_timing.mjs <app-dir> <label> <port> <fixture-dir>`
times the page idle and during `rerun-faces`, `ui_compare.py a.json b.json`
prints the table. `ai_drain.py`, `scan_bench.py`, `lowres_probe.py`,
`api_cost.py` are the server-side benches. `.qa\wt-before` is a worktree at
`5cd481a` for before runs.

Live server (8785) still runs the pre-pass code and has a hung ffmpeg
(pid 39640). Restarting it needs Steve's OK.

---

You are picking up performance work on Library (Steve's photo library:
Python stdlib server + ffmpeg on Windows, `J:\slyOS\projects\photoLibrary`).
Start at `AGENTS.md` → `docs/PICKUP.md`; north star `docs/PRODUCT.md`;
status `docs/STATUS.md`. Follow `J:\slyOS\projects\slyAI\shared\WORKING-ORDER.md`
(doc edit before code, prove with artifacts, at most one taste question).

## What Steve says

"Processing is painfully slow, and so are the other model checks. Browsing,
zooming and opening a picture feel fast now. Filtering is really slow;
filtering by people takes forever. Clicking through things feels horrible,
and so does the initial load."

Goal: find the real bottlenecks in four areas, measure them, then fix the
biggest ones with before/after artifacts:

1. Processing a fresh folder (read, hash, metadata, thumbs).
2. The AI queues: analyze (places), faces, objects, rating, transcribe.
3. Filtering, especially by person, plus clicking between views and filters.
4. First page load.

## Where things stand (HEAD `598a51b`, all local commits, never push)

Already done this session; don't redo it:
- Recovery no longer costs O(n) on every request (it was O(n²) over a scan).
- Previews start mid-scan. Thumbs go first, in grid order; the scan reads
  files in grid order (a 128 KB EXIF date pre-read), so tiles never get
  pushed down.
- `FairLock` has a foreground lane (HTTP requests and the scan) and a
  background lane (encoders).
- Each Add folder or rescan writes a processing log under
  `library-data/logs/processing/`.
- JPEG tiles show the camera's embedded EXIF thumbnail (`which=camera`)
  until the real thumb exists.
- Browser-ready JPEG/PNG/WebP/GIF up to 26 MP get no preview
  (`preview: not-applicable`); the viewer shows the thumb, then the original.

Measured on 120 of Steve's JPEGs, before and after the last two changes:
- Top 20 tiles all pictures: 8.2 s → 3.3 s.
- All renditions done: 51.9 s → 16.9 s.

Evidence: `docs/features/processing-feedback/Rev1.0/assets/camera-tiles/{before,after}/result.json`.

## Known facts (measured; don't re-derive)

- **The drive limits reading.**
  - `J:` is an SSK NVMe in a USB enclosure. Cold reads run at about 39 MB/s
    (about 14 photos/s); recently read photos at 136 MB/s; cached files at
    406 MB/s. That looks like a USB 2 link. Steve has been told to check the
    port; don't run hardware or disk benchmarks, because auto-review blocks them.
  - py-spy put 64% of scan time in `sha256_file` reads.
- **The scan reads every file several times.** `sha256_file`, then
  `read_content_identifier` (`read_bytes`), then `_still_from_jpeg`
  (`read_bytes`), plus the 128 KB pre-read. Only the first read is cold, but
  that's 3× the memory copies, and the hash and EXIF parse could share one
  buffer.
- **Encoding:**
  - One ffmpeg process per file. A thumb averages about 147 ms; a preview
    (when one is still made) about 239 ms.
  - Six encoders at below-normal priority. Eight gave about +20% throughput;
    not adopted.
  - `-threads 1` made no difference.
  - Untested idea: ffmpeg's MJPEG decoder accepts `-lowres 1..3`, decoding
    at 1/2, 1/4 or 1/8 scale. A 320 px thumb from a 4032 px JPEG could decode
    at 1/8 (504 px), which should cut thumb time a lot. Measure it, and check
    that EXIF orientation still applies.
- **AI queues on the live server right now** (551 items):
  - analyze: 115 done.
  - infer-faces: 550 done.
  - objects: 550 done, but `library-data/logs/server.log` shows
    `processing-drain:objects:MemoryError` repeatedly around 17:30Z.
  - transcribe: 1 error (`OSError`).
  - **rate: 0 done, 546 pending, state "running". It never progresses.**
    That was already on the backlog. An earlier pass found rating runs
    pure-Python per-pixel loops (~786K pixels per photo) while holding the
    global catalog lock, and recomputes best-of groups on every step.
  - Since `598a51b`, objects reads the original instead of the preview, and
    `objects._probe_size` now swaps width and height for EXIF orientation
    5–8. `rating.decode_rgb` still squeezes rotated originals to a fixed
    size; that's an existing issue.
  - Each model decodes its own input with its own ffmpeg call. One shared
    decode (for example, one 640 px upright RGB frame per photo, used by
    faces, objects and rating) is an obvious candidate.
- **Catalog requests are fast on an idle server.** Warm `GET /api/items`
  takes 0.04–0.07 s (first call 0.41 s); `/api/groups` 0.03 s;
  `/api/people`, `/api/tags` and `/api/sources` 0.13–0.21 s.
  - So slow filtering is most likely in the page (`library.js` rebuilding
    or sorting the grid, the people panel, or `getBoundingClientRect` in
    `paintGridStills` over every cell), or it's lock contention while the AI
    drains run.
  - **Measure in the browser, both idle and while processing.**
  - Steve currently has no named people (`/api/people` → `[]`), because the
    folder library was reset. Build a scratch fixture with faces and named
    people to reproduce the people filter.
- **Page polling:** the page polls `/api/activity` every second. While
  scanning or with renditions pending, it also polls health and runs
  `loadCatalog` (jobs, people, tags, items, groups, sources, settings in
  parallel) every second.
- **Known gap:** a scan cut off by a server restart does not resume.

## Tools that already work

- **Unit tests:** `.qa\venv\Scripts\python.exe -m unittest discover -s tests -t . -p "test_*.py"` (52 OK).
- **Perf bench:** `python -m tests.perf.bench --label X --port 88xx` (prepend
  `C:\ffmpeg\bin` to PATH; `--count N`). Caveat: its "bookkeeping" figure is
  the gap between finished stills, so it now counts encoder idle time and
  needs a server-side measure.
- **Browser check:** `node docs/features/processing-feedback/Rev1.0/assets/camera-tiles/check.mjs <app-dir> <label> <port>`
  drives headless Edge over CDP (Node 24's built-in WebSocket). Copy its
  pattern for filter and first-load timing. Playwright and the browser MCP
  are unavailable.
- **Grid-order check:** `docs/features/processing-feedback/Rev1.0/assets/grid-order/check.py`
  (read its header for arguments).
- **Profiling:** py-spy is in `.qa\venv`; summarize with
  `.qa\spy_summary.py <raw> <thread> <depth>` and `.qa\spy_holders.py <raw>`
  (who holds the lock).
- **Before/after comparisons:** `.qa\wt-before` is a git worktree. Check out
  the commit you want to compare against there.
- **Sandbox quirk:** sandboxed shell commands can't see files that
  outside-sandbox runs wrote under `.qa`. Run scripts through `cmd /c "…"`.

## Rules

- Never write to `library-data/` (the real catalog) or `J:\Pictures`, except
  through the app or by reading originals to copy fixtures. Back up before
  any migration or reset.
- Steve's server is on port 8785. Don't restart or kill it without his OK.
  Use scratch servers (`--root <scratch>`) on other ports.
- Scratch files only under `.qa/`. Commit locally; never push.
- Build only what PRODUCT.md describes; edit PRODUCT.md first. Every claim
  needs an artifact (JSON, log or PNG) written to STATUS.
- Hand Steve files as `file:///J:/…` links (forward slashes) and pages as
  `http://localhost:…` links.

## What to deliver

1. A short ranked table, one row per area, with the measured cost and where
   the time goes: a py-spy profile or a browser performance trace, with
   artifact paths.
2. Fixes for the top two or three, each with a before/after artifact on the
   same fixture.
   - Likely candidates: one read per file in the scan; `-lowres` thumbs; a
     rating rewrite (numpy, outside the lock) so it actually progresses;
     one shared decode for all models; the objects MemoryError; client-side
     filter rendering.
3. STATUS.md updated, local commits, and a plain-language summary for Steve
   with clickable links. Ask at most one taste question.
