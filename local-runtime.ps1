# Optional app-local dependencies. Only this process and its children see these paths.
param([Parameter(Mandatory = $true)][string]$AppFolder)
$localRoot = Join-Path $AppFolder ".local"
$dotnetRoot = Join-Path $localRoot "dotnet"
$ffmpegBin = Join-Path $localRoot "ffmpeg\bin"
if (Test-Path -LiteralPath (Join-Path $dotnetRoot "dotnet.exe")) {
    $env:DOTNET_ROOT = $dotnetRoot
    $env:DOTNET_ROOT_X64 = $dotnetRoot
}
if (Test-Path -LiteralPath (Join-Path $ffmpegBin "ffmpeg.exe")) {
    $env:Path = $ffmpegBin + ";" + $env:Path
}
