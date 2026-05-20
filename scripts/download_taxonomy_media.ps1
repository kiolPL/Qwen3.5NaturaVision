param(
    [string]$LabelsPath = "data\v2\labels.json",
    [string]$OutputDir = "data\taxonomy_media",
    [int]$ImageWidth = 900,
    [int]$DelaySeconds = 2,
    [switch]$SkipImages,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function ConvertTo-QueryString([hashtable]$Parameters) {
    ($Parameters.GetEnumerator() | ForEach-Object {
        "{0}={1}" -f [uri]::EscapeDataString([string]$_.Key), [uri]::EscapeDataString([string]$_.Value)
    }) -join "&"
}

function Get-PageForSpecies([string]$SearchText, [int]$ThumbSize) {
    $params = @{
        action = "query"
        format = "json"
        formatversion = "2"
        generator = "search"
        gsrsearch = $SearchText
        gsrnamespace = "0"
        gsrlimit = "1"
        prop = "extracts|pageimages|info"
        inprop = "url"
        exintro = "1"
        explaintext = "1"
        exchars = "900"
        piprop = "thumbnail|original"
        pithumbsize = "$ThumbSize"
        redirects = "1"
    }
    $uri = "https://pl.wikipedia.org/w/api.php?" + (ConvertTo-QueryString $params)
    $response = Invoke-RestWithRetry -Uri $uri
    return $response.query.pages | Select-Object -First 1
}

function Invoke-RestWithRetry([string]$Uri) {
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            return Invoke-RestMethod -Uri $Uri -Headers (Get-WikiHeaders)
        } catch {
            if ($attempt -eq 5) {
                throw
            }
            $sleep = [Math]::Min(60, [Math]::Pow(2, $attempt) * 2)
            Write-Warning "Request failed on attempt $attempt. Waiting $sleep seconds before retry."
            Start-Sleep -Seconds $sleep
        }
    }
}

function Invoke-FileWithRetry([string]$Uri, [string]$OutFile) {
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Uri -OutFile $OutFile -Headers (Get-WikiHeaders)
            return $true
        } catch {
            if ($attempt -eq 5) {
                Write-Warning "Image download failed after retries: $Uri"
                return $false
            }
            $sleep = [Math]::Min(90, [Math]::Pow(2, $attempt) * 3)
            Write-Warning "Image download failed on attempt $attempt. Waiting $sleep seconds before retry."
            Start-Sleep -Seconds $sleep
        }
    }
}

function Get-WikiHeaders {
    @{
        "User-Agent" = "NaturaVisionDesktop/1.0 educational taxonomy media cache (local student project)"
    }
}

function Get-ImageExtension([string]$ImageUrl) {
    if ([string]::IsNullOrWhiteSpace($ImageUrl)) {
        return ".jpg"
    }
    $path = ([uri]$ImageUrl).AbsolutePath
    $extension = [System.IO.Path]::GetExtension($path)
    if ($extension -match "^\.(jpg|jpeg|png|webp)$") {
        return $extension.ToLowerInvariant()
    }
    return ".jpg"
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$labelsFullPath = if ([System.IO.Path]::IsPathRooted($LabelsPath)) {
    $LabelsPath
} else {
    Join-Path $root $LabelsPath
}
$outputFullPath = if ([System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir
} else {
    Join-Path $root $OutputDir
}

if (-not (Test-Path $labelsFullPath)) {
    throw "labels.json not found: $labelsFullPath"
}
New-Item -ItemType Directory -Force $outputFullPath | Out-Null

$labels = Get-Content $labelsFullPath -Raw | ConvertFrom-Json
foreach ($labelId in $labels.supported_labels) {
    if ($labelId -eq "unknown") {
        continue
    }

    $jsonPath = Join-Path $outputFullPath "$labelId.json"
    if ((Test-Path $jsonPath) -and -not $Force) {
        Write-Host "skip existing $labelId"
        continue
    }

    $entry = $labels.by_id.$labelId
    $queries = @(
        [string]$entry.scientific_name,
        [string]$entry.polish_name,
        [string]$entry.english_name,
        "$($entry.scientific_name) $($entry.polish_name)"
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

    $page = $null
    $query = ""
    foreach ($candidateQuery in $queries) {
        $query = $candidateQuery
        Write-Host "download $labelId -> $query"
        $page = Get-PageForSpecies -SearchText $query -ThumbSize $ImageWidth
        if ($null -ne $page) {
            break
        }
        Start-Sleep -Seconds $DelaySeconds
    }
    if ($null -eq $page) {
        Write-Warning "No Polish Wikipedia page found for $labelId"
        continue
    }

    $imageUrl = $null
    if ($page.thumbnail -and $page.thumbnail.source) {
        $imageUrl = [string]$page.thumbnail.source
    } elseif ($page.original -and $page.original.source) {
        $imageUrl = [string]$page.original.source
    }

    $imageFile = ""
    if (-not $SkipImages -and -not [string]::IsNullOrWhiteSpace($imageUrl)) {
        $imageFile = "$labelId$(Get-ImageExtension $imageUrl)"
        $imagePath = Join-Path $outputFullPath $imageFile
        if (-not (Invoke-FileWithRetry -Uri $imageUrl -OutFile $imagePath)) {
            $imageFile = ""
        }
    }

    $metadata = [ordered]@{
        label_id = $labelId
        title = [string]$page.title
        description = [string]$page.extract
        source_url = [string]$page.fullurl
        image_file = $imageFile
        image_url = [string]$imageUrl
        search_query = $query
        downloaded_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    $metadata | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8
    Start-Sleep -Seconds $DelaySeconds
}

Write-Host "taxonomy media cache written to $outputFullPath"
