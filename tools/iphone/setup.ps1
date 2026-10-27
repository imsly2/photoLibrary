param(
    [switch]$Help,
    [switch]$DryRun,
    [string]$AppFolder
)

# One-time setup for the iPhone photos window. Does not copy photos.
# Keep this file ASCII. Windows PowerShell 5.1 reads a no-BOM file as ANSI.

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host ""
    Write-Host "Setup.bat  -- one-time install on this Windows PC"
    Write-Host ""
    Write-Host "  1. Python 3.12+ with tkinter (winget Python.Python.3.12 if missing)"
    Write-Host "  2. Phone helper exe. If it is missing, winget the .NET 10 SDK and build it."
    Write-Host "     If the exe is already here, winget the .NET 10 runtime when this PC lacks it."
    Write-Host "  3. Apple Devices (winget 9NP83LWLPZ9K) when neither that app nor iTunes is installed."
    Write-Host "     Open Apple Devices once after a reboot so USB port 27015 is listening."
    Write-Host ""
    Write-Host "The window has no pip packages. This does not copy photos."
    Write-Host ""
    Write-Host "  -Help     this text"
    Write-Host "  -DryRun   probe only; do not winget or build"
    Write-Host ""
}

if ($Help) {
    Show-Help
    exit 0
}

if ([string]::IsNullOrWhiteSpace($AppFolder)) {
    $AppFolder = [string]$PSScriptRoot
}
$AppFolder = $AppFolder.Trim().TrimEnd('\', '/')
if ([string]::IsNullOrWhiteSpace($AppFolder) -or -not (Test-Path -LiteralPath $AppFolder -PathType Container)) {
    Write-Host "Could not find the iPhone photos folder."
    Write-Host "Open that folder and run Setup.bat from there."
    exit 1
}
Set-Location -LiteralPath $AppFolder

$HostExe = Join-Path $AppFolder "ui-host\bin\Release\net10.0\win-x64\iphone-photos-host.exe"
$BuildScript = Join-Path $AppFolder "Build-Host.ps1"

function Write-Step {
    param([int]$Number, [int]$Total, [string]$Text)
    Write-Host ""
    Write-Host ("[" + $Number + "/" + $Total + "] " + $Text)
}

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = $machine + ";" + $user
}

function Invoke-WingetInstall {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [string]$Source = "winget"
    )
    # Do not return winget's console lines. A non-empty output array is
    # truthy, so a failed install looked successful to the caller.
    $script:WingetExit = 1
    $wingetArgs = @(
        "install", "--id", $Id, "-e",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity", "--source", $Source
    )
    & winget @wingetArgs
    $script:WingetExit = $LASTEXITCODE
}

function Test-PythonTk {
    $candidates = @()
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $candidates += ,@($py.Source, @("-3")) }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { $candidates += ,@($python.Source, @()) }
    foreach ($pair in $candidates) {
        $exe = [string]$pair[0]
        $extra = @($pair[1])
        & $exe @extra -c "import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            return $exe
        }
    }
    return $null
}

function Test-DotNet10Sdk {
    $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
    if (-not $dotnet) { return $false }
    $sdks = & dotnet --list-sdks 2>&1 | Out-String
    return ($sdks -match "(?m)^10\.")
}

function Get-HostState {
    if (-not (Test-Path -LiteralPath $HostExe)) {
        return "missing"
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $HostExe 2>&1 | Out-String
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($output -match "You must install or update \.NET") {
        return "needs-runtime"
    }
    if ($output -match "Usage:") {
        return "ok"
    }
    return "failed"
}

function Test-ApplePackage {
    foreach ($name in @("AppleInc.AppleDevices", "AppleInc.iTunes")) {
        $pkg = Get-AppxPackage -Name $name -ErrorAction SilentlyContinue
        if ($pkg) { return $true }
    }
    $keys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $rows = Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match "iTunes|Apple Devices|Apple Mobile Device" }
    return [bool]$rows
}

function Test-UsbMux {
    $listen = Get-NetTCPConnection -LocalPort 27015 -State Listen -ErrorAction SilentlyContinue
    return [bool]$listen
}

