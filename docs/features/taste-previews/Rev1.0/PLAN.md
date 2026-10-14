# Taste-Previews — grid thumbs stay painted

Locked after the PR #27 empty-grid poll coalescing. Does not close a
new Check. Keep Setup.bat / Library.bat / ASCII `.ps1`.

## In scope

1. Photo tiles show a real thumb when the file opens in the viewer.
   Do not leave **Preview is not available** on a ready still.
2. Person filter → remove the Person chip (the chip X, not only
   Clear all), and a second on/off cycle, must keep those thumbs.
   Reused cells cannot stick in an `<img>` error state.
3. A full page reload must paint every ready thumb again. A mid-batch
   stall (some tiles paint, then the rest freeze, or refresh does
   nothing) must recover: one in-flight load per cell, leaked slots
   released, and a 1s recover pass re-queues hung stills. Overlapping
   catalog paints cannot abort the rest of the batch.
4. Video tiles keep their poster. Hover play is unchanged.
5. After the first generate, `/api/media?which=thumb` must serve the
   existing file (Cache-Control + disk short-circuit). A second load
   or full refresh paints every visible ready thumb in a tight budget
   without re-encoding.
6. The person face-crop picker is single-select: exactly one
   `aria-pressed="true"`, visible selected chrome, click is immediate.

## Gate

```
python -m tests.qa slice TASTE-PREVIEWS --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-previews/Rev1.0/assets/<run-id>/`.
