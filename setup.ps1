param(
    [switch]$Help,
    [switch]$DryRun,
    [switch]$ProbeAppFolder,
    [string]$AppFolder
)

# Portable one-time setup. Does not start serve.
# Library.bat / launch.ps1 keep the daily listen path.
# Keep this file ASCII. Windows PowerShell 5.1 reads it as the system ANSI
# code page unless a UTF-8 BOM is present. A UTF-8 em-dash (bytes E2 80 94)
# becomes a closing quote (0x94) and the parser then treats a later "using"
# inside a Write-Host string as a using-directive.

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
    Write-Host "Setup.bat  -- one-time portable install on this Windows PC"
    Write-Host ""
    Write-Host "  Setup once   -- this file (Python 3.12+, ffmpeg, .venv, local AI models)"
    Write-Host "  Shortcut     -- Desktop / Start Menu icon (CreateShortcut.bat)"
    Write-Host "  Library      -- Library.bat every day"
    Write-Host "  Update       -- Update.bat or Update Library for new code (git pull)"
    Write-Host ""
    Write-Host "  1. Python 3.12+ and ffmpeg (winget if missing: Python.Python.3.12, Gyan.FFmpeg)"
    Write-Host "     Optional git (winget Git.Git). If git is missing, Update downloads a zip of main."
    Write-Host "     No GitHub account. No gh tool."
    Write-Host "  2. .venv + pip install the app"
    Write-Host "  3. python -m library setup-geo"
    Write-Host "  4. python -m library setup-ml objects"
    Write-Host "  5. python -m library setup-ml faces"
    Write-Host "  6. python -m library setup-ml transcribe"
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

$scriptPath = ""
$scriptDefinition = ""
if ($MyInvocation -and $MyInvocation.MyCommand) {
    $scriptPath = [string]$MyInvocation.MyCommand.Path
    $scriptDefinition = [string]$MyInvocation.MyCommand.Definition
}
$scriptRoot = [string]$PSScriptRoot
$resolved = Resolve-LibraryAppFolder -Hint $AppFolder -ScriptRoot $scriptRoot -ScriptPath $scriptPath -ScriptDefinition $scriptDefinition
if ([string]::IsNullOrEmpty($resolved)) {
    Write-AppFolderFail -BatName "Setup.bat"
    exit 1
}
$AppFolder = $resolved
if ($ProbeAppFolder) {
    Write-Host ("APPFOLDER=" + $AppFolder)
    exit 0
}
try {
    Set-Location -LiteralPath $AppFolder
} catch {
    Write-Host ""
    Write-Host "Could not open the Library folder."
    Write-Host $AppFolder
    Write-Host "Setup did not finish."
    exit 1
}

function Write-Step {
    param(
        [Parameter(Mandatory = $true)][int]$Number,
        [Parameter(Mandatory = $true)][int]$Total,
        [Parameter(Mandatory = $true)][string]$Text
    )
    Write-Host ""
    Write-Host ("[" + $Number + "/" + $Total + "] " + $Text)
}

function Write-FailNext {
    param(
        [Parameter(Mandatory = $true)][string]$Step,
        [string]$Detail
    )
    Write-Host ""
    Write-Host ("Setup could not finish at: " + $Step) -ForegroundColor Red
    if ($Detail) {
        Write-Host $Detail -ForegroundColor Red
    }
    Write-Host "What to try next:"
    Write-Host "  1. Check this PC is on the internet, then run Setup.bat again (safe to re-run)."
    Write-Host "  2. If it asked you to Update Library, run Update.bat, then Setup.bat again."
    Write-Host "  3. If Python or ffmpeg failed, run Setup.bat as the same Windows user after winget finishes."
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

function Test-Git {
    return [bool](Get-Command git -ErrorAction SilentlyContinue)
}

function Ensure-Git {
    if (Test-Git) {
        Write-Host "git: found (Update uses anonymous HTTPS; no GitHub login, no gh)"
        return
    }
    if ($DryRun) {
        Write-Host "Dry-run: git is not on PATH (would winget install Git.Git, or Update uses a zip of main)."
        return
    }
    if ($env:OS -ne "Windows_NT") {
        Write-Host "git is optional. Update can download a zip of main. No GitHub account."
        return
    }
    Write-Host "Git is optional. Trying winget Git.Git (no GitHub account, no gh)..."
    winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
    Refresh-Path
    if (Test-Git) {
        Write-Host "git: installed"
        return
    }
    Write-Host "Git is not installed. That is OK."
    Write-Host "Update Library will download a zip of main over HTTPS."
    Write-Host "No GitHub account and no gh tool are needed. library-data stays put."
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
        Write-FailNext -Step "Python / ffmpeg" -Detail "Python 3.12+ and ffmpeg must be on PATH. Install them, then re-run setup."
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
        Write-FailNext -Step "Python / ffmpeg" -Detail "winget could not put Python 3.12+ and ffmpeg on PATH."
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
        Write-FailNext -Step ".venv" -Detail "Python 3.12+ is required to create .venv."
        Write-Error "Python 3.12+ is required to create .venv."
        exit 1
    }
    Write-Host "Creating .venv..."
    $createArgs = Get-PythonArgumentList -Python $Bootstrap -ModuleArgs @("-m", "venv", ".venv")
    & ([string]$Bootstrap[0]) @createArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Write-FailNext -Step ".venv" -Detail "Could not create .venv."
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
        Write-FailNext -Step "pip" -Detail "pip upgrade failed."
        Write-Error "pip upgrade failed."
        exit 1
    }
    & $VenvPython -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        Write-FailNext -Step "pip" -Detail "pip install of the Library app failed."
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
    Write-Host "Need: setup-geo  (PR places)  +  setup-ml objects  (PR objects)  +  setup-ml faces  (PR faces)  +  setup-ml transcribe  (Whisper)"
}

