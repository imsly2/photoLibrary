# S12 — Pair still and motion as Live Photos

Locked 2026-10-13 after S11 at `f27917f`. **Closes F19.** Re-run F5, F7, F10, F14, F16. Do not wait for taste.

Read PRODUCT F19, CONTRACTS Live pairing, UI-SPEC LIVE badge/hover, FIXTURES live pair, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- A still and a short movie that share the same nonempty Apple `contentIdentifier` within a source are one item, `kind: "live"`. Item id is the still's hash. Both paths are stored (still + motion components).
- Pairing uses the embedded identifier, not filename. Reversed arrival, restart, orphan, and mismatch stay honest.
- Grid badge reads LIVE. Hover, when proxies are allowed, plays the short motion. Missing motion falls back to the still.
- Annotations and history stay on the live item through pairing.
- `python -m tests.qa slice S12`, `check F19`, and re-run F5, F7, F10, F14, F16 on fixture-owned roots.
- Original bytes unchanged. `library/` must not import Pillow. This runner's ffmpeg still cannot decode `quad.heic` / `quad.heif`; keep error+placeholder honesty.

## Out of scope

Settings page, F21/F22 state gallery, new settings. Do not add test-only UI.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts: `result.json`, `stdout.log`, `live-item.json`, `live.png`, `live-playback.json`, `regression.json`.

```powershell
python -m tests.qa slice S12 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F19 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F5 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F7 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F10 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F14 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F16 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Fixture pair with the same content identifier is one item JSON, `kind` `live`, two locations, id = still hash. Record `live-item.json`.
2. Reversed arrival, restart, orphan, and mismatch do not invent a second live pair or steal another item's id.
3. Real page: LIVE badge; hover/explicit play of motion when proxies allow; missing motion falls back to still. Record `live.png` (1280×720) and `live-playback.json`.
4. F5, F7, F10, F14, F16 stay green. Record `regression.json`.
5. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
