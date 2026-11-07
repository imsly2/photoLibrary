# How the library loads today

Facts from the code on 2026-11-06, after the browse-speed change.
The live page is [http://127.0.0.1:8785/](http://127.0.0.1:8785/).
The page script is `library/web/assets/library.js`. The server is
`python -m library serve` from this repo, `ThreadingHTTPServer` in
`library/server.py`.

The page fetches `GET /api/catalog/index` once. That body is the
compact list of every picture (about 4.4 MB on this library). The
page filters, sorts, searches, and groups that list itself. A chip,
person, place, tag, folder, search, sort, Group, Dates, or clear
does not ask the server for a new list and does not call
`releaseGrid`. `showLocalCatalog` reuses tile elements that are
still in the painted-cell map. The Favorites strip is included when
stills are painted.

`/api/items/stream` is still there for a fixture server that has no
index. The live page does not use it for browsing. The full record
for one picture is `GET /api/items/<id>`, fetched when the viewer
opens.

Opening the page does not call `/api/people/suggestions`. Review
matches asks for that. Suggestions are a cached numpy dot product.
The idle rendition drain does not walk every rendition, and it does
not copy the source file list unless a rendition was just published.

The per-folder `.library/` records stay the source of truth. The
index is a rebuildable copy, warmed before the server prints its URL.

## What each control does

Kind and Favorites replace each other. With people, stars, picks,
hide rejects, blurry, and a folder can sit on top of those.
A plain click on a person clears search, scope, place, and tag.
Ctrl-click adds that person. Clicking the person again removes them.
A tag click does the same with people and places cleared. Clear all
resets every filter field and loads again.

| Control | What it sets | Where it runs |
|---|---|---|
| All, Photos, Videos, Favorites, With people | kind, favorite, hasPeople | In the page, on the index |
| Stars, picks, hide rejects, blurry | rating fields | In the page |
| A person, place, or tag | person, place, thing | In the page. Several people still AND |
| A folder | source | In the page |
| Search | q, after the debounce. The grid is not cleared on the keystroke | In the page, including filenames, dates, names, and said-text |
| Recently added | recent. The index marks those ids with bit 256 | In the page |
| Sort or direction | settings.sort / dir. The grid is not cleared first | In the page |
| Group, Dates, Size | arrangement and cell size | In the page |
| Clear all | every filter field cleared | In the page |

Videos still shows a short video that shares a tile with a still.
`isStackHidden` returns false for that case when the Videos chip is on.

A filter still scrolls to the top and remounts the visible rows.
A tile that is still in the painted-cell map keeps its image element.
A new element for a picture already decoded copies those pixels
instead of asking the server again. The painted map holds at most
1024 cells. A decoded-picture memory holds 500.

## Thumbnails

The grid asks for a still only for a tile that is on screen, plus a
short neighbor band once those look loaded. `paintGridStills` ranks
that set. `pumpStillQueue` runs at most `STILL_MAX` (12) at once.
A request that does not finish in 20 seconds is cancelled and tried
again later. Off-screen tiles are not given a still. Leaving the
screen cancels the request by clearing the image `src`.

A photo tile asks for `which=thumb`. If that thumb is queued or
errored, and the picture is not a video, it asks for `which=camera`
(the small JPEG stored in the file) until that fails. A video tile
asks for `which=poster`.

The virtual wall mounts only the rows in the window. The count is
known when the index has been filtered, not when every thumbnail
has arrived. Scrolling, or the visible thumbnails finishing, mounts
again. Favorites cells are painted with the grid cells.

Hover plays a proxy when one is ready. The enlarged still shows for
a photo or a video when the tile is smaller than the thumb. A light
border is the hover mark.

## Preview

Opening a picture uses the preview still, then the original still
when the original can be shown. Opening a video starts a proxy or
the original, then moves to `which=playback` when that file is ready.
The page does not pause grid thumbnails for a docked preview.
`viewerCoversGrid` pauses them only when the viewer covers the grid
(full screen, or undocked). A docked preview and the grid stills
share the browser's connections to this host.

A missing preview file calls `note_wanted`, and the rendition
workers encode it. Those workers are separate threads: half the
CPU count, at least 1, at most 6. On a new server only the
thumbnail queue runs. Faces, objects, places, transcribe, and
rating stay paused until Resume.

## What we control, and what Chromium and Windows control

We choose which URL to request, how many stills we start (12),
which tiles are eligible, and when we cancel one. We choose the
response headers. Thumbs, camera stills, previews, posters, face
crops, proxies, and playback files are sent as
`Cache-Control: private, no-cache` with an ETag
(`_media_cache` in `library/server.py`). The catalog stream is
`no-store`. `private, no-cache` tells the browser to revalidate
before reuse. A new image element therefore waits on the server
even when that exact thumb was downloaded a moment ago. A 304 can
be fast. A busy server makes the tile look empty until the
revalidation returns.

Chromium decides the memory cache, the disk cache, image decode,
and how many connections one host gets. This server is HTTP/1.1.
Chromium keeps about six connections open to one host. The catalog
stream holds one for the whole list. Grid stills, a preview, a
video, and the once-a-second health poll share the rest. We have
no priority flag on those requests. We do not use a service worker
or the Cache API.

The server is threaded: one thread per request. Python's lock
(the GIL) still means one thread at a time runs Python. Reading a
file releases that lock. Building a large JSON line or encoding a
thumb holds it, so other requests wait. The catalog lock is held
only while the stream takes its snapshot, then released. The
ordered list is built before the first byte, including a file
check when unavailable pictures are hidden. Media for one item
does not take that catalog lock. `_send_media` reads the whole
file into memory, then honors a Range header. A video preview is
a full-file read on that request thread.

Windows is the disk under `K:` and the process scheduler. We do
not set I/O priority on thumbnail reads. Encoder threads lower
their priority. Nothing in this pipeline is a Windows shell
thumbnail cache. The pictures on screen are whatever this server
just sent.

## What already shipped, and what he still sees

These are in the tree. He felt the in-memory chips get fast, then
watched person and the other filters go slow again. Do not treat
the in-memory path as done while he still sees a wait and empty tiles.

- Chips no longer call `clearCatalogForQuery` before the local
  answer. The grid is not emptied first on that path.
- Search and Recently added still stream. Until the first records,
  the old pictures stay and the bottom line says the library is
  being filtered. The first records then clear the grid.
- Sort still clears the grid first, then streams.
- The stream reader no longer copies the unread tail on every line,
  and it yields between batches so a click can run while the count
  is still climbing.
- A wall of videos uses fixed cell size and CSS grid columns so a
  tile does not jump sideways while scrolling.
- The preview header shows weekday date, place, and file size when
  the record has them. A video with no location string in the file,
  and no same-name still, has no place. That is a separate gap.

## Files

| File | What it owns |
|---|---|
| `library/web/assets/library.js` | Filters, stream reader, virtual grid, still queue, preview |
| `library/web/assets/style.css` | Cell size, wall columns, hover border |
| `library/server.py` | Stream, media bytes, cache headers, thread per request |
| `library/service.py` | Snapshot, order, stacks, which fields a stream row carries |
| `library/renditions.py` | Thumb, poster, preview, proxy, playback encode pool |
| `docs/UI-SPEC.md` | The screen contract for chips, the bottom line, and the wall |
| `docs/PRODUCT.md` | F3, F11, F15 |
