# Library — pickup

2026-10-13. This is the doorway. Read it before editing code. The other documents
remain the authority for behavior; this page says where the work stands and
where each document lives.

Remote: private [imsly2/photoLibrary](https://github.com/imsly2/photoLibrary),
branch `main`. A cloud agent clones that repository. The parent `slyOS` tree is
not this repository and is not required to continue.

## Read order

1. This file.
2. [AGENTS.md](../AGENTS.md) and [README.md](../README.md).
3. [PRODUCT.md](PRODUCT.md) — features F1–F22 and the Check that closes each one.
4. [CONTRACTS.md](CONTRACTS.md) — records, paths, errors, HTTP, recovery.
5. [UI-SPEC.md](UI-SPEC.md) — screen states and input.
6. [FIXTURES.md](FIXTURES.md) — synthetic media and the QA command.
7. [SLICES.md](SLICES.md) — S00–S14 dependency order.
8. [AGENT-BUILD-MODE.md](AGENT-BUILD-MODE.md) — orchestrator loop and what counts as tested.
9. [STATUS.md](STATUS.md) — which Checks have evidence.
10. The PLAN for the slice you are about to build, under `docs/features/Snn/Rev1.0/PLAN.md`.

[CONVENTIONS.md](CONVENTIONS.md) records why the defaults look like other photo
apps. Reference images in [docs/reference/](reference/) are layout targets, not
passing screenshots.

Shared slyOS workflow notes (`ORCHESTRATION`, `WORKING-ORDER`, `VERIFY-TOOLBOX`,
`WORKFLOW-MEMORY`) live outside this repository. [AGENT-BUILD-MODE.md](AGENT-BUILD-MODE.md)
already contains the loop a cloud clone must follow. If a full slyOS checkout is
present, read those four files too. Do not invent a second workflow.

## What is true on `main`

Commit `9f6094c` is the cloud baseline. It contains the specification, the
fixture media, and three green slices. Score: **1 / 22 Checks = 4.5%**. Only F6
is closed. macOS and Linux launch has not been run, so F2 cannot be closed on
Windows evidence alone.

| Slice | Commit | Result | Closes |
|---|---|---|---|
| S00 | `662789d` | Empty durable library, settings, undo, port reuse, fixture gate | none |
| S01 | `977af0b` | Linked scan, hash identity, Live Photo pair, originals unchanged | none |
| S02 | `82c7f06` | Dates and GPS places | F6 |
| S03 | plan only, `9f6094c` | JPEG thumb and preview plan locked. No rendition code on `main` | none |

S00 evidence: [verify-2](features/S00/Rev1.0/assets/verify-2/result.json),
[orchestrator rerun](features/S00/Rev1.0/assets/orchestrator-rerun/result.json).
S01 evidence: [verify-2](features/S01/Rev1.0/assets/verify-2/result.json),
[orchestrator rerun](features/S01/Rev1.0/assets/orchestrator-rerun/result.json).
F6 evidence: [verify-2](features/S02/Rev1.0/assets/verify-2/f6/result.json),
[orchestrator rerun](features/S02/Rev1.0/assets/orchestrator-rerun/f6/result.json).

Correction loops already used: one each for S00, S01, and S02. Each still has
two remaining. S03 has three.

A Windows checkout may contain unpublished S03 edits (`library/renditions.py`,
`library/web/assets/library.js`, `tests/qa/s03.py`, and related diffs). Those
files are not on `main`, have not been independently verified, and are not the
baseline. Start S03 from [its plan](features/S03/Rev1.0/PLAN.md).

## Code and tests already on `main`

Python package `library/`: settings, history, lock, atomic writes, HTTP server,
scan, catalog JSON, disposable SQLite, metadata, and places. The page at
`library/web/index.html` is still the empty library shell. Launchers are
`launch.ps1` and `launch.sh`. Package metadata is `pyproject.toml`.

Fixture generator: `tests/fixtures/generate.py`. Committed media is under
`tests/fixtures/media/`. Optional private drops go in the ignored folder
`tests/fixtures/user-samples/`. Do not wait for those files, and do not commit
them.

QA runner: `python -m tests.qa`.

```powershell
python -m tests.qa fixtures --output <dir>
python -m tests.qa slice S00 --root <library-data> --artifacts <dir>
python -m tests.qa slice S01 --root <library-data> --artifacts <dir>
python -m tests.qa slice S02 --root <library-data> --artifacts <dir>
python -m tests.qa check F6 --root <library-data> --artifacts <dir>
```

On `main`, S03 and later slices, and every Check except F6, exit as
unimplemented. `python -m tests.qa all` is unimplemented until S14. Run slice
gates one at a time. S00 and S01 collide if they run together. Use a
fixture-owned temporary root and a port in 18765–18864. Leave port 8765 for the
single occupied-port test. Do not scan a personal folder, the camera roll, or
an external drive.

Python 3.12+ and ffmpeg/ffprobe must be on PATH. The fixture generator may use
Pillow and pillow-heif inside the gitignored `.venv`. `library/` does not import
Pillow. There is no exiftool and no ImageMagick requirement.

Plans already written:

- [S00](features/S00/Rev1.0/PLAN.md)
- [S01](features/S01/Rev1.0/PLAN.md)
- [S02](features/S02/Rev1.0/PLAN.md)
- [S03](features/S03/Rev1.0/PLAN.md)

## What is left

Follow [SLICES.md](SLICES.md). Do not skip ahead.

| Next | Closes | Proof |
|---|---|---|
| S03 still renditions | none (F7 and F10 stay open) | oriented JPEG thumb/preview, media bytes, real page screenshot |
| S04 browse (M1) | F9, F11 | grid, viewer, zoom, sort, screenshot packet |
| S05 copy and move | F1, F4 | both add modes, collisions, interrupted copy, relocation |
| S06 formats and video | F5, F7 | every fixture extension, silent proxy, hover policy |
| S07 previews away | F8, F16 | preview store, relocate, missing original and preview |
| S08 annotate and rebuild | F14, F20 | people, places, things, SQLite rebuild |
| S09 search (M2) | F10, F15 | viewer fields, search, playback |
| S10 globe | F12 | offline globe and cluster open |
| S11 tour (M3) | F13 | timed tour, Esc, no network tiles |
| S12 Live Photos | F19 | embedded identifier pairing and playback |
| S13 settings and keyboard | F17, F18, F21 | 16 settings, history, Esc, clipboard |
| S14 whole product (M4) | F2, F3, F22 | launch, CLI/HTTP parity, every screen state, rerun all 22 |

Prepare M1, M2, and M3 screenshot packets and continue. Do not wait for a taste
review. Ask Steve only for a hard blocker or one unresolved product choice. One
taste question waits until M4, and the queue does not stop for it.

## How to continue

The orchestrator locks the slice PLAN, spawns an implementer, then spawns a
fresh verifier who did not write the code. The orchestrator reruns the closing
command and reads the artifacts. The implementer's own log is not the grade.
Commit a green slice as `slice(Snn): <result>`, then push `main` to `origin`.
Leave a failed slice unpushed. Do not force-push. Do not commit runtime
`library-data/`, private samples, or sandbox copies under `docs/features/`.

Preserve originals. Do not add a cloud photo service, accounts, an image model,
phone copying, albums, favorites, or editing tools.

Documented worker slugs, when the tool offers them: recon `composer-2.5-fast`,
implement `cursor-grok-4.5-high-fast`, verify a fresh `grok-4.7-high-fast`.
The 4.5 implementer slug was absent in the first session; that session used
`cursor-grok-4.6-high` and said so. Use a listed slug. Do not invent one.
