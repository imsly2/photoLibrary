param(
    [switch]$NoBrowser,
    [switch]$Update,
    [switch]$SetupMl,
    [string]$AppFolder
)

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

$scriptPath = ""
$scriptDefinition = ""
if ($MyInvocation -and $MyInvocation.MyCommand) {
    $scriptPath = [string]$MyInvocation.MyCommand.Path
    $scriptDefinition = [string]$MyInvocation.MyCommand.Definition
}
$scriptRoot = [string]$PSScriptRoot
$resolved = Resolve-LibraryAppFolder -Hint $AppFolder -ScriptRoot $scriptRoot -ScriptPath $scriptPath -ScriptDefinition $scriptDefinition
if ([string]::IsNullOrEmpty($resolved)) {
    Write-AppFolderFail -BatName "Library.bat"
    exit 1
}
$AppFolder = $resolved
try {
    Set-Location -LiteralPath $AppFolder
} catch {
    Write-Host ""
    Write-Host "Could not open the Library folder."
    Write-Host $AppFolder
    Write-Host "Library did not start."
    exit 1
}

# ArgumentList before/after for a 1-element Get-Python312 result @($python.exe):
#   Before: PowerShell unwraps `return @($cmd.Source)` into a STRING, so
#           $python[0] is the character C and Start-Process FilePath is C
#           ("The system cannot find the file specified."). Separately,
#           $python[1..($python.Length - 1)] is $python[1..0] (indices 1,
#           then 0), so ArgumentList became python.exe, -m, library, serve.
#           Python then died with SyntaxError: Non-UTF-8 code starting with
#           '\x90' in file ... python.exe.
#   After:  return ,@(...) and $python = @(Get-Python312). $exe is
#           [string]$python[0]. Extras only when Count/Length -gt 1
#           (py -3.12). Length-1 ArgumentList is -m, library, serve
#           (or update). Keeps -Update from the presentable-shell tip.

function Test-PythonVersion {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ExtraArgs = @()
    )
    $probe = @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)")
    & $FilePath @ExtraArgs @probe
    return ($LASTEXITCODE -eq 0)
}

function Get-Python312 {
    $venv = Join-Path $AppFolder ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) {
        if (Test-PythonVersion -FilePath $venv) {
            return ,@($venv)
        }
    }
    foreach ($name in @("python", "py")) {
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

try {
    $python = @(Get-Python312)
    $ffmpegOk = Test-Ffmpeg
    if ($python.Count -lt 1 -or -not $python[0] -or -not $ffmpegOk) {
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
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
        $python = @(Get-Python312)
        $ffmpegOk = Test-Ffmpeg
        if ($python.Count -lt 1 -or -not $python[0] -or -not $ffmpegOk) {
            Write-Error "Python 3.12+ and ffmpeg are required on PATH."
            exit 1
        }
    }

    $exe = [string]$python[0]
    if ($Update) {
        Write-Host "Updating... tracking main over anonymous HTTPS (no GitHub login, no gh)."
        Write-Host "If git is missing, downloads a zip of main. library-data is not replaced."
        $updateArgs = Get-PythonArgumentList -Python $python -ModuleArgs @("-m", "library", "update", "--relaunch")
        & $exe @updateArgs
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            Write-Host "Update did not finish. Check the internet, then run Update.bat again."
            Write-Host "If this copy left main, Update will try to move it back. Ask Steve if it says diverged."
        }
        exit $code
    }
    if ($SetupMl) {
        Write-Host "Downloading local object model..."
        $setupArgs = Get-PythonArgumentList -Python $python -ModuleArgs @("-m", "library", "setup-ml", "objects")
        & $exe @setupArgs
        exit $LASTEXITCODE
    }

    $argumentList = Get-PythonArgumentList -Python $python -ModuleArgs @("-m", "library", "serve")
    $proc = Start-Process -FilePath $exe -ArgumentList $argumentList -WorkingDirectory $AppFolder -PassThru -NoNewWindow
    $url = "http://127.0.0.1:8765/"
    $deadline = (Get-Date).AddSeconds(20)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri ($url.TrimEnd("/") + "/api/health") -UseBasicParsing -TimeoutSec 1
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 200
        }
    }
    if (-not $NoBrowser) {
        Start-Process $url
    }
    if ($proc -and -not $proc.HasExited) {
        Wait-Process -Id $proc.Id
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "Library could not start." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    exit 1
}
