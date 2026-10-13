# Library — help

Library is a picture viewer for Steve's mother-in-law, with Steve setting it up
on a Windows PC. Her old pictures and videos are already scattered through folders,
often on external drives. In one sitting: launch the Library folder, point it at
those pictures, browse small pictures quickly, and open one. An agent can then
write who, where, and what is in them so they can be found again.

It is a local library server that travels with its app and data folder. It is not
the phone copier, a cloud host, a bundled image model, a desktop browser shell, or
a tool that rearranges originals on its own. Copying originals is an explicit
choice; linking leaves them where they are. No accounts or separate family mode.

The pictures you already have stay files on disk. The library adds a catalog
beside the server: one JSON record per picture, one per person, one per place,
one per thing. A SQLite file is a search index rebuilt from those records.
Delete the SQLite file and the server builds it again.

This tool does not pull photos off an iPhone. That is
[iphonePhotos](../../iphonePhotos/docs/PRODUCT.md). When that copy has landed
in a folder, add the folder here.

Nothing in this file is optional flavor. A feature is done when its **Check**
passes. [STATUS.md](STATUS.md) records the artifact for each Check. Until then
the feature is not built.

Layout targets, not screenshots of a running app:

- [Years](reference/library-years.jpg)
- [All photos](reference/library-grid.jpg)
- [Add a folder](reference/library-add-folder.jpg)
- [Settings](reference/library-settings.jpg)
- [Search a thing](reference/library-search.jpg)
- [Original missing](reference/library-unavailable.jpg)

## Build contract and locked decisions

This is the finished-product help file, not a report of working software.
[CONTRACTS.md](CONTRACTS.md) owns exact records, operations and errors;
[UI-SPEC.md](UI-SPEC.md) owns screen states and input;
[FIXTURES.md](FIXTURES.md) owns fixed test media;
[SLICES.md](SLICES.md) owns build order and complete Check gates;
[AGENT-BUILD-MODE.md](AGENT-BUILD-MODE.md) owns the orchestrator loop.
There are **22 feature Checks**, one for each F-id below. A Check includes its
original example and the full behavior assertions in SLICES/UI-SPEC; API success
alone cannot close a screen feature. No partial credit. Current passes: STATUS.

| Decision | Locked behavior / reason |
|---|---|
| User and scope | Steve sets up; his mother-in-law browses. Existing photos and video, no new accounts, albums, favorites or editing tools. |
| Packaging | Folder, Python + ffmpeg, local browser, CLI and HTTP. Windows first; macOS/Linux launcher promises need their own verification. |
| Catalog | JSON is authoritative; SQLite is disposable. Relative local paths; volume identity for linked drives. |
| Original safety | Explicit copy or link; ask by default. Never overwrite or reorganize originals. Copy undo leaves bytes. |
| Previews | With-server by default, optional source override; relocation affects only generated previews. |
| Offline | Show cached previews and unavailable banner by default; hide is a setting. Resolve individual files, including unplug-after-launch. |
| Naming | External agent/person writes entity JSON through annotate; no model inference or automatic geographic names. |
| Globe | Shipped texture, no network; cluster opens filtered items; orbit/place/media/orbit tour. |
| Pending/live identity | Bounded pending path digest, transactional hash merge; Live Photo still hash with explicit still/motion components. Earlier shapes could not safely express either. |
| Playback clarification | Full-length silent video proxies. `always` allows hovered proxies even at Years/Months; stills otherwise. Video poster precedes playback. |
| Recovery first | Durable writes, history and log start in foundation, not after user mutations already exist. |
| Scope over mockups | Reference extras are decoration, not features. No added keybinding editor or filesystem clipboard actions from the generic app baseline. |
| Testing | Synthetic/supplied test media only. Fresh verifier evidence for every Check; no real-disk scan in this plan. |

Technical decisions not previously specified are listed explicitly at the top of
CONTRACTS. Changing them requires a doc edit before implementation.

## The finished run

1. Copy this folder onto a drive and run the launcher.
2. The browser opens on this computer and shows an empty library.
3. Add a folder. Choose copy onto this drive, or serve that folder where it is.
4. The server reads each picture and video, writes a JSON record, and builds a
   small still. Videos also get a small movie for the grid.
