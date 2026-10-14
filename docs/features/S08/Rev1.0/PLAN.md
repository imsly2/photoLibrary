# S08 — Store people, places and things; rebuild search

Locked 2026-10-13 after S07 at `a442e8f`. **Closes F14 and F20.** Viewer field commits and chip search stay open until S09 (F10, F15). F18 history cap stays open until S13.

Read PRODUCT F14 and F20, CONTRACTS annotate/merge/entities/pending annotate during scan, FIXTURES annotation and pending-annotation, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- `annotate <id>` / `POST /api/items/<id>/annotations` with the CONTRACTS payload. 200 updated item.
- Normalized boxes `[x,y,width,height]` on the oriented still. Omit means association without a box. Out-of-range boxes rejected (`invalid-argument`).
- Names and aliases reused case-insensitively. Empty/`null` name is an unnamed face. Setting the name updates that person file.
- Place: at most one `placeId`. Rename updates the place file. Non-GPS places exist only as explicit annotations.
- `people merge <keep-id> <drop-id>` / `POST /api/people/merge` `{keepId,dropId}`: rewrite every face, one history transaction, delete the dropped person. Self merge is `invalid-argument`.
- Real annotate on a pending id while `hash-publication` is paused. Annotations and history survive hash merge and restart. Do not reject annotate until hashing finishes.
- `rebuild-index` / `POST /api/rebuild-index` `{}` → 200 `{"ok":true}`. Deletes `catalog.sqlite` and rebuilds from catalog JSON. Search ids match before. Canonical JSON unchanged.
- `python -m tests.qa slice S08`, `check F14`, `check F20` on fixture-owned roots.
- Original bytes unchanged. `library/` must not import Pillow.

## Out of scope

Viewer typing/commit (F10/S09), search chips/inspector UI (F15/S09), globe, tour, Live pairing, settings page. Do not add a setting. Do not add an image model. Do not add test-only UI.

## Annotate

Payload: `{people?:[{id?,name?,box?}],places?:[{id?,name?}],things?:[{id?,name?,aliases?,box?}]}`. At most one place.

- Explicit id names that record. Missing id + matching name/alias reuses. Else create `person_<12hex>` / `thing_<12hex>` / `place_<12hex>`.
- Duplicate identical associations collapse. Distinct boxes may share an entity.
- History `operation: annotate`. Undo restores the previous item and entity files. Creating an entity then undoing must not leave a dangling name that later annotate would reuse incorrectly unless CONTRACTS require the file to remain; follow CONTRACTS: undo the item associations; orphan unused created records may be removed with the same transaction.
- Scan in progress: annotate is allowed; other bulk mutations return `busy`. The writer pauses hash publication for the annotate transaction.

F14 check:

1. `annotate <jpeg-id> --person Ada --thing mug` creates `people/person_*.json` name Ada and `things/thing_*.json` name mug. The item lists those ids.
2. Second item `--thing mug` reuses the same thing id.
3. `GET /api/items?thing=mug` returns both ids and no others.

## Merge, pending, rebuild

- Merge rewrites all faces atomically. History `people-merge`.
- Pending: seed or real scan at `hash-publication`, annotate Ada/mug on the pending id, resume, assert the hash item has the associations and history references the hash id not the pending id.
- Rebuild: annotate one thing, record search ids, delete `catalog.sqlite`, `rebuild-index`, search again, same ids. Artifact `rebuild-before-after.json`. `sqlite-rebuild` barrier still publishes one index.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts: `result.json`, `stdout.log`, `annotation-records/`, `merge.json`, `pending-migration.json`, `rebuild-before-after.json`.

```powershell
python -m tests.qa slice S08 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F14 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F20 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Prove Ada/mug create + reuse + `?thing=mug` search. Copy people/thing/item JSON into `annotation-records/`.
2. Unnamed face then name assignment. Place rename. Out-of-range box rejected. Alias Cup → mug reuses mug.
3. Merge Ada+other into Ada; every face points at keep; drop file gone. Record `merge.json`.
4. Pending annotate during hash barrier, resume and restart. Record `pending-migration.json`.
5. Rebuild after delete sqlite; search ids identical. Record `rebuild-before-after.json`.
6. Original hashes unchanged. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
