# Library — agent door

Start at [docs/PICKUP.md](docs/PICKUP.md). That file is the current build doorway.

North star: [docs/PRODUCT.md](docs/PRODUCT.md). That file is the product.
Status: [docs/STATUS.md](docs/STATUS.md). Conventions: [docs/CONVENTIONS.md](docs/CONVENTIONS.md).
Presentable shell: [docs/UI-SPEC.md](docs/UI-SPEC.md#windows-presentable-shell).

Build only what a feature section in PRODUCT.md describes. A feature is done when its **Check** has been run and the artifact path is written in STATUS. Do not treat an unimplemented Check as a pass.


## Agent inbox (J:\slyOS\inbox)
J:\slyOS\inbox holds short reports from finished agent jobs (what was done, what was found, follow-ups). When Steve asks about past work or wants to find something, read those reports first (newest first) to help him locate it.

A bug, a feature, a commit, or a pull request goes through `J:\slyOS\scripts\Submit-WorkLog.ps1`. Read `J:\slyOS\projects\slyAI\shared\WORK-LOG-DOOR.md` first. That one call writes the inbox report, the chart row, and the spoken note. It works from any project. The door is the current way, and it is allowed to change.

