# Library

A folder you put on a drive. It serves a photo and video library in the browser,
and a command line so an agent can scan, search, and write what is in the pictures.

The phone copier is a different tool: [iphonePhotos](../iphonePhotos/README.md).
Point this server at the folder that copier already filled.

| Read | For |
|------|-----|
| [docs/ONE_SHOT_PROMPT.md](docs/ONE_SHOT_PROMPT.md) | The one prompt that regenerates this product. Start here if you are rebuilding. |
| [docs/UI-SPEC.md](docs/UI-SPEC.md#windows-presentable-shell) | Windows Presentable Shell — family-PC North Star and shipped-vs-gap table. |
| [docs/PRODUCT.md](docs/PRODUCT.md) | The help file. Every feature and the check that proves it. |
| [docs/PICKUP.md](docs/PICKUP.md) | Current build doorway. |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | What existing photo apps already do, and the defaults taken from that. |
| [docs/STATUS.md](docs/STATUS.md) | What is actually true on disk; Check evidence. |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | Records, paths, identity, operations, errors and recovery. |
| [docs/FIXTURES.md](docs/FIXTURES.md) | Exact synthetic test data to build. |
| [docs/SLICES.md](docs/SLICES.md) | Dependency order, 15 slices and milestone stop line. |
| [docs/AGENT-BUILD-MODE.md](docs/AGENT-BUILD-MODE.md) | Orchestrator handoff for the later build. |
| [docs/reference/](docs/reference/) | Layout targets for the main screens. |

The first build follows [docs/SLICES.md](docs/SLICES.md) to make the 22 PRODUCT Checks true with independent evidence. Taste chrome is graded by the UI-SPEC **Presentable for family PC** checklist, not a 23rd Check.
