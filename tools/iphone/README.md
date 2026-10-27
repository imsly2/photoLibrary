# iPhone photos

Adopted tool for pulling the iPhone camera roll onto a PC over USB, with a log of what landed and a way to resume.

The program is [get-and-see](https://github.com/denis-a-evdokimov/get-and-see) v1.1.0. We did not write it. This folder is where it lives in slyOS, and where the run notes live. The pictures themselves stay on a drive you choose later.

| Read | For |
|------|-----|
| [docs/PRODUCT.md](docs/PRODUCT.md) | What it does and how a run works |
| [docs/STATUS.md](docs/STATUS.md) | What is true on this machine right now |
| [TRAPS.md](TRAPS.md) | The old-copies problem, iCloud, and the USB driver |

On a new PC, run `Setup.bat` in this folder once. Then open the window with `Launch-Window.ps1`.

The command-line preview is a single file and does not need .NET. The window's phone helper does. `Setup.bat` installs that runtime.

```powershell
bin\get-and-see.exe copy --dest "D:\YourFolder" --dry-run
```

`--dry-run` lists what it would copy and writes nothing. Leave `--dest` unset until Steve picks the folder.


## Command-line diagnostics on Windows

Run the existing bundled CLI through this wrapper (Windows PowerShell 5.1 works):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/iphone/Cli.ps1 --help
powershell -NoProfile -ExecutionPolicy Bypass -File tools/iphone/Cli.ps1 copy --dest "D:\Photos\Iphone 2017-2026.10" --dry-run --no-dashboard
```

The wrapper uses ignored `.local/iphone-cli-bundle/` for self-contained binary
extraction. It does not install software, change global environment variables,
or choose a copy destination. The dry run does not copy media or write a journal.

**Coverage limitation found on a second PC:** the current `get-and-see copy`
command and Library's ordinary phone helper enumerate `/DCIM` only. A connected
phone also has locally readable media under `/PhotoData/CPLAssets`. Do not use
the DCIM count as a complete Photos-library inventory or as a full-backup claim.
The existing CLI's dry run also does not establish content matches for earlier
Explorer copies; its journal is different from the Library dialog's matcher.

### Expanded read-only inventory and existing-backup comparison

`Inventory.ps1` is a diagnostic entry point inside this tool. It loads the same
bundled **GetAndSee.Core.AfcIPhoneClient** used by the shipped importer, rather
than a second USB implementation. It requires PowerShell 7 running on .NET 10+
(no SDK). Its default roots are `/DCIM` and `/PhotoData/CPLAssets`.

```powershell
pwsh -NoProfile -File tools/iphone/Inventory.ps1 `
  -CompareFolder "D:\Photos\Iphone 2017-2026.10" `
  -Report "C:\Reports\iphone-inventory-unique-name.json" `
  -VerifySamples 5
```

This only lists/stats phone files and optionally streams sample bytes for SHA-256.
It never copies media, modifies the phone/backup, or writes the transfer journal.
Reports must be outside the backup folder, with a new filename. `-Root` can limit
the scan explicitly; report completeness applies only to the requested roots.
Additional photo-resource folders and iCloud-only originals are not guaranteed
covered. Two roots may contain different resources for one asset.

The JSON includes device name/model/fingerprint, per-root counts/bytes, inventory,
errors, filename-size candidates, size-only candidates, and sample SHA-256 results.
CPL files commonly have UUID names while Explorer exports retain original names.
A size-only candidate is **not** a verified duplicate or permission to skip a file.
The tool keeps ambiguous candidates. Only matching hashes are labeled verified.
`-VerifySamples` checks up to the requested count of unique-size pairs between
50 KB and 5 MB; it does not verify the full collection.

Recompute comparisons from a saved report without connecting a phone:

```powershell
pwsh -NoProfile -File tools/iphone/Inventory.ps1 `
  -ReadInventory "C:\Reports\iphone-inventory-unique-name.json" `
  -CompareFolder "D:\Photos\Iphone 2017-2026.10" `
  -Report "C:\Reports\iphone-comparison-new-name.json"
```

Use a fresh live report after changing phones. Offline results retain the saved
device identity. `-ExcludeLocalFolder` accepts folder-name patterns (default
`.library`); include `PhotoLibrary-test-*` when excluding setup test copies.
The diagnostic supplements the current importer; it does not yet change the
copy workflow to include CPLAssets or reconstruct original filenames from UUIDs.
