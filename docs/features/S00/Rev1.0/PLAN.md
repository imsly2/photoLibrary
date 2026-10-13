# S00 — Start an empty durable library

Locked 2026-10-13 after recon [S00 gaps](709ee349-0df4-4862-a336-7c5b00c970e8).
Closes no feature Check. Foundations for F2, F3, F17, F18 only.

Read PRODUCT, CONTRACTS (including Foundation locks), FIXTURES (including
Generator locks), and this file. Do not invent fields, errors, settings, or screens.

## In scope

- Python package `library/` (`__main__.py`, service, HTTP, atomic writes, lock, settings, history, log).
- Static `library/web/` empty-library page. Title Library. Visible text “No pictures yet”. An Add folder control may be present and inert. No sample pictures, globe, search results, or viewer.
- `pyproject.toml`, `launch.ps1`, `launch.sh`.
- Fixture generator and committed media under `tests/fixtures/`.
- `python -m tests.qa` with `fixtures` and `slice S00`.
- Ignored `tests/fixtures/user-samples/` (already has `.gitkeep`).

## Out of scope

Scan, copy, catalog items, renditions, grid, viewer, globe, tour, annotate, search, SQLite, winget installs during tests, macOS/Linux execution (ship `launch.sh`, do not claim it ran), workflow-engine packets.

Unimplemented routes return 404 `{"error":"not-found"}` and log. They must not return fake success.

## Behavior the slice must prove

1. Generator writes every base file and the format-coverage set. Manifest hashes match bytes. An independent probe matches `expectedMetadata`. Live still and movie expose the same embedded content identifier. HEIC/HEIF are real `ftyp` brands, not renamed JPEGs. `broken.heic` is not a valid image. mtimes match the table.
2. `python -m tests.qa fixtures --output <sandbox>` reproduces that tree in a sandbox.
3. Runner refuses a nonempty root that lacks `library-data/.fixture-root`.
4. Isolated launch on a free port in 18765–18864. `GET /api/health` is 200 `{"ok":true}`. `GET /api/runtime` matches `{schemaVersion,pid,root,url}` with the normalized root.
5. First launch creates default `settings.json` (16 keys + schemaVersion, PRODUCT order).
6. Second launch of the same root prints the same URL and does not change the server pid.
7. Dummy listener: launch returns `port-in-use`, dummy still accepts a connection, no foreign process is killed.
8. If 8765 is free, one owned default-port launch passes health and same-pid reuse, then only that pid is stopped. If 8765 is busy, leave the occupant up and record the probe.
9. Offline `settings set port 8770`, `undo`, `settings get` returns 8765. `redo` returns 8770. Empty undo is success.
10. The same undo cycle through HTTP while the server is the writer. CLI forwards to that server.
11. A second writer that cannot take `write.lock` gets `busy` and does not change settings.
12. `LIBRARY_TEST_BARRIER=settings-prepared` leaves port 8765 after recovery. `settings-committed` leaves 8770 after recovery and removes the transaction directory.
13. `GET /api/media/missing?which=original` is 404 `{"error":"not-found"}` and appends a `server.log` line containing a timestamp and that path.
14. Invalid settings values and unknown keys are `invalid-argument` and do not change the file.
15. `dependency-probe.log` records Python, ffmpeg, and ffprobe. Missing ffmpeg or Python < 3.12 fails the slice. Do not run winget.
16. 501 settings commits leave 500 history entries. This is the contract cap, not a new feature.

## Fixtures

Committed under `tests/fixtures/media/` plus `tests/fixtures/manifest.json`.

Base files from FIXTURES. Also one valid PNG, GIF, WebP, HEIC, HEIF, TIFF, BMP, MOV, M4V, AVI, MKV, WEBM, and invalid `broken.heic`. Unicode path `family/旅行 photo.jpg`. One nested path long enough that a raw path would be a bad filename, still under 240 characters.

Stills are 640×480 quadrant images with the filename drawn on the pixels. Distinct patterns, distinct hashes. JPEG orientation defaults to 1 except `oriented.jpg` (raw 640×480, EXIF orientation 6, asymmetric pixels). Videos are H.264 640×480 30 fps 2.000 s with an audible tone except where a container cannot hold AAC; WEBM may use a Vorbis or Opus tone. Duration must probe as 2 seconds within one frame.

`a/clip.mp4` location tag value `+41.8800-087.6300+000.0/` and CreateDate `2024-06-12T15:07:00Z`.

Live pair content identifier `11111111-2222-4333-8444-555555555555` embedded as FIXTURES Generator locks require. No sidecar.

Scenario records in the manifest describe duplicate, collision, modified, interruption, and the other FIXTURES variants. S00 does not execute their catalog effects. It must list each id and the inputs a later slice will build from committed bytes.

Use Pillow for ordinary stills. Use ffmpeg for video. Use pillow-heif (or an ffmpeg HEIF encoder if one exists) for HEIC/HEIF. If a real HEIC/HEIF cannot be written, stop and report the fixture gap. Do not rename a JPEG. Install generator dependencies into the gitignored `.venv`. The server must not import Pillow.

## Modules

- `library/settings.py` — defaults, validation, canonical dump.
- `library/atomic.py` — temp sibling, flush, replace; transaction manifest.
- `library/history.py` — undo files, 500 cap, cursor.
- `library/server.py` — bind, routes, recovery before serving, lock held for the process lifetime.
- `library/__main__.py` — CLI. Running server is the sole writer; CLI mutations forward. Offline CLI takes the lock.
- `tests/qa/probe.py` — independent metadata reader. Must not import generator write functions.
- `tests/fixtures/generate.py` — writer only.

Edit in place. Do not regenerate a file to reformat it. Every new type needs a reader.

## Gate

From the product root, with a fresh sandbox `$qaRoot` and evidence directory
`docs/features/S00/Rev1.0/assets/<run-id>/`:

```powershell
python -m tests.qa fixtures --output $qaRoot
python -m tests.qa slice S00 --root "$qaRoot/library-data" --artifacts $evidence
```

Exit 0 only when every assertion above passed. Skipped assertions are failures.
Artifacts: `result.json`, `stdout.log`, `health.json`, `settings.json`,
`recovery.json`, `dependency-probe.log`, `fixture-manifest.json`.
`result.json` includes pass/fail, assertions, platform, fixture-manifest hash,
revision, commands, and artifact paths.

The implementer may run this and must not call it the grade.
