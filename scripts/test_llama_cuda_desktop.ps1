param(
    [string]$LlamaBinDir = "C:\tmp\llama-b9245-bin-win-cuda-13.1-x64",
    [string]$ModelPath = "D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q4_k_m-fixed.gguf",
    [string]$ProjectorPath = "D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-mmproj-f16.gguf",
    [string]$ImagePath = "D:\NaturaVisionPortable\portable_dataset\images\PLANT_01\100828991.jpg",
    [int]$GpuLayers = 99,
    [int]$ImageTokens = 1024,
    [int]$Predict = 12
)

$ErrorActionPreference = "Stop"

$cli = Join-Path $LlamaBinDir "llama-mtmd-cli.exe"
foreach ($path in @($cli, $ModelPath, $ProjectorPath, $ImagePath)) {
    if (-not (Test-Path $path)) {
        throw "Required file not found: $path"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$labelsPath = Join-Path $repoRoot "data\v2\labels.json"
if (-not (Test-Path $labelsPath)) {
    throw "Required file not found: $labelsPath"
}
$labels = Get-Content $labelsPath -Raw | ConvertFrom-Json
$allowedLabels = @($labels.supported_labels + $labels.training_supported_labels) | Sort-Object -Unique
$taxonomyLines = foreach ($labelId in $labels.supported_labels) {
    if ($labelId -eq "unknown") {
        "- unknown = unsupported or ambiguous image"
        continue
    }
    $entry = $labels.by_id.$labelId
    "- $labelId = $($entry.scientific_name) ($($entry.polish_name); $($entry.english_name))"
}
$systemPrompt = @(
    "You classify exactly one forest organism from a fixed taxonomy."
    "Return JSON only with the single key label_id."
    "Choose exactly one allowed label_id from the list below."
    "If no known label fits, return unknown."
    "Do not output thinking, explanations, markdown, or <think> blocks."
    "Do not invent labels, synonyms, or alternate JSON keys."
    "Allowed labels:"
    $taxonomyLines
) -join "`n"
$schema = @{
    type = "object"
    properties = @{
        label_id = @{
            type = "string"
            enum = $allowedLabels
        }
    }
    required = @("label_id")
    additionalProperties = $false
} | ConvertTo-Json -Compress -Depth 5
$schemaPath = Join-Path $repoRoot "tmp\naturavision-label-schema.json"
New-Item -ItemType Directory -Force (Split-Path -Parent $schemaPath) | Out-Null
Set-Content -Path $schemaPath -Value $schema -Encoding UTF8

Write-Host "== llama.cpp CUDA devices =="
& $cli --list-devices

Write-Host ""
Write-Host "== NaturaVision CUDA smoke inference =="
Write-Host "llama_bin=$LlamaBinDir"
Write-Host "model=$ModelPath"
Write-Host "projector=$ProjectorPath"
Write-Host "image=$ImagePath"
Write-Host "gpu_layers=$GpuLayers image_tokens=$ImageTokens predict=$Predict"

& $cli `
    -m $ModelPath `
    --mmproj $ProjectorPath `
    --image $ImagePath `
    -sys $systemPrompt `
    -p "<__media__>Classify the forest organism. Return JSON only." `
    -n $Predict `
    -c 4096 `
    -fa on `
    --temp 0 `
    --top-k 1 `
    --top-p 1 `
    --min-p 0 `
    --repeat-penalty 1 `
    --presence-penalty 0 `
    --frequency-penalty 0 `
    --seed 42 `
    --image-min-tokens $ImageTokens `
    --image-max-tokens $ImageTokens `
    --json-schema-file $schemaPath `
    -ngl $GpuLayers `
    --no-warmup
