# Read Apple iPhone the way File Explorer does: Internal Storage, then the
# year-month folders Explorer shows. List writes nothing to the phone or the
# backup. Pull copies one file into a new local path and refuses to replace it.
param(
    [Parameter(Mandatory = $true)][ValidateSet("list", "pull")][string]$Action,
    [string]$Relative = "",
    [string]$Dest = ""
)
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$script:writeLock = New-Object System.Object
$script:pulse = [hashtable]::Synchronized(@{ On = $false; Stop = $false; Label = ""; Start = [DateTime]::UtcNow })
$script:pulsePs = $null
$script:pulseRs = $null
$script:lastListMs = 0

function Write-JsonLine($Object) {
    $line = $Object | ConvertTo-Json -Compress -Depth 4
    [System.Threading.Monitor]::Enter($script:writeLock)
    try {
        [Console]::Out.WriteLine($line)
        [Console]::Out.Flush()
    } finally {
        [System.Threading.Monitor]::Exit($script:writeLock)
    }
}

function Start-PulseThread {
    if ($script:pulsePs) { return }
    $rs = [runspacefactory]::CreateRunspace()
    $rs.Open()
    $rs.SessionStateProxy.SetVariable("pulse", $script:pulse)
    $rs.SessionStateProxy.SetVariable("writeLock", $script:writeLock)
    $ps = [powershell]::Create()
    $ps.Runspace = $rs
    [void]$ps.AddScript({
        while ($true) {
            if ($pulse.Stop) { break }
            Start-Sleep -Milliseconds 1000
            if ($pulse.Stop -or -not $pulse.On) { continue }
            $ms = [int](([DateTime]::UtcNow - $pulse.Start).TotalMilliseconds)
            if ($ms -lt 400) { continue }
            if (-not $pulse.On) { continue }
            $line = ([ordered]@{ reading = [string]$pulse.Label; waitingMs = $ms } | ConvertTo-Json -Compress)
            [System.Threading.Monitor]::Enter($writeLock)
            try {
                [Console]::Out.WriteLine($line)
                [Console]::Out.Flush()
            } finally {
                [System.Threading.Monitor]::Exit($writeLock)
            }
        }
    })
    $script:pulseRs = $rs
    $script:pulsePs = $ps
    $script:pulseHandle = $ps.BeginInvoke()
}

function Stop-PulseThread {
    if ($script:pulse) {
        $script:pulse.On = $false
        $script:pulse.Stop = $true
    }
    if ($script:pulseHandle) {
        try { $null = $script:pulseHandle.AsyncWaitHandle.WaitOne(1500) } catch {}
    }
    if ($script:pulsePs) {
        try { $script:pulsePs.Stop() } catch {}
        try { $script:pulsePs.Dispose() } catch {}
        $script:pulsePs = $null
    }
    if ($script:pulseRs) {
        try { $script:pulseRs.Close() } catch {}
        try { $script:pulseRs.Dispose() } catch {}
        $script:pulseRs = $null
    }
}

function Start-FolderPulse($Label) {
    Start-PulseThread
    $script:pulse.Label = [string]$Label
    $script:pulse.Start = [DateTime]::UtcNow
    $script:pulse.On = $true
}

function Stop-FolderPulse {
    if ($script:pulse) { $script:pulse.On = $false }
}

function Get-PhoneStorage {
    $shell = New-Object -ComObject Shell.Application
    $phone = $null
    foreach ($item in @($shell.NameSpace(17).Items())) {
        if ($item.Name -eq "Apple iPhone") {
            $phone = $item
            break
        }
    }
    if (-not $phone) {
        throw "Apple iPhone is not in This PC. Unlock the phone, tap Trust, and open Apple Devices once."
    }
    $storage = $null
    foreach ($item in @($phone.GetFolder.Items())) {
        if ($item.Name -eq "Internal Storage") {
            $storage = $item
            break
        }
    }
    if (-not $storage) {
        throw "Internal Storage is not on the phone."
    }
    $pair = New-Object psobject -Property @{ Shell = $shell; Storage = $storage }
    return ,$pair
}

function Get-ChildItemByName($FolderItem, $Name) {
    foreach ($child in @($FolderItem.GetFolder.Items())) {
        if ($child.Name -eq $Name) {
            return $child
        }
    }
    return $null
}

function Add-FileLine($Item, $RelativePath) {
    $sizeValue = $Item.ExtendedProperty("System.Size")
    if ($null -eq $sizeValue) {
        throw "Explorer did not report a size for $RelativePath"
    }
    Write-JsonLine ([ordered]@{
        rel = $RelativePath
        size = [int64]$sizeValue
    })
}

function Get-FolderItems($FolderItem, $Label, $EmptyWaitMs) {
    # Count on a phone folder climbs, pauses, then climbs again. Properties
    # in Explorer does the same thing. A pause is not the end of the folder.
    # Wait until the count has stayed still for two seconds. A second thread
    # emits waitingMs during a blocking Count so the dialog clock keeps moving.
    Start-FolderPulse $Label
    $listed = [Diagnostics.Stopwatch]::StartNew()
    $items = $FolderItem.GetFolder.Items()
    $last = -1
    $sinceChange = [Diagnostics.Stopwatch]::StartNew()
    $count = 0
    while ($true) {
        $count = [int]$items.Count
        if ($count -ne $last) {
            $last = $count
            $sinceChange.Restart()
            Write-JsonLine ([ordered]@{ reading = $Label; found = $count })
        }
        $stillMs = [int]$sinceChange.ElapsedMilliseconds
        $filled = $count -gt 0 -and $stillMs -ge 2000
        $empty = $count -eq 0 -and $stillMs -ge $EmptyWaitMs
        if ($filled -or $empty) { break }
        Start-Sleep -Milliseconds 200
    }
    Stop-FolderPulse
    $script:lastListMs = [int]$listed.ElapsedMilliseconds
    Write-JsonLine ([ordered]@{ reading = $Label; found = $count; listMs = $script:lastListMs })
    return ,$items
}