function Install-Shortcuts {
    $script = Join-Path $AppFolder "create-shortcut.ps1"
    if (-not (Test-Path -LiteralPath $script)) {
        Write-Host "Shortcut script missing -- run CreateShortcut.bat later if you want an icon."
        return
    }
    if ($DryRun) {
        Write-Host "Dry-run: would create Desktop and Start Menu shortcuts."
        return
    }
    & $script -AppFolder $AppFolder
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Shortcut was not created. Run CreateShortcut.bat after Setup finishes."
    }
}

try {
    if ($DryRun) {
        Write-Host "Dry-run -- no winget, pip, or model download."
        Write-Host "A real Setup.bat needs the internet the first time (models stay in library-data/)."
        Write-Host ""
    } else {
        Write-Host "This first Setup needs the internet (Python/ffmpeg if missing, then model packs)."
        Write-Host "Re-run is safe. Models stay in library-data/. No MSI."
        Write-Host ""
    }

    Write-Step -Number 1 -Total 8 -Text "Checking Python 3.12+, ffmpeg, and optional git (internet if they are missing)..."
    $bootstrap = @(Ensure-PythonAndFfmpeg)
    if (-not $DryRun -and ($bootstrap.Count -lt 1 -or -not $bootstrap[0])) {
        Write-FailNext -Step "Python / ffmpeg" -Detail "Python 3.12+ is required."
        Write-Error "Python 3.12+ is required."
        exit 1
    }
    if ($bootstrap.Count -ge 1 -and $bootstrap[0]) {
        Write-Host ("Python: " + [string]$bootstrap[0])
    }
    if (Test-Ffmpeg) {
        Write-Host "ffmpeg: found"
    }
    Ensure-Git

    Write-Step -Number 2 -Total 8 -Text "Creating .venv (skipped if it already works)..."
    $venvPython = Ensure-Venv -Bootstrap $bootstrap
    if (-not $venvPython) {
        if ($DryRun) {
            Write-Host "Dry-run: no Python 3.12+ to probe library commands."
            Write-MissingUpdate -Missing @("setup-geo", "setup-ml objects", "setup-ml faces", "setup-ml transcribe")
            exit 1
        }
        Write-FailNext -Step ".venv" -Detail "No Python interpreter for setup."
        Write-Error "No Python interpreter for setup."
        exit 1
    }
    Write-Step -Number 3 -Total 8 -Text "Installing Library into .venv (pip)..."
    if (-not $DryRun) {
        Install-App -VenvPython $venvPython
    } elseif (Test-Path -LiteralPath (Get-VenvPythonPath)) {
        Write-Host "Dry-run: .venv already exists; probe commands with it."
        $venvPython = Get-VenvPythonPath
        Install-App -VenvPython $venvPython
    } else {
        Write-Host "Dry-run: probing commands with bootstrap Python (no pip install)."
    }

    $helpText = Get-LibraryHelp -PythonExe $venvPython
    $wanted = @(
        @{ Name = "setup-geo"; Tokens = @("setup-geo"); Pull = "setup-geo (places / cities pack)" },
        @{ Name = "setup-ml objects"; Tokens = @("setup-ml", "objects"); Pull = "setup-ml objects (YOLO)" },
        @{ Name = "setup-ml faces"; Tokens = @("setup-ml", "faces"); Pull = "setup-ml faces (InsightFace)" },
        @{ Name = "setup-ml transcribe"; Tokens = @("setup-ml", "transcribe"); Pull = "setup-ml transcribe (Whisper)" }
    )
    $missing = @()
    $ran = @()
    foreach ($item in $wanted) {
        $present = $false
        if ($helpText -match [regex]::Escape($item.Tokens[0])) {
            $present = Test-LibraryCommand -PythonExe $venvPython -Tokens $item.Tokens
        }
        if (-not $present) {
            Write-Host ("Skip  python -m library " + $item.Name + "  -- not in this copy yet.")
            $missing += $item.Name
            continue
        }
        $stepNumber = 4 + $ran.Count
        Write-Step -Number $stepNumber -Total 8 -Text ("Downloading " + $item.Pull + " ...")
        if ($DryRun) {
            Write-Host ("Dry-run: would run  python -m library " + $item.Name)
            $ran += $item.Name
            continue
        }
        Write-Host ("Running python -m library " + $item.Name + " ...")
        $cmdArgs = @("-m", "library") + $item.Tokens
        & $venvPython @cmdArgs
        if ($LASTEXITCODE -ne 0) {
            Write-FailNext -Step $item.Name -Detail ("python -m library " + $item.Name + " failed.")
            Write-Error ("python -m library " + $item.Name + " failed.")
            exit 1
        }
        $ran += $item.Name
    }

    if ($missing.Count -gt 0) {
        Write-MissingUpdate -Missing $missing
        exit 1
    }

    Write-Step -Number 8 -Total 8 -Text "Creating Desktop and Start Menu shortcuts..."
    Install-Shortcuts

    Write-Host ""
    if ($DryRun) {
        Write-Host "Dry-run ready -- all four setup commands are in this copy."
        Write-Host "Run Setup.bat (without -DryRun) to download packs. Then run Library.bat."
    } else {
        Write-Host "Ready -- run Library.bat"
        Write-Host "Or double-click the Library icon on the Desktop."
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "Library setup could not finish." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    Write-FailNext -Step "setup" -Detail ""
    exit 1
}
