# Taste-Select — batch favorite / remove

Locked after PR #38 (`89c1104`). Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`. No Win7 path work.
No auto-delete on hash match. No batch Delete file, export, move,
or side-by-side compare.

Read UI-SPEC **Filter bar** multi-select + Soon **Multi-select +
batch favorite / remove**, PRODUCT F3 favorite/remove, CONTRACTS
`favorite` / `remove`, and this file.

## In scope

1. Existing Ctrl/Cmd-click toggle and Shift+click range drive
   `#selection-bar`. Count, Favorite, Remove, Clear selection.
2. Batch favorite uses the same `catalog/favorites.json` write as one
   item. All selected become favorite; when every selected item is
   already hearted the control unfavorites (same toggle as one item).
   `POST /api/items/favorite` `{itemIds,favorite}` is one undo step.
3. Batch remove uses the same catalog drop as `remove` (item JSON,
   favorite entry, source file pointers, index). Original bytes stay.
   Generated thumbs/proxies are not wiped (same as single-item remove).
   Explicit confirm; cancel leaves them. `POST /api/items/remove`
   `{itemIds}` is one undo step. Delete key on a multi-selection
   confirm-removes those ids, not Delete file.
4. Chinese strings for the new chrome.

## Out of scope

Duplicate compare UI, multi-select move-to-folder, export, Print,
Live/burst polish, batch Delete file, albums, a 17th setting,
launcher / Win7 path edits, hash-merge auto-delete.

## Gate

```
python -m tests.qa slice TASTE-SELECT --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-select/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
