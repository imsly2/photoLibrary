# Taste-Empty-Grid — catalog has photos, grid shows photos

Locked after the PR #26 empty-grid regression. Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`.

## In scope

1. When the catalog has items and people, the Library grid must show
   photos. Never first-run "No pictures yet".
2. Clear all, All vs Favorites, and Group People must restore or keep
   photos. Groups API failure must not blank the grid.
3. Overlapping / slow `/api/items` must still land photos.

## Gate

```
python -m tests.qa slice TASTE-EMPTY-GRID --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-empty-grid/Rev1.0/assets/<run-id>/`.
