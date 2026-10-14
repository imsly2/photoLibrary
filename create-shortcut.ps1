param(
    [switch]$Help,
    [switch]$DryRun
)

# Desktop + Start Menu shortcuts to Library.bat.
# Keep this file ASCII. Windows PowerShell 5.1 reads it as the system ANSI
# code page unless a UTF-8 BOM is present. Do not use em-dashes or smart quotes.

$ErrorActionPreference = "Stop"
$AppFolder = $PSScriptRoot
Set-Location $AppFolder

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
