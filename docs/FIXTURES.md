# Library — fixed acceptance fixtures

2026-10-12. This is a fixture specification, not media generated in this task.
Future S00 supplies `tests/fixtures/`, a reproducible generator and manifest.
Use synthetic pictures/clips and intentionally supplied licensed codec samples;
never enumerate a real photo drive or borrow Steve's family pictures for tests.

## Base set

Images are 640×480 color quadrants with visible filenames; JPEG has EXIF orientation
1 unless noted. Distinct patterns ensure distinct hashes. mtime is pinned to the
value below after copying fixtures, so dates cannot depend on checkout time.

| File under tests/fixtures/media/ | Exact facts | Checks |
|---|---|---|
| a/IMG_1042.jpg | DateTimeOriginal 2024:06:12 15:04:00; GPS 41.880000,-87.630000; mtime 2022-01-01T00:00:00Z | F4–F16,F20 |
| a/near.jpg | DateTimeOriginal 2024:06:12 15:05:00; GPS 41.880450,-87.630000 (~50 m north) | F6,F9,F12,F13 |
| b/far.jpg | DateTimeOriginal 2023:06:12 15:04:00; GPS 41.925000,-87.630000 (~5 km north) | F6,F9,F11–F13 |
| b/no-exif.jpg | No EXIF/GPS/date in filename; mtime 2022-02-03T04:05:06Z | F6,F11–F13,F16 |
| b/created.jpg | CreateDate 2024:07:04 12:00:00 only; no GPS | F6,F9 |
| b/holiday_20200102.jpg | No EXIF/GPS; mtime 2022-01-01T00:00:00Z | F6 filename fallback |
| b/holiday_2020-01-03.jpg | No EXIF/GPS; same pinned mtime | F6 filename fallback |
| b/oriented.jpg | Raw 640×480, orientation 6; DateTimeOriginal 2024:06:12 15:06:00; no GPS | F6,F7,F10,F14 box orientation |
| a/clip.mp4 | H.264 640×480, 30 fps, 2.000 s, audible test tone; QuickTime location +41.8800-087.6300+000.0/; CreateDate 2024-06-12T15:07:00Z | F4,F6,F7,F10,F12,F13 |
| live/LIVE_0001.jpg | Still, content identifier 11111111-2222-4333-8444-555555555555; date 2024:06:13 10:00:00; GPS absent | F19 |
| live/LIVE_0001.mov | H.264 640×480 30 fps 2.000 s, matching Apple content identifier in metadata; no GPS | F19 |

Identifiers must be embedded in media, not merely asserted by a test stub. Store
the metadata extraction dump and generator recipe in `tests/fixtures/manifest.json`.
Live metadata that the chosen writer cannot produce is a fixture gap, not a reason
to pair by filename. A supplied tiny pair needs origin/license and independently
verified content identifiers before S00 passes.

Offline place names use a tiny shipped pack under `tests/fixtures/geo/`
(`cities.csv` plus attribution). It is not the full GeoNames dump. Copy
it into a sandbox `library-data/geo/` with `setup-geo --from`, or let
production `setup-geo` fetch cities5000. Never commit `library-data/geo/`.
The Chicago-area GPS JPEGs (IMG_1042, near, far, clip) resolve to
`Chicago, Illinois` against that fixture pack.

The original F6 three-JPEG check uses IMG_1042, near, far only: exactly two places.
The no-GPS fixture is added for globe omission. Use named subsets, never assert
the same total against the entire growing test tree. Original F11 uses IMG_1042,
far and no-exif: newest 2024, then 2023, then pinned 2022.

## Fixed variants and failure cases

Generate these from the base set into a fresh sandbox for each scenario. List their
hashes and expected relationships in manifest; builders may not invent extra media
or change expected counts in a slice to make a test pass.

