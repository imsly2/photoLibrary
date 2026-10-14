# Taste-I18N — English / 中文

Locked for Steve's mother-in-law. Does not close a new Check.
Zero new Python dependencies. Setup.bat / Library.bat / `.ps1` stay ASCII.

## In scope

1. Header language switch English / 中文. Persist `settings.language`
   (`en` | `zh-Hans`). Existing settings.json files fill `en`.
2. Chrome Steve's MIL sees: header, Search, filter bar, Group, Sort,
   People, Processing, empty states, viewer, tags, Setup/Library in-app
   strings, date headings where practical.
3. Search Chinese query text against names, tags, places, and built-in
   labels.

## Gate

```
python -m tests.qa slice TASTE-I18N --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-i18n/Rev1.0/assets/<run-id>/`.
