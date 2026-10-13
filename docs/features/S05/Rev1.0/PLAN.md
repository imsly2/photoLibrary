# S05 — Copy a source and move the library intact

Locked 2026-10-13 after S04 at `5d0d692`. **Closes F1 and F4.**

Read PRODUCT F1 and F4, CONTRACTS copy/identity/undo, FIXTURES collision/moved-library/moved-linked-volume, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- `scan --copy-here` and `POST /api/sources` with `mode: copy-here`.
- Add folder dialog **Copy onto this drive** on the real page. `addFolderDefault` ask / copy-here / serve-from-there. CLI flag wins. ask + no flag is `choice-required`.
- Copy under `originals/<safe-name>-<source-id>/`, keep folder structure. Locations `kind: library-relative`. Existing files never overwritten; collisions write `name_2.ext`, `name_3.ext`.
- Convert a linked source with `copy-here <source-id>` after seeded annotations: same item ids, copied locations become primary, old volume locations stay alternates.
- Interrupted copy at the `.partial-<sourceId>` boundary resumes without extra copies or publishing a partial as an original.
- Move the app+data sandbox to a new absolute path. Copied originals and catalog still open. Linked volume remount uses the test volume seam, never a drive letter as identity.
- Copy undo removes catalog registration and does not delete copied original bytes.
- `python -m tests.qa slice S05`, `check F1`, `check F4`.
- Original byte hashes unchanged. `library/` must not import Pillow.

## Out of scope

Video proxies, preview relocate, annotate command (seed only), globe, search, settings page. Do not close F5, F7, F8, F16.

## Gate

Fresh fixture-owned roots. Artifacts: `result.json`, `stdout.log`, `paths-before-after.json`, `copied-items/`, `collision.json`, `original-hashes.json`.

```powershell
python -m tests.qa slice S05 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F1 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F4 --root "$qaRoot/library-data" --artifacts $evidence
```

Prove both Add choices, collision suffix, interrupted resume, convert-after-seed, move+remap, undo leaves bytes. Exit 0 only when every proof ran. Pin fixture mtimes from the manifest. Never weaken assertions.
