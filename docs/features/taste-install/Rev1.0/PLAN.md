# Taste-Install -- family Setup / shortcut / Update main / restart

Sits on main after PR #28 (`92d6170`). Does not close a Check. No MSI.
Does not start S13/S14.

## In scope

1. Desktop + Start Menu `Library.lnk` from Setup and `CreateShortcut.bat`,
   icon `library.ico`, target `Launch.bat` / `Library.bat`.
2. Update always tracks `main` over anonymous HTTPS git (no `gh`, no
   GitHub login, `credential.helper=` off). If git is missing, zip
   overlay of `archive/refs/heads/main.zip` preserving `library-data/`.
   Repo must be public. Show SHA. Clear text if diverged.
3. After a successful Update that wrote new code, stop only this app's
   `python -m library serve` on the settings port and relaunch. If Library
   was not running, finish Update without launching.
4. Setup progress + failure next-steps. Internet called out. Idempotent.
   ASCII `.bat` / `.ps1`, no em-dashes.
5. README + empty-library hint. In-app Update strings through i18n.

## Gate

```
python -m tests.qa slice TASTE-SETUP --root "$qaRoot/library-data" --artifacts $setupEvidence
python -m tests.qa slice TASTE-INSTALL --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-install/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
