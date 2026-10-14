# Taste-Reveal — Explorer selects the real on-disk file

Sits on `cursor/grid-density-date-6efb` (PR #12). Steve’s Windows
taste bug: Reveal in Explorer opened Documents (or another wrong
folder) instead of the directory that contains the image or video.
Does not close a Check. No 17th setting.

Read PRODUCT F3 / F10 / F16, CONTRACTS reveal, UI-SPEC checklist 15,
and this file.

## In scope

1. `POST /api/items/<id>/reveal` resolves the current original the
   same way media `which=original` does, then opens Explorer with
   that **absolute** file selected: `explorer.exe /select,"fullpath"`.
2. Catalog-relative copy-here paths are resolved under the library
   folder before launch. The JSON `path` / `folder` are absolute.
3. Missing originals return 404 `unavailable` and do **not** launch
   Explorer (Windows would otherwise fall back to Documents).
4. The viewer shows “Original is not on this computer” when Reveal
   fails. `#reveal-error` sits with the actions.
5. Open uses the same resolved file; it does not launch a missing path.

## Out of scope

S13/S14, filmstrip, multi-select, Print, `?`, macOS/Linux F2.
Do not change `launch.ps1` or `/api/update`.

## Gate

```
python -m tests.qa slice TASTE-REVEAL --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-reveal/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
