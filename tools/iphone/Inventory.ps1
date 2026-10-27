#requires -Version 7.0
<#
.SYNOPSIS
Read-only inventory and comparison using the bundled GetAndSee.Core iPhone client.
.DESCRIPTION
Requires PowerShell 7 running on .NET 10+. No SDK or extra phone driver stack.
Only connects, lists, stats, and optionally reads source bytes for SHA-256.
Does not copy media, update the transfer journal, or modify backup files.
#>
[CmdletBinding()]
param(
    [string[]]$Root = @('/DCIM', '/PhotoData/CPLAssets'),
    [string]$CompareFolder,
    [Parameter(Mandatory=$true)][string]$Report,
    [string]$ReadInventory,
    [ValidateRange(0,100)][int]$VerifySamples = 0,
    [string[]]$ExcludeLocalFolder = @('.library')
)
$ErrorActionPreference = 'Stop'
$reportPath = [IO.Path]::GetFullPath($Report)
if (Test-Path -LiteralPath $reportPath) { throw 'Report already exists. Choose a new report filename.' }
if ($CompareFolder) {
    $CompareFolder = (Get-Item -LiteralPath $CompareFolder -ErrorAction Stop).FullName
    if (-not (Test-Path -LiteralPath $CompareFolder -PathType Container)) { throw 'CompareFolder must be a directory.' }
    if ($reportPath.StartsWith($CompareFolder.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Save the report outside the backup folder to keep the comparison read-only.'
    }
}
if ($ReadInventory -and $VerifySamples) { throw 'Sample verification needs a live device, not a saved inventory.' }
$phone = $null
$files = [Collections.Generic.List[object]]::new()
$roots = [Collections.Generic.List[object]]::new()
$errors = [Collections.Generic.List[object]]::new()
$started = [DateTimeOffset]::UtcNow.ToString('o')
$device = $null
try {
    if ($ReadInventory) {
        $saved = Get-Content -LiteralPath $ReadInventory -Raw | ConvertFrom-Json
        $device = $saved.device
        foreach ($f in $saved.files) { $files.Add($f) }
        foreach ($r in $saved.roots) { $roots.Add($r) }
        foreach ($e in $saved.errors) { $errors.Add($e) }
    } else {
        if ([Environment]::Version.Major -lt 10) { throw 'Use PowerShell 7 on .NET 10+ for Inventory.ps1. The ordinary host list command still works with the .NET 10 runtime.' }
        $helper = Join-Path $PSScriptRoot 'ui-host/bin/Release/net10.0/win-x64'
        foreach ($dll in @('iMobileDevice-net.dll','GetAndSee.Core.dll')) {
            $path = Join-Path $helper $dll
            if (-not (Test-Path -LiteralPath $path)) { throw "Missing bundled helper library: $path. Run tools/iphone/Setup.bat." }
            Add-Type -Path $path
        }
        $phone = [GetAndSee.Core.Device.AfcIPhoneClient]::new([TimeSpan]::FromSeconds(30), $null)
        $null = $phone.ConnectAsync([Threading.CancellationToken]::None).GetAwaiter().GetResult()
        $idBytes = [Text.Encoding]::UTF8.GetBytes($phone.Device.Udid)
        $device = [ordered]@{
            name = $phone.Device.Name
            productType = $phone.Device.ProductType
            fingerprint = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($idBytes)).ToLowerInvariant()
        }
        Write-Host ("Connected: {0} ({1})" -f $device.name, $device.productType)
        foreach ($start in $Root) {
            if (-not $start.StartsWith('/')) { throw 'Phone roots must be absolute AFC paths, such as /DCIM.' }
            $todo = [Collections.Generic.Stack[string]]::new()
            $todo.Push($start.TrimEnd('/'))
            $count = 0; [long]$bytes = 0; $folderCount = 0
            while ($todo.Count) {
                $folder = $todo.Pop(); $folderCount++
                try {
                    $names = $phone.ListDirectoryAsync($folder, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
                    foreach ($name in $names) {
                        $source = $folder + '/' + $name
                        $stat = $phone.GetFileInfoAsync($source, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
                        if ($stat.IsDirectory) { $todo.Push($source); continue }
                        $mtime = if ($null -ne $stat.ModifiedAt) { $stat.ModifiedAt.ToString('o') } else { $null }
                        $files.Add([pscustomobject]@{path=$source; size=[long]$stat.Size; mtime=$mtime; root=$start})
                        $count++; $bytes += $stat.Size
                    }
                } catch {
                    $errors.Add([pscustomobject]@{path=$folder; message=$_.Exception.Message})
                    if ($errors.Count -ge 20) { throw 'Too many scan errors; inventory is incomplete.' }
                }
                if ($folderCount % 100 -eq 0) { Write-Host ("{0}: {1} folders, {2} files, {3:N0} bytes" -f $start,$folderCount,$count,$bytes) }
            }
            $roots.Add([pscustomobject]@{path=$start; files=$count; bytes=$bytes; folders=$folderCount})
            Write-Host ("{0}: {1} files, {2:N0} bytes" -f $start,$count,$bytes)
        }
    }
    $comparison = $null
    $checks = [Collections.Generic.List[object]]::new()
    if ($CompareFolder) {
        $bySize = [Collections.Generic.Dictionary[long,object]]::new()
        $byNameSize = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($f in $files) {
            [long]$n = $f.size
            if (-not $bySize.ContainsKey($n)) { $bySize[$n] = [Collections.Generic.List[object]]::new() }
            $bySize[$n].Add($f)
            $null = $byNameSize.Add([IO.Path]::GetFileName($f.path) + '|' + $n)
        }
        $locals = [Collections.Generic.List[object]]::new()
        $todo = [Collections.Generic.Stack[string]]::new(); $todo.Push($CompareFolder)
        while ($todo.Count) {
            $folder = $todo.Pop()
            foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($folder)) {
                $attrs = [IO.File]::GetAttributes($entry)
                if (($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
                if (($attrs -band [IO.FileAttributes]::Directory) -ne 0) {
                    $skip = $false
                    foreach ($pattern in $ExcludeLocalFolder) { if ([IO.Path]::GetFileName($entry) -like $pattern) { $skip = $true } }
                    if (-not $skip) { $todo.Push($entry) }
                } else {
                    $f = [IO.FileInfo]::new($entry)
                    $locals.Add([pscustomobject]@{path=$f.FullName;size=$f.Length;name=$f.Name})
                }
            }
        }
        $candidates = [Collections.Generic.List[object]]::new()
        [long]$localBytes=0; [long]$candidateBytes=0; $sameNameSize=0
        foreach ($f in $locals) {
            $localBytes += $f.size
            if ($byNameSize.Contains($f.name+'|'+$f.size)) { $sameNameSize++ }
            if ($bySize.ContainsKey([long]$f.size)) {
                $candidateBytes += $f.size
                $candidates.Add([pscustomobject]@{local=$f.path;size=$f.size;sourceCandidates=@($bySize[[long]$f.size].ToArray() | ForEach-Object {$_.path})})
            }
        }
        $comparison = [ordered]@{folder=$CompareFolder; localFiles=$locals.Count; localBytes=$localBytes; nameAndSizeCandidates=$sameNameSize; sizeOnlyCandidates=$candidates.Count; sizeOnlyCandidateBytes=$candidateBytes; note='Candidate counts are not verified duplicates. UUID source names may differ from Explorer names. No automatic skip decisions.'; candidates=$candidates.ToArray()}
        if ($VerifySamples) {
            $selected = @($candidates | Where-Object {$_.sourceCandidates.Count -eq 1 -and $_.size -ge 50000 -and $_.size -le 5000000} | Sort-Object size | Select-Object -First $VerifySamples)
            foreach ($pair in $selected) {
                $remote = $null; $local = $null
                try {
                    $remote = $phone.OpenReadAsync($pair.sourceCandidates[0], [Threading.CancellationToken]::None).GetAwaiter().GetResult()
                    $remoteHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($remote)).ToLowerInvariant()
                    $remote.Dispose(); $remote = $null
                    $local = [IO.File]::OpenRead($pair.local)
                    $localHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($local)).ToLowerInvariant()
                    $checks.Add([pscustomobject]@{source=$pair.sourceCandidates[0];local=$pair.local;size=$pair.size;sourceSHA256=$remoteHash;localSHA256=$localHash;verified=($remoteHash -eq $localHash)})
                    Write-Host ("SHA-256 sample: {0}" -f ($remoteHash -eq $localHash))
                } finally { if ($remote) {$remote.Dispose()}; if ($local) {$local.Dispose()} }
            }
        }
    }
    [long]$total=0; foreach ($f in $files) {$total += $f.size}
    $result = [ordered]@{schemaVersion=1;method='Bundled GetAndSee.Core AfcIPhoneClient; list/stat/read only';startedUtc=$started;finishedUtc=[DateTimeOffset]::UtcNow.ToString('o');device=$device;readFromInventory=$ReadInventory;roots=$roots.ToArray();files=$files.ToArray();fileCount=$files.Count;bytes=$total;errors=$errors.ToArray();completeForRequestedRoots=($errors.Count -eq 0);coverageNote='Not an entire Photos/iCloud library guarantee. Roots may contain alternative resources for the same photo.';comparison=$comparison;sampleChecks=$checks.ToArray()}
    $parent = [IO.Path]::GetDirectoryName($reportPath)
    $null = [IO.Directory]::CreateDirectory($parent)
    [IO.File]::WriteAllText($reportPath, ($result | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    Write-Host ("Inventory: {0} files, {1:N0} bytes. Report: {2}" -f $files.Count,$total,$reportPath)
    if ($errors.Count) { throw "Inventory contains $($errors.Count) errors; see report." }
} finally { if ($phone) { $phone.Dispose() } }
