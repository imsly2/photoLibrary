# Taste — split face, merge confirm, Photos together

Locked after Settings PR #36 (`28cfd93`). Does not close a new Check.
ASCII launchers untouched. No albums/cloud.

Read PRODUCT F3/F14, UI-SPEC People + Favorites collapse, CONTRACTS
`people merge` / `people split`, FACES, TASTE-PEOPLE, TASTE-FILTERS,
and this file.

## In scope

1. **Not this person / split face** — `people split` /
   `POST /api/people/split` `{personId,itemId,box?}`. One detection
   leaves that person as a new Unnamed person. Ada stays. Index face
   refs move (`plan_split_index`). Profile and Info crops.
2. **Merge into…** — with 2+ people selected, confirm dialog keeps the
   first selected person and runs existing `people merge`.
3. **Photos together** — AND `person=id1,id2` stays. Grid shows
   `#photos-together` (Favorites-style collapse) then leftover
   per-person groups. Leftover cells are not `data-slot="grid"`.

## Out of scope

S13/S14, albums, cloud, a multi-step wizard, F23. Do not rewrite
Setup.bat / Library.bat / ASCII `.ps1`.

## Gate

```
python -m tests.qa slice FACES --root "$qaRoot/library-data" --artifacts $faces
python -m tests.qa slice TASTE-PEOPLE --root "$qaRoot/library-data" --artifacts $people
python -m tests.qa slice TASTE-FILTERS --root "$qaRoot/library-data" --artifacts $filters
```

After Pull: restart Library. Re-run Faces only if a cluster still needs
a fresh detect.

Artifacts under each feature’s `Rev1.0/assets/<run-id>/`. 16/22
unchanged unless a fresh F-id rerun is recorded in STATUS.
