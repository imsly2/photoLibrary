param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$AppFolder = $PSScriptRoot
Set-Location $AppFolder

function Get-Python312 {
    $candidates = @("python", "py")
    foreach ($name in $candidates) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $args = @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)")
        if ($name -eq "py") { $args = @("-3.12") + $args }
        & $cmd.Source @args
        if ($LASTEXITCODE -eq 0) {
            # Leading comma keeps a one-item array from unwrapping to a string
            if ($name -eq "py") { return ,@($cmd.Source, "-3.12") }
            return ,@($cmd.Source)
        }
    }
    return @()
}

function Test-Ffmpeg {
    return [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
}

$python = @(Get-Python312)
$ffmpegOk = Test-Ffmpeg
if ($python.Count -eq 0 -or -not $ffmpegOk) {
    if ($python.Count -gt 0) {
        Write-Host "Installing missing ffmpeg with winget..."
    } else {
        Write-Host "Installing missing Python 3.12 / ffmpeg with winget..."
    }
    if ($python.Count -eq 0) {
        winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    }
    if (-not $ffmpegOk) {
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
    }
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
    $python = @(Get-Python312)
    $ffmpegOk = Test-Ffmpeg
    if ($python.Count -eq 0 -or -not $ffmpegOk) {
        Write-Error "Python 3.12+ and ffmpeg are required on PATH."
        exit 1
    }
}

$exe = [string]$python[0]
$pyArgs = @()
if ($python.Count -gt 1) {
    $pyArgs = @($python[1..($python.Count - 1)] | Where-Object { $_ })
}
$pyArgs += @("-m", "library", "serve")
Write-Host "Starting library with: $exe $($pyArgs -join ' ')"
$proc = Start-Process -FilePath $exe -ArgumentList $pyArgs -WorkingDirectory $AppFolder -PassThru -NoNewWindow
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
if (-not $ready) {
    Write-Host "Server did not become ready at $url"
}
if (-not $NoBrowser) {
    Start-Process $url
}
if ($proc -and -not $proc.HasExited) {
    Wait-Process -Id $proc.Id
}
exit 0
