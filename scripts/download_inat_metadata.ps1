param(
    [string]$MetadataDir = "",
    [string]$AwsExe = "C:\Program Files\Amazon\AWSCLIV2\aws.exe",
    [string]$CurlExe = "C:\Windows\System32\curl.exe",
    [ValidateSet("curl", "aws")]
    [string]$DownloadTool = "curl",
    [string]$Bucket = "s3://inaturalist-open-data",
    [string]$HttpBase = "https://inaturalist-open-data.s3.amazonaws.com"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

if ([string]::IsNullOrWhiteSpace($MetadataDir)) {
    $MetadataDir = Join-Path $ProjectRoot "data\metadata"
} elseif (-not [System.IO.Path]::IsPathRooted($MetadataDir)) {
    $MetadataDir = Join-Path $ProjectRoot $MetadataDir
}

$LogPath = Join-Path $MetadataDir "download_metadata.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $LogPath -Append
}

if ($DownloadTool -eq "aws" -and -not (Test-Path $AwsExe)) {
    throw "AWS CLI not found at: $AwsExe"
}

if ($DownloadTool -eq "curl" -and -not (Test-Path $CurlExe)) {
    throw "curl not found at: $CurlExe"
}

New-Item -ItemType Directory -Force -Path $MetadataDir | Out-Null

$targets = @(
    "observations.csv.gz",
    "photos.csv.gz",
    "taxa.csv.gz"
)

Write-Log "Starting iNaturalist metadata download."

foreach ($target in $targets) {
    $destination = Join-Path $MetadataDir $target
    $tempPattern = "$target.*"

    if (Test-Path $destination) {
        Write-Log "Skipping existing file: $target"
        continue
    }

    Get-ChildItem -Path $MetadataDir -Filter $tempPattern -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne $target } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    Write-Log "Downloading $target"
    if ($DownloadTool -eq "curl") {
        & $CurlExe -L -C - --retry 10 --retry-all-errors --output $destination "$HttpBase/$target"
    } else {
        & $AwsExe s3 cp "$Bucket/$target" $destination --no-sign-request --no-progress --only-show-errors --cli-read-timeout 0 --cli-connect-timeout 0
    }
    Write-Log "Finished $target"
}

Write-Log "All requested metadata files are present."
