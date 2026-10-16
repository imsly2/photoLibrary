# Library — pickup

Current build doorway. North star: [PRODUCT.md](PRODUCT.md). Screen
contract: [UI-SPEC.md](UI-SPEC.md). What passed: [STATUS.md](STATUS.md).

## Do this next

1. Read **[Windows Presentable Shell](UI-SPEC.md#windows-presentable-shell)**
   and **Video playback and zoom**. Must-for-presentable items are locked
   shell requirements. The **Presentable for family PC** checklist
   (19 steps) is the taste gate.
2. Chrome taste: **Search lives on `#filter-bar`** with All/Photos/Videos/Favorites,
   Person/Place/Tag chips, Clear all, and **one** Group Date/People/Places/Tags
   control (default Date). Sort Newest/Oldest/Name/Location stays in the
   header and does not duplicate Group. Language English/中文 is in the
   header and persists as `settings.language`. Size + Dates live
   in `#library-chrome` at the **bottom-left** of the grid. Right
   **People** splitter (`#library-side`) filters by face (AND when
   several are selected; click a selected person again to remove).
   People and Tags are each collapsible for the session (People open,
   Tags collapsed by default) so Tags never covers a face.
   `#jobs-panel` Pause / Start talks to `/api/jobs`. Keep one Size
   slider, Dates Years/Months/Days/Off, Ctrl+wheel on Size only,
   `#viewer-nav` / `#viewer-zoom-slider` / `#viewer-scrub`. Do **not**
   restore a Level slider, header search, or People/Places/Things search chips.
3. Do **not** start S13/S14 or Soon rows (filmstrip, multi-select, Print,
   `?`, recently added) while a Must checklist row is red. Globe polish
   beyond F12 waits. macOS/Linux launch is pinned.
4. Optional local AI is stacked on this tip: `setup-geo`,
   `setup-ml objects`, `setup-ml faces`. Processing Pause/Start drives
   those drains when models/pack are installed.    People fills from real
   face clusters. `Setup.bat` composes those CLIs. After Update, re-run
   faces with the stricter gates: `python -m library infer-faces --force`
   or Processing **Re-run Faces**. Tune `faceMatchThreshold` (default 0.80,
   Settings slider 0.35–0.95) and `faceMinSidePx` (default 80). Large
   stills use overlapping 1280 detect tiles, then the same original→112
   ArcFace crop. No 23rd Check.
5. A feature Check is still closed only by [STATUS.md](STATUS.md)
   artifacts. 16/22 remains until those run. No 23rd Check.

**After Pull (recently added / keyboard / missing original):** Restart
Library. After a scan, **Recently added** shows those new items.
Settings folder **Show photos** (or the Folder control) filters to that
source. Press `?` for the shortcut list; `V` toggles Fit/Fill in the
viewer. Tiles and Info mark a missing original; Locate opens the last
known folder when it is still there. Nothing is auto-deleted. Re-run
Faces only if a wrongly joined cluster still needs a fresh detect.

Forbidden: accounts, cloud sync, cloud AI, in-app edit, albums.
