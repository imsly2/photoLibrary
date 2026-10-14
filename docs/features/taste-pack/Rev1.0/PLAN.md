# Taste-Pack — lean deploy zip

Sits on main after the Setup AppFolder fix. Does not close a Check.
No MSI. Does not start S13/S14.

## In scope

1. `PackDeploy.bat` (thin `pack-deploy.ps1` + `pack-deploy.py`) writes
   `dist/photoLibrary-deploy.zip` from the repo root. Double-click or
   run from that folder. ASCII `.bat` / `.ps1` (PowerShell 5.1 /
   Chinese-locale).
2. Include Setup / Library / Update launchers, `library/`,
   `pyproject.toml`, `README.md`, `library.ico`, and other rooted
   runtime files (`*.bat` / `*.ps1` / `*.sh` / `*.ico`).
3. Exclude `.venv`, `library-data`, `.git`, `docs`, `tests`, `.qa`,
   `__pycache__`, `*.pyc`, egg-info, CaptureRegion screenshots, agent
   junk, and other fat/dev trees. Zip stays on the order of MBs.
4. Re-run overwrites the same `dist/photoLibrary-deploy.zip`.
5. Print skipped folders, output path, approximate size, and
   “copy zip → extract → Setup.bat”.
6. One short README Quick start paragraph. Family-facing.

## Out of scope

A 23rd Check, changing Setup/Library serve, shipping models or
`library-data`, macOS/Linux launch.

## Gate

```
python -m tests.qa.pack_deploy --artifacts docs/features/taste-pack/Rev1.0/assets/verify-1
```

Prove: planted excludes are absent; zip contains `Setup.bat` and
`library/`. 16/22 unchanged.
