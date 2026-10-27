# Exploratory metadata-only probe. Run in normal PowerShell 7; no phone writes.
param([Parameter(Mandatory=$true)][string]$Report)
$ErrorActionPreference='Stop'
$path=[IO.Path]::GetFullPath($Report)
if(Test-Path -LiteralPath $path){throw 'Choose a new report filename.'}
Add-Type -Path (Join-Path $PSScriptRoot 'WpdReadOnlyProbe.cs')
$result=[ordered]@{probeOnly=$true;completeManifest=$false;deviceWrites=$false;stage=$null;root=@();children=@();error=$null}
$failed=$false
try {
 $null=[MirrorAudit.Reader]::Connect()
 $result.root=@([MirrorAudit.Reader]::Children('DEVICE',''))
 $rows=[Collections.Generic.List[object]]::new()
 foreach($item in $result.root){foreach($child in [MirrorAudit.Reader]::Children($item.Id,$item.Path+'/')){$rows.Add($child)}}
 $result.children=$rows.ToArray()
} catch {
 $failed=$true;$ex=$_.Exception
 while($ex.InnerException){$ex=$ex.InnerException}
 $result.error=[ordered]@{message=$ex.Message;hresult=('0x{0:X8}' -f $ex.HResult)}
} finally {
 $result.stage=[MirrorAudit.Reader]::Stage
 $null=[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
 $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
}
Write-Host ('Probe report: '+$path)
Write-Host ('Stage: '+$result.stage)
if($failed){throw ('WPD probe failed: '+$result.error.message)}
