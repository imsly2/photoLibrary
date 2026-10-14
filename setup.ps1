param(
    [switch]$Help,
    [switch]$DryRun
)

# Portable one-time setup. Does not start serve.
# Library.bat / launch.ps1 keep the daily listen path.

$ErrorActionPreference = "Stop"
$AppFolder = $PSScriptRoot
Set-Location $AppFolder

function Show-Help {
    Write-Host ""
    Write-Host "Setup.bat  — one-time portable install on this Windows PC"
    Write-Host ""
    Write-Host "  Setup once   — this file (Python 3.12+, ffmpeg, .venv, local AI models)"
    Write-Host "  Library      — Library.bat every day"
    Write-Host "  Update       — Update.bat or Update Library for new code (git pull)"
    Write-Host ""
    Write-Host "  1. Python 3.12+ and ffmpeg (winget if missing: Python.Python.3.12, Gyan.FFmpeg)"
    Write-Host "  2. .venv + pip install the app"
    Write-Host "  3. python -m library setup-geo"
    Write-Host "  4. python -m library setup-ml objects"
    Write-Host "  5. python -m library setup-ml faces"
    Write-Host ""
    Write-Host "First model download needs the internet. Models stay under library-data/."
    Write-Host "Re-run is safe (idempotent). No MSI. Does not start Library.bat."
    Write-Host ""
    Write-Host "  -Help     this text"
    Write-Host "  -DryRun   probe only; do not download or pip install"
    Write-Host ""
}

if ($Help) {
    Show-Help
    exit 0
}

function Test-PythonVersion {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ExtraArgs = @()
    )
    $probe = @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)")
    & $FilePath @ExtraArgs @probe
    return ($LASTEXITCODE -eq 0)
}

function Get-VenvPythonPath {
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        return (Join-Path $AppFolder ".venv\Scripts\python.exe")
    }
    return (Join-Path $AppFolder ".venv/bin/python")
}

function Get-BootstrapPython {
    foreach ($name in @("python", "py", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $extra = @()
        if ($name -eq "py") { $extra = @("-3.12") }
        if (Test-PythonVersion -FilePath $cmd.Source -ExtraArgs $extra) {
            if ($extra.Count -gt 0) {
                return ,@($cmd.Source, $extra[0])
            }
            return ,@($cmd.Source)
        }
    }
    return ,[string[]]@()
}

function Get-PythonArgumentList {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Python,
        [Parameter(Mandatory = $true)][string[]]$ModuleArgs
    )
    $extras = @()
    if ($Python.Count -gt 1) {
        $extras = @($Python[1..($Python.Count - 1)] | Where-Object { $_ })
    }
    return ,($extras + $ModuleArgs)
}

function Test-Ffmpeg {
    return [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    if ($env:OS -eq "Windows_NT") {
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
    }
}

function Ensure-PythonAndFfmpeg {
    $python = @(Get-BootstrapPython)
    $ffmpegOk = Test-Ffmpeg
    if ($python.Count -ge 1 -and $python[0] -and $ffmpegOk) {
        return ,$python
    }
    if ($DryRun) {
        if ($python.Count -lt 1 -or -not $python[0]) {
            Write-Host "Dry-run: Python 3.12+ is not on PATH (would winget install Python.Python.3.12)."
        }
        if (-not $ffmpegOk) {
            Write-Host "Dry-run: ffmpeg is not on PATH (would winget install Gyan.FFmpeg)."
        }
        return ,$python
    }
    if ($env:OS -ne "Windows_NT") {
        Write-Error "Python 3.12+ and ffmpeg must be on PATH. Install them, then re-run setup."
        exit 1
    }
    if ($python.Count -gt 0 -and $python[0]) {
        Write-Host "Installing missing ffmpeg with winget..."
    } else {
        Write-Host "Installing missing Python 3.12 / ffmpeg with winget..."
    }
    if ($python.Count -lt 1 -or -not $python[0]) {
        winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    }
    if (-not $ffmpegOk) {
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
    }
    Refresh-Path
    $python = @(Get-BootstrapPython)
    $ffmpegOk = Test-Ffmpeg
    if ($python.Count -lt 1 -or -not $python[0] -or -not $ffmpegOk) {
        Write-Error "Python 3.12+ and ffmpeg are required on PATH."
        exit 1
    }
    return ,$python
}

function Ensure-Venv {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Bootstrap
    )
    $venvPython = Get-VenvPythonPath
    if (Test-Path -LiteralPath $venvPython) {
        if (Test-PythonVersion -FilePath $venvPython) {
            Write-Host "Using existing .venv"
            return $venvPython
        }
    }
    if ($DryRun) {
        Write-Host "Dry-run: would create .venv and pip install the app."
        if (Test-Path -LiteralPath $venvPython) {
            return $venvPython
        }
        if ($Bootstrap.Count -ge 1 -and $Bootstrap[0]) {
            return [string]$Bootstrap[0]
        }
        return $null
    }
    if ($Bootstrap.Count -lt 1 -or -not $Bootstrap[0]) {
        Write-Error "Python 3.12+ is required to create .venv."
        exit 1
    }
    Write-Host "Creating .venv..."
    $createArgs = Get-PythonArgumentList -Python $Bootstrap -ModuleArgs @("-m", "venv", ".venv")
    & ([string]$Bootstrap[0]) @createArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Write-Error "Could not create .venv."
        exit 1
    }
    return $venvPython
}