if ($DryRun) {
    Write-Host "Dry-run -- no winget and no build."
    Write-Host ""
}

$python = Test-PythonTk
Write-Step -Number 1 -Total 3 -Text "Python 3.12+ with tkinter"
if ($python) {
    Write-Host ("Python: " + $python)
} elseif ($DryRun) {
    Write-Host "Dry-run: would winget install Python.Python.3.12."
} else {
    Write-Host "Installing Python 3.12..."
    Invoke-WingetInstall -Id "Python.Python.3.12"
    if ($script:WingetExit -ne 0) {
        Write-Host "Python install failed. Re-run Setup.bat on the internet."
        exit 1
    }
    Refresh-Path
    $python = Test-PythonTk
    if (-not $python) {
        Write-Host "Python installed but tkinter is not importable yet. Open a new window and run Setup.bat again."
        exit 1
    }
    Write-Host ("Python: " + $python)
}

Write-Step -Number 2 -Total 3 -Text "Phone helper (.NET 10)"
$state = Get-HostState
Write-Host ("Helper: " + $state)
if ($state -eq "ok") {
    Write-Host $HostExe
} elseif ($DryRun) {
    if ($state -eq "missing") {
        Write-Host "Dry-run: would install the .NET 10 SDK and build the phone helper."
    } elseif ($state -eq "needs-runtime") {
        Write-Host "Dry-run: would winget install Microsoft.DotNet.Runtime.10."
    } else {
        Write-Host "Dry-run: phone helper did not start. A real run would install the .NET 10 runtime and try again."
    }
} elseif ($state -eq "missing") {
    if (-not (Test-DotNet10Sdk)) {
        Write-Host "Installing the .NET 10 SDK so the helper can be built..."
        Invoke-WingetInstall -Id "Microsoft.DotNet.SDK.10"
        if ($script:WingetExit -ne 0) {
            Write-Host "Could not install the .NET 10 SDK."
            exit 1
        }
        Refresh-Path
    }
    if (-not (Test-Path -LiteralPath $BuildScript)) {
        Write-Host "Build-Host.ps1 is missing."
        exit 1
    }
    & $BuildScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "The phone helper did not build."
        exit 1
    }
    $state = Get-HostState
    if ($state -ne "ok") {
        Write-Host ("Phone helper state after build: " + $state)
        exit 1
    }
    Write-Host $HostExe
} else {
    Write-Host "Installing the .NET 10 runtime..."
    Invoke-WingetInstall -Id "Microsoft.DotNet.Runtime.10"
    if ($script:WingetExit -ne 0) {
        Write-Host "Could not install Microsoft.DotNet.Runtime.10."
        exit 1
    }
    $state = Get-HostState
    if ($state -ne "ok") {
        Write-Host ("Phone helper still will not start (" + $state + ").")
        Write-Host "Close this window, open a new one, and run Setup.bat again."
        exit 1
    }
    Write-Host $HostExe
}

Write-Step -Number 3 -Total 3 -Text "Apple USB driver"
$apple = Test-ApplePackage
$usb = Test-UsbMux
if ($apple) {
    Write-Host "Apple Devices or iTunes is installed."
} elseif ($DryRun) {
    Write-Host "Dry-run: would winget install Apple Devices (9NP83LWLPZ9K)."
} else {
    Write-Host "Installing Apple Devices..."
    Invoke-WingetInstall -Id "9NP83LWLPZ9K" -Source "msstore"
    if ($script:WingetExit -ne 0) {
        Write-Host "Could not install Apple Devices. Install it from the Microsoft Store, open it once, then run Setup.bat again."
        exit 1
    }
    $apple = Test-ApplePackage
}
if ($usb) {
    Write-Host "USB service is listening on port 27015."
} else {
    Write-Host "Port 27015 is not listening yet."
    Write-Host "Open Apple Devices once (or iTunes), then plug in the phone."
}

Write-Host ""
if ($DryRun) {
    Write-Host "Dry-run ready. Run Setup.bat to install anything still missing."
} else {
    Write-Host "Ready -- run Launch-Window.ps1"
}
Write-Host "Setup does not copy photos."
exit 0