5. Sort by date or by place. Zoom from years down to every photo. Open one.
   Spin a globe of every picture that has a location. Click a cluster to
   filter to those pictures and open one. Play a tour that orbits the globe,
   zooms into a place, shows pictures from there, and zooms back out.
6. An agent writes people, places, and things onto records. Search returns
   every picture tied to that name.
7. Plug the drive into another computer and launch it again. Files that were
   copied here open. Files that were only linked, and are not on this computer,
   follow the unavailable setting.

## F1 — Two folders

**App folder.** The thing you copy. Launcher, Python package, web page, this
help file. Runtime catalogs are never tracked in git.

**Library folder.** Created on first launch, default `<app-folder>/library-data/`
inside the portable app folder, beside the launcher. This is the catalog. Move the app folder and the library folder
together and the catalog comes with them.

```text
library-data/
  settings.json
  logs/server.log
  undo/                 # catalog history
  catalog/
    sources/<id>.json
    items/<id>.json
    people/<id>.json
    places/<id>.json
    things/<id>.json
    catalog.sqlite       # rebuilt from the JSON
  renditions/<id>/       # used when previews are stored with the server
    thumb.webp
    preview.webp
    poster.webp          # video
    proxy.mp4            # video
  originals/<source>/    # used when a folder was copied onto this drive
```

When a source stores previews inside the selected folder, those files go in
`<that-folder>/.library/renditions/<id>/` instead of `library-data/renditions/`.
The JSON catalog still lives in `library-data/`.

Paths stored for files on this drive are relative to `library-data/`. A drive
letter is never the identity of a file. A linked folder on another disk stores
the volume serial plus the path from that volume's root.


**Check:** `python -m tests.qa check F1` (planned runner; common root/artifact
arguments and full assertions in SLICES). Move a fixture app/data folder to another sandbox path and remap its drive letter. Copied originals and catalog still open, linked source identity survives a remount, and no catalog was written into tracked source. Artifact: path-resolution JSON and before/after file hashes.

## F2 — Launch

`launch.ps1` on Windows, `launch.sh` on macOS and Linux.

The launcher checks for Python 3.12+ and ffmpeg on PATH. If either is missing
on Windows it installs them with winget (`Python.Python.3.12`, `Gyan.FFmpeg`)
and continues. Then it starts the server and opens the browser at the listen
address.

The server listens on `127.0.0.1` and port `8765` unless settings say otherwise.
Binding every interface is a setting, off by default.

**Check:** `python -m tests.qa check F2` (planned runner; common root/artifact
arguments and full assertions in SLICES). from a clean temp library, `powershell -File launch.ps1` prints a
URL `http://127.0.0.1:8765/` and `GET /api/health` returns
`{"ok": true}`. Artifact: the response body saved to a file. A second launch
against the same library folder does not create a second catalog.

## F3 — Command line and HTTP

Every change an agent can make is a command and the same HTTP call. The web
page uses the HTTP calls. Agents may use either.

Run commands as `python -m library --root <library-data> <command>`.
`--root` defaults to `<app-folder>/library-data`, regardless of working directory.

| Command | HTTP | What it does |
|---------|------|----------------|
| `serve` | the process | Starts the server. |
| `scan <path> --copy-here` | `POST /api/sources` `{"path":"<folder>","mode":"copy-here"}` | Copies, then indexes. |
| `scan <path> --serve-from-there` | `POST /api/sources` `{"path":"<folder>","mode":"serve-from-there"}` | Indexes in place. |
| `sources` | `GET /api/sources` | Lists folders and whether each is available. |
| `copy-here <source-id>` | `POST /api/sources/<id>/copy-here` | Copies a linked folder onto this drive and makes the copy primary. |
| `items` | `GET /api/items` | Lists records. Filters below. |
| `annotate <id>` | `POST /api/items/<id>/annotations` | Writes people, places, things. |
| `people merge <keep-id> <drop-id>` | `POST /api/people/merge` | Reassigns faces to the kept person. |
| `settings get` / `settings set <key> <value>` | `GET` / `PUT /api/settings` | Reads and writes settings.json. |
| `rebuild-index` | `POST /api/rebuild-index` | Deletes SQLite and rebuilds it from JSON. |
| `renditions relocate` | `POST /api/renditions/relocate` | Moves preview files to match current settings. |
| `undo` / `redo` | `POST /api/undo` / `POST /api/redo` | Catalog and settings history. |

