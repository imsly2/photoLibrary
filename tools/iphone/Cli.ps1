# Run the bundled get-and-see CLI with a writable, app-local extraction directory.
# Compatible with Windows PowerShell 5.1. This wrapper does not choose a destination.
$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'bin/get-and-see.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Bundled get-and-see.exe is missing. Restore tools/iphone from the repository.' }
$appFolder = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$bundle = Join-Path $appFolder '.local/iphone-cli-bundle'
$null = [IO.Directory]::CreateDirectory($bundle)
$previous = $env:DOTNET_BUNDLE_EXTRACT_BASE_DIR
$cliArgs = @($args)
if ($cliArgs.Count -eq 0) { $cliArgs = @('--help') }
$code = 1
try {
    $env:DOTNET_BUNDLE_EXTRACT_BASE_DIR = $bundle
    & $exe @cliArgs
    $code = $LASTEXITCODE
} finally {
    $env:DOTNET_BUNDLE_EXTRACT_BASE_DIR = $previous
}
exit $code
