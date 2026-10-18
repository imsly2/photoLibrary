# Processing and preview loading

2026-10-18. Scope: existing F4/F5/F7/F14 processing and presentable-shell
progress row. No new F-id. Preserve concurrent portable-folder work. Standalone
folder HTML remains later, as F4 already records.

## Outcome

- Show grid stills progressively during scans and prioritize thumbnails/posters
  across all items before viewer previews, proxies and playback encodes.
  Queued tiles say Creating preview…; errors retain the unavailable message.
- Keep HTTP catalog/media/status requests responsive during long preview encodes
  and original-file reads. Serialize catalog transactions; do not release the
  catalog lock around publication, recovery, or code using mutable snapshots.
- Show current filename, derivative, elapsed time, completed/waiting/error counts.
  Distinguish missing optional setup from paused work. Keep scan progress visible
  when preview activity is happening at the same time.
- One polling cycle in flight. Fetch activity independently of potentially slow
  jobs/catalog requests. New thumbnails appear without a manual page refresh.

## Gates

1. Fixture-only regression proving all thumbnail/poster jobs precede video
   encodes and thumbnails can complete before scan completion.
2. Hold a test encoder open; GET items, media and jobs and POST pause must answer
   before releasing it. Preserve annotations made during encoding; do not
   resurrect removed items. Capture request latencies and activity payloads.
3. Real ffmpeg fixture JPEG + MP4 pass, including existing F5 and F7 Checks.
   Run F8 if rendition storage changes. Do not close a feature based on a taste
   test alone or call an unavailable Check passed.
   Valid HEIC/HEIF expectations follow an independent decoder probe: assert
   ready, nonempty renditions when decoding succeeds; assert error and no ready
   bytes when it fails. Keep broken.heic's strict error/placeholder coverage.
   Retain original failed evidence when correcting an obsolete decoder assumption.
4. Browser screenshot and DOM evidence: derivative/file, elapsed time, queue
   done/waiting/error counts, preview painting, pause/resume, no poll overlap.
   Review English and Chinese strings; retain console errors/network failures.
5. Fresh verifier owns immutable evidence. Lead re-runs focused gates and records
   artifacts in STATUS; broad 22-Check count stays unchanged unless full Checks run.
6. Scan-history compaction retains first-before/latest-after per path within a
   single undo step. Verify undo, redo, pending annotation rebasing, and existing
   F5 interruption gates. Record history size for a synthetic repeated-source
   workload. Do not combine separate user operations or alter transaction recovery.

## Constraints

Synthetic/committed fixture media only. No rescanning Steve's library, model
downloads, launch/update changes, or modifications to another agent's portable
catalog implementation. No broad rewrite or new scheduler setting. Slow optional
AI work may need a separate safe computation/publication split; document remaining
limits instead of releasing the lock around entire transactions.

## Verification corrections

- Live follow-up: closing/relaunching the browser reused an old backend. Preserve
  catalog/undo/settings before an operational restart; keep the same root/source.
  Native Windows volume lookups measured fast individually. A read-only profile
  on 164 catalog items measured item expansion at 1.37 s and jobs status at
  4.47 s; object counts repeatedly hashed 164 image inputs. Remove content reads
  from status counting, preserving actual worker checks. Test status with hashing
  patched to fail. Log background drain failures instead of silently swallowing
  them. Live thread traces then showed Windows mount enumeration occupying the
  request lock while hundreds of repeated lookups ran. Cache native serial-to-
  mount resolution only within one HTTP request/thread; rediscover on the next
  request so a remounted/unplugged drive cannot reuse cross-request cache state.
  Leave scan/drain publication validation uncached. Focused tests must prove
  one lookup per request and fresh remount/unavailable results on later requests.

- Windows F4 exposed fsync on a read-only descriptor. Copy through a writable
  partial, flush/fsync, then preserve source metadata; include read-only originals.
- F8 exposed restore using a fallback lookup instead of the recorded target.
  Undo relocation restores bytes to the recorded store/path and then serves them.
- Idle catalog polling must still observe CLI settings changes, including Dates,
  so video hover checks keep their external-command coverage.
- Cooperative scan yields use 1 ms rather than a 50 ms delay per boundary.
