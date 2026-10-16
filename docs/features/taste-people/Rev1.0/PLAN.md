# Taste-People — bottom chrome, People panel, processing

Locked after Steve’s photoLibrary UI notes on
`cursor/reveal-spaces-hover-proxy-c876`. Does not close a new Check.
Keep the existing grid and viewer. No 17th setting. No albums.

Read UI-SPEC **People side panel and processing**, PRODUCT F3 / F9 / F14 /
F22, CONTRACTS `GET /api/people`, `PUT /api/people/<id>`, `person` AND,
`GET`/`POST /api/jobs`, and this file.

## In scope

1. Move `#size-slider` and `#date-group` into `#library-chrome` at the
   bottom-left of the library grid. Horizontal Size. Not a right rail.
2. Right vertical splitter `#library-splitter` and collapsible
   `#library-side`. First section: People.
3. People rows: face crop, name or Unnamed, count. Named always;
   unnamed only if `itemCount >= personOfInterestMin` (3).
4. Click filters to that face. Ctrl/Cmd-click ANDs selected faces
   (`person=id1,id2`).
5. Profile: rename + choose thumbnail face. Info still names people.
6. `#jobs-panel`: processing line, Pause / Start (Resume). Renditions
   drain honors pause. Analyze / infer-faces / objects report catalog
   pending and the same pause flag.
7. With 2+ people selected, **Merge into…** (`#people-merge`) confirms
   and keeps the first selected person (Ada←Bob). Profile / Info
   **Not this person** splits one face crop.

## Out of scope

S13/S14, filmstrip, photo multi-select, Print, `?`, all-faces dump,
macOS/Linux F2. Do not restore a Level slider.

## Gate

```
python -m tests.qa slice TASTE-PEOPLE --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-people/Rev1.0/assets/<run-id>/`.
16/22 unchanged unless a fresh F-id rerun is recorded in STATUS.
