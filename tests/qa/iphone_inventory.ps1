param([Parameter(Mandatory=$true)][string]$Scratch)
$ErrorActionPreference='Stop'
$root=Join-Path $Scratch ('inventory-check-'+[Guid]::NewGuid().ToString('N'))
$local=Join-Path $root 'backup'
$null=New-Item -ItemType Directory -Path (Join-Path $local 'nested') -Force
$null=New-Item -ItemType Directory -Path (Join-Path $local '.library') -Force
[IO.File]::WriteAllText((Join-Path $local 'nested/IMG_0001.JPG'),'abc')
[IO.File]::WriteAllText((Join-Path $local 'renamed.HEIC'),'abcd')
[IO.File]::WriteAllText((Join-Path $local 'unmatched.txt'),'ab')
[IO.File]::WriteAllText((Join-Path $local '.library/generated.thumb'),'ignored')
$inputFile=Join-Path $root 'saved.json'
$fixture=@{device=@{name='Fixture';productType='Fixture';fingerprint='fixture-only'}; roots=@(@{path='/DCIM';files=3;bytes=10});errors=@();files=@(@{path='/DCIM/IMG_0001.JPG';size=3},@{path='/PhotoData/CPLAssets/group1/uuid.HEIC';size=4},@{path='/DCIM/IMG_0002.JPG';size=3})}
$fixture | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $inputFile
$report=Join-Path $root 'report.json'
$script=Join-Path $PSScriptRoot '../../tools/iphone/Inventory.ps1'
& $script -ReadInventory $inputFile -CompareFolder $local -Report $report
$r=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if($r.fileCount -ne 3 -or $r.bytes -ne 10){throw 'Saved inventory totals changed'}
if($r.comparison.localFiles -ne 3 -or $r.comparison.localBytes -ne 9){throw 'Nested files/exclusion totals incorrect'}
if($r.comparison.nameAndSizeCandidates -ne 1){throw 'Exact name-size count incorrect'}
if($r.comparison.sizeOnlyCandidates -ne 2 -or $r.comparison.sizeOnlyCandidateBytes -ne 7){throw 'UUID size candidate count incorrect'}
$ambiguous=@($r.comparison.candidates | Where-Object size -eq 3)
if($ambiguous[0].sourceCandidates.Count -ne 2){throw 'Ambiguous candidates were silently collapsed'}
if($r.sampleChecks.Count -ne 0){throw 'Offline comparison must not claim verified hashes'}
$blocked=$false
try { & $script -ReadInventory $inputFile -CompareFolder $local -Report (Join-Path $local 'forbidden-report.json') } catch { $blocked=$true }
if(-not $blocked){throw 'Report inside backup must be rejected'}
$blocked=$false
try { & $script -ReadInventory $inputFile -Report $report } catch { $blocked=$true }
if(-not $blocked){throw 'Existing report must not be overwritten'}
$badFile=Join-Path $root 'incomplete.json'
$fixture.errors=@(@{path='/DCIM';message='fixture disconnect'})
$fixture | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $badFile
$badReport=Join-Path $root 'incomplete-report.json'
$blocked=$false
try { & $script -ReadInventory $badFile -Report $badReport } catch { $blocked=$true }
$bad=Get-Content -LiteralPath $badReport -Raw | ConvertFrom-Json
if(-not $blocked -or $bad.completeForRequestedRoots){throw 'Incomplete inventory must be reported as failed'}
Write-Host 'PASS: totals, nested folders, exclusions, UUID/ambiguous candidates, no false verification, read-only output boundaries, existing-report protection, incomplete-scan failure.'
