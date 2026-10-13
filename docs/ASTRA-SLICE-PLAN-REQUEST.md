# Astra — refine the Library north star and write the slice plan

Paste this whole file into Astra. Repo: `J:\slyOS`. Product: `J:\slyOS\projects\photoLibrary`. Date: 2026-10-12.

You are refining a spec and writing a build plan. Do not write the server. Do not scan a real photo disk. Do not add a feature Steve has not already described.

## Role

Working software architect. Disagree where the spec is thin, contradictory, or would force Steve back into the loop. Lock the answers in the docs. Leave at most one question, and only if a real fork remains that the existing decisions do not cover.

## Read, in this order

1. `J:\slyOS\projects\photoLibrary\docs\PRODUCT.md` — the help file. Every feature has a **Check**. This is the north star.
2. `J:\slyOS\projects\photoLibrary\docs\CONVENTIONS.md`
3. `J:\slyOS\projects\photoLibrary\docs\STATUS.md`
4. `J:\slyOS\projects\photoLibrary\docs\reference\` — layout targets, not screenshots of a running app.
5. `J:\slyOS\projects\slyAI\shared\SPEC-FIRST-PIPELINE.md`
6. `J:\slyOS\projects\slyAI\shared\ORCHESTRATION.md`
7. `J:\slyOS\projects\slyAI\shared\WORKING-ORDER.md`
8. `J:\slyOS\projects\slyAI\shared\STEVE-INPUT-PREFERENCES.md` — table stakes already applied in the help file.
9. `J:\slyOS\projects\iphonePhotos\docs\PRODUCT.md` — the phone copier. It stays a separate tool. The library only indexes a folder.

## What already settled (do not reopen)

- A folder on a drive. Python plus ffmpeg. Browser on this computer. Command line and HTTP are the same operations. No Electron.
- Catalog is JSON next to the server. SQLite is rebuilt from that JSON. Paths on this drive are relative. Drive letters are not identity.
- Add folder asks: copy onto this drive, or serve that folder in place. Default is ask. That default is a setting.
- Preview files default to next to the server. A setting stores them inside the selected folder. A source may override. A command moves them.
- If a linked folder is not on this computer, items stay visible with the small preview and “Original is not on this computer.” A setting hides them.
- People, places, and things are JSON files. Pictures point at them by id. Search reads ids. GPS creates a place with a null name. This product does not ship or run an image model. An agent writes names with `annotate`.
- Location is the coordinates inside the file. JPEG and HEIC use EXIF GPS. MOV and MP4 use QuickTime ISO6709. The iPhone's place name is not in the file and is not required. A WebGL globe uses a texture shipped with the app. No map tiles and no network. Drag spins. Wheel zooms, cursor stays put. Click a cluster filters to those places and opens the newest item. Play is a tour: orbit, zoom to a place, show up to `tourPictures` from that place, zoom out, orbit, repeat until Esc. No coordinates means Play does nothing.
- Never overwrite an existing file. Write `name_2.ext`.
- Undo, Esc, settings file, crash log, cursor-anchored zoom, middle-click pan. Already in the help file.
- The phone USB copy is iphonePhotos. Do not merge the programs.

## Your job

### 1. Say what this product is

Write a short product definition at the top of `PRODUCT.md`, in Steve's words, that a cold agent can repeat:

- Who it is for (Steve, on a Windows PC, pictures already in folders, often on a drive he moves).
- The job in one sitting: launch the folder, point at pictures, browse them fast, and let an agent file what is in them.
- What it is: a library server that lives in a folder and moves with that folder.
- What it is not. The phone copier. A cloud host. An app with a bundled image model. A desktop shell around a browser. A tool that rearranges originals on its own.

If the current help file describes features without saying this, the definition is the missing piece. Steve corrects this paragraph, not the code.

### 2. Write the specs a builder would otherwise invent

The failure this pass exists to stop: an implementer reaches a slice and invents a field, an error, a screen state, or a setting because nobody wrote it down.

Before any slice is buildable, these docs exist and `PRODUCT.md` points at them. Write them now. If a behavior is already in `PRODUCT.md`, move the contract detail into the spec and leave the help file as the user-facing description plus the **Check**. Do not contradict `PRODUCT.md`. If you must change a behavior, mark it in the locked-decisions table with the reason.

| Spec | Write it | What a slice is forbidden to invent |
|------|----------|-------------------------------------|
| `docs/PRODUCT.md` | Keep as the help file. Add F-ids, the product definition, a locked-decisions table. | A feature with no id. A second north star. |
| `docs/CONTRACTS.md` | Every JSON file: item, source, person, place, thing, settings, undo entry. Id rules, hash vs pending id, path rules, box units, error JSON, HTTP status codes, CLI exit codes. | A new field, a new error string, a new status code. |
| `docs/UI-SPEC.md` | Each screen state: empty library, scanning, ready, unavailable original, preview missing, settings, globe, globe tour. Gestures and keys. How each file in `docs/reference/` maps to a state. The globe and the tour have no reference image yet. Specify the motion in words from `PRODUCT.md`: orbit, zoom in, play pictures, zoom out. What the page does not decide (layout tweaks Steve has not asked for stay as the reference image). | A new screen, a new gesture, a modal the help file does not name. A tile server. |
| `docs/FIXTURES.md` | The files under `tests/fixtures/`, the EXIF and GPS values, the Live Photo pair, and which Check uses which file. | A fixture made up inside a slice. |
| `docs/SLICES.md` | The layer plan below. | A slice that needs a contract you did not write. If you find one, write the contract first. |
| `docs/AGENT-BUILD-MODE.md` | The orchestrator loop below. | A second workflow. |

Walk `PRODUCT.md` once and list, in `CONTRACTS.md` at the top, every decision you had to make that the help file left open (package layout, how the page is served, exact error body, pending-id rename). Those are locked decisions. A later slice that wants a different answer stops and edits the spec. It does not pick one in code.

Number the features F1, F2, … in `PRODUCT.md`, each still ending in the **Check** it already has. Add a Check only where a described behavior has none.

### 3. Lay out layers, milestones, and slices

Write `J:\slyOS\projects\photoLibrary\docs\SLICES.md`.

Progressive slices. Each slice leaves something an agent can run. Later slices only add. A slice may not depend on a slice listed after it.

Use layers. Suggested shape, change it if the dependencies are wrong:

| Layer | Runnable result |
|-------|-----------------|
| 0 | Launcher, health URL, empty library folder, settings.json |
| 1 | Scan fixtures, item JSON, metadata, places from GPS, resumable second scan, rebuild SQLite |
| 2 | Thumbs, medium stills, video poster, video proxy, preview-store setting and relocate |
| 3 | Browser: years / months / days / all, open one item, sort |
| 3b | Globe from place coordinates, click cluster filters and opens, Play tour |
| 4 | Copy-here and serve-from-there, unavailable show/hide |
| 5 | Annotate people / places / things, search, merge people |
| 6 | Live Photo pair, undo, clipboard, crash log, keyboard |

For every slice record:

- Id and one-line result
- Feature ids and **Check** commands it closes
- What must already be green
- Gate an agent runs (command, expected result, artifact path under `docs/features/` or `library-data` temp)
- Whether Steve has to look. Most slices are no. A milestone is yes.

Milestones are the slices Steve can taste in a few minutes, with pictures or a local URL attached. Name them. The first one should be: a fixture folder scanned, small pictures on screen, one photo opened. Not the AI names. Names are a later milestone because they are JSON an agent writes, and the page only has to show them.

### 4. The stop line

Steve wants an orchestrator to keep going until a percentage of the north star is tested, then he tests.

Define that percentage as **Checks passed / Checks in PRODUCT.md**, not a vibe. Recommend the number and which milestone it lands on. Default recommendation if you agree: do not stop for Steve until the first browser milestone is green (he looks once). After that, the loop continues unattended until **100% of Checks** have verifier artifacts. If you believe he should stop earlier, say which Checks are in that prefix and why the rest can wait.

“Tested” means a fresh verifier, not the implementer, ran the Check and wrote the artifact path into `docs/STATUS.md`. The implementer’s own log is not a pass.

### 5. Orchestrator plan

Add `docs/AGENT-BUILD-MODE.md` for this product. It tells the orchestrating agent:

- Read `SLICES.md` and implement the next slice whose dependencies are green.
- Order is dependency order from `SLICES.md`, not the order of the help file.
- Recon, then implement, then a different agent verifies. Max 3 correction loops, then stop and summarize.
- Orchestrator does not write product code.
- One local git commit per green slice, message names the slice. No push.
- Update `docs/STATUS.md` only with Checks that have artifact paths.
- Stop for Steve only at a milestone marked taste, or at the stop percentage, with the URL and the artifact paths.
- One question to Steve maximum, and only at that stop.

Follow `ORCHESTRATION.md` for who types what. If a model slug in that file is not available, use the closest cheaper model that is. Do not invent a second workflow.

The orchestrator treats a missing contract as a stop. It does not invent the field, the error, the screen, or the setting in the slice. It writes the gap into `docs/STATUS.md` and halts that slice.

## Write back

1. `PRODUCT.md` — product definition, F-ids, locked decisions, holes closed.
2. `docs/CONTRACTS.md`
3. `docs/UI-SPEC.md`
4. `docs/FIXTURES.md`
5. `docs/SLICES.md`
6. `docs/AGENT-BUILD-MODE.md`
7. A short note: what this product is, in one paragraph; which specs you added so they would not be invented later; the stop percentage; the first taste milestone; the single question if one remains.

Do not start the server.
