# Taste-Video — Windows video + zoom on the Presentable Shell Must tip

Locked after Steve’s Windows notes on video and zoom. Sits on
`cursor/windows-presentable-shell-must-806a` (PR #8). Does not close a
new Check. Does not rewrite Win7 chrome ids. No 17th setting. No cloud.

Read UI-SPEC **Video playback and zoom**, PRODUCT F7 / F9 / F10 / F21,
and this file.

## In scope

1. Viewer video stays fitted and centered across Play and proxy→original.
2. Grid hover plays at every Size, including a zoomed-out Dates-off wall.
3. Grid **Level** (`#zoom-slider`) and **Size** (`#size-slider`) are two
   labeled controls; viewer Zoom stays only in the viewer.
4. Plain wheel zooms the open still or video.
5. Progressive start: proxy first, then original; `currentTime` kept.
6. `#viewer-scrub` and `.tile-scrub`.
7. `launch.ps1` unwrap / reverse-slice fix from PR #9, keeping `-Update`.

## Out of scope

S13/S14, filmstrip, multi-select, Print, `?`, recently added, macOS/Linux
F2. Do not change `playProxies` default stills for dated Years/Months.

## Gate

```
python -m tests.qa slice TASTE-VIDEO --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa.launch_ps1_args
```

Artifacts under `docs/features/taste-video/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
