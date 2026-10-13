# Taste-Windows — Add folder, server hardness, viewer chrome, launcher

Locked 2026-10-13 after Steve’s Windows notes on `cursor/s03-still-renditions-8e1d`. Does not close a new Check. Re-run F4 and F10. Pin macOS/Linux F2.

Read PRODUCT F2/F4/F10, CONTRACTS scan/picker/disconnect, UI-SPEC Add/Scanning/Disconnected/Viewer, and this file. Do not invent a 17th setting, upload, or Electron.

## In scope

1. **Add folder.** `POST /api/sources` returns 202 with `scan.state` running **before** the scan finishes. Close the dialog on 202. Confirm the folder, show scan status, poll, show items as they become ready. Never leave the dialog open on `busy`. Browse → `POST /api/pick-folder` (Windows native picker; 404 `picker-unavailable` here). Typed path still works. Serve stdout prints scan progress during normal work.
2. **Server hardness.** Client abort (`BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError`, WinError 10053) is non-fatal: no 500, no `internal-error`, server keeps serving. Page shows “Library is not responding” and retries health/catalog until 200.
3. **Viewer.** Visible Previous/Next/Back. Zoom in/out buttons (existing Ctrl+wheel stays). Display-only 90° rotate; do not rewrite originals. Arrows and Esc unchanged.
4. **Windows launcher.** `Library.bat` at the app folder runs `launch.ps1` in a visible console and opens the browser. Do not change `launch.sh`. Do not claim F2.

## Out of scope

macOS/Linux F2, F3 matrix, F22 gallery, photo editing, albums.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts under `docs/features/taste-windows/Rev1.0/assets/<run-id>/`: `result.json`, `stdout.log`, `add-progress.json`, `disconnect.json`, `viewer-chrome.png`, `scan-console.log`.

```
python -m tests.qa slice TASTE-WIN --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F4 --root "$qaRoot/library-data" --artifacts $evidence/f4
python -m tests.qa check F10 --root "$qaRoot/library-data" --artifacts $evidence/f10
```

The gate must:

1. `POST /api/sources` returns 202 while `scan.state` is still `running` (or finishes so fast the 202 body already has the source; then prove the HTTP response was sent without waiting on a second long copy). Dialog closed; `#scan-status` visible; typed path still adds the fixture folder. `POST /api/pick-folder` on this Linux runner is 404 `picker-unavailable`.
2. A client abort during a JSON write does not kill the server; health still 200. Offline/kill-server page shows “Library is not responding”; restore health clears it.
3. Viewer has Previous, Next, Back, zoom in/out, rotate. Rotate does not change original bytes. Arrows still work. `viewer-chrome.png` is 1280×720.
4. `Library.bat` exists and invokes `launch.ps1`. `launch.sh` unchanged.
5. F4 and F10 stay green. Never weaken assertions. `library/` must not import Pillow.

The implementer may run these and must not call that log the grade.
