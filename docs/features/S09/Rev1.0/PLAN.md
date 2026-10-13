# S09 — Find and open annotated pictures (M2)

Locked 2026-10-13 after S08 at `59ab5ab`. **Closes F10 and F15.** F21/F22 stay open. This is the M2 packet. Do not wait for taste.

Read PRODUCT F10 and F15, CONTRACTS items query and media, UI-SPEC viewer labels/search/inspector, FIXTURES annotation, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- Viewer shows existing people, place, and things from the item record. Typing a name and committing (Enter or blur) sends the existing `annotate` API. Labels refresh. Failed requests keep the text and show an inline error. No box-drawing editor.
- Search box substring against names, aliases, and filename. Chips restrict `q` to People, Places, or Things. Clicking a displayed entity label sets its id filter and inspector.
- Inspector count and filenames come from unique item ids, never location count. Empty search: “No matching pictures”. Clearing returns the broader grid.
- Filtered arrows and Esc: next/previous use the current filtered order; Esc restores filter, level, and scroll.
- Preview then original for stills; poster then original/proxy for video, with browser fallback. Exercise on current media.
- `python -m tests.qa slice S09`, `check F10`, `check F15` on fixture-owned roots.
- Original bytes unchanged. `library/` must not import Pillow.

## Out of scope

Globe, tour, Live badge pairing, settings page, keyboard-complete F21, F22 state gallery. Do not add a setting. Do not add test-only UI.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts: `result.json`, `stdout.log`, `search-mug.png`, `viewer-annotations.png`, `inspector.json`, `playback.json`. Browser proofs 1280×720 from the real page.

```powershell
python -m tests.qa slice S09 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F10 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F15 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Annotate Ada/mug via the real viewer fields (not only CLI). Labels refresh. Record `viewer-annotations.png`.
2. `GET /api/media` preview and original content types/lengths for a photo; video poster/original/proxy fallback in the browser. Record `playback.json`.
3. `check F15`: `q=IMG_1042` returns that filename; substring/name/id/chip queries; empty search; inspector count and filenames; no duplicate locations in results. Record `inspector.json` and `search-mug.png`.
4. Filtered arrows stop at ends. Esc restores the filter. No console errors on valid actions.
5. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
