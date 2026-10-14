param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$AppFolder = $PSScriptRoot
Set-Location $AppFolder

# ArgumentList before/after for a 1-element Get-Python312 result @($python.exe):
#   Before: $python[1..($python.Length - 1)] is $python[1..0] (indices 1, then 0),
#           so ArgumentList became python.exe, -m, library, serve.
#           Python then died with SyntaxError: Non-UTF-8 code starting with '\x90'
#           in file ... python.exe — or Start-Process could not find the file.
#   After:  extras only when Length -gt 1 (py -3.12). Length-1 ArgumentList is
#           -m, library, serve. FilePath stays the interpreter.

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

function Get-ServeArgumentList {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Python
    )
    $extras = @()
    if ($Python.Length -gt 1) {
        $extras = @($Python[1..($Python.Length - 1)] | Where-Object { $_ })
    }
    return ,($extras + @("-m", "library", "serve"))
}

function Test-Ffmpeg {
    return [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
}

try {
    $python = Get-Python312
    if ($null -eq $python) { $python = [string[]]@() }
    $ffmpegOk = Test-Ffmpeg
    if ($python.Count -lt 1 -or -not $ffmpegOk) {
        if ($python.Count -gt 0) {
            Write-Host "Installing missing ffmpeg with winget..."
        } else {
            Write-Host "Installing missing Python 3.12 / ffmpeg with winget..."
        }
        if ($python.Count -lt 1) {
            winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
        }
        if (-not $ffmpegOk) {
            winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        }
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
        $python = Get-Python312
        if ($null -eq $python) { $python = [string[]]@() }
        $ffmpegOk = Test-Ffmpeg
        if ($python.Count -lt 1 -or -not $ffmpegOk) {
            Write-Error "Python 3.12+ and ffmpeg are required on PATH."
            exit 1
        }
    }

    $argumentList = Get-ServeArgumentList -Python $python
    $proc = Start-Process -FilePath ([string]$python[0]) -ArgumentList $argumentList -WorkingDirectory $AppFolder -PassThru -NoNewWindow
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
