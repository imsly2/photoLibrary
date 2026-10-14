# S06 — Finish scan formats and video renditions

Locked 2026-10-13 after S05 at `381c737`. **Closes F5 and F7.** F8 stays open until S07. F10 stays open until S09. F19 stays open until S12.

Read PRODUCT F5 and F7, CONTRACTS rendition/scan/media/hover, UI-SPEC grid hover and viewer playback, FIXTURES format-coverage and HEIC-failure, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- Decode every supported still format with ffmpeg: JPEG, PNG, GIF, WebP, HEIC, HEIF, TIFF, BMP. Write `thumb.webp` and `preview.webp`. GIF and TIFF use the first frame/page.
- Decode every supported video container with ffmpeg: MP4, MOV, M4V, AVI, MKV, WEBM. Write `poster.webp` (one frame near the start, thumb size) and `proxy.mp4` (H.264, no audio, full duration, width at most `proxyWidth`).
- Failed HEIC (`broken.heic`) keeps its item and metadata. Thumb/preview stay `error` with null paths and the grid placeholder. Scan records `decode-error`. A later drain must not invent WebP for it.
- Scan-without-serve leaves new stills and videos `queued` and writes no rendition files. Serve drains queued jobs. A GET never repairs a missing file.
- `playProxies` already exists: `days-and-all` (default), `always`, `off`. Real grid hover plays the muted looped proxy on at most one cell. Viewer play is independent and falls back to the proxy when the browser cannot decode the original.
- `python -m tests.qa slice S06`, `check F5`, `check F7` on fixture-owned roots.
- `library/` must not import Pillow. Original bytes stay unchanged.

## Out of scope

Preview relocate, with-source store, annotate command, globe, tour, Live Photo pairing beyond the existing S01 pair, settings page, search chips. Do not close F8, F10, F16, F19. Do not add a setting. Do not add test-only UI.

## Renditions

ffmpeg is the product decoder. Default autorotate stays on. Do not pass `-noautorotate`. Never upscale. Keep aspect. If the encoder needs even sides, round down so the longest side still respects the cap.

Photos (`kind: photo`):

- Slots: thumb, preview. Poster and proxy stay `not-applicable` and null.
- Longest side thumb `min(oriented longest side, thumbPx)`. Preview `min(oriented longest side, previewPx)`.
- `b/oriented.jpg` remains 240×320 thumb and 480×640 preview. Catalog width/height stay raw 640/480.

Videos (`kind: video`):

- Slots: poster, proxy. Thumb and preview stay `not-applicable` and null.
- `poster.webp` is one frame near the start. Longest side `min(source longest side, thumbPx)`.
- `proxy.mp4` is H.264, no audio stream, full clip duration. Width `min(source width, proxyWidth)` (default 480). Height keeps aspect, even if required.
- `a/clip.mp4` is 640×480, 30 fps, 2.000 s with an audible tone. The proxy is at most 480 px wide, silent, and 2.000 s within one frame (1/30 s). ffprobe, not the writer, is the grade.

Live items stay as S01 left them. Do not pair new Live Photos. Do not invent poster/proxy for the still-only half.

Write beside the destination, replace, then publish the relative path and `ready`. A rendition update is not a history entry. `store` stays `with-server`. Paths are `renditions/<id>/<slot>.webp` or `renditions/<id>/proxy.mp4`.

A drain failure on a valid file sets that slot to `error`, keeps the item, and writes no empty file. Explicit rescan retries `error` slots even when size+mtime match. GET never retries.

`broken.heic` stays `error` / null paths / no WebP / source `decode-error`. Valid-brand HEIC/HEIF that this runner's ffmpeg cannot decode also stay `error` plus placeholder; record that in `format-matrix.json`. Do not rename a JPEG. Do not mark an undecoded valid file as `ready`.

## Hover and viewer

Change `playProxies` only through existing CLI/HTTP settings. No new key.

- `off`: hover never starts a proxy.
- `days-and-all`: hover plays at Years, Months, Days, and All (and a Dates-off wall).
- `always`: same hover as the default (every Dates grouping, including Years/Months mosaics).
- Only the hovered cell plays. Leave restores the poster/still. Playback is muted and looped. Audio must not start.
- Explicit viewer play uses the original when the browser can decode it, otherwise the proxy. Poster shows first. This is independent of hover.

Prove hover and fallback on the real page at 1280×720. Endpoint success alone is not the viewer proof.

## Scan (F5)

Re-prove, do not weaken, the S01 scan facts that F5 owns:

- Second scan of an unchanged folder: stdout contains `skipped` for unchanged files and `added` 0.
- Skip `library-data/`, `.library/`, junctions/symlinks, and non-allowed extensions.
- Every format-coverage file is indexed. Item id is SHA-256 of bytes. Unicode and long paths stay flat pending names then hash ids.
- Pending → hash: `LIBRARY_TEST=1` + `hash-publication` barrier still works. Seeded pending annotations move with the hash.
- Same bytes at a second path are one item with two locations.
- Same source path with later mtime and different bytes is a new hash item; the old item keeps `current=false` and cannot serve the new bytes.
- Restart after the hash-publication barrier publishes exactly one item.
- `broken.heic` plus a valid JPEG in the same scan: JPEG completes, failed item/placeholder retained, scan error reported, CLI exit 1 when errors exist.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts under `docs/features/S06/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `ffprobe.json`, `scan-resume.json`, `hover-playback.json`, `format-matrix.json`.

```powershell
python -m tests.qa slice S06 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F5 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F7 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Scan the format-coverage tree with `--serve-from-there` and no server. Assert stills and videos are `queued` with null paths and no rendition files. `broken.heic` is `error` with no WebP.
2. Start the real server. Poll until JPEG thumb/preview and `clip.mp4` poster/proxy are `ready`. Timeout is a failure.
3. Measure with ffprobe. Record codec, width, height, duration, audio-stream count, and byte size in `ffprobe.json`. JPEG oriented sizes unchanged from S03. Proxy width ≤ 480, H.264, audio streams 0, duration 2.000 s ± 1/30 s.
4. `format-matrix.json` lists every format-coverage file: indexed hash, kind, slot statuses, and whether ffmpeg produced a non-empty ready file. GIF/TIFF first-frame stills. Browser-unsupported originals must have a playable proxy.
5. `check F5`: second-scan added=0/skipped, exclusions, pending+seeded annotations, duplicates, changed path, restart, HEIC failure. Record `scan-resume.json`.
6. `check F7`: JPEG thumb+preview and MP4 poster+proxy exist and are non-empty; queued and error states; all three hover policies on the real page (only one cell plays; off plays none; always plays at Years). Record `hover-playback.json` from the browser, not from mocked media.
7. Original byte hashes unchanged. Exit 0 only when every proof ran. Never weaken an assertion or change expected fixture values.

The implementer may run these gates and must not call that log the grade.
