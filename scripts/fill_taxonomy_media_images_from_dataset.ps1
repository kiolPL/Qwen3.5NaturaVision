param(
    [string]$MediaDir = "data\taxonomy_media",
    [string]$DatasetImagesDir = "D:\NaturaVisionPortable\portable_dataset\images",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$mediaFullPath = if ([System.IO.Path]::IsPathRooted($MediaDir)) {
    $MediaDir
} else {
    Join-Path $repoRoot $MediaDir
}

if (-not (Test-Path $mediaFullPath)) {
    throw "Media directory not found: $mediaFullPath"
}
if (-not (Test-Path $DatasetImagesDir)) {
    throw "Dataset images directory not found: $DatasetImagesDir"
}

foreach ($jsonPath in Get-ChildItem $mediaFullPath -Filter "*.json") {
    $metadata = Get-Content $jsonPath.FullName -Raw | ConvertFrom-Json
    $labelId = [string]$metadata.label_id
    if ([string]::IsNullOrWhiteSpace($labelId)) {
        continue
    }

    $currentImageFile = [string]$metadata.image_file
    if (-not $Force -and -not [string]::IsNullOrWhiteSpace($currentImageFile)) {
        $currentImagePath = Join-Path $mediaFullPath $currentImageFile
        if (Test-Path $currentImagePath) {
            Write-Host "skip existing image $labelId"
            continue
        }
    }

    $sourceDir = Join-Path $DatasetImagesDir $labelId
    if (-not (Test-Path $sourceDir)) {
        Write-Warning "No dataset image folder for $labelId"
        continue
    }

    $allowedExtensions = ".jpg", ".jpeg", ".png", ".webp"
    $sourceImage = Get-ChildItem $sourceDir -File |
        Where-Object { $allowedExtensions -contains $_.Extension.ToLowerInvariant() } |
        Sort-Object Length -Descending |
        Select-Object -First 1
    if ($null -eq $sourceImage) {
        Write-Warning "No dataset image found for $labelId"
        continue
    }

    $extension = $sourceImage.Extension.ToLowerInvariant()
    $targetImageFile = "$labelId-dataset$extension"
    $targetImagePath = Join-Path $mediaFullPath $targetImageFile
    Copy-Item -LiteralPath $sourceImage.FullName -Destination $targetImagePath -Force

    $updated = [ordered]@{}
    foreach ($property in $metadata.PSObject.Properties) {
        if ($property.Name -eq "image_file") {
            $updated[$property.Name] = $targetImageFile
        } else {
            $updated[$property.Name] = $property.Value
        }
    }
    if (-not $updated.Contains("image_file")) {
        $updated["image_file"] = $targetImageFile
    }
    $updated["dataset_image_source"] = $sourceImage.FullName
    $updated | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath.FullName -Encoding UTF8
    Write-Host "filled $labelId from $($sourceImage.FullName)"
}
