param(
    [switch]$Help,
    [switch]$DryRun,
    [string]$AppFolder
)

# Thin wrapper around pack-deploy.py. Keep this file ASCII. Windows
# PowerShell 5.1 reads it as the system ANSI code page unless a UTF-8 BOM
# is present. Do not use em-dashes or smart quotes.

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
        $markers = @("Setup.bat", "Library.bat", "Launch.bat", "setup.ps1", "launch.ps1", "PackDeploy.bat")
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
    Write-Host "PackDeploy.bat  -- write a lean zip for USB / family PCs"
    Write-Host ""
    Write-Host "  Writes dist\photoLibrary-deploy.zip (overwrites that file)."
    Write-Host "  The zip is the app only: Setup, Library, Update, and library code."
    Write-Host "  It does not include .venv, library-data, docs, tests, or .git."
    Write-Host ""
    Write-Host "  Copy the zip, extract it, then run Setup.bat on the other PC."
    Write-Host "  Safe to run again. No MSI. Does not start Library."
    Write-Host ""
    Write-Host "  -Help     this text"
    Write-Host "  -DryRun   list includes and excludes; do not write the zip"
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
    Write-AppFolderFail -BatName "PackDeploy.bat"
    exit 1
}
$AppFolder = $resolved
try {
    Set-Location -LiteralPath $AppFolder
} catch {
    Write-Host ""
    Write-Host "Could not open the Library folder."
    Write-Host $AppFolder
    Write-Host "Pack did not finish."
    exit 1
}

$pyScript = Join-Path $AppFolder "pack-deploy.py"
if (-not (Test-Path -LiteralPath $pyScript)) {
    Write-Host ""
    Write-Host "Missing pack-deploy.py in the Library folder."
    Write-Host "Did not finish."
    exit 1
}

function Test-PythonWorks {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ExtraArgs = @()
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @ExtraArgs "-c" "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Get-PackPython {
    $found = @()
    $venvWin = Join-Path $AppFolder ".venv\Scripts\python.exe"
    $venvUnix = Join-Path $AppFolder ".venv\bin\python"
    if (Test-Path -LiteralPath $venvWin) {
        $found += ,@($venvWin)
    }
    if (Test-Path -LiteralPath $venvUnix) {
        $found += ,@($venvUnix)
    }
    foreach ($name in @("python", "python3", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        if ($name -eq "py") {
            $found += ,@($cmd.Source, "-3")
        } else {
            $found += ,@($cmd.Source)
        }
    }
    foreach ($item in $found) {
        $exe = [string]$item[0]
        $extra = @()
        if ($item.Count -gt 1) {
            $extra = @($item[1])
        }
        if (Test-PythonWorks -FilePath $exe -ExtraArgs $extra) {
            if ($extra.Count -gt 0) {
                return ,@($exe, $extra[0])
            }
            return ,@($exe)
        }
    }
    return ,[string[]]@()
}

$python = @(Get-PackPython)
if ($python.Count -lt 1 -or -not $python[0]) {
    Write-Host ""
    Write-Host "Need Python 3 to pack the zip."
    Write-Host "Install Python 3.12+ (or run Setup.bat first), then run PackDeploy.bat again."
    exit 1
}

$pyArgs = @()
if ($python.Count -gt 1) {
    $pyArgs += [string]$python[1]
}
$pyArgs += $pyScript
$pyArgs += "--app-folder"
$pyArgs += $AppFolder
if ($DryRun) {
    $pyArgs += "--dry-run"
}

& ([string]$python[0]) @pyArgs
exit $LASTEXITCODE
