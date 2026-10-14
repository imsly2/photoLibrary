# Library — contracts

Spec locked 2026-10-12. Nothing here is implemented yet. [PRODUCT.md](PRODUCT.md)
owns scope; this file owns wire and disk shapes. Fields below are exhaustive;
an unlisted field, setting, route, or error requires a spec edit before code.

## Decisions the earlier help file left open

| Decision | Locked answer and reason |
|---|---|
| Package and page | Python `library/` package, `library/__main__.py`, static assets in `library/web/`, `pyproject.toml`, root launchers. Serve `/` and `/assets/*` from that package, same origin as `/api/*`. No separate web server or Electron. Default root is `<app-folder>/library-data` beside the launcher regardless of working directory; it is ignored by git. Explicit --root overrides it. |
| Shared operations | CLI and HTTP call one application service. A running server is the sole catalog writer; CLI mutations forward to it. Offline CLI takes the same root lock. No two writers. |
| Pending names | Use `pending-<sourceId>-<path-digest>` where path-digest is lowercase SHA-256 of normalized relative-path UTF-8. This bounds filenames even for long or Unicode paths; never embed raw separators. Hash finalization is a recoverable transaction, including annotations and rendition references. |
| File identity | Final item id is lowercase SHA-256 of bytes; location identifies source + relative path + component. Live Photo id is the still hash. Same path with changed bytes is a new item, not permission to transfer old annotations. |
| Source identity | `src_` plus 12 random lowercase hex digits, persisted and reused for the same volume identity + selected relative directory. Copy destination is `originals/<safe-name>-<source-id>/` to avoid same-named source collisions. |
| Copy resume | Persist source-to-destination mappings before publishing catalog changes; resume verifies completed copies by hash. A partial file never counts as an original. Existing unrelated files use `_2`, `_3`, etc. |
| Availability | Test existence of individual components, not merely the drive. Resolve again on source/item/media requests, so unplugging after launch is reflected. A present duplicate can serve an absent primary without changing identity. |
| Preview ownership | A deduplicated item has one rendition set. Use its primary still/photo/video source's override or the global setting. Relocation verifies destination bytes before removing old generated files. |
| Scan progress | Persist progress in the source record; HTTP POST starts work and returns 202 before the scan finishes, with `scan.state` running. Poll sources; no additional jobs screen/API. Reads (items, groups, sources, settings, media, health) stay available during scan. CLI waits for completion and prints the final summary. The serve process prints scan progress lines on stdout during normal work, not only on failure. |
| Client disconnect | A client that aborts a response (`BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError`, WinError 10053) is non-fatal. Do not write 500, do not treat it as `internal-error`, and do not stop the server. |
| Folder picker | `POST /api/pick-folder` `{}` opens the server computer's native folder dialog on Windows and returns 200 `{path}` or `{path:null}` if cancelled. Non-Windows or no UI returns 404 `picker-unavailable`. Typed paths remain valid. No upload. |
| Family update | `GET /api/update` reports `{ok,branch,revision,dirty,message,git_sha,git_branch,git_date}` for the app-folder git copy (`revision` / `git_sha` are the short checkout SHA). `GET /api/version` is the same tip for the header: `{ok,git_sha,git_branch,git_date,git_subject,label}` (`label` is the SHA, or `local` when this folder is not a git copy). `POST /api/update` `{}` fetches and fast-forwards the **current** branch only (`git pull --ff-only`). 200 always, with `ok` true/false, a family-readable `message`, and the new `git_sha` on success. Never force, never checkout another branch, never a command prompt. Missing git or a non-git folder is `ok:false`, not a crash. Pull does not restart the serve process; the header refreshes the SHA from the response. |
| Open default | `POST /api/items/<id>/open` `{}` launches the current original with the OS default program (`os.startfile` on Windows). 200 `{path,opened}` or 404 `unavailable`. |
| Windows double-click | `Library.bat` at the app folder starts `launch.ps1` in a visible console and opens the browser. F2 still grades `powershell -File launch.ps1`. Do not claim macOS/Linux launch from this change. |
| Portable Setup | `Setup.bat` once on a PC (via `setup.ps1`) installs Python 3.12+ / ffmpeg with the same winget ids, creates `.venv`, `pip install -e .`, then calls `python -m library setup-geo`, `setup-ml objects`, and `setup-ml faces` when those commands exist. Missing commands print that Update Library must `git pull` them and exit 1. `-Help` / `-DryRun` do not download. Does not start serve. No MSI. Models stay under `library-data/`. |
| Live page origin | The page is same-origin with `/api`. Navigation, History API, Back, and links use the current `window.location.origin` or root-relative paths. Never construct `http://<host>:<settings.port>` or a stored runtime URL from another listen. Browser Back while this document is open stays on that origin (close viewer or remain on the grid); it must not load a stale port such as 18765 when the server is on 8765. |
| History | One user operation is one durable transaction; automatic scan progress/hash/rendition updates are not separate undo steps. Scan/copy undo never removes original bytes. History replay must preserve later scan-derived identity. |
| Dates | Preserve floating EXIF time without inventing a zone. Normalize explicit offsets to UTC; mtime uses UTC. Date-only filenames mean midnight. Date grouping uses the stored calendar date, independent of browser timezone. |
| Days vs All | Both include every matching item under day headings when Dates is Years/Months/Days. The page Dates control is Years / Months / Days / Off; `all` remains a valid `zoomLevel` / groups API value and displays as Days. A session Size slider is the only density control and does not change Dates. Dates Off flattens the current item set onto one continuous wall. No representative-photo selection algorithm. |
| Search chips | Add `scope=people|places|things` to `items` and `groups` for the already-described chips. No scope means names plus filenames. Filters combine with AND, values within a place list with OR. |
| Annotate semantics | Add associations, reuse named entities deterministically, optionally rename an explicit entity id. Optional local workers (after one-time `setup-geo` / `setup-ml`) may write associations: GPS city names only when `place.name` is null; YOLO Things through name-only annotate (COCO person ignored); InsightFace unnamed face clusters. No name guessing, caption system, gender/age labels, or box-drawing tool. Faces and pixels never leave the machine. |
| Local place names | Optional offline GeoNames-class cities pack in `library-data/geo/` (fetched by `setup-geo`, never shipped in git). When the pack is present, scan / `resolve_place` / `analyze-places` may set `place.name` to city/region **only when that name is null**. Never overwrite a nonempty name. Never call a cloud geocoder. Missing pack leaves name null. Not a settings key. Not an image model. |
| Live pairing | Same Apple content identifier within the same source pairs still + movie across scan order/restart. Filenames alone never pair. Locations need a component discriminator. |
| Playback | Full-length silent proxies as PRODUCT says; the convention's word “short” means low-resolution, not truncated. When the original is not a browser-safe MP4 (H.264 + AAC/mp3), a full-quality `playback.mp4` is generated (same pixel size, H.264 + AAC; remux when the bitstream already allows). Viewer starts on the proxy, then the original if the browser can decode it, else `playback`. The badge names Preview / Full / Original honestly. Originals stay on disk. |
| Platform promise | Windows is the primary acceptance platform. Keep the described macOS/Linux launchers; their launch and volume identity tests need those platforms before F2 can pass in full. Missing runners are recorded, never counted green. |
| API completion | Exact responses, annotation payload, merge route, range requests, and error table below fill missing technical details, not new user features. |
| Port conflict | Keep 8765 default. Reopen a healthy matching-root server; a different service/root produces `port-in-use`. Never kill it or silently choose a port. |
| Settings scope | Keep the 16 browse settings. Do not add a keybinding editor, authentication, accounts, remote hosting, or albums because a reference mentions them. A per-item favorite heart (`catalog/favorites.json`) and Windows Reveal in Explorer are named actions, not settings. Optional local geo/objects/faces stay pack/model switches. Two face-quality keys (`faceMatchThreshold`, `faceMinSidePx`) also live in settings.json so InsightFace matching can be tuned without a rebuild; they are not F17 page chrome. |
| Favorite | One catalog file, not an item field and not a setting. `{schemaVersion:1,itemIds:[…]}` unique ids sorted lexically. Missing file means none. Item reads add computed `favorite`. `PUT` or `POST /api/items/<id>/favorite` `{favorite:bool}` is one undoable `favorite` history operation. Viewer heart, tile hearts, and the Favorites section share this file. Pending-id hearts remap to the hash id on publication. Unknown id is `not-found`. `favorite=1` on items/groups keeps hearted items; omitted means all. |
| Reveal in Explorer | Windows action that selects the current original path, or `lastKnownPath` when the original is away, in Explorer. No-op when no path exists. Does not copy, move, or upload. |
| Globe drag | Horizontal drag: rightward motion increases yaw (0.25 deg/px). Vertical drag: upward motion increases pitch. Texture is the shipped local `earth.png`. |
| Presentable shell | Family-PC chrome is specified in UI-SPEC **Windows Presentable Shell**. No 17th setting, no Electron, no accounts. Must remove / delete-file routes are below. Slideshow, fullscreen, viewer keys, Info facts, and Update progress are page chrome on existing APIs (item reads already carry capturedAt, camera, dimensions, size, path, GPS). Soon rows that need a new route (copy-file-to-folder) still wait for an edit here. |

