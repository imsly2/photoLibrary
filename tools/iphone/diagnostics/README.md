# Exploratory Windows layout probe

See [the handoff](../../../docs/hand-offs/IPHONE-MIRROR-BACKUP-2026-10-27.md).
This prototype requests GENERIC_READ and lists root/immediate-child metadata.
It is not a complete exporter or copy command. Use PowerShell 7 on a normal
Windows desktop with one unlocked Apple device connected. Validate COM interop
before extending it. The Codex execution context failed with 0x80073D54; the
wrapper records the failing stage. Runtime reports are private: keep outside Git.

```powershell
pwsh -NoProfile -File tools/iphone/diagnostics/Probe-WindowsLayout.ps1 -Report "C:\Reports\wpd-probe-new.json"
```

No phone or backup media is written. Existing reports are not overwritten.
