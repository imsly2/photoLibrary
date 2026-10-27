# iPhone mirror backup: development handoff

Date: 2026-10-27. Branch: `setup/second-windows-pc`.
Repository: https://github.com/imsly2/photolibrary

## Resume here

The user requires an **exact mirror of the folder names and filenames Windows
Explorer shows under Apple iPhone > Internal Storage**, completing an earlier
partial Explorer copy. Do not invent another date-folder scheme or guess the
`_a`, `_b`, `_c` assignments. The next run is diagnostic/dry-run only. A full
backup is explicitly on hold pending review and separate user approval.

Second-PC clone: `C:\AI Projects\Github\photolibrary`.
Backup: `D:\Photos\Iphone 2017-2026.10`.

Preserve existing development-PC changes before switching. Fetch and open this
branch, not just main, to obtain the unmerged setup/diagnostic changes:

```powershell
git fetch origin
git switch --track origin/setup/second-windows-pc
# If the local branch already exists, use instead:
# git switch setup/second-windows-pc
# git pull --ff-only
```

Read AGENTS.md, docs/PICKUP.md and docs/PRODUCT.md. This handoff supersedes the
preliminary wrong-phone, DCIM-only whole-library, and storage-used conclusions
in older STATUS entries. No full product feature Check was closed.

## Work already committed

| Commit | Change |
|---|---|
| fb3a69f | Missing-.NET message variants, nonfatal restricted Apple inspection, setup tests/documentation and environment-file exclusions. |
| 5346118 | local-runtime.ps1 supports ignored app-local .NET/ffmpeg paths in setup and launcher. |
| edc8c96 | Interrupted/short-transfer partial-cleanup regression tests. |
| 7d1e29e | Existing CLI wrapper, expanded read-only inventory/comparison diagnostic, tests and documentation. |

`tools/iphone/Cli.ps1` runs the bundled `bin/get-and-see.exe`, using a writable
`.local/iphone-cli-bundle` extraction directory for that process. Its --help was
tested under Windows PowerShell 5.1. No global PATH change or SDK is required.

`tools/iphone/Inventory.ps1` loads the SHIPPED GetAndSee.Core.AfcIPhoneClient DLL
and uses its connect/list/stat/read methods. It is not a replacement USB stack.
Default roots: /DCIM and /PhotoData/CPLAssets. Reports include device fingerprint,
root totals, source records, errors, comparison candidates and optional SHA-256
sample checks. It requires PowerShell 7 on .NET 10+ (available in this Codex
runtime, not necessarily the ordinary Windows shell). No SDK is needed.

**The ordinary import dialog and shipped COPY command remain DCIM-only.**
Inventory.ps1 does not expand the copy pipeline, reconstruct original names,
implement mirror mode or guarantee full Photos/iCloud coverage.

## Confirmed omission: CPLAssets

`tools/iphone/ui-host/Program.cs` ListAsync calls DcimEnumerator.EnumerateAsync()
with its default /DCIM root. The shipped get-and-see copy --dry-run has the same
scope. Inspect:

- tools/iphone/get-and-see/src/GetAndSee.Core/Device/DcimEnumerator.cs
- tools/iphone/get-and-see/src/GetAndSee.Cli/Commands/CopyCommand.cs
- tools/iphone/ui/phone.py and ui/match.py
- library/iphone_import.py

Fresh live scan through the actual bundled tool core, wife's connected phone:

| Root | Files | Bytes | Decimal GB |
|---|---:|---:|---:|
| /DCIM | 5,199 | 22,435,897,542 | 22.44 |
| /PhotoData/CPLAssets | 12,269 | 98,961,183,717 | 98.96 |
| Combined requested roots | 17,468 | 121,397,081,259 | 121.40 |

No root scan errors. An independent read-only AFC probe agreed. One new 590,843-byte
JPG appeared between scans and was included by the next tool scan. These were
fresh scans. CLI's 20.9 GB display is binary GiB: the same DCIM bytes as 22.44 GB.

This counts files/resources, not unique Photos assets, and does not prove all
cloud originals are accessible. Other PhotoData folders include derivatives and
caches. A broader derivative walk was stopped; do not claim it was complete or
add its bytes as extra originals indiscriminately.

### Important corrections

- A DIFFERENT phone was initially connected: 21,096 files / 150,123,360,560 bytes.
  Its preliminary 192 skips and 145.95 GB copy proposal are INVALID for the wife's
  full backup. The user confirmed the swap.
- Seven small setup test files came from that other phone. They were checksum
  checked, copied into an isolated PhotoLibrary-test-* folder and indexed. Exclude
  that folder from the wife's comparison; do not delete it without approval.
- The wife's zero filename-size matches covered DCIM only. It did NOT prove the
  older originals were absent: many are readable in CPLAssets under UUID names.