## Files and atomic writes

All JSON is UTF-8, one object per file, schemaVersion `1`. Unknown fields and
invalid types are rejected on application writes. Existing invalid JSON stops the
operation with `invalid-catalog`; it is never silently discarded. The SQLite
schema is private and disposable; it must not become a second source of truth.

`settings.json`, source/item/entity JSON and `undo/entries/<id>.json` are canonical.
`undo/state.json` stores history order/cursor. `runtime.json` and `write.lock` are
runtime coordination only. `.transactions/<id>/manifest.json` and before/after
files are recovery material, removed after successful recovery/commit. No fixture,
real catalog, original, generated rendition, runtime file, or log enters git;
only intentionally supplied test media under `tests/fixtures/` may be tracked.

Writes use a temporary sibling, flush, then atomic replacement. Multi-file writes
use a prepared manifest `{schemaVersion,id,state,changes}` where state is
`prepared|committed`, changes use the same shape as history below. Recovery rolls
prepared changes back and committed changes forward before serving any request.
SQLite rebuilds after recovery. Test interruption at each boundary.

Runtime record: `{schemaVersion,pid,root,url}` with absolute normalized root;
lock ownership is enforced by the OS, not presence of a stale file. CLI checks
the root in this record against `/api/runtime` before forwarding. This read-only
route returns the same object. Roots and paths are local information, never sent
to third-party services.

