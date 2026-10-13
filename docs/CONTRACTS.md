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
| Scan progress | Persist progress in the source record; POST starts work and returns 202. Poll sources; no additional jobs screen/API. CLI waits for completion and prints the final summary. |
| History | One user operation is one durable transaction; automatic scan progress/hash/rendition updates are not separate undo steps. Scan/copy undo never removes original bytes. History replay must preserve later scan-derived identity. |
| Dates | Preserve floating EXIF time without inventing a zone. Normalize explicit offsets to UTC; mtime uses UTC. Date-only filenames mean midnight. Date grouping uses the stored calendar date, independent of browser timezone. |
| Days vs All | Both include every matching item under day headings. Days has larger cells; All is denser. No representative-photo selection algorithm. |
| Search chips | Add `scope=people|places|things` to `items` and `groups` for the already-described chips. No scope means names plus filenames. Filters combine with AND, values within a place list with OR. |
| Annotate semantics | Add associations, reuse named entities deterministically, optionally rename an explicit entity id. No face detection, name guessing, caption system, or box-drawing tool. |
| Live pairing | Same Apple content identifier within the same source pairs still + movie across scan order/restart. Filenames alone never pair. Locations need a component discriminator. |
| Playback | Full-length silent proxies as PRODUCT says; the convention's word “short” means low-resolution, not truncated. Unplayable browser original falls back to proxy. |
| Platform promise | Windows is the primary acceptance platform. Keep the described macOS/Linux launchers; their launch and volume identity tests need those platforms before F2 can pass in full. Missing runners are recorded, never counted green. |
| API completion | Exact responses, annotation payload, merge route, range requests, and error table below fill missing technical details, not new user features. |
| Port conflict | Keep 8765 default. Reopen a healthy matching-root server; a different service/root produces `port-in-use`. Never kill it or silently choose a port. |
| Settings scope | Keep the 16 existing settings. Do not add a keybinding editor, authentication, accounts, remote hosting, albums, favorites, or other controls because a reference or general baseline mentions them. |

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
| faces | Array `{personId,box?}` |
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
an entity. No inferred face matching.

Renditions: `{store,sourceId,thumb,preview,poster,proxy,status}`. Store is
`with-server|with-source`; sourceId selects the owning source. Paths are relative
to library-data for with-server, to selected source root for with-source (starting
`.library/`). Absent paths null. status maps all four names to
`not-applicable|queued|ready|error`. Photos use thumb/preview, videos poster/proxy,
live items all four. An error never removes the item. Explicit rescan retries
failed renditions even if original bytes are unchanged. Missing previews show a
placeholder; no request automatically mutates the source disk to repair them.

Availability and entity expansion are computed, not persisted: HTTP/CLI item reads
extend disk records with `available` and `motionAvailable` booleans and `entities`:
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

Person `{schemaVersion,id,name}`; name nonempty string or null.
Place `{schemaVersion,id,name,latitude,longitude}`; coordinates both numbers or
both null. A named place without GPS can be searched but has no globe pin.
Thing `{schemaVersion,id,name,aliases}`; name nonempty, aliases distinct strings.
GPS place match uses Haversine distance <= placeMatchMeters, nearest candidate,
id lexical tie break. Enumerate new files by normalized relative path for stable
results. A matched place keeps its existing coordinates and name.

Filename date extraction uses the leftmost valid Gregorian `YYYY-MM-DD` or
`YYYYMMDD` bounded by non-digits or string boundaries. Invalid candidates are
ignored, then mtime is used. Missing DateTimeOriginal falls through to CreateDate;
an invalid date is treated as absent. OffsetTimeOriginal applies to its EXIF time
when present. A source with no usable metadata still gets dimensions null and
mtime as capturedAt during initial indexing; metadata enriches it without changing
identity. Original F11 uses the fixed 2022 mtime, never the current checkout date.

