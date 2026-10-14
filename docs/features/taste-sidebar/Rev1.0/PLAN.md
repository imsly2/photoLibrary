# Taste-Sidebar — People and Tags never overlap

Locked for Steve's mother-in-law browse. Does not close a new Check.
Keep Setup.bat / Library.bat / ASCII `.ps1`.

## In scope

1. People and Tags are each collapsible. Session memory only. People
   starts expanded; Tags starts collapsed.
2. Tags never paints over a person row. Horizontal `#side-vsplit`
   when both are open; each open section clips and scrolls in its
   own flex pane.
3. New chrome has English and 中文 strings.

## Gate

```
python -m tests.qa slice TASTE-SIDEBAR --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-sidebar/Rev1.0/assets/<run-id>/`.
