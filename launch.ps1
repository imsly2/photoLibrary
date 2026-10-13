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
            if ($name -eq "py") { return @($cmd.Source, "-3.12") }
            return @($cmd.Source)
        }
    }
    return @()
}

function Test-Ffmpeg {
    return [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
}

$python = Get-Python312
$ffmpegOk = Test-Ffmpeg
if (-not $python -or -not $ffmpegOk) {
    if ($python) {
        Write-Host "Installing missing ffmpeg with winget..."
    } else {
        Write-Host "Installing missing Python 3.12 / ffmpeg with winget..."
    }
    if (-not $python) {
        winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    }
    if (-not $ffmpegOk) {
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
    }
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
    $python = Get-Python312
    $ffmpegOk = Test-Ffmpeg
    if (-not $python -or -not $ffmpegOk) {
        Write-Error "Python 3.12+ and ffmpeg are required on PATH."
        exit 1
    }
}

$proc = Start-Process -FilePath $python[0] -ArgumentList (@($python[1..($python.Length - 1)] | Where-Object { $_ }) + @("-m", "library", "serve")) -WorkingDirectory $AppFolder -PassThru -NoNewWindow
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
