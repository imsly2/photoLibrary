# Taste-Video — Windows video + zoom + chrome on the Presentable Shell Must tip

Locked after Steve’s Windows notes on video, zoom, and chrome. Sits on
`cursor/video-zoom-taste-1d0c` (PR #10). Does not close a new Check.
Does not rewrite Win7 chrome ids (`#viewer-nav`, `#viewer-zoom-slider`,
`#open-original`). No 17th setting. No cloud. Keep `launch.ps1` and
`/api/update` healthy.

Read UI-SPEC **Video playback and zoom**, PRODUCT F7 / F9 / F10 / F21,
and this file.

## In scope

1. Viewer video stays fitted and centered across Play and proxy→original.
2. Grid hover plays at every Size, including a zoomed-out Dates-off wall.
3. One grid **Size** slider (`#size-slider`, eight stops). No Level slider.
4. Dates `#date-group`: Years / Months / Days / Off. Off = one continuous
   wall. Dates is not a second zoom slider and does not move Size.
5. Grid Ctrl+wheel drives Size only.
6. Viewer zoom is a vertical side `#viewer-zoom-slider` with
   `#viewer-zoom-pct`. Plain wheel is primary zoom.
7. `#viewer-scrub` lives in `#viewer-bottom` (not over the picture).
   `.tile-scrub` stays on hovered tiles.
8. Progressive start: proxy first, then original (MP4) or
   `playback.mp4` (MOV/AVI/MKV); `currentTime` kept. `#viewer-source`
   names Preview / Loading full… / Original / Full / Preview — full
   unavailable.
9. Clicking a video tile autoplays the viewer at the tile’s `currentTime`.
10. `launch.ps1` unwrap / reverse-slice fix from PR #9, keeping `-Update`.
11. `clip.mov` serves a full-sound `playback.mp4`; badge says Full.
    Browser-safe `clip.mp4` stays Original and does not store a
    playback file. Preserve Originals keeps the MOV on disk.
12. Proxies stay small (width ≤ `proxyWidth`, CRF 28, no audio). A
    stored playback, when needed, stays under the 1280 / CRF 23
    policy so a 4K phone clip cannot write a multi-GB sibling.
    Browser-safe MP4 is `not-applicable`. Orphan `*.tmp` is removed.

## Out of scope

S13/S14, filmstrip, multi-select, Print, `?`, recently added, macOS/Linux
F2. Hover play + `.tile-scrub` work in dated Years/Months (default
`days-and-all`), not only Days and Dates=Off. `playProxies=off` still
leaves tiles still.
Do not fight a separate version-label PR.

## Gate

```
python -m tests.qa slice TASTE-VIDEO --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa.launch_ps1_args
```

Artifacts under `docs/features/taste-video/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
