param(
    [switch]$NoBrowser,
    [switch]$Update,
    [switch]$SetupMl,
    [switch]$Attach,
    [string]$Page,
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
& (Join-Path $AppFolder "local-runtime.ps1") -AppFolder $AppFolder
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

function Get-LibraryListenUrl {
    param([Parameter(Mandatory = $true)][string]$Folder)
    $port = 8765
    $hostName = "127.0.0.1"
    $settingsPath = Join-Path $Folder "library-data\settings.json"
    if (Test-Path -LiteralPath $settingsPath) {
        try {
            $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
            if ($settings.port) { $port = [int]$settings.port }
            if ($settings.listenHost) { $hostName = [string]$settings.listenHost }
        } catch {
            $port = 8765
            $hostName = "127.0.0.1"
        }
    }
    if ($hostName -eq "0.0.0.0" -or $hostName -eq "::") {
        $hostName = "127.0.0.1"
    }
    return ("http://{0}:{1}/" -f $hostName, $port)
}

function Open-LibraryPage {
    param([Parameter(Mandatory = $true)][string]$Url)
    $open = $Url
    if ($Page -eq "import-iphone") {
        $open = $Url.TrimEnd("/") + "/#import-iphone"
    }
    Write-Host $open
    if (-not $NoBrowser) {
        Start-Process $open
    }
}

function Test-ThisLibraryIsOpen {
    param([Parameter(Mandatory = $true)][string]$Folder)
    $url = Get-LibraryListenUrl -Folder $Folder
    $runtime = Get-LibraryRuntime -Url $url
    if ($null -eq $runtime) { return $false }
    if ([int]$runtime.schemaVersion -ne 1) { return $false }
    $root = Join-Path $Folder "library-data"
    if (-not (Test-SameLibraryRoot -Left ([string]$runtime.root) -Right $root)) { return $false }
    return (Test-LibraryHealth -Url $url)
}

function Test-LibraryHealth {
    param([Parameter(Mandatory = $true)][string]$Url)
    try {
        $resp = Invoke-WebRequest -Uri ($Url.TrimEnd("/") + "/api/health") -UseBasicParsing -TimeoutSec 1
        return ($resp.StatusCode -eq 200 -and $resp.Content -match '"ok"\s*:\s*true')
    } catch {
        return $false
    }
}

function Get-LibraryRuntime {
    param([Parameter(Mandatory = $true)][string]$Url)
    try {
        $resp = Invoke-WebRequest -Uri ($Url.TrimEnd("/") + "/api/runtime") -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -ne 200) { return $null }
        return ($resp.Content | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Test-SameLibraryRoot {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
        return $false
    }
    try {
        $a = [System.IO.Path]::GetFullPath($Left).TrimEnd('\', '/')
        $b = [System.IO.Path]::GetFullPath($Right).TrimEnd('\', '/')
    } catch {
        return $false
    }
    return [string]::Equals($a, $b, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-SpawnedBy {
    param([int]$Ancestor, [int]$Candidate)
    # The venv python.exe is a redirector. Start-Process sees that pid.
    # The real interpreter is its child, and that child is the listener.
    $current = $Candidate
    for ($i = 0; $i -lt 8; $i++) {
        if ($current -eq $Ancestor) { return $true }
        if ($current -le 4) { return $false }
        $info = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $current) -ErrorAction SilentlyContinue
        if (-not $info) { return $false }
        $parent = [int]$info.ParentProcessId
        if ($parent -eq $current) { return $false }
        $current = $parent
    }
    return $false
}

function Stop-ThisLibraryServe {
    param([Parameter(Mandatory = $true)][string]$Folder)
    $root = Join-Path $Folder "library-data"
    $url = Get-LibraryListenUrl -Folder $Folder
    $runtime = Get-LibraryRuntime -Url $url
    if ($null -eq $runtime) { return 0 }
    if ([int]$runtime.schemaVersion -ne 1) { return 0 }
    if (-not (Test-SameLibraryRoot -Left ([string]$runtime.root) -Right $root)) { return 0 }
    $listenPid = 0
    try { $listenPid = [int]$runtime.pid } catch { return 0 }
    # PID 0 and PID 4 are Idle and System. Never stop those.
    if ($listenPid -le 4) { return 0 }
    $killPid = $listenPid
    $info = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $listenPid) -ErrorAction SilentlyContinue
    if ($info) {
        $parentId = [int]$info.ParentProcessId
        if ($parentId -gt 4) {
            $parent = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $parentId) -ErrorAction SilentlyContinue
            if ($parent -and [string]$parent.CommandLine -match "library serve") {
                $killPid = $parentId
            }
        }
    }
    Write-Host ("Library is already open as pid {0}. Stopping it so this launch loads the latest code." -f $listenPid)
    & taskkill.exe /PID $killPid /T /F | Out-Host
    $deadline = (Get-Date).AddSeconds(8)
    while ((Get-Date) -lt $deadline) {
        $alive = Get-Process -Id $listenPid -ErrorAction SilentlyContinue
        if (-not $alive) { return $listenPid }
        Start-Sleep -Milliseconds 200
    }
    Write-Host ("Could not stop the Library that is already open (pid {0})." -f $listenPid)
    return -1
}

try {
    if ($Attach -and (Test-ThisLibraryIsOpen -Folder $AppFolder)) {
        Write-Host "Library is already open. This window can close."
        Open-LibraryPage (Get-LibraryListenUrl -Folder $AppFolder)
        exit 0
    }

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

    $replacedPid = Stop-ThisLibraryServe -Folder $AppFolder
    if ($replacedPid -lt 0) {
        if (Test-ThisLibraryIsOpen -Folder $AppFolder) {
            Write-Host "Could not restart Library. The one already open is still running."
            Open-LibraryPage (Get-LibraryListenUrl -Folder $AppFolder)
            exit 0
        }
        Write-Host "Could not stop the Library that is already open, and it is not answering."
        exit 1
    }

    $argumentList = Get-PythonArgumentList -Python $python -ModuleArgs @("-m", "library", "serve")
    $proc = Start-Process -FilePath $exe -ArgumentList $argumentList -WorkingDirectory $AppFolder -PassThru -NoNewWindow
    $expectedRoot = Join-Path $AppFolder "library-data"
    $url = Get-LibraryListenUrl -Folder $AppFolder
    $deadline = (Get-Date).AddSeconds(60)
    $ready = $false
    $serverPid = 0
    while ((Get-Date) -lt $deadline) {
        $url = Get-LibraryListenUrl -Folder $AppFolder
        $runtime = Get-LibraryRuntime -Url $url
        $listenerPid = 0
        if ($runtime -and $runtime.pid) { $listenerPid = [int]$runtime.pid }
        if (
            $listenerPid -gt 4 -and
            (Test-SameLibraryRoot -Left ([string]$runtime.root) -Right $expectedRoot) -and
            (Test-SpawnedBy -Ancestor $proc.Id -Candidate $listenerPid)
        ) {
            $ready = $true
            $serverPid = $listenerPid
            break
        }
        if ($proc.HasExited) { break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) {
        if ($proc -and -not $proc.HasExited) {
            Write-Host "Library is still starting. Leave this window open."
            $deadline = (Get-Date).AddSeconds(60)
            while ((Get-Date) -lt $deadline) {
                $url = Get-LibraryListenUrl -Folder $AppFolder
                $runtime = Get-LibraryRuntime -Url $url
                $listenerPid = 0
                if ($runtime -and $runtime.pid) { $listenerPid = [int]$runtime.pid }
                if (
                    $listenerPid -gt 4 -and
                    (Test-SameLibraryRoot -Left ([string]$runtime.root) -Right $expectedRoot) -and
                    (Test-SpawnedBy -Ancestor $proc.Id -Candidate $listenerPid)
                ) {
                    $ready = $true
                    $serverPid = $listenerPid
                    break
                }
                if ($proc.HasExited) { break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
    if (-not $ready) {
        if (Test-ThisLibraryIsOpen -Folder $AppFolder) {
            Write-Host "Library is already open."
            Open-LibraryPage (Get-LibraryListenUrl -Folder $AppFolder)
            exit 0
        }
        if ($replacedPid -gt 0) {
            Write-Host "Library could not replace the server that was already open."
        } else {
            Write-Host "Library could not start. Its listen port is already in use."
        }
        Write-Host "Leave any Library window that is already open. Closing it stops the server."
        exit 1
    }
    Write-Host ("Library is running as pid {0}." -f $serverPid)
    Open-LibraryPage $url
    if ($serverPid -gt 4) {
        Wait-Process -Id $serverPid
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "Library could not start." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    exit 1
}