`GET /api/items` accepts `sort=date|location|name`, `dir=asc|desc`,
`person=`, `place=`, `thing=`, `from=`, `to=`, `unavailable=0|1`, `q=` for a
name or filename. Names match case-insensitively. `scope=people|places|things`
restricts the query for the existing search chips.

`GET /api/media/<id>?which=thumb|preview|poster|proxy|original` returns the
file. `original` on a missing disk returns HTTP 404 and
`{"error":"unavailable"}`. The thumb still returns if that preview file is
on this computer.

Exit codes: `0` success, `1` failed, `2` bad arguments. An empty search is
success.


**Check:** `python -m tests.qa check F3` (planned runner; common root/artifact
arguments and full assertions in SLICES). Run every mutation through CLI and HTTP on equivalent fixture roots, compare normalized canonical JSON, response/error semantics and exit codes. Reads return the same ids. Artifact: parity and invalid-input report.

## F4 — Add a folder

The Add folder dialog shows the path and two choices.

**Copy onto this drive.** Files are copied under
`library-data/originals/<safe-name>-<source-id>/`, keeping the folder structure below
the folder you picked. Those copies are the primary files. They travel with
the library. The scan then runs on the copies.

**Serve from that folder.** Nothing is copied. The source remembers the volume
serial and the path from that volume's root. On this computer the server
opens those files. On another computer, if that volume is not mounted, the
source is unavailable.

The dialog's starting choice is the setting `addFolderDefault`: `ask` (default),
`copy-here`, or `serve-from-there`. The web dialog always confirms the path and
choice; non-ask settings preselect the mode. An explicit CLI flag wins. With no
flag and default ask, CLI returns `choice-required` instead of blocking for input.

A later **Copy onto this drive** on a linked source copies the files, points
the same item ids at the copies, and leaves the old folder untouched. Annotations
already written stay on those ids.

An existing file is never overwritten. A name collision writes `name_2.ext`
beside the existing file and the record points at the new name.

**Check:** `python -m tests.qa check F4` (planned runner; common root/artifact
arguments and full assertions in SLICES). a temp folder with `a/photo.jpg` and `a/clip.mp4`.
`scan --copy-here` creates both files under `originals/` and two item JSON
files whose `locations[0].kind` is `library-relative`.
`scan --serve-from-there` on a second folder writes no file into `originals/`
and sets `locations[0].kind` to `volume`. Artifact: both item JSON files.

## F5 — Scan

Scanning walks the folder recursively. It skips `library-data/`, any
`.library/` directory, and files it already recorded with the same size and
modified time.

For each new picture or video it writes an item JSON file and queues
renditions. The item id becomes the SHA-256 of the file bytes. Until the hash
finishes, the id uses `pending-<sourceId>-<path-digest>`, then the record
is atomically renamed or merged into the hash record. Annotations written on the pending id move with it.

Two files with the same hash are one item with two locations. Search returns
that item once.

The scan is resumable. Stop the process and run the same command again. Files
already hashed and unchanged are left alone.

Supported pictures: JPEG, PNG, GIF, WebP, HEIC, HEIF, TIFF, BMP.
Supported videos: MP4, MOV, M4V, AVI, MKV, WEBM.

A HEIC that fails to decode still gets a record and a metadata pass. The
rendition is marked `error` and the grid shows a placeholder until a decoder
is available. ffmpeg is the decoder the launcher installed.

**Check:** `python -m tests.qa check F5` (planned runner; common root/artifact
arguments and full assertions in SLICES). run scan twice on a fixture folder. The second run's stdout says
`skipped` for every unchanged file and `added` 0. Artifact: the second run's
stdout.

## F6 — Metadata

Read from the file, in this order for the capture instant: EXIF
`DateTimeOriginal`, then `CreateDate`, then a `YYYY-MM-DD` or `YYYYMMDD` in
the filename, then the file's modified time. `capturedAtSource` records which
one was used.