## Ids, paths, and item records

Entity ids are `person_|place_|thing_` plus 12 random lowercase hex digits.
Normalize matching names by trim + Unicode NFC + casefold; preserve entered case
for display. New ids must be collision-checked. Never derive a person's identity
solely from a name when an explicit id is supplied.

Paths in persisted relative fields use `/`, no drive prefix, no `..`, no leading
slash. Resolve and check containment before reading or writing; do not recurse
through symlinks/junctions. A source may not be the library-data directory or
inside it; recursively exclude the actual configured data root and every
`.library` directory, not just a coincidentally named folder.

`volumeSerial` means a stable volume identifier: Windows serial with platform
prefix `windows:`, macOS volume UUID `macos:`, Linux filesystem UUID `linux:`.
Mount paths/drive letters are lookup results only. Unsupported identity lookup
fails `volume-identity-unavailable`; never quietly persist the current letter.

Item fields (all required except box):

| Field | Shape |
|---|---|
| schemaVersion, id, kind | `1`, pending or final id, `photo|video|live` |
| filename | Original primary display basename; unchanged when a copy collision renames its destination |
| capturedAt, capturedAtSource | ISO timestamp; `exif|filename|mtime`; CreateDate also maps to `exif` |
| placeId | place id or null |
| metadata | `{width,height,orientation,camera,lens,durationSec,latitude,longitude}`; unknown values null; orientation 1–8; positive pixel sizes; seconds nonnegative; GPS within latitude ±90 and longitude ±180 |
| contentIdentifier | Apple identifier string or null |
| locations | Array of location objects below; one primary per component |
| renditions | Object below |
| faces | Array `{personId,box?,detScore?,matchScore?}` |
| things | Array `{thingId,box?}` |

Location: `{sourceId,role,component,kind,current,libraryRelativePath,volumeSerial,
pathFromVolumeRoot,lastKnownPath,sizeBytes,modifiedAt,sha256}`.
current is a boolean, initially true. A location known to have been replaced by
different bytes becomes current=false and remains as historical path information;
it can never serve those replacement bytes as the old picture. Role
`primary|alternate`; component `still|motion` (ordinary photo is still,
ordinary video is motion); kind `library-relative|volume`.
For library-relative only libraryRelativePath is nonnull; for volume only
volumeSerial and pathFromVolumeRoot are nonnull. lastKnownPath is absolute display
text for clipboard fallback, never resolution authority. sha256 is null until
hashed. modifiedAt is UTC ISO with filesystem precision retained; sizeBytes integer.

Boxes are `[x,y,width,height]` normalized to the oriented still or oriented video
frame: x,y >=0, width,height >0, x+width and y+height <=1. Omitted means association
without a box. Duplicate identical associations collapse; distinct boxes may share
an entity. Optional local inference may attach a box by matching a face embedding
to a stored person centroid; it never invents a name.

Renditions: `{store,sourceId,thumb,preview,poster,proxy,playback,status}`.
Store is `with-server|with-source`; sourceId selects the owning source. Paths
are relative to library-data for with-server, to selected source root for
with-source (starting `.library/`). Absent paths null. status maps those
names to `not-applicable|queued|ready|error`. Photos use thumb/preview
(`playback` not-applicable). Videos use poster/proxy plus `playback` when
the original is not a browser-safe MP4; a browser-safe MP4 marks
`playback` not-applicable. Live items use stills plus video slots. Older
records without `playback` read as that default (queued for video/live,
not-applicable for photos). An error never removes the item. Explicit
rescan retries failed renditions even if original bytes are unchanged.
Missing previews show a placeholder; no request automatically mutates the
source disk to repair them.

Favorites are a separate catalog file `catalog/favorites.json`:
`{schemaVersion:1,itemIds:[…]}` with unique item ids, sorted. Missing file is
empty. HTTP/CLI item reads add computed `favorite` true when the id is listed.
`PUT` or `POST /api/items/<id>/favorite` `{favorite:true|false}` rewrites that
file in a history transaction (`operation: favorite`) and returns the updated
item read. Unknown ids are `not-found`. Pending-id hearts remap to the hash id
on publication. `favorite=1` on items/groups keeps hearted items.

`POST /api/items/<id>/reveal` `{}` resolves the current original the same way
media `which=original` does. 200 `{path,folder,opened}` with absolute local
paths; Windows opens Explorer with the file selected, macOS `open -R`, Linux
the folder via `xdg-open` when present. `opened` is false when the OS helper
cannot run. Missing original is 404 `unavailable`. Reveal never accepts a raw
path from the client. `POST /api/items/<id>/open` uses the same resolution and
opens the file itself (`os.startfile` / `open` / `xdg-open`).

