# Taste-Version — visible checkout SHA

Sits on the video + zoom taste tip. Does not close a Check. No SemVer.
No 17th setting.

Read UI-SPEC **Update** / **Update UX finish**, CONTRACTS `GET /api/version`
and `POST /api/update` `git_sha`, and this file.

## In scope

1. `GET /api/version` reports the live app-folder short SHA (`git_sha`).
2. Header `#library-version` next to Update Library shows that SHA.
3. `POST /api/update` success includes the new `git_sha`; the label
   refreshes from the response. The serve process does not restart.
4. Non-git copy: `label` is `local`, `git_sha` is null. Health stays
   `{"ok":true}`.

## Out of scope

S13/S14, SemVer marketing versions, auto-restart after pull, macOS/Linux
F2.

## Gate

```
python -m tests.qa slice TASTE-VERSION --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-version/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