Also stored when present: width, height, orientation, camera, lens, duration
in seconds for video, latitude, longitude.

A picture or video has a location only when the file itself carries one.
On an iPhone that is the camera writing coordinates into the file while
Location Services is on for Camera. JPEG and HEIC store them in EXIF GPS
(latitude, longitude, altitude). MOV and MP4 store them as a QuickTime
ISO6709 location string, not EXIF. The scan reads both.

The place name you see in the iPhone Photos app is not in the file. Photos
looks the coordinates up and keeps the name in its own database. A copied
camera roll brings the coordinates across and leaves the name behind. This
library stores the coordinates and leaves `name` null until a person or an
agent sets it. A screenshot, a download, or a photo shared with location
removed has no coordinates and does not appear on the globe.

GPS attaches a place. A new fix within `placeMatchMeters` (default 100) of an
existing place reuses that place id. The place `name` stays null until set.
Sort by location uses the name when it exists, otherwise a label made from the
rounded coordinates, otherwise the group "No location".

**Check:** `python -m tests.qa check F6` (planned runner; common root/artifact
arguments and full assertions in SLICES). fixture JPEG with EXIF date `2024-06-12T15:04:00` and GPS near
41.88, -87.63. After scan, the item's `capturedAtSource` is `exif` and
`placeId` points at a place JSON whose `name` is null and whose coordinates
match. A second JPEG 50 meters away gets the same `placeId`. A third, 5 km
away, gets a different place. Artifact: the three item files and two place files.

## F7 — Previews

Every picture gets:

- `thumb.webp`, longest side `thumbPx` (default 320), for the grid.
- `preview.webp`, longest side `previewPx` (default 1600), for the viewer
  before the original loads.

Every video gets:

- `poster.webp`, one frame near the start, at thumb size.
- `proxy.mp4`, width `proxyWidth` (default 480), H.264, no audio, long enough
  to cover the whole clip. The grid and the carousel play this file. Opening
  the item plays the original when it is available.

Renditions are queued by the scan and continue while the server is running.
The grid shows a placeholder until the thumb exists, then the thumb.

Years and months show stills under the default setting. Days and All play the proxy, muted and
looped, on the cell under the pointer. `playProxies` changes that:
`days-and-all` (default), `always`, or `off`.

**Check:** `python -m tests.qa check F7` (planned runner; common root/artifact
arguments and full assertions in SLICES). after scan of one JPEG and one 2-second MP4, these files exist and
are non-empty: `thumb.webp`, `preview.webp` for the JPEG; `poster.webp` and
`proxy.mp4` for the video. The proxy's width is at most `proxyWidth`.
Artifact: ffprobe JSON for the proxy plus the file sizes.

## F8 — Where preview files are stored

Setting `previewStore`:

| Value | Files land in |
|-------|----------------|
| `with-server` (default) | `library-data/renditions/<id>/` |
| `with-source` | `<selected-folder>/.library/renditions/<id>/` |

A source JSON field `previewStore` overrides the global setting when it is
not null.

`renditions relocate` moves existing preview files to match the current
settings and updates each item's `renditions` object. Originals are not moved
by this command.

If previews were stored with the source and that disk is absent, the item
record remains and the media call for the thumb returns
`{"error":"preview-unavailable"}`.

**Check:** `python -m tests.qa check F8` (planned runner; common root/artifact
arguments and full assertions in SLICES). set `previewStore` to `with-source`, scan a folder, and see the
thumb under that folder's `.library/renditions/`. Run `renditions relocate`
after setting `with-server`. The thumb is beside the server and gone from the
source tree. Artifact: both directory listings, before and after.

## F9 — Zoom

Four levels: Years, Months, Days, All. The slider and Ctrl+wheel move between
them. The item under the cursor stays in view. The level is saved in
`zoomLevel`.

Years is one card per year, a mosaic of that year's thumbs.
Months is one card per month.
Days is a header per day and the photos from that day.
All is every item under day headers.

Reference: [years](reference/library-years.jpg), [grid](reference/library-grid.jpg).

**Check:** `python -m tests.qa check F9` (planned runner; common root/artifact
arguments and full assertions in SLICES). a fixture library spanning two years. `GET /api/groups?level=years`
returns two groups. `level=months` returns one group per month that has items.
`level=days` and `level=all` return one group per day. Artifact: the four
JSON responses.