function Walk-Folder($FolderItem, $Prefix, $EmptyWaitMs) {
    $label = if ($Prefix) { $Prefix } else { "Internal Storage" }
    $items = Get-FolderItems $FolderItem $label $EmptyWaitMs
    $listMs = $script:lastListMs
    if (-not $Prefix) { $script:rootCount = $items.Count }
    $seenHere = @{}
    $filesHere = 0
    $sizeMs = 0
    $sizeSw = [Diagnostics.Stopwatch]::StartNew()
    foreach ($child in $items) {
        $name = [string]$child.Name
        if ([string]::IsNullOrWhiteSpace($name) -or $name -eq "." -or $name -eq ".." -or $name.Contains("/") -or $name.Contains("\")) {
            $script:skipped++
            $where = if ($Prefix) { $Prefix } else { "Internal Storage" }
            [Console]::Error.WriteLine("Skipped an item with no usable name in $where")
            continue
        }
        $nameKey = $name.ToLowerInvariant()
        if ($seenHere.ContainsKey($nameKey)) {
            [Console]::Error.WriteLine("Repeated listing $name")
            continue
        }
        $seenHere[$nameKey] = $true
        $relative = if ($Prefix) { $Prefix + "/" + $name } else { $name }
        if ($child.IsFolder) {
            $sizeMs += [int]$sizeSw.ElapsedMilliseconds
            $sizeSw.Reset()
            Write-JsonLine ([ordered]@{ reading = $relative })
            Walk-Folder $child $relative 900
            $sizeSw.Start()
        } else {
            Add-FileLine $child $relative
            $filesHere++
        }
    }
    $sizeMs += [int]$sizeSw.ElapsedMilliseconds
    if ($filesHere -gt 0 -or $listMs -ge 1000) {
        Write-JsonLine ([ordered]@{
            reading = $label
            listMs = $listMs
            files = $filesHere
            sizeMs = $sizeMs
        })
    }
}

function Resolve-PhoneFile($Storage, $RelativePath) {
    $parts = @($RelativePath -split "[\\/]" | Where-Object { $_ -ne "" })
    if ($parts.Count -lt 1) {
        throw "Choose a file on the phone."
    }
    foreach ($part in $parts) {
        if ($part -eq "." -or $part -eq ".." -or $part.Contains(":") ) {
            throw "That phone path is not an Internal Storage file."
        }
    }
    $current = $Storage
    foreach ($part in $parts) {
        $current = Get-ChildItemByName $current $part
        if (-not $current) {
            throw "Not on the phone: $RelativePath"
        }
    }
    if ($current.IsFolder) {
        throw "That phone path is a folder: $RelativePath"
    }
    return $current
}

$pair = Get-PhoneStorage
$shell = $pair.Shell
$storage = $pair.Storage
if ($Action -eq "list") {
    $script:skipped = 0
    $script:rootCount = 0
    try {
        Write-JsonLine ([ordered]@{ phone = "Apple iPhone" })
        Write-JsonLine ([ordered]@{ reading = "Internal Storage" })
        # A cold phone fills Internal Storage after a short wait. A stuck phone
        # stays empty until the cable is unplugged, and waiting longer does not help.
        Walk-Folder $storage "" 4000
        if ($script:rootCount -eq 0) {
            [Console]::Error.WriteLine("Internal Storage opened empty. Unplug the phone, plug it back in, unlock it, and try Look again.")
            exit 1
        }
        Write-JsonLine ([ordered]@{ skipped = $script:skipped })
    } finally {
        Stop-PulseThread
    }
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Relative) -or [string]::IsNullOrWhiteSpace($Dest)) {
    throw "Pull needs -Relative and -Dest."
}
$destPath = [IO.Path]::GetFullPath($Dest)
if (Test-Path -LiteralPath $destPath) {
    throw "Destination already exists: $destPath"
}
$item = Resolve-PhoneFile $storage $Relative
$expected = [int64]$item.ExtendedProperty("System.Size")
$parent = [IO.Path]::GetDirectoryName($destPath)
if ([string]::IsNullOrWhiteSpace($parent)) {
    throw "Pull needs a destination folder."
}
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$folder = $shell.NameSpace($parent)
if (-not $folder) {
    throw "Could not open the destination folder."
}
# Silent, yes to all, no mkdir prompt, no error dialog. CopyHere returns before the file lands.
$folder.CopyHere($item, (4 -bor 16 -bor 512 -bor 1024)) | Out-Null
$deadline = (Get-Date).AddMinutes(30)
do {
    Start-Sleep -Milliseconds 300
    if ((Test-Path -LiteralPath $destPath) -and ((Get-Item -LiteralPath $destPath).Length -eq $expected)) {
        exit 0
    }
} while ((Get-Date) -lt $deadline)
throw "Explorer did not finish copying $Relative"