Settings are exactly PRODUCT's existing 16 keys plus schemaVersion=1.
Enums are those listed in PRODUCT; listenHost is `127.0.0.1|0.0.0.0`, port integer
1–65535. thumbPx, previewPx, proxyWidth, tourPictures are positive integers;
placeMatchMeters, tourOrbitSec, tourPictureSec positive finite numbers.
Reject booleans as numbers. Do not change settings halfway through a single
operation: snapshot them at operation start. New preview dimensions affect new
renditions, not old bytes; previewStore affects new jobs, relocate explicitly
moves existing files. Listen settings take effect on next launch; other settings
on the next request. Settings PUT is a validated partial object, atomically merged.

History entry `{schemaVersion,id,operation,createdAt,changes}`; id random 12 hex,
UTC createdAt; operation `scan|copy-here|annotate|people-merge|settings|relocate`.
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
| serve / GET `/api/health` | health 200 `{"ok":true}`; root identity uses GET `/api/runtime` |
| scan path [--copy-here OR --serve-from-there] / POST `/api/sources` | `{path,mode?,previewStore?}`; flags override setting; ask + absent mode = `choice-required`, never an interactive CLI prompt. 202 source record; rescan same origin reuses source. |
| sources / GET `/api/sources` | 200 array of sources |
| copy-here source-id / POST `/api/sources/<id>/copy-here` | `{}`; 202 source record; already copied is successful no-op |
| items / GET `/api/items` | 200 array of item read objects; CLI flags mirror query keys |
| GET `/api/groups` | `level=years|months|days|all` plus item filters/sort; array `{key,itemIds}`; year YYYY, month YYYY-MM, day YYYY-MM-DD; same ids exactly once as item results; groups ordered by first occurrence in sorted items, contents retain item order. Flattening can differ from item sort when dates interleave; viewer arrows use item sort. No invented “best” photos. |
| GET `/api/places` | array `{id,latitude,longitude,name,itemCount,newestItemId}` for places with coordinates and visible items; same unavailable policy as items |
| GET `/api/globe/tour` | array `{placeId,itemIds}` ordered newest item date descending then place id; items newest first capped by tourPictures, only readable ready preview (still/live) or proxy (video). Skip empty places. |
| annotate id / POST `/api/items/<id>/annotations` | payload below; 200 updated item |
| people merge keep drop / POST `/api/people/merge` | `{keepId,dropId}`; 200 kept person; rewrite all faces and history transaction, remove dropped record; self merge invalid |
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
normalized exact name; place also comma-separated ids. `q` is normalized substring
against names, thing aliases and filename. Scope chips restrict q to that entity
type. `from` inclusive and `to` exclusive ISO date/timestamp filter capturedAt.
unavailable omitted follows settings; 0 means available only, 1 means include both.
Sort ties: date then id; name then date then id; location puts named, unnamed GPS,
no-location groups in that category order regardless of dir; dir orders names/
coordinates and dates within category. Compare capturedAt as stored normalized
ISO components; floating dates remain floating, never guess a timezone.

GET `/api/media/<id>?which=thumb|preview|poster|proxy|original` returns bytes,
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
| 404 | `not-found` (unknown id/route), `unavailable` (known original missing), `preview-unavailable` (known rendition not readable) |
| 409 | `busy`, `port-in-use`, `volume-identity-unavailable` |
| 416 | `invalid-range` |
| 500 | `io-error`, `invalid-catalog`, `decode-error`, `internal-error` |

CLI-only missing tools use `dependency-missing` and exit 1. Scan per-file errors
use `io-error|decode-error|invalid-argument`; continue other files but final CLI
exit is 1 if errors exist. Failed HEIC decode preserves metadata/item and records
rendition error; it is not proof that every HEIC is decodable. Launcher installs
the already-named Python/ffmpeg dependencies on Windows only, re-resolves PATH,
reports failure honestly, and gives prerequisites on other platforms.

GET `/` serves the five-view page; unknown asset paths return not-found. Mutation
requests accept application/json from the same origin/CLI; reject unrelated
browser origins as 400 invalid-argument. No remote account, login, or cloud setup.
The shipped globe assets and ordinary browsing must work with external network
blocked. Dependency installation is the one described setup-time network use.
