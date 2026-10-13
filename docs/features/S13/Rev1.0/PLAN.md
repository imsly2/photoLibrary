# S13 — Complete settings, history and keyboard across views

Locked 2026-10-13 after S12. **Closes F17, F18, F21.** Do not invent settings or keys.

Read PRODUCT F17, F18, F21, CONTRACTS settings/undo/errors, UI-SPEC settings and keyboard, and this file.

## In scope

- Settings page: the existing 16 user settings only, grouped as the reference. Valid commit persists through HTTP immediately. `listenHost`/`port` apply next launch; label says “Applies next launch”. Inline validation keeps the last valid value. Esc returns to the prior Library/Globe view.
- Undo/redo: Ctrl+Z / Ctrl+Shift+Z; ~500 history cap; branch; restart; merge/copy/relocate undo. Undo of copy-here does not delete copied bytes.
- Esc innermost: tour/gesture, Add dialog, Viewer, Settings, then selection.
- Clipboard: Ctrl+C copies the primary path; unavailable copies lastKnownPath and says it is not on this computer.
- `server.log` gets time and path on uncaught errors and failed media reads.
- Keyboard table in PRODUCT F21, including focused-text exceptions and cursor anchors.
- `python -m tests.qa slice S13`, `check F17`, `check F18`, `check F21` on fixture-owned roots.
- Original bytes unchanged. `library/` must not import Pillow.

## Out of scope

F2 launch, F3 parity matrix, F22 state gallery. Do not add a 17th setting. Do not add test-only UI.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts: `result.json`, `stdout.log`, `settings-roundtrip.json`, `history.json`, `clipboard.txt`, `input-trace.json`, `server.log`.

```powershell
python -m tests.qa slice S13 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F17 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F18 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F21 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. `settings set previewStore with-source` then `settings get` shows `with-source` on disk without restart. Invalid values keep the last valid. Host/port labeled next launch.
2. `settings set port 8770`, undo, `settings get` is 8765. Forced 404 `/api/media/missing?which=original` writes `server.log` with time and path.
3. Drive every F21 key/gesture in the real browser, including focused-text exceptions, cursor anchors, pan, clipboard, Esc during each tour phase. Record `input-trace.json`, `clipboard.txt`, measurements, screenshots.
4. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