| Variant / scenario | Construction and expected result |
|---|---|
| duplicate | Byte-copy IMG_1042 to second/source/same.jpg; one hash item, two locations, one search result. Seed different explicit place assignments in ordered history on pending/existing records; latest wins, exactly one primary remains, face/thing associations union. |
| collision | Seed a different destination photo.jpg and photo_2.jpg; copying photo.jpg writes photo_3.jpg, both seeded hashes unchanged |
| modified | Same source path gets different quadrant bytes and later mtime; new hash item, old annotations remain with old hash and historical current=false primary. Old item cannot serve new bytes; clipboard retains lastKnownPath. |
| unsafe/Unicode paths | `family/旅行 photo.jpg` and a nested long filename; pending JSON remains flat, final id hashes correctly; path traversal requests rejected |
| interruption | Kill at copy temporary write, hash publication, catalog transaction and SQLite rebuild boundaries; restart then rescan; no duplicate items or lost annotation |
| pending annotation | Seed a valid pending record with Ada/mug associations and matching history transaction before releasing the hash barrier; later repeat through real annotate in F14. Final item preserves association and history. |
| absent source | Resolver maps test volume `windows:fixture-offline` to no mount, with a known cached preview. Never unplug a real drive. |
| moved library | Copy app+data sandbox to a new absolute directory/drive mapping, original root made inaccessible; relative originals still resolve |
| moved linked volume | Test resolver remounts the same serial at a different letter; primary resolves there; a different serial at the old letter must not resolve |
| preview missing | Remove only sandbox generated rendition; record survives, 404 preview-unavailable and stable placeholder |
| denied/relocate interrupted | Test filesystem denies write or interrupts copy of rendition; old reference/bytes survive, original checksums unchanged |
| HEIC failure | Invalid `broken.heic` plus valid JPEG in same scan; failed item/placeholder preserved, JPEG completes, scan error reported |
| format coverage | One valid PNG,GIF,WebP,HEIC,HEIF,TIFF,BMP and MOV,M4V,AVI,MKV,WEBM. Same quadrant/test-tone recipe, distinct hashes. Codec samples require metadata dump and provenance. GIF/TIFF use first frame/page. Browser-unsupported original must play proxy. |
| orphan/mismatch live | Still alone, movie alone, then complete pair in opposite orders; different identifiers with same basename must stay separate |
| date edge | Invalid date substring falls back to mtime; valid offset EXIF normalizes UTC; two equal timestamps tie by id; filename containing two valid dates uses leftmost |
| empty/no-GPS | Empty media directory and subset of no-exif only; empty grid/search/globe/tour without failures |
| settings/history | Port 8765 → 8770 → undo → redo, restart between steps; 501 changes caps 500; new edit clears redo; copy undo leaves every original byte |
| annotation | Ada on first photo, mug on first+second; alias Cup → mug; second person id merged into Ada; rename place Kitchen; out-of-range boxes rejected |
| local objects | `tests/fixtures/objects/still.jpg` is a supplied still with a COCO-class object (not part of the S00/S01 media tree). After `setup-ml objects` and `analyze`, the item has at least one Thing, Info/search show it, and a prior human `--thing mug` on the same or another still keeps that name and id. COCO `person` is ignored. |
| local transcript | `tests/fixtures/transcript/spoken-en.mp4` and `spoken-zh.mp4` are short **spoken** clips (TTS; not silent or tone-only). After `setup-ml transcribe` and `transcribe`, English contains garden/fountain, Chinese contains 今天 and weather/garden, each has an extractive summary + keywords, search finds a spoken word with `saidInVideo`, and a second pass skips the same size+mtime. |
| local rating | TASTE-RATING writes generated stills (sharp, blurred, underexposed, overexposed, colorful, gray, and a three-frame burst). After `setup-ml aesthetic --backend fixture` and `rate-photos`, blur scores below sharp, dark/bright are flagged, the sharpest burst frame is `bestOfGroup`, user stars persist and override the suggestion, reject hides and never deletes, filters/sort work, a second pass skips same size+mtime, Off disables the stage, and Smart loads on CPU. |
| face-cluster | Synthetic stills with two beacon/identity “faces” (person A on two photos, person B on two, both on one, plus a no-face still). After `setup-ml faces` (fixture backend) and `infer-faces`, two unnamed people, boxes in range, same-person reuse, search by person after a human name, merge reassigns faces. Never a guessed name. |

