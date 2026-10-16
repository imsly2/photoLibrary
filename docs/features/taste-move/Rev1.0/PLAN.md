# Taste-Move — multi-select Move to folder

Locked after PR #40 (`72d9ab9`). Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`. No Win7 path work.
No export. No batch Delete file.

Read UI-SPEC `#selection-bar` Move, PRODUCT F3 `move`, CONTRACTS
Move to folder, and this file.

## In scope

1. `#selection-bar` **Move** opens `#move-folder`. Destination is a
   registered Settings folder and/or a browsed subfolder. Confirm
   shows count + destination. Cancel moves nothing.
2. `move <id> [id…] --to <folder>` / `POST /api/items/move` relocates
   originals. Same-drive rename; cross-drive copy+verify+delete.
   Never overwrite (`name_2.ext` or skip). Mid-item failure rolls
   that item's bytes back so the catalog matches disk.
3. Thumbs, proxies, playback, faces, favorites, tags, and people stay
   on the same item ids. Reveal opens the new path. Rescan does not
   create duplicates or redo ready work.
4. Chinese strings for the new chrome.

## Out of scope

Export, Print, Live/burst polish, batch Delete file, albums, a 17th
setting, launcher / Win7 path edits, auto-delete on hash match.

## Gate

```
python -m tests.qa slice TASTE-MOVE --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-move/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
