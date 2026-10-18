# Library — help

Library is a picture viewer for Steve's mother-in-law, with Steve setting it up
on a Windows PC. Her old pictures and videos are already scattered through folders,
often on external drives. In one sitting: launch the Library folder, point it at
those pictures, browse small pictures quickly, and open one. An agent can then
write who, where, and what is in them so they can be found again.

It is a local library server that travels with its app and data folder. It is not
the phone copier, a cloud host, a required bundled image model, a desktop browser
shell, or a tool that rearranges originals on its own. Optional local place,
object, and face workers can be downloaded into the library folder; they stay
off until setup and never call a cloud API. Copying originals is an explicit
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
| User and scope | Steve sets up; his mother-in-law browses. Existing photos and video, no new accounts, albums, or editing tools. A per-item favorite heart writes `catalog/favorites.json` (viewer heart, tile hearts, collapsible Favorites). Windows Reveal in Explorer is a named action, not a setting. Neither is an album system. |
| Packaging | Folder, Python + ffmpeg, local browser, CLI and HTTP. Windows first; macOS/Linux launcher promises need their own verification. |
| Catalog | JSON is authoritative; SQLite is disposable. Relative local paths; volume identity for linked drives. |
| Original safety | Explicit copy or link; ask by default. Never overwrite or reorganize originals. Copy undo leaves bytes. |
| Previews | With-server by default, optional source override; relocation affects only generated previews. |
| Offline | Show cached previews and unavailable banner by default; hide is a setting. Resolve individual files, including unplug-after-launch. |
| Naming | External agent/person writes entity JSON through annotate. Optional **one-time local** installs may fill names on this computer: `setup-geo` (GPS city/region, never overwrite a human name), `setup-ml objects` (YOLO Things; ignore COCO person), `setup-ml faces` (InsightFace unnamed clusters; never guess a real name), `setup-ml transcribe` (Whisper speech-to-text on videos with sound; extractive summary + keywords, no cloud LLM), `setup-ml aesthetic` (local NIMA/MobileNet ONNX for Smart rating; CPU, GPU if present). No cloud geocoder or cloud AI. Browse works with models missing. |
| Globe | Shipped realistic local Earth texture, no network; drag right yaws east (inverted from the first grab); up/down unchanged; cluster opens filtered items; orbit/place/media/orbit tour. |
| Pending/live identity | Bounded pending path digest, transactional hash merge; Live Photo still hash with explicit still/motion components. Earlier shapes could not safely express either. |
| Playback clarification | Full-length silent video proxies (width ≤ `proxyWidth`, CRF 28, no audio). Hover plays the muted proxy on the cell under the pointer at every Dates grouping (Years / Months / Days / Off) and every Size. `playProxies=off` disables hover play. Video poster precedes playback. Viewer play starts on the proxy, then swaps to the original when it is already browser-safe, otherwise to a size-capped `playback.mp4` (≤1280, CRF 23) without a fit/time jump. `#viewer-source` names the file that is playing. `#viewer-scrub` (bottom chrome, not over the picture) and `.tile-scrub` seek. |
| Recovery first | Durable writes, history and log start in foundation, not after user mutations already exist. |
| Scope over mockups | Reference extras are decoration, not features. No albums, storage meter, or keybinding editor. Library and Globe in the header are pressed/unpressed buttons. Favorite and Reveal in Explorer are named sibling actions, not mockup leftovers. |
| Testing | Synthetic/supplied test media only. Fresh verifier evidence for every Check; no real-disk scan in this plan. |
| Windows Presentable Shell | First-class family-PC surface, not a taste overlay. Must-for-presentable (fullscreen, slideshow, viewer keys, EXIF Info, Open with, empty/error, remove vs delete-file, sort/filters, search, Update UX) plus the earlier launch/grid/viewer locks live in [UI-SPEC — Windows Presentable Shell](UI-SPEC.md#windows-presentable-shell). The **Presentable for family PC** checklist there is the taste definition of done. Soon rows do not block it. No 23rd Check. No accounts or editor. |

Technical decisions not previously specified are listed explicitly at the top of
CONTRACTS. Changing them requires a doc edit before implementation.

## The finished run

1. Copy this folder onto a drive. On a new Windows PC, run `Setup.bat`
   once (Python, ffmpeg, local faces/objects/places packs, Desktop /
   Start Menu shortcut). Then use the Library icon or `Library.bat`
   every day. New code is `Update.bat` / Update Library (always
   `main`, then auto-restart if Library is open). Run `Setup.bat`
   again only if models were added.
2. The browser opens on this computer and shows an empty library.
3. Add a folder. Choose copy onto this drive, or serve that folder where it is.
4. The server reads each picture and video, writes a JSON record, and builds a
   small still. Videos also get a small movie for the grid.
5. Sort by date or by place. Zoom from years down to every photo. Open one.
   Spin a globe of every picture that has a location. Click a cluster to
   filter to those pictures and open one. Play a tour that orbits the globe,
   zooms into a place, shows pictures from there, and zooms back out.
6. After a one-time local install, GPS pictures can show a city, objects
   can become Things, and faces can become unnamed People clusters.
   An agent or a person still writes names. Search returns every picture
   tied to that name.
7. Plug the drive into another computer and launch it again. Files that were
   copied here open. Files that were only linked, and are not on this computer,
   follow the unavailable setting.

## Windows Presentable Shell

The family Windows PC is the primary surface. Locked Must-for-presentable
in [UI-SPEC](UI-SPEC.md#windows-presentable-shell):

1. Fullscreen (F11 or F); Esc exits fullscreen then the viewer
2. Slideshow (F5; Space pause; Esc stop; empty “Add photos first”)
3. Viewer keys: arrows; Ctrl++/− or **plain wheel** zoom (side slider
   secondary); Ctrl+0 fit; Ctrl+1 100%; Ctrl+R rotate; Space play/pause
   video; tooltips show shortcuts
4. Info = EXIF/file facts first (date, camera, dimensions, size, path,
   GPS; empty “No camera info”), then people/places/things
5. Open with default app beside Reveal in Explorer
6. Empty / first-run / error: Add-folder CTA; scan Retry; missing-file
   placeholder; reconnect banner
7. Remove from library (Delete key + confirm, originals stay) vs Delete
   file (extra confirm, Recycle Bin)
8. Sort Newest / Oldest / Name; filters All / Photos / Videos / Favorites
9. Search filename + date + existing tags (Chinese text too); empty “No matches for …”
10. Update UX finish (launcher + in-app; Updating…; already current / failed; header shows checkout SHA)

Also locked: `Library.bat`, native Add folder, live-origin Back, grid
wall/hearts/VIDEO, Win7 prev/next/slider/pan, no overlay pills, no
“Showing original”, globe yaw + local Earth, progressive video start,
hover at every Size, one grid Size slider + Dates Years/Months/Days/Off
in the bottom-left cluster, a right People splitter, processing
Pause/Start, vertical side viewer Zoom, viewer/tile scrub in bottom
chrome. macOS/Linux launch is pinned later.

**Presentable for family PC** is the 19-step checklist in UI-SPEC. Until
that path is green, do not call the shell presentable, and do not
prioritize S13 settings or Soon rows (filmstrip, multi-select, Print,
`?`, recently added) over a Must gap. Those rows are not F23–Fn. Remove
and delete-file are CONTRACTS commands, not a new Check.

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
    favorites.json       # item ids marked with a heart
    catalog.sqlite       # rebuilt from the JSON
  geo/                   # optional offline cities pack (setup-geo); not in git
    cities.csv
    ATTRIBUTION.txt
  models/                # optional; created by setup-ml objects / faces / transcribe / aesthetic
    yolov8n.onnx
    objects.json
    objects-state.json
    faces/
      manifest.json
      index.json
      buffalo_s/
    whisper/             # faster-whisper small; transcribe.json manifest
    aesthetic/           # NIMA MobileNet ONNX; aesthetic.json manifest
  renditions/<id>/       # used when previews are stored with the server
    thumb.webp
    preview.webp
    poster.webp          # video
    proxy.mp4            # video
  originals/<source>/    # used when a folder was copied onto this drive
```

[F23 — Folder library](#f23--folder-library) replaces the per-folder layout
described in the rest of this paragraph and in F8 once it ships; until then
this is what the code does.

When a folder is served from where it is, with previews stored in that
folder, everything generated for those pictures lives in
`<that-folder>/.library/`. Renditions are
`<that-folder>/.library/renditions/<id>/`. The processed records are
`<that-folder>/.library/catalog/`: the source, each item, the people,
places, and things those items use, the hearts for those items, the face
embeddings for those items, and the object-analysis notes for those items.
Move the folder, or open it on another computer, and Library reads that
catalog, points it at the folder's new location, and shows the pictures
with the work already done. Settings, undo, and the optional models stay
in `library-data/`. A folder copied onto this drive still keeps its
catalog in `library-data/`.

Paths stored for files on this drive are relative to `library-data/`. A drive
letter is never the identity of a file. A linked folder on another disk stores
the volume serial plus the path from that volume's root.


**Check:** `python -m tests.qa check F1` (planned runner; common root/artifact
arguments and full assertions in SLICES). Move a fixture app/data folder to another sandbox path and remap its drive letter. Copied originals and catalog still open, linked source identity survives a remount, and no catalog was written into tracked source. Artifact: path-resolution JSON and before/after file hashes.

## F2 — Launch

`launch.ps1` on Windows, `launch.sh` on macOS and Linux. On Windows,
double-click `Library.bat` in the app folder; it runs `launch.ps1` in a
visible console so scan progress is readable. Do not require typing a
command prompt. macOS/Linux launch stays `launch.sh` and is not graded here.

On a new Windows PC, double-click `Setup.bat` once first. It installs
Python 3.12+ and ffmpeg the same way as the launcher (winget
`Python.Python.3.12`, `Gyan.FFmpeg`), creates `.venv`, installs the app,
and runs `setup-geo` plus `setup-ml objects`, `setup-ml faces`,
`setup-ml transcribe`, and `setup-ml aesthetic` when those commands exist. If a command is missing, it prints that Update
Library must pull it and exits non-zero. Models stay under
`library-data/`. No MSI. First run needs the internet. Daily use is
`Library.bat` or the Desktop / Start Menu shortcut Setup writes
(`CreateShortcut.bat` can recreate it). New code is Update Library /
`Update.bat` (anonymous HTTPS `git` of `main`, or a zip of `main` if
git is missing). No GitHub login. When that writes a newer `main` and
Library is already open, stop only this app's server on its settings
port and relaunch. `Setup.bat` does not start the server. Setup may
winget `Git.Git`; if git is still missing, Update uses the zip.

The launcher checks for Python 3.12+ and ffmpeg on PATH. If either is missing
on Windows it installs them with winget (`Python.Python.3.12`, `Gyan.FFmpeg`)
and continues. Then it starts the server and opens the browser at the listen
address.

The server listens on `127.0.0.1` and port `8765` unless settings say otherwise.
Binding every interface is a setting, off by default.

Command Center and Photon Arena own ports `8765`–`8774` on a dev PC.
Library does not take a port in that band when another program already
holds it, and it does not stop that program. It stores port `8785` in
settings and opens `http://127.0.0.1:8785/`. The next launch uses the
stored port. If `8785` is also taken by something else, launch stops
with `port-in-use` and does not pick a third port. A family PC where
`8765` is free stays on `8765`.

The opened page stays on that live origin. Back (in-app or the browser button)
must not jump to another host or port — including a leftover QA listen such as
`127.0.0.1:18765`. History, links, and fetches use the current origin or
root-relative paths. Never embed `settings.port` or a stored runtime URL from
a previous listen.

Family installs update without a command prompt and without a GitHub
account. Never call `gh`. Prefer plain `git` over anonymous HTTPS
(`https://github.com/imsly2/photoLibrary.git`): fetch `main`, checkout
`main`, fast-forward only. Credential helpers stay off so Windows does
not pop a login. If `git` or `.git` is missing, download
`…/archive/refs/heads/main.zip` and overlay files, never replacing
`library-data/` or `.venv`. The repo must be public for that anonymous
path. While it runs the page says Updating… Then one i18n sentence:
updated / already current / pull failed / diverged / need-public. The
header shows this copy's short SHA (or `local`). When Update writes a
newer `main` and Library is running, stop only this app's python serve
on the settings port and relaunch. If Library was not running, Update
just finishes.

**Check:** `python -m tests.qa check F2` (planned runner; common root/artifact
arguments and full assertions in SLICES). from a clean temp library, `powershell -File launch.ps1` prints a
URL `http://127.0.0.1:8765/` and `GET /api/health` returns
`{"ok": true}`. When another program already holds `8765`, that same
launch stores port `8785`, prints `http://127.0.0.1:8785/`, and health
on that URL returns `{"ok": true}` while the other program keeps
`8765`. Artifact: the response body saved to a file. A second launch
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
| `sources` | `GET /api/sources` | Lists folders and whether each is available. Each row includes `path` (lastKnown), `stats` (photos/videos/live/total and rendition done/queued/error), and last `scan` state. |
| `rescan <source-id>` | `POST /api/sources/<id>/rescan` `{}` | Re-walks that folder. Unchanged size+mtime files are skipped; names/tags/faces stay; error renditions are re-queued. Does not wipe the catalog. HTTP 202 while running. |
| `remove-source <source-id>` | `POST /api/sources/<id>/remove` `{}` | Drops that folder from the catalog (and items that only belonged to it). Originals stay. Not Delete file. |
| `copy-here <source-id>` | `POST /api/sources/<id>/copy-here` | Copies a linked folder onto this drive and makes the copy primary. |
| `items` | `GET /api/items` | Lists records. Filters below. |
| `duplicates` | `GET /api/duplicates` | Groups items that already look like copies: several current locations on one hash, or the same filename on two or more items. Read-only. Never deletes. |
| `annotate <id>` | `POST /api/items/<id>/annotations` | Writes people, places, things. |
| `favorite <id> [id…] --on` / `--off` | `PUT` or `POST /api/items/<id>/favorite` `{"favorite":true\|false}`; many ids: `POST /api/items/favorite` `{"itemIds":[…],"favorite":true\|false}` | Marks or clears hearts in `catalog/favorites.json`. Several ids are one undo step. |
| `reveal <id>` | `POST /api/items/<id>/reveal` `{}` | Opens the original's folder (Explorer on Windows). |
| `locate <id>` | `POST /api/items/<id>/locate` `{}` | Opens the last-known folder when the original is missing. Does not delete the catalog record. |
| `open <id>` | `POST /api/items/<id>/open` `{}` | Opens the original in the default app. |
| `remove <id> [id…]` | `POST /api/items/<id>/remove` `{}`; many ids: `POST /api/items/remove` `{"itemIds":[…]}` | Drops catalog records; original bytes stay. Several ids are one undo step. Not Delete file. |
| `move <id> [id…] --to <folder>` | `POST /api/items/move` `{"itemIds":[…],"destination":"<folder>"}` or `{"itemIds":[…],"sourceId":"<id>","subpath"?}` | Relocates selected originals into a registered source folder or a subfolder. Thumbs/proxies/playback stay; catalog paths update. Never overwrites (`name_2.ext`). One undo step. |
| `delete-file <id>` | `POST /api/items/<id>/delete-file` `{}` | Recycle Bin the original (Windows), then remove from the catalog. UI extra-confirms. |
| `update` | `POST /api/update` `{}` | Pulls a newer app folder when this copy is a git checkout. Success includes the new short `git_sha`. `GET /api/update` and `GET /api/version` report that SHA. |
| `people` / `people list` | `GET /api/people` | Lists people with counts, visibility, and thumbnail face. Unnamed clusters below `personOfInterestMin` (3) stay in the payload with `visible:false`. |
| `people update <id> --name … --thumbnail <item-id>` | `PUT /api/people/<id>` | Renames a person or chooses the thumbnail face item. |
| `people merge <keep-id> <drop-id>` | `POST /api/people/merge` | Reassigns faces to the kept person. |
| `people suggestions` | `GET /api/people/suggestions` | Likely same-person pairs from face-centroid cosine. Never merges. |
| `people not-same <a> <b>` | `POST /api/people/not-same` | Remembers that those two people are not the same. Suggestions skip the pair. |
| `people split <id> --item <item-id> [--box x,y,w,h]` | `POST /api/people/split` | Removes one face detection from that person. The crop becomes a new Unnamed person. |
| `tags` / `tags list` | `GET /api/tags` | Lists user tags (Things) with counts. Hiking / Singing / Painting are names. |
| `tags create <name>` | `POST /api/tags` `{"name":"Hiking"}` | Creates a tag Thing without attaching it. Reuses a matching name. |
| `tags apply --item <id> --add Hiking --remove Painting` | `POST /api/items/tags` `{"itemIds":["…"],"add":["Hiking"],"remove":["Painting"]}` | Applies or removes tags on one or many items. Human tags survive re-infer. |
| `jobs` | `GET /api/jobs` | Background queue status: renditions, analyze, infer-faces, objects, transcribe, rate. |
| `jobs pause` / `jobs resume` | `POST /api/jobs` `{"action":"pause"\|"resume"}` | Pauses or resumes the serve-process drain. Does not block browse. |
| `setup-geo` [--from \<dir\>] [--force] | (CLI setup; no catalog write) | Fetches or copies the offline cities pack into `library-data/geo/`. |
| `analyze-places` | `POST /api/places/analyze` `{}` | Fills null GPS `place.name` from that pack. Never overwrites a set name. |
| `setup-ml objects` | (CLI / `Setup.bat` / `launch.ps1 -SetupMl`; no HTTP) | Downloads a small local YOLO into `models/`. CPU. No cloud inference. |
| `setup-ml faces` | `POST /api/faces/setup` | Installs InsightFace buffalo_s ONNX into `models/faces/`. Never uploads photos. |
| `setup-ml transcribe` | (CLI / `Setup.bat`; no HTTP) | Downloads faster-whisper `small` into `models/whisper/`. GPU if CUDA is present, else CPU int8. No cloud inference. |
| `setup-ml aesthetic` | (CLI / `Setup.bat`; no HTTP) | Downloads a local NIMA/MobileNet ONNX (~13 MB) into `models/aesthetic/`. CPU via onnxruntime; CUDA when the provider is present. No cloud inference. |
| `analyze` / `analyze --item <id>` | `POST /api/analyze` `{}` or `{"itemId":"<id>"}` | Runs local object detection and writes Things through `annotate`. |
| `infer-faces` | `POST /api/faces/infer` | Detects faces, clusters unnamed people. Never guesses a name. |
| `transcribe` / `transcribe --item <id>` / `--force` | `POST /api/transcribe` `{}` or `{"itemId":"<id>","force"?}` | Local speech-to-text on videos with audio. Skips same size+mtime. Off in Settings skips the queue. |
| `rate-photos` / `rate-photos --item <id>` / `--force` | `POST /api/rate` `{}` or `{"itemId":"<id>","force"?}` | Suggested 1–5 stars from sharpness, exposure, and faces. Smart blends a local aesthetic score. Skips same size+mtime. Off skips the queue. Never deletes or auto-rejects. |
| `rate <id> --stars N` / `--pick` / `--reject` / `--clear` | `POST /api/items/<id>/rating` `{stars?,pick?,reject?,clear?}` | User rating always wins. Reject hides from default views; the file stays. 0 / `--clear` clears yours. |
| `settings get` / `settings set <key> <value>` | `GET` / `PUT /api/settings` | Reads and writes settings.json. |
| `rebuild-index` | `POST /api/rebuild-index` | Deletes SQLite and rebuilds it from JSON. |
| `renditions relocate` | `POST /api/renditions/relocate` | Moves preview files to match current settings. |
| `undo` / `redo` | `POST /api/undo` / `POST /api/redo` | Catalog and settings history. |

The header **Update Library** button calls `POST /api/update` so a family
install can pull a newer app folder without opening a command prompt.
The header shows the checkout SHA from `GET /api/version` and refreshes
it from a successful update payload.

`GET /api/items` accepts `sort=date|location|name|rating`, `dir=asc|desc`,
`person=` (one id/name, or comma-separated ids meaning **all** faces),
`place=`, `thing=` (one id/name, or comma-separated ids/names meaning
**all** those tags), `kind=photo|video|live` or a comma list,
`from=`, `to=`, `unavailable=0|1`, `q=` for a name, filename, date, or
words in a video transcript / summary. A transcript hit adds computed
`saidInVideo` `{start,text,field}` so the grid can show **Said in video**
and the viewer can seek to that time.
`source=` keeps items that belong to that Settings folder. `recent=1`
keeps items added by the last scan that wrote `library-data/recent.json`
(session Recently added). Names match case-insensitively, including Chinese. `scope=people|places|things`
still restricts a query on the API. `kind` keeps only those media
kinds (`photo,live` for Photos). The filter bar All / Photos / Videos /
Favorites / Recently added controls send no kind, `kind=photo,live`, `kind=video`,
`favorite=1`, or `recent=1`. Kind, favorite, recent, and source are transient
filters, not settings.
`favorite=1` keeps only hearted items. Item reads include computed
`favorite` (not stored on the item JSON) and computed `rating`
(`suggested`, `yours`, effective `stars`, `pick`, `reject`, `flags`,
`bestOfGroup`). `minStars=4` keeps effective stars ≥ 4 (yours wins).
`pick=1` keeps picks. `hideRejects=1` hides rejects from that list
(never deletes). `flag=blurry|too-dark|too-bright` keeps flagged
items. `sort=rating` orders by effective stars, then pick, then
suggested. `q` also matches a capturedAt date (`YYYY`, `YYYY-MM`,
`YYYY-MM-DD`).

`GET /api/groups` accepts the same item filters plus `level=years|months|days|all`
for date groups, or `by=people|places|tags` for entity groups (Unknown /
No place / Untagged buckets). Date `level` stays required when `by` is
omitted or `date`.

`GET /api/media/<id>?which=thumb|preview|poster|proxy|original|face` returns the
file. `which=face&box=x,y,w,h` is the square People-picker crop. An
optional `v=` is ignored by the server; the page adds it so images cached by
an older server (which let the browser keep them a week) are never reused.
Generated files are sent `no-cache` with an ETag, so the browser checks
each time and a deleted file shows as missing on the next load.
`original` on a missing disk returns HTTP 404 and
`{"error":"unavailable"}`. The thumb still returns if that preview file is
on this computer.

Exit codes: `0` success, `1` failed, `2` bad arguments. An empty search is
success.


**Check:** `python -m tests.qa check F3` (planned runner; common root/artifact
arguments and full assertions in SLICES). Run every mutation through CLI and HTTP on equivalent fixture roots, compare normalized canonical JSON, response/error semantics and exit codes. Reads return the same ids. Artifact: parity and invalid-input report.

## F4 — Add a folder

The Add folder dialog shows the path and two choices. On Windows, Browse
opens a native folder picker on this computer and fills the path — he does
not have to type a directory. Typed or pasted paths still work. After Add,
the dialog closes on the 202, the library confirms the folder, and scan
progress appears in the page and the server console. Pictures show as they
become ready. The dialog never stays open on a dead `busy` wait.

**Copy onto this drive.** Files are copied under
`library-data/originals/<safe-name>-<source-id>/`, keeping the folder structure below
the folder you picked. Those copies are the primary files. They travel with
the library. The scan then runs on the copies.

**Serve from that folder.** Nothing is copied. The source remembers the volume
serial and the path from that volume's root. On this computer the server
opens those files. On another computer, if that volume is not mounted, the
source is unavailable. This choice stores the generated tiles, previews, and
proxy videos inside that folder, at `<folder>/.library/renditions/<id>/`, and
sets the source's `previewStore` to `with-source`. The processed records
for those pictures are written into `<folder>/.library/catalog/` as well,
so moving the folder takes the tiles, the names, the faces, the places,
and the ratings with it. A later add of a folder that already has that
catalog loads it, points the records at the folder where it is now, and
shows the finished pictures instead of processing them again. A standalone
HTML page in that folder comes later.

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
The scan remains one undo step. Its history keeps the first previous value
and latest new value for each catalog path, rather than every intermediate
source snapshot, so adding more files does not inflate that step quadratically.

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
library stores the coordinates. `name` stays null until either a person or
an agent sets it, or a **local** offline geo pack fills it.

The geo pack lives in `library-data/geo/` (not in git). Steve fetches it
once with `python -m library setup-geo` or `Setup-geo.bat`. The pack is a
GeoNames-class cities table — nearest city/region, no network at scan
time, no cloud API. Without the pack, behavior is unchanged: `name`
stays null. `Setup.bat` runs that same `setup-geo` (plus `setup-ml`).

When a place has coordinates and `name` is null, scan / `resolve_place`
(and `analyze-places` for a library scanned before the pack) set
`name` to that city/region, like `Chicago, Illinois`. A nonempty name
written by a person or an agent is never overwritten. A screenshot, a
download, or a photo shared with location removed has no coordinates and
does not appear on the globe.

GPS attaches a place. A new fix within `placeMatchMeters` (default 100) of an
existing place reuses that place id. Sort by location uses the name when it
exists, otherwise a label made from the rounded coordinates, otherwise the
group "No location". Info and search show the name the same way they show
an annotated place.

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
- `proxy.mp4`, width at most `proxyWidth` (default 480), H.264, no audio,
  CRF 28, long enough to cover the whole clip. This is the small
  scrub/preview the grid and the carousel play — not a second copy of
  the original.
- `playback.mp4` only when the original is not a browser-safe MP4
  (typical iPhone `.MOV` / HEVC). A browser-safe MP4 (H.264 + AAC/mp3
  in `.mp4` / `.m4v`) is `not-applicable`: the viewer plays the original
  and no playback file is stored. When a stored playback is still
  needed it is full-length H.264 + AAC with a size policy: longest
  side at most 1280, CRF 23, AAC 128k. Remux (bitstream copy) only
  when the source is already those codecs, already ≤1280 wide, and
  under 80 MiB — never a silent multi-GB duplicate of a 4K phone
  clip. Encode leftovers (`*.tmp`) are removed on success, failure,
  and the next drain. The original file stays on disk.

Opening the item starts the proxy immediately, then swaps to the original
when the browser can decode it, otherwise to `playback.mp4`, keeping time
and fit. `#viewer-source` says Preview, Loading full…, Original, Full
(library H.264/AAC), or Preview — full unavailable.

Renditions are queued by the scan and continue while the server is running.
The grid shows a placeholder until the thumb exists, then the thumb.
Queued thumbnails say “Creating preview…”; a failed or missing preview has
the unavailable message instead, so waiting work is distinguishable from failure.
Grid thumbnails and video posters take priority across the folder, ahead of
viewer previews and full-length video encodes. They begin while the folder
is still being scanned. Reading original bytes and encoding previews leave
catalog and media requests free to respond; catalog publication stays serialized.
Processing names the current derivative (thumbnail, poster, preview, proxy,
or playback), and each queue shows completed, waiting, and failed work.
Reading queue status does not hash or decode original pictures. Object counts
use completed analysis records keyed by catalog item identity; the worker still
checks its actual input when it runs. Optional queues never delay thumbnail work
just to calculate their displayed counts.
Status polling keeps at most one poll in flight so a slow response does not
build up a backlog of requests.

**Processing speed.** Measured on the family PC against a fixed fixture:
80 of Steve's own JPEGs (about 3.5 MB each) plus one iPhone `.MOV`, added
as serve-from-folder with previews kept in the folder (the real setup).
The cost of one picture does not depend on how big the library already
is. Budgets, from the moment Add folder starts:

| What | Budget |
|------|--------|
| Reading the folder (hash + metadata + record) | at least 15 pictures/s; the last tenth of files no slower than 1.25× the first tenth |
| First grid thumbnail visible | within 3 s |
| Every grid thumbnail and the video poster | within 30 s |
| A picture opened in the viewer | its 1600 px preview within 2 s of opening, even while thumbnails are still queued |
| Everything done (thumbs, previews, video proxy/playback) | within 90 s |
| Bookkeeping per finished file (all work except ffmpeg) | at most 50 ms |
| Catalog and status requests while processing | `GET /api/jobs` p95 ≤ 300 ms, `GET /api/items` p95 ≤ 1 s |

Bookkeeping is the per-file cost of picking the next job, finding the
original, writing the record, undo history, and the folder copy of the
records. It must not re-read the whole catalog or rewrite growing files
for every picture.

**Check (speed):** `python -m tests.perf.bench` starts a scratch server on
a copy of the fixture, adds the folder through HTTP, opens one picture
mid-run, and prints each budget with its measured value and PASS/FAIL.
Exit code is nonzero when any budget fails. `--count N` changes the
fixture size; `--count 400` is the scaling run. Artifact: the bench JSON
under `docs/features/processing-feedback/Rev1.0/assets/perf-bench/`.

**Missing previews.** A preview file can disappear while its record still
says ready — most often because someone deleted a folder's `.library/`.
Library never shows a picture it no longer has: the browser revalidates
every thumb, preview, poster, and face crop with the server (ETag; an
unchanged file answers 304 without sending bytes), so a deleted file stops
showing on the next load instead of living on in the browser cache. Within
a few seconds Library notices a ready slot whose file is gone, puts it back
in the queue, Processing counts it as waiting, and the grid shows
“Creating preview…” until the new file exists. Until F23 ships, deleting
`.library/` does not forget names, faces, places, or ratings on this
computer — those live in `library-data/catalog/` and the folder copy is
written again. With F23, deleting `.library/` resets that folder (see F23).

**Check (missing previews):** `python -m tests.qa.missing_previews` adds a
scratch copy of the fixture as serve-from-folder through HTTP, waits until
Processing is idle, records a thumbnail's ETag, deletes the folder's
`.library/`, then asserts: media responses require revalidation; the old
ETag no longer gets 304; Processing shows waiting previews within 10 s;
within 60 s every slot the catalog calls ready has a non-empty file on
disk and serves 200. Artifact: `result.json` under
`docs/features/processing-feedback/Rev1.0/assets/missing-previews/`.

Years, Months, Days, and a Dates-off wall play the proxy, muted and
looped, on the cell under the pointer. `playProxies` changes that:
`days-and-all` (default) and `always` both hover-play at every Dates
grouping; `off` never does. Hover playback fills the whole
tile at every Size stop; the still stays underneath as a poster. The tile never splits still on
one side and video on the other. Every video cell shows a VIDEO badge; live
cells keep LIVE. A small scrub on the hovered tile seeks that preview.

**Check:** `python -m tests.qa check F7` (planned runner; common root/artifact
arguments and full assertions in SLICES). after scan of one JPEG and one 2-second MP4, these files exist and
are non-empty: `thumb.webp`, `preview.webp` for the JPEG; `poster.webp` and
`proxy.mp4` for the video. The proxy's width is at most `proxyWidth`, it
has no audio, and the file stays under a small size bound. The MP4 does
not get a `playback.mp4`. Artifact: ffprobe JSON for the proxy plus the
file sizes.

## F8 — Where preview files are stored

Setting `previewStore`:

| Value | Files land in (F23 folder library) |
|-------|----------------|
| `with-server` (default) | `library-data/folders/<folder-name>-<source-id>/` |
| `with-source` | `<selected-folder>/.library/` |

A source JSON field `previewStore` overrides the global setting when it is
not null. Choosing **Serve from that folder** sets that source to
`with-source`. **Copy onto this drive** keeps its folder library inside the
copy's `.library/` either way (the copy is already on this drive).

Each item records which folder library holds its files
(`renditions.store`: `folder-source` or `folder-server`). Changing the
setting sends new files to the new place; files already made stay where
they are and keep working. `renditions relocate` moves existing preview
files and the item's `<name>.json` to match the current settings, and undo
moves them back. Originals are not moved by this command. Items still in the
old layout (`with-server`: `library-data/renditions/<id>/`, `with-source`:
`.library/renditions/<id>/`) are read and relocated as before until
migration (F23) renames them.

If previews were stored with the source and that disk is absent, the item
record remains and the media call for the thumb returns
`{"error":"preview-unavailable"}`.

**Check:** `python -m tests.qa check F8` (planned runner; common root/artifact
arguments and full assertions in SLICES). set `previewStore` to `with-source`, scan a folder, and see the
thumb as `<name>.thumb.webp` in that folder's `.library/`. Run `renditions relocate`
after setting `with-server`. The thumb and `<name>.json` are under
`library-data/folders/` and gone from the source tree; undo puts them back.
Artifact: both directory listings, before and after.

## F9 — Zoom

One Size slider steps cell pixels (eight useful stops: 72, 104, 144,
192, 256, 336, 420, 520). Ctrl+wheel on the grid drives that slider
only. Size does not change date grouping. Size is a session view option,
not a settings.json key. Size and Dates sit together at the **bottom
of the library grid** (bottom-left cluster).

Date grouping is a separate `#date-group` control: Years, Months, Days,
or Off. It is not a second zoom slider. Years is one card per year.
Months is one card per month. Days is a header per day and the photos
from that day. Off cascades every matching thumb onto one continuous
wall — no date-section gaps. Years/Months/Days persist in `zoomLevel`
(`all` remains a valid API/settings value and displays as Days). Off is
session-only.

`#arrange` Group Date / People / Places / Tags (session-only, default
Date) draws one header per date, person, place, or tag on the current
set, plus Unknown / No place / Untagged. An item lands in one group.
Click any group header to collapse or expand it; remembered for the
session. This is the only arrangement control. Sort stays Newest /
Oldest / Name / Location. Search lives on `#filter-bar` and does not
duplicate Group.

Changing Dates or Size must keep already-loaded thumbnails on screen;
the grid does not blank during the interaction. The item under the
cursor stays in view when Dates changes.

Tiles that are large enough (Size 144 px and up) show a heart control in
the same corner language as the VIDEO/LIVE badge — under or beside that
badge. At the two tiniest stops (72 and 104) the heart hides so a wall
stays readable. Clicking the heart marks or clears the item; it does not
open the viewer. A Favorites section sits at the top of the Library grid
whenever any current result is hearted. It starts expanded and can
collapse to its heading. Hearted items also stay in their date or wall
positions. Ctrl+Z undoes a heart.

Library and Globe in the header are view toggles, not plain labels: hover
and active/click states are visible, and the pressed view stays marked.

Reference: [years](reference/library-years.jpg), [grid](reference/library-grid.jpg).

**Check:** `python -m tests.qa check F9` (planned runner; common root/artifact
arguments and full assertions in SLICES). a fixture library spanning two years. `GET /api/groups?level=years`
returns two groups. `level=months` returns one group per month that has items.
`level=days` and `level=all` return one group per day. Artifact: the four
JSON responses.

## F10 — Open a picture

Click a cell to open the viewer. Previous and Next sit at the **bottom** with
Rotate, Windows Photo Viewer style. Arrow keys move in the current sort and
stop at the ends. Back (and Esc) returns to the grid he came from on the
**same** live origin and port. Browser Back does the same while the page is
open; it must not load a stale port or call a hop that leaves this listen URL.

The viewer chrome is Windows Photo Viewer–ish. Previous and Next sit at
the **bottom**; Left/Right arrows still change photo and stop at the ends.
Rotate sits next to them (button or Ctrl+R). Zoom is a **vertical side slider** (with percentage) plus
**plain wheel** (primary), Ctrl+wheel and Ctrl++/− — not discrete
zoom-in/out buttons, including smaller than fit. The slider does not
sit on the bottom scrubber. Ctrl+0 fits; Ctrl+1 is 100%. Click-hold
pans while zoomed. Rotate turns the displayed still 90° and does not
change the file. F11 or F toggles fullscreen; Esc leaves fullscreen,
then the viewer. F5 starts a slideshow; Space pauses it; Esc stops it.

A heart in the viewer favorites or unfavorites that item. The mark is
stored in `catalog/favorites.json` and is visible on the heart.

For a photo the viewer shows `preview.webp` first, then the original if
available, with no “Showing original” button or notification. Reveal in
Explorer and Open sit side by side. Reveal opens the original's containing
folder on this computer whenever the file is here (`explorer.exe` argv
`/select,fullpath` on Windows — comma glued, no extra quotes, so paths
with spaces still select the file). Open launches that file in the computer's default app. Delete
removes the catalog record (confirm; bytes stay). Delete file extra-confirms
and Recycle-Bins the original. For video the viewer shows the poster, then
starts the proxy and swaps to the original when the browser can decode
it, otherwise to `playback.mp4` (full quality + sound). `#viewer-source`
beside the filename says Preview, Loading full…, Original, Full, or
Preview — full unavailable. A silent proxy is never labeled Original. Play preview still
toggles pause/play on click. `#viewer-scrub` sits in `#viewer-bottom`
and seeks at any zoom or source. It does not overlay the picture.
Ctrl+wheel zooms the picture, anchored at the cursor. Middle-click drags
it; a still also pans with a left drag, and any zoomed item pans with a
left drag. Click a video, or press Space (when no slideshow), to play or
pause. Playback of a video uses the original when the browser can decode
it, otherwise `playback.mp4`, otherwise the proxy.

Person, Place, and Thing are **not** pills painted over the preview. A
top-right **Info** control shows file facts first (date taken, camera,
dimensions, size, path, GPS; empty “No camera info for this file.”), then
the people, places, and things already written on the record; clicking
one filters the grid to that entity. The three type-in fields stay inside
Info and stay labeled Person, Place, and Thing. Tooltips name the shortcuts.

**Check:** `python -m tests.qa check F10` (planned runner; common root/artifact
arguments and full assertions in SLICES). `GET /api/media/<photo-id>?which=preview` returns image bytes.
`GET /api/media/<photo-id>?which=original` returns the original bytes when the
source is available. Artifact: both responses' content types and lengths.

## F11 — Sort

The toolbar’s presentable sort labels are Newest, Oldest, and Name
(`sort=date&dir=desc`, `sort=date&dir=asc`, `sort=name`). Location sort
stays available. Default is Newest. Filters All / Photos / Videos /
Favorites are mutually exclusive: no kind, `kind=photo,live`,
`kind=video`, or `favorite=1`. They keep the current sort among those
items.

Date uses `capturedAt`. Location groups by place name, then unnamed GPS
places, then "No location", and by date inside a group. Name uses the filename.

**Check:** `python -m tests.qa check F11` (planned runner; common root/artifact
arguments and full assertions in SLICES). three fixtures with dates June 2024, June 2023, and no EXIF.
`GET /api/items?sort=date&dir=desc` returns the 2024 item first. The no-EXIF
item's `capturedAtSource` is `mtime` and it sorts by that time.
Artifact: the items JSON.

## F12 — Globe

A Globe view draws every place that has coordinates. The earth is a WebGL
globe with a **realistic** equirectangular Earth texture shipped as
`library/web/assets/earth.png` (license beside it). Abstract blob continents
are not presentable. The page does not load map tiles and does not send
coordinates anywhere. Drag spins the globe: left-right yaw is inverted from
the first grab (drag right turns the globe so the surface follows the pointer
east); up/down pitch is unchanged. The wheel zooms it, and the point under
the cursor stays put.

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
The server does not ship a model and does not guess names. After a
one-time local install, optional workers on this computer may write
associations through the same catalog:

- `setup-geo` / `analyze-places` fills a null GPS `place.name` from the
  offline cities pack. It never overwrites a human or agent name.
- `setup-ml objects` / `analyze` looks at each still and writes Things
  through annotate. Name-only payloads reuse an existing thing id.
  Human tags stay. The COCO `person` class is ignored.
- `setup-ml transcribe` / `transcribe` runs only on videos with an
  audio stream. faster-whisper `small` detects language (Chinese and
  English at least), stores timestamped segments/words on the item
  `transcript`, and writes a one-or-two-sentence **extractive** summary
  plus keywords (no local LLM, no cloud). Same size+mtime is skipped.
  `transcribeVideos` (default true) turns the Transcribe queue off.
  Search matches those words; results show **Said in video**.
- `setup-ml aesthetic` / `rate-photos` scores photo and Live stills.
  Basic (default) combines Laplacian sharpness (normalized per
  resolution), histogram exposure, and face size/sharpness from
  existing detections into a suggested 1–5 plus flags (`blurry`,
  `too-dark`, `too-bright`). Smart blends that with a local NIMA
  ONNX score. `ratingMode` `off|basic|smart` (default `basic`) turns
  the Rating queue off or picks the stage. Same size+mtime is
  skipped. User stars / pick / reject always win. Reject only hides
  from default views; the file stays. Never auto-deletes or
  auto-rejects. Live/burst stacks and duplicate groups mark a
  suggested best-of-group. `ratingLearn` (default false) may nudge
  local suggestion weights from picks and rejects; reversible.
- `setup-ml faces` / `infer-faces` detects faces on the full frame
  fitted to 640×640, maps boxes back to the original, then
  landmark-aligns / crops **original** pixels to 112×112 for ArcFace.
  Large stills also run overlapping 1280 tiles (merged with NMS) so a
  small face in a high-res phone photo is not crushed by the 640 pass.
  Embeddings live in `models/faces/index.json`. Cosine must be strictly
  above `faceMatchThreshold` (default **0.80**). Small or weak detections
  need a clearer score before they join an already-named person. A human
  confirms every name in the People panel or Info. Faces never leave
  the machine. After changing the slider, Processing **Re-run Faces**.

Browse stays up when models or the geo pack are missing (`models-missing`
/ idle queues). Processing Pause/Start on `/api/jobs` starts or stops
the real serve-time drains. Processing also shows the file in progress
(`GET /api/activity`: phase, filename, done/total, and seconds on that
file) and the listen address of this Library server. The folder read
names each picture as it is hashed. Later queues name the picture
whose preview, place, face, objects, transcript, or rating is running.

Exact person, place, thing, item and annotation payloads are in
[CONTRACTS](CONTRACTS.md#source-entity-settings-and-history-records). Names can be
empty until somebody supplies them. The records stay readable JSON.

`box` is x, y, width, height, each from 0 to 1, on the oriented picture.
It may be omitted. A face is a box that points at a person. A person with
`"name": null` is an unnamed face. Setting the name updates that person file.
`people merge <keep-id> <drop-id>` rewrites every face, merges stored
face embeddings when `models/faces/index.json` exists, and deletes the
dropped person file. `people split` takes one boxed face off a person
and writes it as a new Unnamed person; the original person (Steve, Ada)
stays. The People panel **Merge into…** confirm (two or more selected)
runs the same merge. **Review matches** steps suggested pairs
(Merge / Not same / Skip); nothing merges until Merge. **Not this person**
on a profile or Info crop runs split. With two or more people selected, the grid still ANDs
(`person=id1,id2`) and shows a collapsible **Photos together** group
(intersection) above leftover photos for each selected person.

The Library page lists people in a right side panel. Named people always
appear. An unnamed cluster appears only when that face is on at least
`personOfInterestMin` photos (constant 3). Click filters to that face;
clicking a selected person again removes that filter. Selecting several
people keeps photos that contain all of them. Active people, places, and
tags show as chips on `#filter-bar` with one-click remove and Clear all.
The panel is where unknowns are named and a thumbnail face is chosen
(square `which=face&box=` crops, not a CSS zoom of the whole thumb).
Info still names a person on the open item.

User tags (Hiking, Singing, Painting) are Things: create, apply or remove
on one item or a multi-selection, filter by chip, group by tag. They
persist in the catalog and survive objects/faces re-infer.

Naming a thing reuses an existing thing id when the name matches,
case-insensitively, including aliases. Otherwise annotate creates the thing file.

**Check:** `python -m tests.qa check F14` (planned runner; common root/artifact
arguments and full assertions in SLICES). `annotate <id> --person Ada --thing mug` creates `people/person_*.json`
with `"name": "Ada"`, `things/thing_*.json` with `"name": "mug"`, and the item
lists those ids. A second item annotated `--thing mug` reuses the same thing id.
`GET /api/items?thing=mug` returns both ids and no others.
Artifact: the people file, the thing file, and the search JSON.

## F15 — Search

The search box lives on `#filter-bar` and matches a person, place, or
thing name, a filename, a capturedAt date (`YYYY`, `YYYY-MM`,
`YYYY-MM-DD`), or words in a video transcript / extractive summary /
keywords. A transcript hit shows **Said in video** on the tile; opening
it seeks the viewer to that timestamp. Chinese query text matches those same fields. A local
city/region written on a GPS place is a place name. Built-in labels
(Unnamed / 未命名, Unknown / 未知, No place / 无地点, Untagged /
无标签) also match. `scope=people|places|things` remains on the API.
Empty results say “No matches for …”. Reference:
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
a banner "Original is not on this computer", and Open with default program
and Reveal do nothing. Play preview plays the proxy for a video. Reference:
[unavailable](reference/library-unavailable.jpg).

**Check:** `python -m tests.qa check F16` (planned runner; common root/artifact
arguments and full assertions in SLICES). a source JSON with a volume serial that is not mounted.
`GET /api/sources` marks it unavailable. With `unavailableItems=show`,
`GET /api/items` includes the item. `GET /api/media/<id>?which=original`
returns 404 `unavailable`. Set `hide` and the item disappears from
`GET /api/items` until `unavailable=1`. Artifact: the three responses.

## F17 — Settings

`library-data/settings.json` holds the 17 browse settings (the earlier 16
plus `language`) plus the internal `schemaVersion: 1` field (not a
control), two face-quality keys used by optional local InsightFace,
`transcribeVideos` (default true) which turns the Transcribe queue on or
off, `ratingMode` (`off|basic|smart`, default `basic`) which turns the
Rating queue on or off, and `ratingLearn` (bool, default false) which
optionally nudges local suggestion weights. `sort` also accepts
`rating`. The defaults below list those values. The header language switch writes
`language`. The command line edits this file, including
`faceMatchThreshold` (default 0.80, Settings slider 0.35–0.95) and
`faceMinSidePx`, so matching can be tuned without a rebuild. Higher
threshold means fewer false merges and more Unnamed people. The browser
does not keep a second copy. A pre-language file is filled with `en` on
load. A pre-transcribe file is filled with `transcribeVideos: true`.
A pre-rating file is filled with `ratingMode: "basic"` and
`ratingLearn: false`.

The **Settings** page (`#settings-view`, Ctrl+, / header Settings) is
the family chrome for this file. **Folders / sources come first:** every
catalog source with lastKnown path, available?, mode (copy-here vs
serve-from-there), photo/video counts, how many items have finished core
previews vs still queued or error, and last scan state (running /
complete / error + added/skipped). **Add folder** uses the same dialog
as the header. **Refresh** calls `rescan` on that source (skip unchanged;
do not delete library-data). **Remove folder** is catalog-only. Other
settings.json keys are controls on the same page; `previewStore` says
where new renditions live. Language stays in the header.

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
  "zoomLevel": "years",
  "language": "en",
  "faceMatchThreshold": 0.8,
  "faceMinSidePx": 80,
  "transcribeVideos": true,
  "ratingMode": "basic",
  "ratingLearn": false
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
them. Undo of remove-from-library restores the catalog record. Undo of
delete-file restores the catalog only — not the Recycle-Binned bytes.

Esc cancels the innermost active interaction: confirm dialog, Info,
slideshow, fullscreen, tour or gesture, Add dialog, viewer, settings, then
selection. Text fields retain their standard editing shortcuts. Delete
removes from the library after confirm. Delete file is a separate extra
confirm.

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
both paths are stored on the item. Burst stills (sequential names, close
`capturedAt`) and unpaired same-stem still+short-video pairs share one grid
tile with a badge; the viewer expands the stack. Originals and item JSON are
not rewritten.

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
| Ctrl+wheel on the grid | Change Size (density), cursor stays put |
| Ctrl+wheel, plain wheel, or Ctrl++/− in the viewer | Zoom the picture, cursor stays put |
| Ctrl+0 / Ctrl+1 | Fit / 100% in the viewer |
| V | Toggle Fit / Fill in the viewer |
| ? | Open the keyboard cheat sheet |
| I / Alt+Enter | Toggle Info |
| Ctrl+R | Rotate the displayed still 90° |
| Middle-click drag | Pan the open picture |
| Click a cell | Open it |
| Click or Space in the viewer | Play or pause video (Space pauses a slideshow if one is running) |
| Arrows | Previous and next open item |
| 1–5 | Rate the open picture (user stars always win) |
| P | Pick |
| X | Reject (hide from default views; never deletes) |
| 0 | Clear your rating / pick / reject |
| F11 or F | Toggle viewer fullscreen |
| F5 | Start slideshow of the current set |
| Delete | Remove from library (confirm; originals stay) |
| Esc | Confirm, keyboard help, Info, slideshow, fullscreen, tour/gesture, dialog, viewer, settings, then selection |
| Ctrl+F | Search |
| Ctrl+, | Settings |
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo |
| Ctrl+C | Copy the primary path |
| Ctrl+P | Print the open viewer still, fit to the page |
| Esc during the tour | Stop the tour and stay on the globe |

F is fullscreen, not favorite. `?`, V (Fit/Fill), I / Alt+Enter, and
Ctrl+P print are presentable chrome, not F21 extras.


**Check:** `python -m tests.qa check F21` (planned runner; common root/artifact
arguments and full assertions in SLICES). Drive every key and gesture in the table in the browser, including focused-text exceptions, cursor anchors, pan, clipboard, and Esc during each tour phase. Artifact: input trace, clipboard text, numeric measurements and screenshots.

## F22 — Web pages

One page, five views. The address is the live listen host and port. Back
and every in-page link stay on that origin; do not leave stale port links.

| View | What you see |
|------|----------------|
| Library | The zoomed grid, Add folder, sort Newest/Oldest/Name/Location, language English/中文, `#filter-bar` (Search, All/Photos/Videos/Favorites, Person/Place/Tag chips, Clear all, Group Date/People/Places/Tags), Size and Dates Years/Months/Days/Off in the bottom-left cluster, right People + Tags panel (each section collapsible; Tags start collapsed) and processing Pause/Start, Favorites section, Update Library and the checkout SHA. Header Library is a pressed button when this view is current. |
| Globe | The WebGL earth, clusters, Play for the tour. Header Globe is a pressed button when this view is current. |
| Viewer | One item, preview then original, bottom Prev/Next/Rotate, vertical side zoom slider with %, bottom video scrub, fullscreen, slideshow, Info (file facts then names), viewer heart, Reveal and Open side by side, Remove / Delete file. Presentable chrome: [UI-SPEC](UI-SPEC.md#windows-presentable-shell). |
| Search | The same grid, filtered. Inspector for the person, place, or thing. |
| Settings | Folders/sources first (path, available, mode, counts, preview progress, last scan, Add, Refresh, Remove), then the settings file as controls. |

Add folder matches [library-add-folder.jpg](reference/library-add-folder.jpg).


**Check:** `python -m tests.qa check F22` (planned runner; common root/artifact
arguments and full assertions in SLICES). Visit all five views and every state in UI-SPEC, including empty/scanning/ready/missing original/missing preview and recoverable errors. Reference extras must be absent. Artifact: inspected screenshots, console and offline network logs.

## F23 — Folder library

Every folder Library knows has one **folder library**: a flat folder whose
file names say which picture they belong to. For a folder served from where
it is, it is `<folder>/.library/`. For a folder copied onto this drive it is
the `.library/` inside the copy under `library-data/originals/`. For a folder
that cannot be written to (or `previewStore` `with-server`) it is
`library-data/folders/<folder-name>-<source-id>/`. Same layout everywhere.

```text
J:\Pictures\Favorites\
  IMG_0456.JPG
  IMG_0457.MOV
  2023\IMG_0001.JPG
  .library\
    index.html                  # open in any browser, no app needed
    index.js                    # the data index.html reads
    folder.json                 # this folder: id, name, last scan
    people.json                 # people used in this folder (names, ids)
    places.json                 # places used in this folder
    things.json                 # tags/objects used in this folder
    IMG_0456.JPG.json           # everything known about IMG_0456.JPG
    IMG_0456.JPG.thumb.webp
    IMG_0456.JPG.preview.webp
    IMG_0457.MOV.json
    IMG_0457.MOV.poster.webp
    IMG_0457.MOV.proxy.mp4
    IMG_0457.MOV.playback.mp4   # only when the original will not play in a browser
    2023\IMG_0001.JPG.json
    2023\IMG_0001.JPG.thumb.webp
    2023\IMG_0001.JPG.preview.webp
```

**Names.** Each generated file is the picture's path inside the folder, with
its extension, plus a suffix: `.json`, `.thumb.webp`, `.preview.webp`,
`.poster.webp`, `.proxy.mp4`, `.playback.mp4`. Subfolders are mirrored. A
Live Photo is named after its still (`IMG_0456.JPG.*`); its `.json` lists
both files. Folder-level files never end in a picture extension plus suffix,
so they cannot clash with a picture's files.

**`<name>.json`** is the record for that picture, readable by a person:
file name, size, modified time, content fingerprint (SHA-256), date taken,
camera facts, the place by name and coordinates, the people by name with
face boxes, tags, rating and stars, heart, and processing status. Ids for
places and people are kept beside the names so the app can link them.

**Where the truth lives.** For its pictures, the folder library is the only
record. `library-data/` keeps settings, undo, models, logs, the library-wide
people list (one person across many folders), and `catalog.sqlite`, a speed
index rebuilt from the folder libraries. Delete a folder's `.library/` and
that folder starts over: its pictures are read and processed again, and its
names, faces, places, and ratings are gone. Move the folder, or open it on
another computer, and everything comes with it.

**Identity.** The fingerprint inside each `.json` is how Library knows a
picture. Rename or move a picture inside the folder and the next scan finds
it by fingerprint and renames its generated files to match; nothing is made
again. The same picture in two folders has a folder library entry in each;
stars, hearts, and names written to it are written to every copy.

**Migration.** A folder in the old layout (`.library/catalog/` and
`.library/renditions/<id>/`, or `library-data/catalog/items/`) is moved to
this layout on first launch after the update, folder by folder: files are
renamed into place, never regenerated, and the old folders are removed only
after every file is verified. A crash mid-migration resumes; undo history
from before the migration stays readable.

**`index.html`.** Opening it from Explorer shows that folder's pictures as a
grid of thumbs; clicking one shows its preview, date, place, people, and
rating. It works from `file://`, offline, with no server. It is rewritten
when processing is idle.

**Check:** `python -m tests.qa.folder_library` on a scratch copy of the
fixture with a subfolder, a Live Photo pair, a video, and a duplicate in a
second folder. It asserts: every picture has `<name>.json` and its derived
files under the names above; no fingerprint-named file or folder exists;
renaming a picture renames its files without re-encoding (byte-identical);
deleting `.library/` resets that folder (Processing re-queues it, names and
ratings for it are gone, the other folder keeps its own); an old-layout
fixture migrates with every rendition byte-identical and nothing
regenerated; `index.html` opened through `file://` in a browser shows the
grid and one picture's info. Artifact: before/after directory listings,
hashes, and an `index.html` screenshot under
`docs/features/folder-library/Rev1.0/assets/`.

## What the first build includes

Every F1–F22 Check above. The exact fixture set and scenarios are in
[FIXTURES.md](FIXTURES.md); it is a specification today, not files already made.
All checks use a fixture-owned temp library and never a real photo disk.

Build in [SLICES.md](SLICES.md) dependency order. First taste is small fixture
pictures on screen and one photo opened; names and globe come later. The
family-PC gate after A+B+C is the UI-SPEC **Presentable for family PC**
checklist — close gaps on that path before treating S13 settings as the
next taste job. Then continue to 100% (22/22) fresh-verifier-backed
Checks. [STATUS.md](STATUS.md) records what actually passed, not what the
help file promises.
