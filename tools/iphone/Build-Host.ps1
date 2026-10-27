# Build the read-only phone helper. Needs the .NET SDK. Does not copy photos.
$ErrorActionPreference = "Stop"
$Project = Join-Path $PSScriptRoot "ui-host\IphonePhotos.Host.csproj"
$Exe = Join-Path $PSScriptRoot "ui-host\bin\Release\net10.0\win-x64\iphone-photos-host.exe"

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    Write-Error "dotnet is not installed. The window will say the phone helper is not built yet."
}

dotnet build $Project -c Release
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Phone helper: $Exe"
