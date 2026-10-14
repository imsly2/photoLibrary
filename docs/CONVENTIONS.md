# Library — conventions

Prior art for [PRODUCT.md](PRODUCT.md). The help file wins when they disagree.
Steve's cross-project input defaults are in
[STEVE-INPUT-PREFERENCES.md](../../slyAI/shared/STEVE-INPUT-PREFERENCES.md).

Surveyed: Apple Photos (iPhone and Mac), Immich, digiKam, Smriti (photovault),
Adobe Lightroom Classic's catalog-plus-originals split, Windows Photo Viewer,
Windows Photos, Google Photos (browse chrome only), XnView-class local
browsers. Family-PC chrome from those tools is locked in
[UI-SPEC — Windows Presentable Shell](UI-SPEC.md#windows-presentable-shell);
this file does not authorize accounts, editing, or albums.

## What those tools already do

| Behavior | Where it shows up | Library default |
|----------|-------------------|-----------------|
| Years, then months, then days, then every photo | Apple Photos pinch zoom. Immich uses a date timeline with year and month buckets. | Dates dropdown: Years / Months / Days / Off (one wall). On a desktop, Ctrl+wheel and one Size slider change density only. The picture under the cursor stays put. |
| Originals stay put | Lightroom and Smriti index files in place. digiKam can import or reference. | Add-folder asks: copy onto this drive, or serve that folder in place. Remembered per folder. The default prompt is a setting. |
| Catalog travels with the disk | Smriti writes `.photovault/` on the drive and stores relative paths. digiKam warns that a SQLite catalog on a USB stick is slow, and still lets you choose the folder. | JSON records live next to the server. SQLite is rebuilt from them. Paths on this drive are relative to the library folder. |
| Small pictures for browsing | Immich, digiKam, Smriti, and Apple Photos all keep generated thumbnails apart from masters. | A thumb and a medium still for every photo. A poster and a full-length silent low-resolution movie for every video. Where those files sit is a setting. |
| Date comes from the camera | Every tool above prefers EXIF over the file's modified time. | `capturedAtSource` is `exif`, then a date in the filename, then file modified time. The fallback is marked. |
| Place comes from GPS | The iPhone writes coordinates into the file (EXIF GPS on JPEG and HEIC, QuickTime ISO6709 on MOV). The city name lives in the Photos database, not in the file. Apple Photos, Immich, and digiKam then show a map. | Read the coordinates from the file. The place name stays empty until someone sets it. A WebGL globe ships its own earth texture. No map tiles, no network. Click a cluster to filter and open. Play orbits, zooms in, shows pictures from that place, and zooms out. |
| People and object search | Immich and Apple Photos run their own models. digiKam can store face tags. | This server stores the names. It does not ship a model. An agent writes people, places, and things into JSON. Optional `setup-ml` / `setup-geo` can fill unnamed GPS cities, YOLO Things, and unnamed face clusters **locally**. Search reads that JSON. No cloud. |
| Missing volume | Lightroom shows offline files with a badge and still shows the preview if the preview was generated. | If the original is not on this computer, the item can stay in the grid with its small preview. Showing or hiding those items is a setting. |
| Viewer chrome | Windows Photo Viewer: bottom prev/next, F11 slideshow/fullscreen, rotate, open-with, print. Windows Photos: F5 slideshow, Esc, Alt+Enter info, Ctrl+0/+/−/R, All/Photos/Videos. Apple Photos: heart, Info, fit. Google Photos: favorites strip, videos, search. IrfanView / XnView: fullscreen, EXIF, filmstrip, portable. | Must-for-presentable is locked in UI-SPEC: fullscreen, slideshow, viewer keys, EXIF-first Info, Open beside Reveal, empty/error, remove vs delete-file, sort/filters, search, Update UX. Filmstrip / Print / `?` are Soon. No cloud, AI, burn, or email. |
| Remove vs delete | Apple Photos: Delete removes from an album; Command-Delete removes from the library. Photos/IrfanView can trash bytes with confirm. | Delete key removes from the library (confirm; originals stay). Delete file is extra confirm + Recycle Bin. Undo restores catalog only. |

## Input overlay

Applied from the cross-project defaults, not reinvented here:

- Ctrl+Z / Ctrl+Shift+Z undo catalog and settings edits. A deep history, about 500 steps, stored in files.
- Esc exits the innermost interaction: tour/gesture, dialog, viewer, settings, then selection.
- Settings are a page, saved as JSON beside the catalog.
- Crashes and request errors append to a log file in the library folder.
- Nothing important is stored in browser localStorage.
- Ctrl+C copies the selected item's path as text.
- Wheel zoom is anchored on the cursor. Middle-click drags the open picture.
- In the viewer, click video/live motion or press Space to play or pause. A still click does nothing. A click in the grid opens the item.
- A file that is already on disk is never overwritten. A copy writes `name_2.ext` beside it.

## Preview files

Generated pictures are not originals. Two honest places exist, and both are in use in the wild:

- Next to the catalog (Smriti, Lightroom previews). They travel with the server. A folder you did not copy still shows its small pictures on another computer.
- Inside the folder you selected (sidecar style). They sit with those originals. If that disk is unplugged, the small pictures are unplugged too.

The setting `previewStore` chooses. Default is next to the server, because the library was meant to move as one folder. Each source may override it.

## Refinement 2026-10-12

PRODUCT and UI-SPEC clarify the existing defaults: reference artwork does not add
Albums, storage meters, or native window chrome. Presentable hover plays the
proxy in Years, Months, Days, and Off; `playProxies=off` disables;
`days-and-all` is the older stills-at-Years/Months value. The product keeps
its 16 settings and fixed shortcuts; the generic baseline does not authorize
a new keybinding editor in this build.

## Refinement 2026-10-13

Favorite (viewer heart, tile hearts, Favorites strip) and Reveal in Explorer
are authorized named actions — not albums and not a 17th setting. The
Windows Presentable Shell in UI-SPEC is the family-PC North Star.
Fullscreen, slideshow, EXIF Info, remove vs delete-file, one Size slider,
Dates Years/Months/Days/Off, side zoom %, bottom scrub + mute/volume,
hover in Years and Months, Preview/Original/Full badge, MOV `playback.mp4`,
Reveal argv that survives spaces, header SHA + Update, and the rest of
the Must list are locked requirements, not backlog. Filmstrip, multi-select,
Print, and `?` stay Soon. Reference art still does not add Albums or a
storage meter. Optional local packs (`Setup.bat` / `setup-ml` / `setup-geo`)
are specified; they do not add a Check. No MSI. No cloud default.

## Refinement 2026-10-14

Docs audit on `cursor/reveal-explorer-8d56` folds sibling tips #12–#16
and pending Reveal-spaces / MOV / Years-Months hover / Preview badge
notes into PRODUCT, UI-SPEC, and CONTRACTS. Shipped vs gap is the
honesty table in UI-SPEC. One-shot rebuild prompt:
[ONE_SHOT_PROMPT.md](ONE_SHOT_PROMPT.md).