`POST /api/update` runs `git pull` in the app folder when `.git` exists.
It is not a setting. A copied folder without git returns 404 `update-unavailable`.
A 200 success body includes the new short `git_sha` (and `revision`) so the
header can refresh without restarting the server.

Availability, motion, favorite, and entity expansion are computed, not persisted:
HTTP/CLI item reads extend disk records with `available`, `motionAvailable`,
and `favorite` booleans and `entities`:
`{people:[person-record],places:[place-record],things:[thing-record]}` containing
every referenced entity exactly once, sorted by id (places empty or one). These
are the complete record shapes above/below, including names and aliases; no extra
entity-read route is needed. Inspectors query items by entity id for counts and
filenames; non-GPS places are included in this expansion even though not on globe.
Photo requires a still, video a
motion, live availability refers to its still; motion can independently be absent.
Resolve only current locations whose stored size/mtime still match the file;
a mismatch makes it unavailable until rescan, never implicitly reassigned.
Use available primary then alternates sorted by sourceId/path. Clipboard copies
the resolved primary path when present; otherwise its lastKnownPath, with notice.

Hash finalization unions locations and associations into an existing hash record,
updates history references and queued work, publishes only one item, then removes
pending JSON. Keep the existing hash record's primary per component, demoting
incoming primaries to alternates; if that component is new, keep its incoming
primary. Explicit copy conversion is the exception: the copied location becomes
primary. The existing primary source remains rendition owner. For singular
placeId, the most recent explicit place assignment in committed history wins;
history order (not wall-clock time) breaks ties. When neither candidate has a
retained explicit assignment, keep the existing nonnull placeId, otherwise the
incoming one. An expired history entry is older than any retained one. Face/thing
associations are unioned, never discarded. Test conflicting place assignments
and two incoming primaries; this is the ordinary last assignment rule for the
one place field, not a new conflict-resolution UI. A pending id no longer present
returns `not-found`; clients refresh
source/items after scan progress changes. If a file changes during read, do not
publish its hash: record a source error and retry on the next scan. Size+mtime is
the explicit unchanged heuristic, not proof against deliberate same-size edits.

Live pairing uses exact nonempty contentIdentifier within a source. Prefer the
lexically first still path then motion path if ambiguous, leaving others ordinary
items. Keep the still hash as the one id, absorb motion associations/locations and
history references. Dedup across other sources still uses bytes, not identifier
alone. Orphans remain normal photo/video items until a matching component arrives.

## Source, entity, settings, and history records

Source: `{schemaVersion,id,name,mode,origin,copyRoot,previewStore,files,scan}`.
mode `copy-here|serve-from-there`; origin
`{volumeSerial,pathFromVolumeRoot,lastKnownPath}` records the selected directory.
copyRoot is relative destination under originals/ or null. previewStore is null
(inherit), with-server, or with-source. For a copied source, with-source refers to
the copied folder, never back to the old disk.

files is a map keyed by original selected-folder-relative path, each value
`{destination,itemId,component,sizeBytes,modifiedAt,sha256,state}`. destination is
library-relative for copied files, null for linked; state
`pending|copied|indexed|error`. Copy-only internal temporary file is destination
plus `.partial-<sourceId>`; exclude it from enumeration. Scan is
`{state,added,skipped,errors}` with state `idle|running|complete|interrupted|error`;
errors array `{path,error}` uses errors below. Source reads add `available`.
An absent linked disk is not evidence to delete locations. Changed files mark
only their old location current=false and create a current location on the new
hash item. The old item retains its primary, lastKnownPath and annotations but
cannot read replacement bytes. An old item with no current readable locations
is unavailable, and Ctrl+C can still copy its historical primary path.
Copy-here conversion adds copied primary locations, retains old
volume locations as alternates, and preserves ids and annotations.

Person `{schemaVersion,id,name}` plus optional `thumbnailItemId` (item
id whose face crop is the sidebar thumbnail). Name is a nonempty string
or null. Absent `thumbnailItemId` means the largest / highest-score boxed
face, else the first still that references the person. Unknown extra keys stay rejected.
Place `{schemaVersion,id,name,latitude,longitude}`; coordinates both numbers or
both null. A named place without GPS can be searched but has no globe pin.
Thing `{schemaVersion,id,name,aliases}`; name nonempty, aliases distinct strings.
GPS place match uses Haversine distance <= placeMatchMeters, nearest candidate,
id lexical tie break. Enumerate new files by normalized relative path for stable
results. A matched place keeps its existing coordinates and name. If that name
is null and `library-data/geo/cities.csv` is present, the name may be filled
with the nearest city/region from that pack; coordinates stay. A person or
agent name is never replaced.

