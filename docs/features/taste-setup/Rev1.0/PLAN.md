# Taste-Setup — portable Setup.bat

Sits on the reveal/hover/people tip. Does not close a Check. No MSI.
No 17th setting. Does not change `Library.bat` / `launch.ps1` serve.

Read PRODUCT F2 (Setup once), UI-SPEC **Portable install**, and this file.

## In scope

1. `Setup.bat` is the one-time family-PC install: Python 3.12+, ffmpeg
   (same winget ids as `launch.ps1`), `.venv`, `pip install -e .`.
2. Then `python -m library setup-geo`, `setup-ml objects`, and
   `setup-ml faces` when those commands exist on this copy.
3. If a command is missing, print that **Update Library** must pull it
   and exit non-zero. Same `Setup.bat` works after the stack merge
   without a rewrite.
4. `-Help` / `-DryRun` probe only (no winget, pip, or model download).
5. First real run needs the internet. Models stay under `library-data/`.
6. Story: Setup once → Library daily → Update for code.

## Out of scope

Duplicating model download logic, changing serve, S13/S14, a 23rd Check,
macOS/Linux launch.

## Gate

```
python -m tests.qa slice TASTE-SETUP --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-setup/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