## F10 — Open a picture

Click a cell to open the viewer. Arrow keys move to the next and previous item
in the current sort. Esc returns to the grid.

For a photo the viewer shows `preview.webp` first, then the original if available.
For video it shows the poster, then plays the original or proxy; a browser that
cannot decode the original falls back to the proxy.
Ctrl+wheel zooms the picture, anchored at the cursor. Middle-click drags it.
Click a video, or press Space, to play or pause. Playback of a video uses the
original when available, otherwise the proxy.

The viewer lists the place, the people, and the things already written on the
record.

**Check:** `python -m tests.qa check F10` (planned runner; common root/artifact
arguments and full assertions in SLICES). `GET /api/media/<photo-id>?which=preview` returns image bytes.
`GET /api/media/<photo-id>?which=original` returns the original bytes when the
source is available. Artifact: both responses' content types and lengths.

## F11 — Sort

The toolbar sorts by date, location, or name. Direction is ascending or
descending. Default is date, newest first (`sort=date`, `dir=desc`).

Date uses `capturedAt`. Location groups by place name, then unnamed GPS
places, then "No location", and by date inside a group. Name uses the filename.

**Check:** `python -m tests.qa check F11` (planned runner; common root/artifact
arguments and full assertions in SLICES). three fixtures with dates June 2024, June 2023, and no EXIF.
`GET /api/items?sort=date&dir=desc` returns the 2024 item first. The no-EXIF
item's `capturedAtSource` is `mtime` and it sorts by that time.
Artifact: the items JSON.

## F12 — Globe

A Globe view draws every place that has coordinates. The earth is a WebGL
globe with a texture shipped inside the app folder. The page does not load
map tiles and does not send coordinates anywhere. Drag spins the globe.
The wheel zooms it, and the point under the cursor stays put.

Pins that overlap at the current zoom draw as one cluster with a count.
Pictures with no coordinates are absent.

Click a cluster. The library filters to the places in that cluster, and the
viewer opens on the newest item in it. Esc closes the viewer and leaves the
filtered grid. Opening Globe again shows the globe.

`GET /api/places` returns each place's id, latitude, longitude, name, item
count, and the id of the newest item. The page clusters those pins. `place`
on `GET /api/items` accepts one id or a comma-separated list.

**Check:** `python -m tests.qa check F12` (planned runner; common root/artifact
arguments and full assertions in SLICES). after the metadata fixtures, `GET /api/places` returns two places
and does not include the JPEG that has no GPS. `GET /api/items?place=<id>`
returns only items with that place id. Artifact: both JSON responses.

## F13 — Globe tour

Play on the globe starts a tour. It loops until Esc.

1. The globe orbits.
2. It picks a place that has pictures and zooms in on that pin.
3. It plays pictures from that place, newest first, up to `tourPictures`
   (default 5). Each still stays up for `tourPictureSec` (default 3). A video
   plays its proxy for that many seconds, not the whole file.
4. It zooms back out and orbits for `tourOrbitSec` (default 8).
5. It picks another place and repeats.

The tour uses the medium photo still and the video proxy from the rendition set. Items without a readable medium still (photo/live) or proxy (video) are skipped;
a place with no eligible item is skipped. With no
located pictures, Play does nothing and the page says there is no location to
show.

Esc stops the tour and leaves the globe where it stopped.

```json
"tourOrbitSec": 8,
"tourPictures": 5,
"tourPictureSec": 3
```

`GET /api/globe/tour` returns the places in play order, each with the item ids
it will show, skipping items that have no coordinates. The page plays that list.

**Check:** `python -m tests.qa check F13` (planned runner; common root/artifact
arguments and full assertions in SLICES). `GET /api/globe/tour` for the metadata fixtures includes both GPS
places, lists item ids that belong to each place, and omits the JPEG with no
GPS. Artifact: the tour JSON.

## F14 — People, places, and things

These are the serialized index. Each one is a JSON file. Pictures point at
them by id. Search does not look at pixels. It reads the ids.

An agent, or a person typing in the viewer, writes them with `annotate`.
The server does not download or run an image model. Analysis is whoever calls
`annotate` after looking at `preview.webp`.

