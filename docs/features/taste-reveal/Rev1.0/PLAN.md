# Taste-Reveal — Explorer selects the real on-disk file

Sits on `cursor/reveal-explorer-8d56` (PR #14 tip `1cac4c9`). Steve’s
Windows taste bugs after Update Library: Reveal still opened Documents
on paths with spaces; grid hover preview stopped playing; large videos
looked like the full file while still on the proxy. Does not close a
Check. No 17th setting.

Read PRODUCT F3 / F7 / F10 / F16, CONTRACTS reveal, UI-SPEC checklist
8 / 15 and **Video playback and zoom**, and this file.

## In scope

1. `POST /api/items/<id>/reveal` resolves the current original the
   same way media `which=original` does, then opens Explorer with
   argv `["explorer.exe", "/select," + absolutePath]`. The comma is
   glued to the path. No extra quotes in that arg. Paths with spaces
   (e.g. `J:\Iphone Backup\Another Rope Swing.MOV`) must select the
   file, never Documents.
2. Catalog-relative copy-here paths are resolved under the library
   folder before launch. The JSON `path` / `folder` are absolute.
3. Missing originals return 404 `unavailable` and do **not** launch
   Explorer (Windows would otherwise fall back to Documents).
4. The viewer shows “Original is not on this computer” when Reveal
   fails. `#reveal-error` sits with the actions.
5. Open uses the same resolved file; it does not launch a missing path.
6. Viewer video chrome: `#viewer-mute` and `#viewer-volume` sit beside
   `#viewer-scrub`. Hover proxies stay silent. Not a setting.
7. Grid hover plays again at every Size when policy allows (Days /
   All, dated Years/Months, Dates=Off wall, or `playProxies=always`).
   Catalog rebuild must not leave a hovered tile paused.
8. `#viewer-source` beside the filename: Preview / Loading full… /
   Original / Full / Preview — full unavailable. Progressive
   proxy→original or `playback.mp4` stays; the label must not
   pretend a silent proxy is the full file. MOV uses Full when the
   library H.264/AAC derivative is playing.

## Out of scope

S13/S14, filmstrip, multi-select, Print, `?`, macOS/Linux F2.
Do not change `launch.ps1` or `/api/update`.
Hover play in dated Years/Months is the family default (Steve).
`playProxies=off` still leaves tiles still.

## Gate

```
python -m tests.qa slice TASTE-REVEAL --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa slice TASTE-VIDEO --root "$qaRoot/library-data" --artifacts $videoEvidence
```

Artifacts under `docs/features/taste-reveal/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
