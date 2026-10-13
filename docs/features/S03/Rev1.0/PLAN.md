# S03 — Produce and open still renditions

Locked 2026-10-13 after recon [S03 stills](482428df-4e53-4404-bb3e-27b76f0de1dc).
Depends on S02 at `82c7f06`. **Closes no Check.** F7 stays open until S06. F10 stays open until S09.

Read PRODUCT F7 and the viewer preview sentence, CONTRACTS rendition and `/api/media` rules, UI-SPEC preview states, FIXTURES, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- JPEG photos only: write `thumb.webp` and `preview.webp`, then publish their paths.
- `GET /api/media/<id>` byte responses, Content-Type, length, one Range, and the existing error codes.
- A real page that lists catalog items and opens one still. Evidence is a screenshot of that running page.
- `python -m tests.qa slice S03` on a fixture-owned root.
- S00, S01, and S02 gates still exit 0 when run one at a time.

## Out of scope

Video `poster.webp` and `proxy.mp4`, hover, grid zoom, sort, search, settings editing, globe, tour, copy-here, relocate, annotate, and non-JPEG still decode. Do not close F7 or F10. Do not add a setting. Do not import Pillow or pillow-heif from `library/`. The fixture generator keeps those in the gitignored `.venv`.

## Decoder and files

ffmpeg is the product decoder. It is already required by the launcher. Default autorotate stays on. Do not pass `-noautorotate`.

For a JPEG photo whose thumb and preview are `queued`:

- Decode the current primary still.
- Apply EXIF orientation so the pixels are upright.
- Never upscale.
- Longest side of the thumb is `min(oriented longest side, thumbPx)`.
- Longest side of the preview is `min(oriented longest side, previewPx)`.
- Keep aspect. If the encoder needs even sides, round down so the longest side still respects the cap.
- Write WebP. `library-data/renditions/<id>/thumb.webp` and `preview.webp`.
- Store those paths relative to `library-data`: `renditions/<id>/thumb.webp` and `renditions/<id>/preview.webp`.
- Set that slot's status to `ready` only after the file exists and is non-empty. Write the file beside the destination, then replace, then update the catalog. A rendition update is not a history entry.
- `store` stays `with-server`. Poster and proxy stay `not-applicable` and null for photos.

`b/oriented.jpg` is the proof. Raw pixels are 640×480 with EXIF orientation 6, so the upright frame is 480×640. With defaults, the thumb is 240×320 and the preview is 480×640. Catalog `metadata.width` and `metadata.height` stay the raw 640 and 480. Original bytes stay unchanged.

Other still formats and every video stay as S02 left them (`queued` or `not-applicable`, paths null). Do not mark them `error` for lack of an S03 decoder.

`broken.heic` stays an item with thumb and preview `error` and null paths. Write no WebP for it. Do not clear its scan `decode-error`.

## When work runs

`scan` without `serve` leaves new JPEG renditions `queued` and writes no WebP. That is the queued proof. No new barrier.

While `serve` is running, drain queued JPEG thumb and preview jobs. The page polls until they are `ready`. A missing or unreadable rendition is not repaired by the GET.

Deleting `preview.webp` only leaves the item JSON in place. The next preview GET is `preview-unavailable`. Do not change status just because a test deleted the file. Do not recreate it on GET.

## HTTP

`GET /api/media/<id>?which=thumb|preview|poster|proxy|original`

- Missing or unknown `which`: 400 `invalid-argument`.
- Unknown id: 404 `not-found`, and append one `logs/server.log` line `{utc-iso}\t{path}\t{error}`.
- Known item, `which=original`, source not readable: 404 `unavailable`.
- Known item, rendition path null, status not `ready`, or file missing: 404 `preview-unavailable`. Queued, error, and a deleted preview all use this code.
- Ready thumb or preview: WebP bytes, `Content-Type: image/webp`, `Content-Length` equal to the file.
- Readable original: exact file bytes. `.jpg` and `.jpeg` use `image/jpeg`.
- Live `original` without `component` is the still. `component=motion` on an item with no motion location is 400 `invalid-argument`. Ordinary photos omit `component`.
- One range only. `Range: bytes=0-0` on a ready thumb returns 206, `Content-Range: bytes 0-0/<length>`, `Content-Length: 1`, and that first byte. A range that starts past the end, ends before it starts, uses another unit, or lists more than one range returns 416 `{"error":"invalid-range"}`.
- No filesystem path in the URL. Errors are JSON only.

`GET /api/media/missing?which=original` stays 404 `not-found`. `renditions relocate` stays unimplemented.

## Page

When the catalog has items, do not show the empty state. Load items with `GET /api/items`. Request each thumb with `GET /api/media/<id>?which=thumb`. No fixture pixels baked into the HTML, and no mocked media responses.

Until the thumb is readable, the cell shows the stable text “Preview is not available”. No broken-image icon and no spinner that never ends.

Clicking the oriented JPEG opens a viewer whose image is `GET /api/media/<id>?which=preview`. Esc closes it. A single list plus that viewer is enough. Do not build zoom levels, search, settings, globe, or video playback. Add folder may stay inert. No test-only controls in the product page.

## Gate

Fresh fixture-owned root. Do not scan a personal folder. Artifacts under `docs/features/S03/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `sizes.json`, `media-responses.json`, `first-still.png`.

```powershell
python -m tests.qa slice S03 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Scan the fixture tree with `--serve-from-there` and no server. Assert the oriented JPEG is `queued` with null paths and no WebP, and `broken.heic` is `error` with no WebP.
2. Start the real server. Poll until the oriented thumb and preview are `ready`. Timeout is a failure.
3. Measure the WebP with ffprobe, not by trusting the writer. Record width, height, and byte size in `sizes.json`. Thumb 240×320. Preview 480×640. Both longest sides within 320 and 1600.
4. Record status, Content-Type, length, and body sha256 for thumb, preview, original, the one-byte range, the bad range, the unknown id, and the deleted preview. Original body sha256 equals the file. Range bodies are checked, not assumed.
5. Open the real page at 1280×720 in a browser controlled by the test. A Playwright install in the gitignored `.venv` is allowed. `library/` must not import it. Click the oriented item. Save `first-still.png` only after the preview image has loaded from the server. Esc returns to the list. The PNG is 1280×720 and comes from that page, not from a drawing or a fixture file copy.
6. Exit 0 only when every proof ran. Skipped assertions fail.

The implementer may run this gate and must not call that log the grade. Run S00, S01, and S02 only sequentially, never beside S03.
