# Taste-Objects — optional local YOLO Things

Sits on the grid/date chrome tip. Does not close a Check. No 17th setting.
No faces. No cloud inference.

Read PRODUCT F3 / F14 (`setup-ml objects`, `analyze`), CONTRACTS optional
local objects, and this file.

## In scope

1. `python -m library setup-ml objects` (or `Setup.bat` / `launch.ps1 -SetupMl`)
   downloads YOLOv8n ONNX into `library-data/models/`.
2. `analyze` / `POST /api/analyze` runs CPU detection and writes Things
   through the existing annotate APIs.
3. Background analyze during `serve` when the model file is present.
4. Human tags stay (no delete, no rename-by-id).
5. COCO `person` is ignored; no people / faces written.
6. Info and search show the new Things on existing surfaces.
7. Fixture/proof: at least one tagged still under
   `tests/fixtures/objects/still.jpg`.

## Out of scope

Face detection, geographic names, cloud APIs, a 17th setting, S13/S14,
a 23rd Check.

## Gate

```
python -m tests.qa slice TASTE-OBJECTS --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-objects/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