## QA interface to build, not an existing command

S00 creates `python -m tests.qa fixtures --output <sandbox>` and
`python -m tests.qa slice <S-id> --root <sandbox>/library-data --artifacts <dir>`.
Use `python -m tests.qa check F<n> ...` for one complete Check, and
`python -m tests.qa all ...` at the final stop. Every invocation fails nonzero if
an assertion is missing, skipped, or fails. No placeholder green Checks.

The runner refuses a nonempty/unmarked root, writes a fixture-owned marker, uses
an isolated port from the sandbox settings when 8765 is occupied, and cleans up
only processes/files it owns. One explicit isolated default-port test is required
for Launch; do not kill Command Center. A resolver injection is a test seam only,
never a UI setting or a production identity shortcut.

`manifest.json` has `{schemaVersion:1,files:[{path,sha256,sizeBytes,mtime,
expectedMetadata,provenance}],scenarios:[{id,inputs,expected}]}`. Freeze generated
bytes and expected metadata before implementation gates use them. Manifest hash
goes in each result. Expose interruption barriers only in test harness. PNG capture
and measurements must use actual browser controls and rendered pixels.

## Generator locks (2026-10-13)

`expectedMetadata` is `{kind,width,height,orientation,durationSec,hasAudio,
capturedAt,capturedAtSource,latitude,longitude,contentIdentifier}`. Use null when
the fact is absent. `capturedAt` keeps the embedded source spelling (EXIF
`YYYY:MM:DD HH:MM:SS`, QuickTime ISO, or null when only mtime applies).
`provenance` is `{recipe,verifiedBy,extraction}`. `extraction` is the independent
probe output, not a copy of the generator's input table. `scenarios[].id` values
are exactly the variant names in the table above.

The QA marker is `library-data/.fixture-root` with
`{"schemaVersion":1,"owner":"tests.qa"}`. The runner may create a missing root,
refuses a nonempty root without that file, and deletes only processes and files
it created.

Ordinary `slice` and `check` runs write a free `port` from 18765–18864 into that
sandbox's settings before launch and do not connect to 8765. The explicit
default-port case, only inside slice S00: if 8765 is free, launch an owned
server there, assert health, assert a second launch keeps the same pid, then
stop only that pid. Also bind an owned dummy listener on another port, point a
second root at it, assert `port-in-use`, and assert the dummy still accepts a
connection. If 8765 is already occupied, do not kill it; record that a harmless
probe still reaches the occupant, and still run the dummy case.

`result.json` `revision` is `git rev-parse HEAD`. `dependency-probe.log` records
Python, ffmpeg, and ffprobe versions. The slice fails if Python is older than
3.12 or either binary is missing. Do not run winget from the slice.

Still content identifiers are an XMP `ContentIdentifier` element in namespace
`http://ns.apple.com/exif/1.0/`. Motion content identifiers are the QuickTime
key `com.apple.quicktime.content.identifier`. Video GPS is
`com.apple.quicktime.location.ISO6709` with the value in the base table. A
matching filename is not a pair. HEIC/HEIF bytes must carry an `ftyp` brand of
`heic`, `heix`, `heif`, or `mif1`. A renamed JPEG is a failed fixture.

JPEG GPS is EXIF GPSLatitude/GPSLongitude. Orientation is the EXIF Orientation
tag. CreateDate-only means DateTimeDigitized present and DateTimeOriginal
absent. Independent checks use ffprobe for video and a reader that does not
call the generator's write functions for stills.

Each gate writes `result.json` (check/slice, pass/fail, assertions, platform,
fixture-manifest hash, revision, commands, artifact paths), `stdout.log`, relevant
canonical JSON/response captures, and browser `*.png`, `measurements.json`,
`network.json`, `console.json` when applicable. Exact fixture hashes cannot be
claimed today: the generator and media do not yet exist.
