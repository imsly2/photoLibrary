# Taste-Duplicates — side-by-side compare

Locked after PR #39 (`79daf9a`). Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`. No Win7 path work.
No export. **Never auto-delete on hash match.**

Read UI-SPEC Info + `#selection-bar`, PRODUCT F5 hash merge and F3
`remove`, CONTRACTS locations/`sha256` and batch `remove`, and this
file. Catalog already stores exact copies as **one item with several
locations**. Info did not list those extra paths. Same filename on
different items (re-export / slightly different bytes) is the other
existing signal. Do not invent a second orphan catalog.

## In scope

1. Info **Also at** lists extra current paths on a multi-location
   item, plus **Compare copies**. Hash is a file fact.
2. `#duplicate-compare` shows sides with preview and stats
   (dimensions, size, path/folder, date, hash). Each distinct item
   has Keep / Remove. Default is Keep.
3. Apply with any Remove uses the existing confirm +
   `POST /api/items/remove` from #39. Cancel leaves both. Originals
   stay. Hash match never removes anything by itself.
4. `#filter-duplicates` opens detected groups. Selection **Compare**
   (2+ items) opens the same dialog for those ids.
5. `GET /api/duplicates` and CLI `duplicates` are the read-only
   grouping. Chinese strings for the new chrome.

## Out of scope

Auto-delete on hash match, location-drop API, multi-select
move-to-folder, export, Print, Live/burst, batch Delete file,
launcher / Win7 path edits.

## Gate

```
python -m tests.qa slice TASTE-DUPLICATES --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-duplicates/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
