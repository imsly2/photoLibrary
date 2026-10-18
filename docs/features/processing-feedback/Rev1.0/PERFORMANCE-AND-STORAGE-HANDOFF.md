# Performance and storage handoff

This note is a current continuation brief for performance and derivative-storage work. It does not change the product contract or record a completed Check. Preserve the older evidence and unresolved gates in [HANDOFF.md](HANDOFF.md) and [PLAN.md](PLAN.md).

## User report and current boundary

The real library still takes about 2–5 seconds per photo and appears to show thumbnails only. The larger 1600px preview is not visible yet, and videos have not been reached. This is a significant regression from the user's earlier known-good app. Recent GET `/api/items` observations (33.50 s to 1.76 s) are a partial recovery from the broken starting point; they are neither an end-to-end benchmark nor an improvement over the earlier known-good baseline.

The scheduler currently confirms one plausible reason previews are absent: `service.drain_step` passes `grid_only=self._scanning`, and `next_rendition_job` returns queued thumbs/posters before later slots and returns no later job at all while `grid_only` is true. After scanning, it still chooses a queued grid item before preview work. This describes the scheduling policy; it does not establish why each photo takes 2–5 seconds. Measure the stages before attributing that delay.

Current session evidence is limited: catalog snapshot had 164 items and 19 ready thumbnails; Chrome later showed 135 cells / 15 painted images, then 29 preview jobs done with zero errors, while the 551-file scan was at 51. Those are observations during one live run, not a throughput benchmark. A parent GET items observation fell from 33.50 to 1.76 seconds compared with the broken starting point only. Do not call this an improvement over the prior known-good app.

The app was restarted on port 8785 with the same catalog and source `src_acda5625dae4`; the 551-file folder scan resumed. Originals and catalog were preserved, with backups under `library-data/recovery/2026-10-18-processing-*`. No root reset or commit was made. Focused tests passed; earlier fresh F5 and browser checks passed, while F4/F7/F8 remain mixed or unresolved (13/22 recorded passed). Do not characterize the suite as green or run it again as part of this handoff.

Known implementation in the uncommitted working tree includes scan activity independent of derivative generation, grid-first thumbnails during scans, unlocked pure reads/encoding followed by revalidation, compact first-before/latest-after scan history, flushed writable partials for Windows copies, relocation restore to recorded targets, idle settings refresh, and HEIC capability probing. Recent small fixes also avoid hashing every input for objects status, scope native Windows mount lookup caches to one HTTP request, and log worker exceptions.

## Storage design proposal

Current layout, simplified:

```text
.library/
  catalog/
    source.json
    items/<id>.json
    people/…  places/…  things/…
  renditions/<id>/
    thumb.webp  preview.webp  poster.webp  proxy.mp4  playback.mp4
```

The IDs are content hashes: identical file bytes can share one catalog identity
even if filenames or locations differ. That is useful internally; it does not
require exposing hash-only folder names to someone browsing Explorer. Item JSON
currently holds file facts and entity references, while shared entity records
hold names. This explains why the metadata looks split up.

The user finds `.library/renditions/<SHA>/` separate from `.library/catalog` confusing and wants filenames that make the media relationship obvious, or a per-media folder holding its derivatives and a short description. Proposed shape for discussion:

```text
.library/media/<original-relative-path-including-extension>/
  item.json
  thumb.webp
  preview.webp
  poster.webp
  proxy.mp4
  playback.mp4
```

For example, `trip/IMG_0042.JPG` would map to `.library/media/trip/IMG_0042.JPG/`. Keep the stable hash ID internal in `item.json`, source index, and APIs for identity and deduplication; it should not be the only human-visible directory name. Including the original relative path and extension distinguishes common duplicate basenames in different folders.

This is a proposal, not an approved final layout or a shipped migration. Before choosing it, resolve rename behavior, deduplication across sources, Live/burst pairs and other entities, favorites, and how existing generated work is retained or relocated. Never discard generated work during a layout change. A simpler filename-prefixed alternative such as `.library/thumbs/<relative-name>.webp` is easier to browse, but spreads each item's derivatives across folders and needs careful naming/escaping and collision rules. The co-located per-media folder makes each item's artifacts and JSON easier to inspect, at the cost of path movement/rename semantics and migration complexity. Do not migrate real media or pick the final layout by fiat.