Filename date extraction uses the leftmost valid Gregorian `YYYY-MM-DD` or
`YYYYMMDD` bounded by non-digits or string boundaries. Invalid candidates are
ignored, then mtime is used. Missing DateTimeOriginal falls through to CreateDate;
an invalid date is treated as absent. OffsetTimeOriginal applies to its EXIF time
when present. A source with no usable metadata still gets dimensions null and
mtime as capturedAt during initial indexing; metadata enriches it without changing
identity. Original F11 uses the fixed 2022 mtime, never the current checkout date.

Settings are PRODUCT's existing 16 browse keys plus schemaVersion=1 and the
two face-quality keys `faceMatchThreshold` (0–1 exclusive of 0, default 0.5)
and `faceMinSidePx` (positive integer, default 80). A pre-face-quality 16-key
file is filled from those defaults on load. Enums are those listed in PRODUCT;
listenHost is `127.0.0.1|0.0.0.0`, port integer
1–65535. thumbPx, previewPx, proxyWidth, tourPictures, faceMinSidePx are positive integers;
placeMatchMeters, tourOrbitSec, tourPictureSec positive finite numbers.
Reject booleans as numbers. Do not change settings halfway through a single
operation: snapshot them at operation start. New preview dimensions affect new
renditions, not old bytes; previewStore affects new jobs, relocate explicitly
moves existing files. Listen settings take effect on next launch; other settings
on the next request. Settings PUT is a validated partial object, atomically merged.

History entry `{schemaVersion,id,operation,createdAt,changes}`; id random 12 hex,
UTC createdAt; operation `scan|copy-here|annotate|favorite|people-merge|person-update|settings|relocate|remove|delete-file|analyze-places|faces-infer|faces-cleanup`.
changes array `{path,before,after}` with library-relative canonical JSON path and
full JSON object or null. Store at most 500 committed entries. State
`{schemaVersion,entries,cursor}` lists oldest first and cursor counts applied
entries. New edits after undo discard redo entries. One user operation may update
many records. Original-copy effects are not reversed. Relocate undo restores
references only when the referenced renditions are recoverable; retain old
generated bytes under `undo/files/<entry-id>/<item-id>/<rendition-name>` until
eviction, restoring by copying verified bytes when replayed. Never point history at deleted rendition bytes. Undo/redo and
recovery must leave SQLite consistent. Individual write transactions serialize;
reads remain available. Between file transactions a scan permits annotate, so an
agent can annotate a pending item. The single writer pauses hash publication for
that annotate transaction. Settings changes also serialize and affect subsequent
operations. Other bulk mutations (copy conversion, relocation, rebuild, undo/redo,
people merge or another scan) return `busy` while scanning.

Scan registration creates one history entry at start and later file transactions
extend that same entry. Automatic metadata/hash/location changes must be rebased
into the applicable before/after snapshots of intervening annotation entries,
preserving their annotation differences; undoing an annotation must not restore
a stale pending id or delete a later-discovered location. This history rebase is
part of the same recovery transaction as hash finalization. S08 explicitly tests
annotate during scan, finalization, undo/redo, then restart. Do not solve it by
silently rejecting annotation until hashing finishes.

## Commands and HTTP

Syntax: `python -m library --root <root> <command>`. JSON success on stdout,
errors on stderr. `serve` prints URL before serving; scan prints progress lines
then a final JSON `{sourceId,added,skipped,errors}`. Error exits: 1 execution
failure, 2 invalid invocation/payload, 0 success including empty results.
Commands with JSON bodies accept `--json <UTF-8-file>`; no shell JSON escaping
required. Both interfaces must produce equivalent resulting canonical records.

