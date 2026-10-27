# Read Apple iPhone the way File Explorer does: Internal Storage, then the
# year-month folders Explorer shows. List writes nothing to the phone or the
# backup. Pull copies one file into a new local path and refuses to replace it.
param(
    [Parameter(Mandatory = $true)][ValidateSet("list", "pull")][string]$Action,
    [string]$Relative = "",
    [string]$Dest = ""
)
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Write-JsonLine($Object) {
    $line = $Object | ConvertTo-Json -Compress -Depth 4
    [Console]::Out.WriteLine($line)
}

function Get-PhoneStorage {
    $shell = New-Object -ComObject Shell.Application
    $phone = $null
    foreach ($item in @($shell.NameSpace(17).Items())) {
        if ($item.Name -eq "Apple iPhone") {
            $phone = $item
            break
        }
    }
    if (-not $phone) {
        throw "Apple iPhone is not in This PC. Unlock the phone, tap Trust, and open Apple Devices once."
    }
    $storage = $null
    foreach ($item in @($phone.GetFolder.Items())) {
        if ($item.Name -eq "Internal Storage") {
            $storage = $item
            break
        }
    }
    if (-not $storage) {
        throw "Internal Storage is not on the phone."
    }
    $pair = New-Object psobject -Property @{ Shell = $shell; Storage = $storage }
    return ,$pair
}

function Get-ChildItemByName($FolderItem, $Name) {
    foreach ($child in @($FolderItem.GetFolder.Items())) {
        if ($child.Name -eq $Name) {
            return $child
        }
    }
    return $null
}

function Add-FileLine($Item, $RelativePath) {
    $sizeValue = $Item.ExtendedProperty("System.Size")
    if ($null -eq $sizeValue) {
        throw "Explorer did not report a size for $RelativePath"
    }
    Write-JsonLine ([ordered]@{
        rel = $RelativePath
        size = [int64]$sizeValue
    })
}

function Walk-Folder($FolderItem, $Prefix) {
    foreach ($child in @($FolderItem.GetFolder.Items())) {
        $name = [string]$child.Name
        if ([string]::IsNullOrWhiteSpace($name) -or $name -eq "." -or $name -eq ".." -or $name.Contains("/") -or $name.Contains("\")) {
            throw "Explorer returned a folder name that cannot be a backup path."
        }
        $relative = if ($Prefix) { $Prefix + "/" + $name } else { $name }
        if ($child.IsFolder) {
            Walk-Folder $child $relative
        } else {
            Add-FileLine $child $relative
        }
    }
}

function Resolve-PhoneFile($Storage, $RelativePath) {
    $parts = @($RelativePath -split "[\\/]" | Where-Object { $_ -ne "" })
    if ($parts.Count -lt 1) {
        throw "Choose a file on the phone."
    }
    foreach ($part in $parts) {
        if ($part -eq "." -or $part -eq ".." -or $part.Contains(":") ) {
            throw "That phone path is not an Internal Storage file."
        }
    }
    $current = $Storage
    foreach ($part in $parts) {
        $current = Get-ChildItemByName $current $part
        if (-not $current) {
            throw "Not on the phone: $RelativePath"
        }
    }
    if ($current.IsFolder) {
        throw "That phone path is a folder: $RelativePath"
    }
    return $current
}

$pair = Get-PhoneStorage
$shell = $pair.Shell
$storage = $pair.Storage
if ($Action -eq "list") {
    Write-JsonLine ([ordered]@{ phone = "Apple iPhone" })
    Walk-Folder $storage ""
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Relative) -or [string]::IsNullOrWhiteSpace($Dest)) {
    throw "Pull needs -Relative and -Dest."
}
$destPath = [IO.Path]::GetFullPath($Dest)
if (Test-Path -LiteralPath $destPath) {
    throw "Destination already exists: $destPath"
}
$item = Resolve-PhoneFile $storage $Relative
$expected = [int64]$item.ExtendedProperty("System.Size")
$parent = [IO.Path]::GetDirectoryName($destPath)
if ([string]::IsNullOrWhiteSpace($parent)) {
    throw "Pull needs a destination folder."
}
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$folder = $shell.NameSpace($parent)
if (-not $folder) {
    throw "Could not open the destination folder."
}
# Silent, yes to all, no mkdir prompt, no error dialog. CopyHere returns before the file lands.
$folder.CopyHere($item, (4 -bor 16 -bor 512 -bor 1024)) | Out-Null
$deadline = (Get-Date).AddMinutes(30)
do {
    Start-Sleep -Milliseconds 300
    if ((Test-Path -LiteralPath $destPath) -and ((Get-Item -LiteralPath $destPath).Length -eq $expected)) {
        exit 0
    }
} while ((Get-Date) -lt $deadline)
throw "Explorer did not finish copying $Relative"
