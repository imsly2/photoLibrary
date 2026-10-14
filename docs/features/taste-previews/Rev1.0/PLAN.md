# Taste-Previews — grid thumbs stay painted

Locked after the PR #27 empty-grid poll coalescing. Does not close a
new Check. Keep Setup.bat / Library.bat / ASCII `.ps1`.

## In scope

1. Photo tiles show a real thumb when the file opens in the viewer.
   Do not leave **Preview is not available** on a ready still.
2. Person filter → remove the Person chip (the chip X, not only
   Clear all), and a second on/off cycle, must keep those thumbs.
   Reused cells cannot stick in an `<img>` error state.
3. A full page reload must paint every ready thumb again, not stall
   after the first few. Loads are queued so a refresh cannot abort the
   rest of the batch.
4. Video tiles keep their poster. Hover play is unchanged.

## Gate

```
python -m tests.qa slice TASTE-PREVIEWS --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-previews/Rev1.0/assets/<run-id>/`.
