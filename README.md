# Library

A folder you put on a drive. It serves a photo and video library in the browser,
and a command line so an agent can scan, search, and write what is in the pictures.

The phone copier is a different tool: [iphonePhotos](../iphonePhotos/README.md).
Point this server at the folder that copier already filled.

| Read | For |
|------|-----|
| [docs/PICKUP.md](docs/PICKUP.md) | Where the build stands, how to run the tests, and the next slice. |
| [docs/PRODUCT.md](docs/PRODUCT.md) | The help file. Every feature and the check that proves it. |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | What existing photo apps already do, and the defaults taken from that. |
| [docs/STATUS.md](docs/STATUS.md) | What is actually true on disk; Check evidence. |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | Records, paths, identity, operations, errors and recovery. |
| [docs/UI-SPEC.md](docs/UI-SPEC.md) | Screen states, inputs and reference boundaries. |
| [docs/FIXTURES.md](docs/FIXTURES.md) | Exact synthetic test data to build. |
| [docs/SLICES.md](docs/SLICES.md) | Dependency order, 15 slices and milestone stop line. |
| [docs/AGENT-BUILD-MODE.md](docs/AGENT-BUILD-MODE.md) | Orchestrator handoff for the later build. |
| [docs/reference/](docs/reference/) | Layout targets for the main screens. |

S00, S01, and F6 already run against fixture folders. The remaining work follows [docs/SLICES.md](docs/SLICES.md) until all 22 PRODUCT Checks have independent evidence. Current standing and commands: [docs/PICKUP.md](docs/PICKUP.md).