| Command / request | Body / response |
|---|---|
| serve / GET `/api/health` | health 200 `{"ok":true}`; root identity uses GET `/api/runtime`; checkout SHA uses GET `/api/version` |
| GET `/api/version` | 200 `{ok,git_sha,git_branch,git_date,git_subject,label}` from the live app-folder git tip; non-git / no git is 200 `ok:false` with `git_sha:null` and `label:"local"` |
| scan path [--copy-here OR --serve-from-there] / POST `/api/sources` | `{path,mode?,previewStore?}`; flags override setting; ask + absent mode = `choice-required`, never an interactive CLI prompt. HTTP 202 source record is sent before the scan finishes (`scan.state` running). Rescan same origin reuses source. CLI still waits and prints the final summary. |
| POST `/api/pick-folder` | `{}`; Windows native folder dialog; 200 `{path}` or `{path:null}`; otherwise 404 `picker-unavailable` |
| GET `/api/update` | 200 `{ok,branch,revision,dirty,message,git_sha,git_branch,git_date}` for the app-folder git copy; `revision` is the short SHA |
| POST `/api/update` | `{}`; 200 `{ok,updated,revision,git_sha,message}` after `git pull --ff-only` (`git_sha` is the new tip); 404 `update-unavailable` when the app folder is not a git checkout |
| sources / GET `/api/sources` | 200 array of sources |
| copy-here source-id / POST `/api/sources/<id>/copy-here` | `{}`; 202 source record; already copied is successful no-op |
| items / GET `/api/items` | 200 array of item read objects; CLI flags mirror query keys |
| GET `/api/groups` | `level=years|months|days|all` plus item filters/sort; array `{key,itemIds}`; year YYYY, month YYYY-MM, day YYYY-MM-DD; same ids exactly once as item results; groups ordered by first occurrence in sorted items, contents retain item order. Flattening can differ from item sort when dates interleave; viewer arrows use item sort. No invented “best” photos. |
| GET `/api/places` | array `{id,latitude,longitude,name,itemCount,newestItemId}` for places with coordinates and visible items; same unavailable policy as items |
| GET `/api/globe/tour` | array `{placeId,itemIds}` ordered newest item date descending then place id; items newest first capped by tourPictures, only readable ready preview (still/live) or proxy (video). Skip empty places. |
| annotate id / POST `/api/items/<id>/annotations` | payload below; 200 updated item |
| favorite id --on/--off / PUT or POST `/api/items/<id>/favorite` | `{favorite:true\|false}`; 200 updated item with computed `favorite`; writes `catalog/favorites.json`; no-op success when unchanged |
| reveal id / POST `/api/items/<id>/reveal` | `{}`; 200 `{path,folder,opened}` or 404 `unavailable` |
| open id / POST `/api/items/<id>/open` | `{}`; 200 `{path,opened}` or 404 `unavailable`; default-app launch |
| remove id / POST `/api/items/<id>/remove` | `{}`; 200 `{ok:true,id}`; drops item JSON, favorite entry, and index row; original bytes stay; undoable `remove`. Unknown id is `not-found`. |
| delete-file id / POST `/api/items/<id>/delete-file` | `{}`; 200 `{ok:true,id,trashed}`; Windows Recycle Bin the current original when possible (`trashed` true/false), then the same catalog drop as remove; undoable `delete-file` restores catalog only. 404 `unavailable` if no current file. UI extra-confirms; CLI is explicit. |
| people / people list / GET `/api/people` | 200 `{personOfInterestMin,people}` where each person is `{id,name,itemCount,visible,named,thumbnail}`. `personOfInterestMin` is the constant **3** (not a settings key). `visible` is true for any named person and for unnamed clusters with `itemCount >= personOfInterestMin`. `thumbnail` is `{itemId,box?}` or null. |
| people update id / PUT `/api/people/<id>` | `{name?,thumbnailItemId?}`; 200 updated person read (same shape as a people-list row). Name null unnames. `thumbnailItemId` must be an item that already has that person. Undoable `person-update`. Unknown id is `not-found`. |
| people merge keep drop / POST `/api/people/merge` | `{keepId,dropId}`; 200 kept person; rewrite all faces and history transaction, remove dropped record, merge `models/faces/index.json` embeddings when that file exists; self merge invalid |
| jobs / GET `/api/jobs` | 200 `{ok,paused,processing,queues}` where `queues` is renditions, analyze, infer-faces, objects, each `{id,label,pending,done,error,state,available}`. Renditions counts come from item rendition status. Analyze counts unnamed GPS places; `available` is the local geo pack. Infer-faces counts photo/live stills not yet scanned; `available` is face models ready. Objects counts stills not yet analyzed; `available` is the YOLO file. Missing pack/models: `available` false, queue idle, no crash. `state` is `running\|paused\|idle`. Browse stays up. |
| jobs pause / jobs resume / POST `/api/jobs` | `{action:"pause"\|"resume"\|"rerun-faces"}`; 200 same body as GET. Pause stops the serve-process drain for renditions, analyze-places, infer-faces, and objects. Resume starts them again. `rerun-faces` clears the face scanned map and force-redetects with current quality gates; named people are kept. Does not block `GET /api/items`. |
| setup-geo [--from dir] [--force] | CLI only. Writes `geo/cities.csv` under the library root. `--from` copies or converts a local pack (fixture or air-gapped). Default fetches GeoNames cities5000 + admin1 (setup-time network only). Already present is success unless `--force`. JSON `{ok,path,cityCount,downloaded,source}`. Download/write failure is `io-error`. Missing `--from` path is `invalid-argument`. Not a catalog/history write. |
| analyze-places / POST `/api/places/analyze` | `{}`; 200 `{ok,named,skipped,packReady}`; fills null GPS place names from the local pack; no-op success when nothing to fill or pack missing (`packReady` false). Undoable `analyze-places`. Busy while scanning. |
| setup-ml objects | CLI / `Setup.bat` / `launch.ps1 -SetupMl` only. Downloads YOLOv8n ONNX into `models/yolov8n.onnx` and writes `models/objects.json`. Installs `onnxruntime` when missing. No HTTP route. No cloud inference. Already-present matching file is success. |
| analyze [--item id] / POST `/api/analyze` | `{}` or `{itemId?}`. 200 `{ok,analyzed,tagged,skipped,items}` after local detection writes Things through annotate. Missing model is 404 `model-unavailable`. An explicit itemId re-runs that still; omitted itemId analyzes pending items only. `GET /api/analyze` is 200 `{ok,installed,model,pending}`. |
| setup-ml faces / POST `/api/faces/setup` | `{backend?}`; default InsightFace buffalo_s ONNX into `models/faces/`. 200 `{ok,backend,ready,modelsDir}`. Downloads models only; never uploads photos. `backend=fixture` is allowed only when `LIBRARY_TEST=1`. |
| infer-faces / POST `/api/faces/infer` | `{force?,cleanup?,itemIds?}`; 200 `{ok,backend,items,faces,peopleCreated,peopleReused,skipped}`. Detect → embed → cluster unnamed people; reuse catalog ids only when cosine is strictly above `faceMatchThreshold` (InsightFace default 0.50; fixture stays 0.85). Detections below `faceMinSidePx` (default 80) or InsightFace det score 0.65 are dropped. `force` re-detects with those gates and rebuilds centroids from the new quality faces; named person files are kept. `cleanup` (without force) drops stored faces that fail min-size / stored scores and rebuilds index face lists. After Update, Steve should run `python -m library infer-faces --force` or Processing **Re-run Faces**. Missing models: 404 `models-missing`. Videos skipped. Items that already have faces skipped unless `force`. One undoable `faces-infer` or `faces-cleanup` history entry. |
| GET `/api/faces` | 200 `{ok,ready,backend,modelsDir}` ; `ready` false when setup has not run |
| settings get / GET `/api/settings` | 200 complete settings |
| settings set key value / PUT `/api/settings` | partial settings object; 200 complete settings |
| rebuild-index / POST `/api/rebuild-index` | `{}`; 200 `{"ok":true}`; atomic replacement index, unchanged canonical JSON |
| renditions relocate / POST `/api/renditions/relocate` | `{}`; 200 `{"ok":true}` after completion; unavailable source gives failure and preserves old files/references |
| undo, redo / POST `/api/undo`, `/api/redo` | `{}`; 200 `{"ok":true}`; empty history also no-op success |