For readable per-media JSON, consider including resolved people/place/tag names
alongside their stable IDs, with an explicit rule about which representation is
authoritative. Shared people, favorites, and folder membership still need a
small shared index; avoid forcing users to inspect that index to understand a
single media item's generated files.

## Measurable next work

Use one small, checksum-stable fixture batch and compare the current checkout with the earlier known-good commit/environment if available. Record serial per-stage times and output counts. The first profile should separate read/hash and metadata work, ffmpeg startup/decode, encode, file flush/fsync, transaction publication, source/history writes, portable-folder mirroring, lock wait, and UI/catalog refresh. Do not claim a bottleneck until the measurements show it.

Inspect the per-item publication path: current rendition slot status and ready publication each go through catalog transactions. Repeated source JSON/history writes and mirror sync/fsync under the lock are hypotheses worth measuring, not established causes. Do not describe that as whole-catalog mirroring without evidence. Also measure whether separate ffmpeg launches for thumbnail and preview repeat decode; if so, evaluate a decode-once path that can still publish the thumbnail immediately.

Then make one bounded change aimed at the measured dominant stage. Keep thumbnails responsive while ensuring a selected viewer preview and video work cannot be starved indefinitely by an endless grid queue. Preserve original identity checks, revalidation, recovery, and undo guarantees. Consider worker parallelism only after measuring CPU and disk costs; serialize publication and bound concurrency. Avoid a broad rewrite before a small profile and one targeted change.

## Suggested gated sequence

1. Capture a checksum-stable fixture and compare per-stage timings against the earlier known-good state where reproducible; report any unavailable baseline plainly.
2. Measure full thumbnail-to-preview publication latency and scheduler fairness for a selected photo and a video.
3. Change one demonstrated bottleneck or starvation condition, then run only the targeted validation needed for that change.
4. Separately design storage naming and migration, with fixture checksums, cache preservation, undo, and crash/recovery behavior. Do not touch the real library for the proposal.

Do not restart the real server without a specific need. Do not rerun the whole 22-check set for this work.

## Focused code map

- `library/service.py:Library.drain_step`: scan-time grid-only gating and queue order.
- `library/renditions.py:next_rendition_job`, `drain_step`, `write_webp`: job priority, encoding, and publication.
- `library/scan.py:_index_file`, `_extend`: per-file indexing and history extensions.
- `library/history.py:plan_extend_entry`: compact history representation, still rewritten on extension.
- `library/atomic.py:transact` and `library/portable.py:mirror_changes`: durable writes and source-folder mirrors.
- `library/server.py:unlocked_io`, `serve` and `library/volumes.py:volume_lookup_scope`: lock handoff, worker loop, request-scoped mount resolution.
- `library/web/assets/library.js:loadCatalog`, `loadJobs`, `catalogNeedsStills`: refresh cost and visible readiness.
- `library/objects.py:analyze_status`: cheap status counts; actual inference retains its byte checks.

## Smaller-agent continuation prompt

```text
Read docs/PICKUP.md and docs/features/processing-feedback/Rev1.0/HANDOFF.md plus PERFORMANCE-AND-STORAGE-HANDOFF.md. First measure one checksum-stable fixture batch, including serial timings for read/hash/metadata, ffmpeg startup/decode/encode, flush/fsync, transaction/source/history publication, portable mirror, lock wait, and UI/catalog refresh. Compare to the earlier known-good commit/environment if available; report if not reproducible. Measure thumbnail-to-preview latency and whether separate ffmpeg launches repeat decode. Then implement only one small fix for the demonstrated dominant bottleneck or viewer/video starvation, preserving identity checks and recovery. Do not rerun all 22 checks, restart the real server without need, change the storage layout, migrate real media, or commit. Keep the filename-logical co-located storage idea as an unapproved proposal and preserve existing generated work. Record exact targeted validation and remaining uncertainty.
```
