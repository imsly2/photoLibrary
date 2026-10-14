# Library

A folder you put on a drive. It serves a photo and video library in the browser,
and a command line so an agent can scan, search, and write what is in the pictures.

The phone copier is a different tool: [iphonePhotos](../iphonePhotos/README.md).
Point this server at the folder that copier already filled.

| Read | For |
|------|-----|
| [docs/PRODUCT.md](docs/PRODUCT.md) | The help file. Every feature and the check that proves it. |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | What existing photo apps already do, and the defaults taken from that. |
| [docs/STATUS.md](docs/STATUS.md) | What is actually true on disk; Check evidence. |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | Records, paths, identity, operations, errors and recovery. |
| [docs/UI-SPEC.md](docs/UI-SPEC.md) | Screen states, inputs and reference boundaries. |
| [docs/FIXTURES.md](docs/FIXTURES.md) | Exact synthetic test data to build. |
| [docs/SLICES.md](docs/SLICES.md) | Dependency order, 15 slices and milestone stop line. |
| [docs/AGENT-BUILD-MODE.md](docs/AGENT-BUILD-MODE.md) | Orchestrator handoff for the later build. |
| [docs/reference/](docs/reference/) | Layout targets for the main screens. |

## Windows (family PC)

Copy this folder onto a drive.

1. **Setup once** — double-click `Setup.bat` (Python 3.12+, ffmpeg, `.venv`, local faces / objects / places). Needs the internet the first time. Models stay in `library-data/`. No MSI.
2. **Library daily** — double-click `Library.bat`.
3. **Update for code** — **Update Library** in the header, or `Update.bat` (`git pull`). Run `Setup.bat` again only if new local models were added.

`Setup.bat -Help` prints that story. `Setup.bat -DryRun` probes without downloading.
