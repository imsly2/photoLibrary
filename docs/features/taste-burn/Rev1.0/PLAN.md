# Taste-Burn — merge wizard, Live/burst stacks, Print

Locked after fillers PR #42 (`9a610ef`). Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`. No Win7 path work.
No export. No auto-delete or auto-merge.

Read PRODUCT F3/F14/F19, UI-SPEC People + Soon Print, CONTRACTS
`people merge` / item `stack`, TASTE-PEOPLE, TASTE-FILLERS, and this
file.

Already on main (skip): Recently added, folder filter, `?` help,
Fit/Fill, missing-original badge (#42). Multi-select / Move /
duplicates (#39–#41). Merge into… confirm (#37).

## In scope

1. **Light people merge wizard** — `people suggestions` /
   `GET /api/people/suggestions` ranks other people by face-centroid
   cosine. `#people-review` steps **Merge / Not same / Skip**. Merge
   runs existing `POST /api/people/merge`. Not same writes
   `catalog/people-not-same.json`. Skip only advances. Never merge
   without a Merge click.
2. **Live/burst polish** — computed `stack` on item reads. Live items
   and same-stem still+short-video pairs share one tile (LIVE). Burst
   stills (sequential names, close `capturedAt`) share one tile
   (`BURST n`). Expand in the viewer. Originals and item JSON stay.
3. **Print Ctrl+P** — browser print of the open viewer still, fit to
   the page (`#print-sheet` + `@media print`).
4. Chinese strings for the new chrome.

## Out of scope

S13/S14, filmstrip as a general strip, export, batch Delete file,
albums, a 17th setting, launcher / Win7 path edits, auto-delete,
auto-merge.

## Gate

```
python -m tests.qa slice TASTE-BURN --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-burn/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