- A lockdown disk-usage property implied only ~38 GB used. That inference was
  wrong. Direct AFC filesystem information showed ~1.2 GB free of a roughly
  238 GiB filesystem, agreeing with Explorer. Do not repeat the 38 GB claim.

## Existing Explorer backup and verified matching

Excluding .library generated data and the isolated setup test folder:

- 7,988 files / 80,167,326,538 bytes (~74.66 binary GiB, commonly labeled GB by Windows).
- 132 dated folders, 201402_a through 202605_a.
- 202512_a alone is ~7.06 decimal GB, not the entire backup.
- Expanded comparison has 7,367 local files with same-size source candidates,
  accounting for 79,550,068,310 local bytes (~99.23% of local bytes).
- Candidates are NOT checksum-verified duplicates. Keep ambiguous candidates.
- Five sampled UUID-source/local pairs matched SHA-256 despite different names.
- All 11 files in existing 202112_a then matched SHA-256 against tool-read sources,
  including a HEIC/MOV pair. Explorer's actual source folder showed those same
  11 leaf names. Mirror mode must retain 202112_a paths and skip verified files.

A verified relationship joins a raw CPL UUID filename with the local original
name `202112_a\IMG_9495.JPG`. Do not require raw and exported names to agree.
The five initial and eleven folder samples overlap; do not claim 16 distinct
verified files.

The old Python matcher recursively scans existing subfolders, so a different
parent folder name does not itself prevent matching. But it compares exact,
case-sensitive filenames plus sizes and trusts resume journal records. UUID names
will not match Explorer names. Its "exact match" label is not a checksum claim;
logged source path/size can skip without validating current local bytes.

## Concrete mirror-layout failure and preview discrepancy

User opened the REAL Windows folder:
`This PC > Apple iPhone > Internal Storage > 202610_a` (2,114 items observed).
A visible 23-file sample was recorded, not a complete Windows manifest. Some
Windows names differ even from DCIM names; adding CPL coverage alone is not enough.

Missing sample: `202610_a\IMG_3967.HEIC`, displayed as 2,716 KB.
The tool has one exact-name candidate `/DCIM/103APPLE/IMG_3967.HEIC`, 2,780,957
bytes, agreeing with the rounded display size. It was streamed into MEMORY only.
Capture metadata: 2026-10-01 00:18:14, iPhone 17 Pro. Modification timestamp:
2026-09-30 16:19:28.950 UTC. No same-size local backup file or exact target exists.

The actual DateFolderOrganizer class produced:

| Calculation | Relative destination |
|---|---|
| Required mirror of observed Windows path | 202610_a\IMG_3967.HEIC |
| Dry-run calculation: metadata absent, modification timestamp | 2026-09\IMG_3967.HEIC |
| Copy-path calculation with actual capture metadata | 2026-10\IMG_3967.HEIC |

Both current paths fail Explorer mirroring. Preview and eventual copy can disagree
on the month. Inspect GetAndSee.Core/Organize/DateFolderOrganizer.cs and
ExifMetadataExtractor.cs. The Library dialog's Python matcher is a separate path
and uses modification time for new YYYY-MM folders; do not leave these inconsistent.

The Windows virtual resource itself was not independently streamed/hashed. Binding
evidence is unique filename, agreeing size/type and capture month, and the actual
observed folder. This is a diagnostic proposal, NOT a copy-ready global manifest.
No global `_a`/`_b` partition rule was inferred or verified.

## Next engineering step: exact Windows export manifest

Try WPD (Windows Portable Devices) from a normal development process, requesting
GENERIC_READ ONLY. Enumerate DEVICE -> Internal Storage -> dated folders -> files.
Collect device identity/time, object ID, persistent ID if available, parent ID,
exact relative path/original filename, byte size, content type and timestamps.
Record errors/partial coverage. Object IDs may be session-specific.

Use Windows' actual folder assignments. Then establish the relationship to raw
AFC resources, or read the Windows resource when a reliable join is unavailable.
Validate edited/original variants, Live Photos/sidecars and potential export
transcoding. Size/timestamp similarity alone cannot authorize skipping.

### Blocker encountered here

Shell.Application saw the phone but returned zero children while Explorer visibly
showed the folders (145 root items observed). A read-only WPD COM probe failed with
0x80073D54, "The process has no package identity." The handoff probe now isolates the failure to **open-read-only**: manager
activation/device enumeration succeeded, but the GENERIC_READ device Open call
failed. This could be specific to the Codex process context. Reproduce normally
on the dev PC before changing security/access settings; it does not prove WPD
cannot enumerate the hierarchy.

