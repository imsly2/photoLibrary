param(
    [switch]$Help,
    [switch]$DryRun,
    [string]$AppFolder
)

# Desktop + Start Menu shortcuts to Library.bat.
# Keep this file ASCII. Windows PowerShell 5.1 reads it as the system ANSI
# code page unless a UTF-8 BOM is present. Do not use em-dashes or smart quotes.

$ErrorActionPreference = "Stop"

function Get-TrimmedFolder {
    param([string]$Path)
    if ([string]::IsNullOrEmpty($Path)) {
        return ""
    }
    $item = $Path.Trim()
    while ($item.Length -gt 3 -and ($item.EndsWith("\") -or $item.EndsWith("/"))) {
        $item = $item.Substring(0, $item.Length - 1)
    }
    return $item
}

function Resolve-LibraryAppFolder {
    param(
        [string]$Hint,
        [string]$ScriptRoot,
        [string]$ScriptPath,
        [string]$ScriptDefinition
    )
    $candidates = @()
    if (-not [string]::IsNullOrEmpty($Hint)) {
        $candidates += Get-TrimmedFolder $Hint
    }
    if (-not [string]::IsNullOrEmpty($ScriptRoot)) {
        $candidates += Get-TrimmedFolder $ScriptRoot
    }
    if (-not [string]::IsNullOrEmpty($ScriptPath)) {
        $parent = Split-Path -Parent $ScriptPath
        if (-not [string]::IsNullOrEmpty($parent)) {
            $candidates += Get-TrimmedFolder $parent
        }
    }
    if (-not [string]::IsNullOrEmpty($ScriptDefinition)) {
        if (Test-Path -LiteralPath $ScriptDefinition) {
            $parent = Split-Path -Parent $ScriptDefinition
            if (-not [string]::IsNullOrEmpty($parent)) {
                $candidates += Get-TrimmedFolder $parent
            }
        }
    }
    $here = ""
    try {
        $here = Get-TrimmedFolder ([string](Get-Location).Path)
    } catch {
        $here = ""
    }

    foreach ($item in $candidates) {
        if ([string]::IsNullOrEmpty($item)) { continue }
        if (Test-Path -LiteralPath $item -PathType Container) {
            try {
                return [System.IO.Path]::GetFullPath($item)
            } catch {
                return $item
            }
        }
    }
    if (-not [string]::IsNullOrEmpty($here) -and (Test-Path -LiteralPath $here -PathType Container)) {
        $markers = @("Setup.bat", "Library.bat", "Launch.bat", "setup.ps1", "launch.ps1", "CreateShortcut.bat")
        foreach ($name in $markers) {
            if (Test-Path -LiteralPath (Join-Path $here $name)) {
                try {
                    return [System.IO.Path]::GetFullPath($here)
                } catch {
                    return $here
                }
            }
        }
    }
    return $null
}
# end Resolve-LibraryAppFolder

function Write-AppFolderFail {
    param([string]$BatName)
    Write-Host ""
    Write-Host ("Could not find the Library folder (the folder with " + $BatName + ").")
    Write-Host "Open that folder and run the .bat again."
    Write-Host "Did not finish."
}

function Show-Help {
    Write-Host ""
    Write-Host "CreateShortcut.bat  -- Desktop and Start Menu icon for Library"
    Write-Host ""
    Write-Host "  Target   Library.bat in this folder"
    Write-Host "  Icon     library.ico (or Library.bat if the ico is missing)"
    Write-Host "  Places   Desktop and Start Menu Programs"
    Write-Host ""
    Write-Host "Safe to re-run. Does not start Library. No MSI."
    Write-Host ""
    Write-Host "  -Help     this text"
    Write-Host "  -DryRun   print paths only; do not write .lnk files"
    Write-Host ""
}

if ($Help) {
    Show-Help
    exit 0
}

$scriptPath = ""
$scriptDefinition = ""
if ($MyInvocation -and $MyInvocation.MyCommand) {
    $scriptPath = [string]$MyInvocation.MyCommand.Path
    $scriptDefinition = [string]$MyInvocation.MyCommand.Definition
}
$scriptRoot = [string]$PSScriptRoot
$resolved = Resolve-LibraryAppFolder -Hint $AppFolder -ScriptRoot $scriptRoot -ScriptPath $scriptPath -ScriptDefinition $scriptDefinition
if ([string]::IsNullOrEmpty($resolved)) {
    Write-AppFolderFail -BatName "CreateShortcut.bat"
    exit 1
}
$AppFolder = $resolved
try {
    Set-Location -LiteralPath $AppFolder
} catch {
    Write-Host ""
    Write-Host "Could not open the Library folder."
    Write-Host $AppFolder
    Write-Host "Shortcut was not created."
    exit 1
}

function Get-LibraryTarget {
    $launch = Join-Path $AppFolder "Launch.bat"
    $library = Join-Path $AppFolder "Library.bat"
    if (Test-Path -LiteralPath $launch) {
        return $launch
    }
    return $library
}

function Get-LibraryIcon {
    $ico = Join-Path $AppFolder "library.ico"
    if (Test-Path -LiteralPath $ico) {
        return $ico
    }
    return (Get-LibraryTarget)
}

function Get-ShortcutPaths {
    $desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Library.lnk"
    $programs = [Environment]::GetFolderPath("Programs")
    if (-not $programs) {
        $programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    }
    $startMenu = Join-Path $programs "Library.lnk"
    return @($desktop, $startMenu)
}

function Write-LibraryShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$Icon
    )
    $folder = Split-Path -Parent $LinkPath
    if ($folder -and -not (Test-Path -LiteralPath $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($LinkPath)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = $AppFolder
    $shortcut.WindowStyle = 1
    $shortcut.Description = "Library"
    $shortcut.IconLocation = $Icon
    $shortcut.Save()
}

try {
    $target = Get-LibraryTarget
    $icon = Get-LibraryIcon
    if (-not (Test-Path -LiteralPath $target)) {
        Write-Host "Library.bat is missing from this folder." -ForegroundColor Red
        Write-Host "Copy the whole Library folder, then run CreateShortcut.bat again."
        exit 1
    }

    $paths = @(Get-ShortcutPaths)
    Write-Host ("Target: " + $target)
    Write-Host ("Icon:   " + $icon)
    foreach ($link in $paths) {
        Write-Host ("Link:   " + $link)
    }

    if ($DryRun) {
        Write-Host "Dry-run -- no shortcut files written."
        exit 0
    }

    foreach ($link in $paths) {
        Write-LibraryShortcut -LinkPath $link -Target $target -Icon $icon
        Write-Host ("Wrote " + $link)
    }
    Write-Host "Shortcut ready -- double-click Library on the Desktop."
    exit 0
} catch {
    Write-Host ""
    Write-Host "Could not create the Library shortcut." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    Write-Host "What to try next: run CreateShortcut.bat again, or right-click Library.bat and Send to Desktop."
    exit 1
}