Annotate body: `{people?:[{id?,name?,box?}],places?:[{id?,name?}],
things?:[{id?,name?,aliases?,box?}]}`. At most one place (item has one placeId).
An id must exist; name with an id updates that entity globally; absent id requires
a name, reusing a matching entity or creating it. To make an unnamed face,
`{name:null}` creates a new person. Name-only person/place match reuses smallest
matching id; people with the same display name can still be distinguished by id.
Thing name/alias collisions resolve to smallest id. Supplied aliases append;
no removal interface is invented. Existing GPS place is renamed in place when
annotating its name without an explicit other id. A new non-GPS place has null
coordinates. Empty payload is invalid. CLI shorthand `--person Ada --thing mug`
maps to these arrays; `--place Kitchen` and `--json` cover existing operations.

Queries: sort=date|location|name, dir=asc|desc, person/place/thing exact id or
normalized exact name; place also comma-separated ids (OR). `person` with
comma-separated **ids** keeps items that contain **all** those people
(AND). A single person token still matches id or exact name. `kind` is one of
`photo|video|live` or a comma-separated list of those (Photos filter is
`photo,live`). Unknown kind is `invalid-argument`. `favorite=1` keeps hearted
items only; any other `favorite` value is `invalid-argument`. `q` is normalized substring
against names, thing aliases, filename, and capturedAt calendar text
(`YYYY`, `YYYY-MM`, `YYYY-MM-DD`). Scope chips restrict q to that entity
type. `from` inclusive and `to` exclusive ISO date/timestamp filter capturedAt.
unavailable omitted follows settings; 0 means available only, 1 means include both.
Sort ties: date then id; name then date then id; location puts named, unnamed GPS,
no-location groups in that category order regardless of dir; dir orders names/
coordinates and dates within category. Compare capturedAt as stored normalized
ISO components; floating dates remain floating, never guess a timezone.

GET `/api/media/<id>?which=thumb|preview|poster|proxy|playback|original` returns bytes,
correct Content-Type and length. Live original is still by default;
`component=motion` chooses the movie (ordinary video is already motion). Support
single byte Range with 206/Content-Range and 416 invalid-range. Preview swaps and
video seeking are verified in browser. No raw filesystem paths are accepted.

All non-media success responses are JSON. Errors are always `{"error":"<code>"}`,
no HTML tracebacks. Detailed time/path/exception goes in logs/server.log, including
failed media reads; never ship an invented error as a one-off exception.

| Status | Error codes / condition |
|---|---|
| 400 | `invalid-argument` (type, field, range, unknown query), `choice-required` |
| 404 | `not-found` (unknown id/route), `unavailable` (known original missing), `preview-unavailable` (known rendition not readable), `picker-unavailable` (no Windows folder dialog), `update-unavailable` (app folder is not a git checkout), `model-unavailable` (objects model not installed), `models-missing` (face models not installed) |
| 409 | `busy`, `port-in-use`, `volume-identity-unavailable` |
| 416 | `invalid-range` |
| 500 | `io-error`, `invalid-catalog`, `decode-error`, `internal-error` |