function Install-App {
    param([Parameter(Mandatory = $true)][string]$VenvPython)
    if ($DryRun) {
        Write-Host "Dry-run: would run  $VenvPython -m pip install -e ."
        return
    }
    Write-Host "Installing app into .venv..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip upgrade failed."
        exit 1
    }
    & $VenvPython -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install of the Library app failed."
        exit 1
    }
}

function Get-LibraryHelp {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $PythonExe -m library --help 2>&1 | Out-String
        return $output
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-LibraryCommand {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string[]]$Tokens
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $all = @("-m", "library") + $Tokens + @("--help")
        $output = & $PythonExe @all 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $output -notmatch "invalid choice") {
            return $true
        }
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Write-MissingUpdate {
    param([string[]]$Missing)
    Write-Host ""
    Write-Host "This copy does not have the local AI setup commands yet:" -ForegroundColor Yellow
    foreach ($item in $Missing) {
        Write-Host "  - python -m library $item"
    }
    Write-Host ""
    Write-Host "Run Update Library (or Update.bat) to git pull those modules,"
    Write-Host "then run Setup.bat again."
    Write-Host "Need: setup-geo  (PR places)  +  setup-ml objects  (PR objects)  +  setup-ml faces  (PR faces)"
}

try {
    if ($DryRun) {
        Write-Host "Dry-run — no winget, pip, or model download."
        Write-Host "A real Setup.bat needs the internet the first time (models stay in library-data/)."
        Write-Host ""
    }

    $bootstrap = @(Ensure-PythonAndFfmpeg)
    if (-not $DryRun -and ($bootstrap.Count -lt 1 -or -not $bootstrap[0])) {
        Write-Error "Python 3.12+ is required."
        exit 1
    }
    if ($bootstrap.Count -ge 1 -and $bootstrap[0]) {
        Write-Host ("Python: " + [string]$bootstrap[0])
    }
    if (Test-Ffmpeg) {
        Write-Host "ffmpeg: found"
    }

    $venvPython = Ensure-Venv -Bootstrap $bootstrap
    if (-not $venvPython) {
        if ($DryRun) {
            Write-Host "Dry-run: no Python 3.12+ to probe library commands."
            Write-MissingUpdate -Missing @("setup-geo", "setup-ml objects", "setup-ml faces")
            exit 1
        }
        Write-Error "No Python interpreter for setup."
        exit 1
    }
    if (-not $DryRun) {
        Install-App -VenvPython $venvPython
    } elseif (Test-Path -LiteralPath (Get-VenvPythonPath)) {
        Write-Host "Dry-run: .venv already exists; using it to probe commands."
        $venvPython = Get-VenvPythonPath
        Install-App -VenvPython $venvPython
    } else {
        Write-Host "Dry-run: probing commands with bootstrap Python (no pip install)."
    }

    $helpText = Get-LibraryHelp -PythonExe $venvPython
    $wanted = @(
        @{ Name = "setup-geo"; Tokens = @("setup-geo"); Pull = "setup-geo (places / cities pack)" },
        @{ Name = "setup-ml objects"; Tokens = @("setup-ml", "objects"); Pull = "setup-ml objects (YOLO)" },
        @{ Name = "setup-ml faces"; Tokens = @("setup-ml", "faces"); Pull = "setup-ml faces (InsightFace)" }
    )
    $missing = @()
    $ran = @()
    foreach ($item in $wanted) {
        $present = $false
        if ($helpText -match [regex]::Escape($item.Tokens[0])) {
            $present = Test-LibraryCommand -PythonExe $venvPython -Tokens $item.Tokens
        }
        if (-not $present) {
            Write-Host ("Skip  python -m library " + $item.Name + "  — not in this copy yet.")
            $missing += $item.Name
            continue
        }
        if ($DryRun) {
            Write-Host ("Dry-run: would run  python -m library " + $item.Name)
            $ran += $item.Name
            continue
        }
        Write-Host ("Running python -m library " + $item.Name + " ...")
        $cmdArgs = @("-m", "library") + $item.Tokens
        & $venvPython @cmdArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error ("python -m library " + $item.Name + " failed.")
            exit 1
        }
        $ran += $item.Name
    }

    if ($missing.Count -gt 0) {
        Write-MissingUpdate -Missing $missing
        exit 1
    }

    Write-Host ""
    if ($DryRun) {
        Write-Host "Dry-run ready — all three setup commands are in this copy."
        Write-Host "Run Setup.bat (without -DryRun) to download packs. Then run Library.bat."
    } else {
        Write-Host "Ready — run Library.bat"
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "Library setup could not finish." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    exit 1
}
