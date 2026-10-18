# Library — pickup

Current build doorway. North star: [PRODUCT.md](PRODUCT.md). Screen
contract: [UI-SPEC.md](UI-SPEC.md). What passed: [STATUS.md](STATUS.md).

## Do this next

1. Read **[Windows Presentable Shell](UI-SPEC.md#windows-presentable-shell)**
   and **Video playback and zoom**. Must-for-presentable items are locked
   shell requirements. The **Presentable for family PC** checklist
   (19 steps) is the taste gate.
2. Chrome taste: **Search lives on `#filter-bar`** with All/Photos/Videos/Favorites,
   4 stars and up / Picks / Hide rejects / Blurry, Person/Place/Tag chips,
   Clear all, and **one** Group Date/People/Places/Tags
   control (default Date). Sort Newest/Oldest/Name/Location/Rating stays in the
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
3. Do **not** start S13/S14 or leftover Soon rows (filmstrip as a
   general strip, export) while a Must checklist row is red. Globe polish
   beyond F12 waits. macOS/Linux launch is pinned.
4. Optional local AI is stacked on this tip: `setup-geo`,
   `setup-ml objects`, `setup-ml faces`, `setup-ml transcribe`,
   `setup-ml aesthetic`. Processing Pause/Start drives those drains
   when models/pack are installed.
   People fills from real face clusters. Videos with sound get a local
   Whisper transcript plus an extractive summary. Photos get suggested
   1–5 stars (Basic sharpness/exposure/faces; Smart adds a local NIMA
   ONNX). `Setup.bat` composes those CLIs. After Update, re-run
   Setup.bat once for the Whisper and aesthetic models, restart Library,
   and Start Processing. Re-run faces with the stricter
   gates: `python -m library infer-faces --force` or Processing **Re-run
   Faces**. Tune `faceMatchThreshold` (default 0.80, Settings slider
   0.35–0.95) and `faceMinSidePx` (default 80). Large stills use overlapping
   1280 detect tiles, then the same original→112 ArcFace crop. No 23rd Check.
5. A feature Check is still closed only by [STATUS.md](STATUS.md)
   artifacts. Current processing-feedback handoff reopens F4/F7/F8: 13/22
   recorded passed. Continue [HANDOFF](features/processing-feedback/Rev1.0/HANDOFF.md)
   before broader work. No 23rd Check.

**After Pull (rating / transcript / merge wizard / Live-burst / Print):**
Rerun `Setup.bat` once so `setup-ml transcribe` can download Whisper
`small` and `setup-ml aesthetic` can download the local NIMA ONNX if
this PC does not have them yet. Restart Library. Start Processing so
the Transcribe and Rating queues can run. Settings **Rating** stays
**Basic** unless Steve chooses Off or Smart. Settings **Transcribe
videos** stays On unless Steve turns it off. 1–5 rates the open
picture; P picks; X rejects (hides from default views; the file
stays); 0 clears. Filter chips: 四星及以上 / 精选 / 隐藏排除 / 模糊.
Nothing is auto-deleted or auto-rejected. Export stays on hold.
People **Review matches** steps likely same-person pairs (Merge / Not
same / Skip). Nothing merges until Merge. Live and burst stacks share
one tile with a badge; open the viewer to expand. Ctrl+P prints the
open picture fit to the page. Recently added, `?`, Fit/Fill, and the
missing-original badge stay from #42. Re-run Faces only if a cluster
still needs a fresh detect.

Forbidden: accounts, cloud sync, cloud AI, in-app edit, albums.