Exact person, place, thing, item and annotation payloads are in
[CONTRACTS](CONTRACTS.md#source-entity-settings-and-history-records). Names can be
empty until somebody supplies them. The records stay readable JSON.

`box` is x, y, width, height, each from 0 to 1, on the oriented picture.
It may be omitted. A face is a box that points at a person. A person with
`"name": null` is an unnamed face. Setting the name updates that person file.
`people merge <keep-id> <drop-id>` rewrites every face and deletes the dropped
person file.

Naming a thing reuses an existing thing id when the name matches,
case-insensitively, including aliases. Otherwise annotate creates the thing file.

**Check:** `python -m tests.qa check F14` (planned runner; common root/artifact
arguments and full assertions in SLICES). `annotate <id> --person Ada --thing mug` creates `people/person_*.json`
with `"name": "Ada"`, `things/thing_*.json` with `"name": "mug"`, and the item
lists those ids. A second item annotated `--thing mug` reuses the same thing id.
`GET /api/items?thing=mug` returns both ids and no others.
Artifact: the people file, the thing file, and the search JSON.

## F15 — Search

The search box matches a person, place, or thing name, or a filename.
Chips limit the match to People, Places, or Things. Reference:
[search](reference/library-search.jpg).

The inspector for a thing shows its name, how many pictures point at it, and
the filenames. The same inspector exists for a person and a place.

**Check:** `python -m tests.qa check F15` (planned runner; common root/artifact
arguments and full assertions in SLICES). covered by the annotate check above, plus `GET /api/items?q=IMG_1042`
returns the fixture whose filename contains that string. Artifact: that response.

## F16 — When the original is not here

On launch, each source is resolved. A `library-relative` location is available
when its file exists relative to the library folder you started. A `volume` location is
available when a mounted disk has that serial and the path exists on it.
Otherwise the item is unavailable.

Setting `unavailableItems`:

| Value | Grid |
|-------|------|
| `show` (default) | The item stays. The cell uses the thumb if that file is here. |
| `hide` | The item is left out of the grid and out of `GET /api/items` unless `unavailable=1`. |

Opening an unavailable item shows the preview when the preview file is here,
a banner "Original is not on this computer", and Open original does nothing.
Play preview plays the proxy for a video. Reference:
[unavailable](reference/library-unavailable.jpg).

**Check:** `python -m tests.qa check F16` (planned runner; common root/artifact
arguments and full assertions in SLICES). a source JSON with a volume serial that is not mounted.
`GET /api/sources` marks it unavailable. With `unavailableItems=show`,
`GET /api/items` includes the item. `GET /api/media/<id>?which=original`
returns 404 `unavailable`. Set `hide` and the item disappears from
`GET /api/items` until `unavailable=1`. Artifact: the three responses.

## F17 — Settings

`library-data/settings.json` holds the 16 settings shown on the settings page
plus the internal `schemaVersion: 1` field (not a control). The defaults below
list the user settings. The page edits this
file. The command line edits this file. The browser does not keep a second copy.

```json
{
  "previewStore": "with-server",
  "unavailableItems": "show",
  "addFolderDefault": "ask",
  "playProxies": "days-and-all",
  "listenHost": "127.0.0.1",
  "port": 8765,
  "thumbPx": 320,
  "previewPx": 1600,
  "proxyWidth": 480,
  "placeMatchMeters": 100,
  "tourOrbitSec": 8,
  "tourPictures": 5,
  "tourPictureSec": 3,
  "sort": "date",
  "dir": "desc",
  "zoomLevel": "years"
}
```

Reference: [settings](reference/library-settings.jpg).

Changing `listenHost` or `port` applies on the next launch. Everything else
applies on the next request.

**Check:** `python -m tests.qa check F17` (planned runner; common root/artifact
arguments and full assertions in SLICES). `settings set previewStore with-source` then `settings get` prints
`with-server` replaced by `with-source`, and the file on disk matches.
Restart is not required for that key. Artifact: the file contents.

## F18 — Undo, Esc, clipboard, log

Ctrl+Z undoes the last catalog or settings change. Ctrl+Shift+Z redoes it.
History is files in `library-data/undo/`, about 500 steps, then the oldest
file is dropped. Undo of a newly added copied source removes its catalog registration and
does not delete the copied originals. Undo of converting an existing linked source
restores its earlier catalog locations. Those files stay until a person deletes
them.

Esc cancels the innermost active interaction: tour or gesture, dialog, viewer,
settings, then selection. Text fields retain their standard editing shortcuts.

Ctrl+C copies the primary path of the selected item as text. If the item is
unavailable, the copied text is the last known path and the page says it is
not on this computer.

Uncaught server errors and failed media reads append a line to
`library-data/logs/server.log` with the time and the path.

**Check:** `python -m tests.qa check F18` (planned runner; common root/artifact
arguments and full assertions in SLICES). `settings set port 8770`, then `undo`, then `settings get` prints
`8765`. `server.log` exists after a forced 404 to `/api/media/missing?which=original`.
Artifact: settings JSON after undo, and the log line.

## F19 — Live Photos

A still and a short movie that share the same Apple content identifier are one
item, `kind: "live"`. The still is the picture. The movie is the motion.
The grid badge reads LIVE. Hover, when proxies are allowed to play, plays that
short movie. The two files keep one item id, taken from the still's hash, and
both paths are stored on the item.

**Check:** `python -m tests.qa check F19` (planned runner; common root/artifact
arguments and full assertions in SLICES). a fixture pair with the same content identifier produces one item
JSON, `kind` `live`, and two locations. Artifact: that JSON file.

## F20 — Rebuild

`rebuild-index` removes `catalog.sqlite` and creates it from every JSON file
under `catalog/`. Search after a rebuild returns the same ids as before.

**Check:** `python -m tests.qa check F20` (planned runner; common root/artifact
arguments and full assertions in SLICES). annotate one thing, delete `catalog.sqlite`, run `rebuild-index`,
search the thing, get the same item id. Artifact: the search JSON.

## F21 — Keyboard

| Key | Action |
|-----|--------|
| Ctrl+wheel on the grid | Change year / month / day / all, cursor stays put |
| Ctrl+wheel in the viewer | Zoom the picture, cursor stays put |
| Middle-click drag | Pan the open picture |
| Click a cell | Open it |
| Click or Space in the viewer | Play or pause video |
| Arrows | Previous and next open item |
| Esc | Active tour/gesture, dialog, viewer, settings, then selection |
| Ctrl+F | Search |
| Ctrl+, | Settings |
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo |
| Ctrl+C | Copy the primary path |
| Esc during the tour | Stop the tour and stay on the globe |


**Check:** `python -m tests.qa check F21` (planned runner; common root/artifact
arguments and full assertions in SLICES). Drive every key and gesture in the table in the browser, including focused-text exceptions, cursor anchors, pan, clipboard, and Esc during each tour phase. Artifact: input trace, clipboard text, numeric measurements and screenshots.

## F22 — Web pages

One page, five views. The address is the listen host and port.

| View | What you see |
|------|----------------|
| Library | The zoomed grid, Add folder, search, sort. |
| Globe | The WebGL earth, clusters, Play for the tour. |
| Viewer | One item, preview then original, people and things. |
| Search | The same grid, filtered. Inspector for the person, place, or thing. |
| Settings | The settings file, as controls. |

Add folder matches [library-add-folder.jpg](reference/library-add-folder.jpg).


**Check:** `python -m tests.qa check F22` (planned runner; common root/artifact
arguments and full assertions in SLICES). Visit all five views and every state in UI-SPEC, including empty/scanning/ready/missing original/missing preview and recoverable errors. Reference extras must be absent. Artifact: inspected screenshots, console and offline network logs.

## What the first build includes

Every F1–F22 Check above. The exact fixture set and scenarios are in
[FIXTURES.md](FIXTURES.md); it is a specification today, not files already made.
All checks use a fixture-owned temp library and never a real photo disk.

Build in [SLICES.md](SLICES.md) dependency order. First taste is small fixture
pictures on screen and one photo opened; names and globe come later. Then continue
to 100% (22/22) fresh-verifier-backed Checks. [STATUS.md](STATUS.md) records what
actually passed, not what the help file promises.