CLI-only missing tools use `dependency-missing` and exit 1, including a
missing `onnxruntime` during `setup-ml` / `analyze`. Scan per-file errors
use `io-error|decode-error|invalid-argument`; continue other files but final CLI
exit is 1 if errors exist. Failed HEIC decode preserves metadata/item and records
rendition error; it is not proof that every HEIC is decodable. Launcher installs
the already-named Python/ffmpeg dependencies on Windows only, re-resolves PATH,
reports failure honestly, and gives prerequisites on other platforms.

## Foundation locks (2026-10-13)

These close S00 ambiguities. They are not new user features.

Matching-root reopen: normalize both roots (absolute, symlinks resolved, Windows
casefold). If the configured address accepts connections, GET `/api/health` and
GET `/api/runtime`. When health is `{"ok":true}` and `runtime.root` matches,
print that url and exit 0. Do not bind, do not take `write.lock`, and do not
create a second catalog. If the address is occupied but those checks fail or
the root differs, exit 1 with stderr `{"error":"port-in-use"}` and leave the
occupant running. Never terminate another process.

`launch.ps1 -NoBrowser` and `launch.sh --no-browser` skip opening a browser.
The default remains to open one. This is not a settings key.

When `LIBRARY_TEST=1`, `LIBRARY_TEST_BARRIER` may be `settings-prepared`,
`settings-committed`, `hash-publication`, `catalog-committed`, or
`sqlite-rebuild`. The process flushes the named boundary, then exits 86 with
stderr `{"error":"test-barrier","barrier":"<name>"}` before the next step.
Recovery on the next open rolls `prepared` back and `committed` forward, then
serves. Without `LIBRARY_TEST=1` the variable is ignored. It is not an HTTP
parameter or a setting. Order for a settings change: write manifest `prepared`
(full before/after) → barrier `settings-prepared` → atomic replace → history
entry → manifest `committed` → barrier `settings-committed` → delete the
transaction directory. Scan barriers: `hash-publication` after the pending
record and its sha256 are durable and before the final item is the only
published record; `catalog-committed` after that item JSON and the one scan
history entry are committed and before SQLite changes; `sqlite-rebuild` after
`catalog.sqlite` is removed and before the replacement is durable. The next
open finishes publication or rebuild and must not create a second item.

When `LIBRARY_TEST=1`, `LIBRARY_TEST_VOLUMES` may be a path to JSON mapping a
volume serial to an absolute mount path or null. Null means not mounted. This
is the only test seam for volume identity. Production ignores it. It is not a
setting. A missing real volume still uses the OS serial lookup.

Log lines are UTF-8 `{utc-iso}\t{path}\t{error}\n`. `path` is the request path
including query. Unknown media ids log `not-found`.

Settings JSON key order is `schemaVersion` then the 16 PRODUCT browse keys
and the two face-quality keys `faceMatchThreshold`, `faceMinSidePx`. Indent 2,
trailing newline, UTF-8.

GET `/` may be the empty-library page (header, Add folder control present but
inert until a later slice, text “No pictures yet”). No sample pictures and no
claim that scan, search, globe, or viewer already work.

GET `/` serves that page; unknown asset paths return not-found. Mutation
requests accept application/json from the same origin/CLI; reject unrelated
browser origins as 400 invalid-argument. No remote account, login, or cloud setup.
The shipped globe assets and ordinary browsing must work with external network
blocked. Dependency installation and optional one-time `setup-geo` /
`setup-ml objects` / `setup-ml faces` are the described setup-time
network uses. Scan, Info, search, globe, infer, and analyze do not call
a geocoder or a cloud model.

When `LIBRARY_TEST=1`, `setup-ml faces --backend fixture` (or
`POST /api/faces/setup` `{"backend":"fixture"}`) installs a deterministic
local detector that reads synthetic beacon/identity colors from fixture
stills. Production `setup-ml faces` always installs InsightFace buffalo_s
and ignores `backend=fixture`. The fixture backend never uploads and never
emits a display name. It is not a setting.

Optional local face models live under `models/faces/` inside the library
root: `manifest.json`, InsightFace ONNX files, and `index.json`
`{schemaVersion,backend,matchThreshold,people,scanned?,forceRescan?}` where `people`
maps person id → `{centroid,faces:[{itemId,box}]}` and `scanned` maps
already-inferred item ids. InsightFace `matchThreshold` default is 0.50
ArcFace cosine (fixture 0.85). `index.json` is ML state, not catalog truth;
person JSON stays `{schemaVersion,id,name}`. Infer never writes a nonempty
name. Gender/age ONNX files are not loaded and are removed after a
buffalo_s install. A catalog face may store `detScore` and `matchScore`
(0–1) for later cleanup and thumbnail ranking.

`library-data/models/` for objects is created by `setup-ml objects`.
`models/objects.json`: `{schemaVersion,kind,model,input,labels,sha256,bytes}`.
`models/objects-state.json` maps item id → `{sha256,names}` so background
analyze skips an unchanged still. The `person` class is dropped; analyze
never writes people.

When those files exist and jobs are not paused, `serve` drains one
analyze-places / infer-faces / objects step after a rendition miss.
Missing pack or model is idle, not an error.