A sanitized exploratory probe and wrapper are included in tools/iphone/diagnostics.
The wrapper records the failing activation/connection stage. It only requests
read access and enumerates metadata. It is NOT a production exporter, complete
manifest or copy command. Validate COM interop and activation outside this context.
Keep runtime reports private and outside Git.

Microsoft references used for the interface definitions and read-only flow:

- https://learn.microsoft.com/en-us/windows/win32/wpd_sdk/enumerating-content
- https://learn.microsoft.com/en-us/windows/win32/wpd_sdk/establishing-a-connection
- https://github.com/microsoft/win32metadata/tree/main/generation/WinSDK/RecompiledIdlHeaders/um

## Acceptance and safe order of work

1. Obtain a complete, device-bound Windows manifest, with exact suffixes and no
   silent enumeration errors. No guessed folder paths.
2. Resolve raw-resource/export relationships and existing content matches. Block
   unresolved mappings and collisions instead of assigning a fallback path.
3. Make a dry-run manifest: source -> existing match -> destination -> action ->
   verification/error. Preview and copy must consume the SAME resolved plan.
4. Test a completed old month, a missing new month, split `_a`/`_b` folders,
   HEIC/MOV Live Photo, edited resources/AAE, reused IMG numbers, same-name/different
   content, capture-vs-modified month boundary, and interrupted reads.
5. Skip verified content; never overwrite conflicting existing files. Bind resume
   to device/resource identity and validate local bytes, not name/size alone.
6. After plan review and separate approval, do a SMALL test import. Full backup
   remains on hold. Report verified/candidate/unresolved and inaccessible/iCloud-only
   originals separately. Never infer completeness from counts alone.

## Diagnostic commands and validation

From repo root, choose NEW report names OUTSIDE the photo backup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/iphone/Cli.ps1 --help
powershell -NoProfile -ExecutionPolicy Bypass -File tools/iphone/Cli.ps1 copy --dest "D:\Photos\Iphone 2017-2026.10" --dry-run --no-dashboard

# PowerShell 7 on .NET 10+:
pwsh -NoProfile -File tools/iphone/Inventory.ps1 `
  -CompareFolder "D:\Photos\Iphone 2017-2026.10" `
  -ExcludeLocalFolder '.library','PhotoLibrary-test-*' `
  -VerifySamples 5 -Report "C:\Reports\iphone-inventory-new.json"
```

Sample verification selects unique-size pairs between 50 KB and 5 MB; it does NOT
verify the full collection. -ReadInventory is offline analysis, not a new live scan.
See tools/iphone/README.md. For the exploratory Windows metadata probe:

```powershell
pwsh -NoProfile -File tools/iphone/diagnostics/Probe-WindowsLayout.ps1 -Report "C:\Reports\wpd-probe-new.json"
```

Checks completed:

- 18 pytest checks: importer, folder index, item store.
- 11 bundled match unittests, including interrupted/short transfer cleanup.
- tests/qa/iphone_inventory.ps1: totals/nesting/exclusions, UUID and ambiguous
  candidates, no false verification, report boundaries, overwrite refusal and
  incomplete-scan failure. All passed.
- CLI help, DCIM dry run, wrapper help and live expanded diagnostic scan: passed.
- Content-verification samples above passed. No broad feature Checks rerun.
- Mirror calculation test demonstrates current failures, not a passed mirror-copy test.

## Setup/collaboration state and remaining work

Python 3.14.5 editable install and local HTTP server ran successfully. Source HEAD
and the running process can differ; restart deliberately after updates/switches.
Do not identify loaded code solely from Git HEAD or a cached UI revision label.
.NET 10 runtime is app-local under ignored .local/dotnet; its ZIP SHA-512 was
checked against Microsoft release metadata. ffmpeg installation/download and
preview verification are INCOMPLETE. Optional model packs are unverified.

GitHub Desktop collaborator push access worked. Terminal credential-manager use
failed in this restricted shell with an MSYS named-object access error. Use Desktop
when necessary; do not extract/embed tokens. Verify the remote branch SHA after
pushing. Main has not been changed by this work.

Update Library deliberately switches to main and fast-forwards it. Do not press
Update while developing on this feature branch. After review/merge, prefer a daily
main checkout and separate development checkout for changes.

## Private evidence, intentionally not committed

Detailed inventories/hashes/reports remain in this second-PC setup chat's local
outputs directory under Documents/Codex. Relevant filenames:

- iPhone-tool-live-inventory.json
- iPhone-backup-investigation.md
- iPhone-mirror-existing-folder-test.json
- iPhone-mirror-missing-file-test.json
- iPhone-mirror-layout-test.md

Old wrong-phone/DCIM-only copy proposals are superseded. Do not publish photos,
raw device identifiers/fingerprints, GPS/face data, catalogs, previews, secrets or
private per-file inventories. This sanitized handoff contains the continuation facts.
