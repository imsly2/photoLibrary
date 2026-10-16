# Taste-Fillers — Recently added, keyboard help, missing original

Locked after Move PR #41 (`bd583a5`). Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`. No Win7 path work.
No export. No auto-delete.

Read UI-SPEC Soon **Recently added + per-folder browse**, **Keyboard
help `?`**, **Fit / Fill**, **Tile badges … missing**, PRODUCT F3
items filters + `locate`, CONTRACTS queries, and this file.

## In scope

1. **Recently added + folder filter** — session `library-data/recent.json`
   after a scan that added items. `#filter-recent` and
   `GET /api/items?recent=1`. Settings folder **Show photos** and
   `#filter-folder` send `source=<id>`. Not albums.
2. **Keyboard help** — `?` opens `#keyboard-help` (locked keys only,
   not an editor). Esc closes it first. `I` / Alt+Enter toggle Info.
   Viewer **Fit / Fill** buttons beside the zoom slider; `V` toggles
   Fill. Ctrl+0 stays Fit.
3. **Missing-original badge** — tile `.missing-badge` and Info flag
   when `available` is false. No auto-delete. Reveal if the last-known
   file is still there; Locate (`POST /api/items/<id>/locate`) if the
   last-known folder is still there.
4. Chinese strings for the new chrome.

## Out of scope

S13/S14, filmstrip, Print, export, batch Delete file, albums, a 17th
setting, launcher / Win7 path edits, auto-delete on missing files.

## Gate

```
python -m tests.qa slice TASTE-FILLERS --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-fillers/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
