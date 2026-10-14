# Taste-Filters — chips, arrange, tags

Locked after Steve's install-night notes. Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`. No 17th setting. No albums.

Read UI-SPEC **Filter bar, chips, arrange, and tags**, PRODUCT F3 / F9 /
F11 / F14 / F22, CONTRACTS `person`/`thing` AND, `GET /api/groups?by=`,
`/api/tags`, and this file.

## In scope

1. Search stays in the header. All filters move to `#filter-bar`.
2. Active Person / Place / Tag chips with one-click remove and Clear all.
   Single `filter` object is the source of truth. Click a selected person
   again deselects that person.
3. Group Dates / People / Places / Tags. Unknown / No place / Untagged.
4. Collapse any group header; session memory.
5. Multi-person AND (`person=id1,id2`) with fixture data of 2–3 people
   and chip-removal proof.
6. User tags (Things): create, apply/remove on one or many selected
   items, filter chip, group by tag. Persist; survive re-infer.

## Out of scope

S13/S14, filmstrip, Print, `?`, batch Delete file, albums, a 17th
setting. Do not rewrite Setup.bat or launch.ps1.

## Gate

```
python -m tests.qa slice TASTE-FILTERS --root "$qaRoot/library-data" --artifacts $evidence
```

Also keep TASTE-PEOPLE, F9, F11, F14, F15 green.

Artifacts under `docs/features/taste-filters/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
