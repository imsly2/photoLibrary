# Taste-Settings — Folders, rescan, face slider, picker crop

Sits on `cursor/settings-sources-reveal-f272`. Family Settings page plus
Steve’s face-match follow-up. Does not close F17. No albums/cloud.

Read PRODUCT F17 / F14, CONTRACTS sources + `which=face`, UI-SPEC
Settings, FACES PLAN, and this file.

## In scope

1. `#settings-view` (Ctrl+, / header Settings). **Folders first:** every
   catalog source with lastKnown path, available, mode, photo/video
   counts, rendition done/queued/error, last scan. Add folder reuses the
   named dialog. Refresh = `POST /api/sources/<id>/rescan` (skip
   unchanged size+mtime; re-queue error renditions). Remove folder is
   catalog-only (`remove-source`).
2. Remaining settings.json keys as controls. `previewStore` says where
   new renditions live. Language stays in the header.
3. `faceMatchThreshold` default **0.80**, Settings range 0.35–0.95 step
   0.01, live output, Re-run Faces note after a change. `faceMinSidePx`
   stays a number (default 80).
4. Detect stays full-frame 640 → map boxes → original 112 ArcFace.
   Large stills add overlapping 1280 tiles, NMS merge, same 112 embed.
5. People picker uses `GET /api/media/<id>?which=face&box=` square
   crops (`object-fit: cover`). Pending tiles keep an honest placeholder.
   Pressed ring stays.
6. Reveal argv + lastKnown fallback stay (TASTE-REVEAL).

## Out of scope

S13/S14, F17 Check close, align-before-detect, albums, cloud.

## Gate

```powershell
python -m tests.qa slice TASTE-SETTINGS --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa slice FACES --root "$qaRoot/library-data" --artifacts $faces
python -m tests.qa slice TASTE-REVEAL --root "$qaRoot/library-data" --artifacts $reveal
```
