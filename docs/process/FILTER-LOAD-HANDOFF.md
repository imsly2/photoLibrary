# Handoff — as fast as the machine allows

Paste the prompt below into the next agent.

---

You are advising on the photo library at `J:\slyOS\projects\photoLibrary`. The goal is to make loading pictures and filtering them as fast as digitally possible on this PC. That is the whole goal. Nothing in the current design is a requirement. Do not preserve a mechanism because it is already built. Do not start from an assumption about the right shape. Look at what the machine can do, and tell us how to structure this to get there.

Advice first. Say how you would structure it, what you would throw out, and what would still be slow after that and why. Do not begin by editing the product to match a guess.

## What he sees

On the live library, opening the page counts pictures for a long time. Thumbnails fill part of the screen and then stop. The page is hard to use until the count finishes. Filtering was almost instant for a moment, including turning filters off and on, and he was happy. Then it regressed. A filter, a person, and clearing that filter wait while a list comes in. When it arrives, tiles that already had pictures are blank and the thumbnails build again, slowly. It feels like more than one loader is competing. He does not know which change brought the wait back. Making one path faster has left the same stall on another path.

The library he is using includes the iPhone folder at `K:\Photos\Iphone 2017-2026.10`. The page is [http://127.0.0.1:8785/](http://127.0.0.1:8785/). A small test catalog can look fine while this one is still slow. Judge the advice against this library.

## What the code does now

This is the current machine, not a design to keep. Line-level detail is in `docs/process/LOADING-PIPELINE.md`.

The page is `library/web/assets/library.js`. The server is `python -m library serve` (`ThreadingHTTPServer` in `library/server.py`). One thread per request. Python still runs one thread at a time. File reads release that lock. Building a JSON line or encoding a thumb holds it. Encoder threads are a separate pool, half the CPU count, from 1 to 6 (`library/renditions.py`). On a new server only thumbnails run. Other processing stays paused until Resume.

The catalog stream is `/api/items/stream`, NDJSON, `Cache-Control: no-store`. The catalog lock is held only for a snapshot. The ordered list is built before the first byte. If unavailable files are hidden, that build checks every original. Each row sent to the browser is a full item view, including people, places, and tags. The browser reads that stream on the main thread, in batches, and yields between batches.

Every filter click calls `loadCatalog`. Two paths:

- In memory, when a finished wide list is still held on the page. The wide list is saved only when a stream ends with no search, scope, person, place, tag, kind, favorite, folder, Recently added, stars, picks, blurry, or With people. Hide-rejects and the sort are part of that memory. A refresh forgets it. All, Photos, Videos, Favorites, With people, stars, picks, blurry, and a folder use this path when that list exists. A person, place, or tag uses it only when the saved records carry those entities.
- From the server otherwise. Search, Recently added, and sort always take this path. Sort empties the grid first. The other server filters leave the old tiles up until the first new records arrive, then delete the tiles and paint the new list from empty.

Even the in-memory path scrolls to the top and mounts the visible rows again. A tile kept in a map of at most 1024 painted cells can keep its image element. Any other tile is new and asks for a thumbnail again.

Thumbnails: only on-screen tiles, then a short neighbor band. At most 12 at once. A photo asks for `which=thumb`, or the camera's embedded JPEG if the thumb is not ready. A video asks for `which=poster`. Off-screen requests are cancelled. Hover can play a proxy and show a larger still.

Preview: a photo goes preview still, then original. A video goes proxy or original, then a playback file when one exists. A docked preview does not pause grid thumbnails. They share the browser's connections.

Chromium, not us, owns the memory cache, disk cache, image decode, and the connection cap. This server is HTTP/1.1. Chromium keeps about six connections to one host. The catalog stream holds one for the whole list. Thumbs, preview, and video share the rest. We send thumbs, previews, posters, proxies, and playback as `Cache-Control: private, no-cache` with an ETag, so a new image element revalidates with the server before reuse. We do not use a service worker or the Cache API. We have no priority flag. Media reads the whole file into memory, then applies a Range header. Windows is only the disk and the scheduler. This is not the Windows thumbnail cache.

## What to come back with

How to structure loading and filtering so this library is as fast as this PC allows. What in the current machine is in the way. What is already at a limit set by the disk, the browser, or Python, and what is our structure. How we would know, on this library, that a later change got slower.
