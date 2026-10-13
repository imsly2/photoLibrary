# S11 — Tour the places (M3)

Locked 2026-10-13 after S10. **Closes F13.** This is the M3 packet with S10. Do not wait for taste.

Read PRODUCT F13, CONTRACTS `GET /api/globe/tour`, UI-SPEC tour motion, FIXTURES GPS set, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- `GET /api/globe/tour`: array `{placeId,itemIds}` ordered newest item date descending then place id. Items newest first, capped by `tourPictures`. Only readable ready preview (still/live) or proxy (video). Skip empty places. Omit no-GPS.
- Play on the globe starts a looping tour. No new setting. Existing defaults: `tourOrbitSec` 8, `tourPictures` 5, `tourPictureSec` 3.
- Motion: orbit 6 deg/s for `tourOrbitSec`; ease to the next place over 1 s; present up to `tourPictures` at `tourPictureSec` each; ease out 1 s; orbit and advance; wrap at end.
- Stills/live show preview. Videos play muted proxy for the allotted time, not the whole file. Never require original availability. Re-query eligibility each cycle; skip unreadable/missing previews.
- Empty eligible list: camera still, “No locations to show”. Play is a no-op.
- Esc at any phase cancels timers/media and stays at the current globe position. User drag/wheel first stops the tour, then applies that gesture.
- `python -m tests.qa slice S11`, `check F13` on fixture-owned roots.
- Original bytes unchanged. `library/` must not import Pillow.

## Out of scope

Live pairing, settings page, F21/F22. Do not add a setting. Do not add test-only UI.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts: `result.json`, `stdout.log`, `tour.json`, `tour-trace.json`, `tour.mp4`, `stopped-globe.png`.

```powershell
python -m tests.qa slice S11 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F13 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. After the GPS JPEGs plus `clip.mp4` and no-exif, `GET /api/globe/tour` includes both GPS places, lists item ids per place (newest first, cap `tourPictures`), and omits no-exif.
2. Full motion sequence on the real page: orbit, ease-in, media, ease-out, next place, wrap. Record durations in `tour-trace.json` and a short `tour.mp4`.
3. Video uses timed muted proxy, not the whole file. Absent/unreadable preview is skipped. Empty/no-GPS Play is a no-op and shows “No locations to show”.
4. Esc during each phase cancels timers and leaves the globe where it stopped (`stopped-globe.png`). Drag/wheel stops the tour then applies the gesture.
5. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
