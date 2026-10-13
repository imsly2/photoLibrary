# Taste-Windows Track A — Launch, Add folder, scan feedback, live-origin Back

Locked 2026-10-13 after Steve’s Windows notes. **Track A only.** Does not close
a new Check. Re-run F4. Pin macOS/Linux F2. Do not start S13 or S14.
Viewer/grid chrome is a sibling track.

Read PRODUCT F2/F4, CONTRACTS scan/picker/disconnect/live-origin, UI-SPEC
Add/Scanning/Disconnected/Live origin, and this file. Do not invent a 17th
setting, upload, or Electron.

## In scope

1. **Windows launcher.** `Library.bat` at the app folder runs `launch.ps1` in a
   visible console and opens the browser. No command prompt required. Do not
   change `launch.sh`. Do not claim F2.
2. **Native folder picker.** Browse → `POST /api/pick-folder` (Windows native
   picker; 404 `picker-unavailable` here). Typed path still works; it is not
   required on Windows.
3. **Add-folder UX.** `POST /api/sources` returns 202 with `scan.state` running
   **before** the scan finishes for **both** copy-here and serve-from-there.
   Close the dialog on 202. If the POST is `busy`, close and show scan status.
   Confirm the folder, show `#scan-status`, poll, show items as they become
   ready. Serve stdout prints scan progress during normal work.
4. **Live-origin Back.** The page stays on the process that served it
   (`window.location.origin`). In-app Back and browser Back must not navigate
   to another host or port (Steve: server on `:8765`, Back went to `:18765`).
   History and links are root-relative or current-origin only. Never embed
   `settings.port` or a stored runtime URL from another listen.
5. **Disconnect.** Client abort is non-fatal. Banner “Library is not responding”;
   retry health/catalog until 200.

Viewer chrome (Info, bottom Prev/Rotate/Next, zoom slider, Open, Update
Library) is a sibling track and is not this Track A gate.

## Out of scope

S13/S14, macOS/Linux F2, F3 matrix, F22 gallery, viewer/grid visual chrome
(prev/next/zoom/rotate styling), photo editing, albums.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts under
`docs/features/taste-windows/Rev1.0/assets/<run-id>/`: `result.json`,
`stdout.log`, `add-progress.json`, `disconnect.json`, `live-origin.json`,
`scan-console.log`.

```
python -m tests.qa slice TASTE-WIN --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F4 --root "$qaRoot/library-data" --artifacts $evidence/f4
```

The gate must:

1. `POST /api/sources` returns 202 while `scan.state` is still `running` for
   copy-here **and** serve-from-there (or finishes so fast the 202 body already
   has the source; then prove the HTTP response was sent without waiting on a
   second long copy). Dialog closed; `#scan-status` visible; typed path still
   adds the fixture folder. `POST /api/pick-folder` on this Linux runner is 404
   `picker-unavailable`.
2. A client abort during a JSON write does not kill the server; health still 200.
   Offline/kill-server page shows “Library is not responding”; restore health
   clears it.
3. After opening a still, in-app Back and a history Back stay on the live
   origin/port (`live-origin.json`). No absolute link uses a different port.
4. `Library.bat` exists and invokes `launch.ps1`. `launch.sh` unchanged.
5. F4 stays green. Never weaken assertions. `library/` must not import Pillow.

The implementer may run these and must not call that log the grade.
