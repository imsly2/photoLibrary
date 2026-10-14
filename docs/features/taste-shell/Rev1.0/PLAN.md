# Taste-Shell — Windows Presentable Shell Must 6–10

Locked after UI-SPEC **Windows Presentable Shell** on PR #7
(`cursor/viewer-shell-must-2e74`, `bd9746d`). Does not close a new
Check. Does not rewrite Win7 viewer chrome (`#viewer-nav`,
`#viewer-zoom-slider`, `#open-original`, Update Library, Slideshow,
Fullscreen, `#viewer-facts`). No 17th setting. No cloud.

Read PRODUCT F3 / F11 / F15 / F18 / F21, CONTRACTS `remove` / `delete-file`
/ `kind=photo,live` / `q` date, UI-SPEC Must 6–10, and this file.

## In scope

6. Empty / first-run / error: “No pictures yet” + `#empty-add-folder`;
   scan failure path + `#scan-retry`; existing missing-file placeholders;
   reconnect banner (exact text) + `#reconnect-retry`.
7. Remove from library vs Delete file: Delete key + `#confirm-remove`;
   `#delete-file` extra confirm; `POST /api/items/<id>/remove` and
   `/delete-file`; originals stay on remove; Recycle Bin / OS trash on
   delete-file; undo restores catalog only.
8. Sort Newest / Oldest / Name (`#sort-presentable`); Location stays;
   hidden `#sort` / `#dir` keep F11. Filters All / Photos / Videos /
   Favorites (`kind=photo,live`, `kind=video`, `favorite=1`).
9. Search filename + capturedAt date (`YYYY` / `YYYY-MM` / `YYYY-MM-DD`)
   + existing tags; empty “No matches for …”.
10. Update UX finish: `#update-library` shows Updating… then the
    family sentence; `Update.bat` / `launch.ps1 -Update`.

## Out of scope

Viewer fullscreen, slideshow, Info EXIF block, Ctrl+0/1/R tooltips,
filmstrip, multi-select, Print, `?`, recently added, macOS/Linux F2,
S13/S14.

## Gate

API + browser proof under
`docs/features/taste-shell/Rev1.0/assets/<run-id>/`.
Does not close F3 / F11 / F15 / F18 / F21. 16/22 unchanged unless a
fresh F-id rerun is recorded in STATUS.
