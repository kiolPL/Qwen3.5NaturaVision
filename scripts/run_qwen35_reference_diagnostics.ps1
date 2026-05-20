param(
    [string]$ModelPath = "D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q3_k_s-fixed.gguf",
    [string]$ProjectorPath = "D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-mmproj-f16.gguf",
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [string]$LlamaBinDir = "C:\tmp\llama-b9222-bin-win-cpu-x64",
    [ValidateSet("pc_reference_cpu", "pc_reference_vulkan")]
    [string]$Profile = "pc_reference_cpu",
    [int]$ImageTokens = 32,
    [int]$Predict = 16
)

$ErrorActionPreference = "Stop"

$cli = Join-Path $LlamaBinDir "llama-mtmd-cli.exe"
if (-not (Test-Path $cli)) {
    throw "llama-mtmd-cli.exe not found at $cli"
}
foreach ($path in @($ModelPath, $ProjectorPath, $ImagePath)) {
    if (-not (Test-Path $path)) {
        throw "Required file not found: $path"
    }
}

$gpuLayers = if ($Profile -eq "pc_reference_vulkan") { 99 } else { 0 }
$deviceArgs = if ($Profile -eq "pc_reference_vulkan") { @("-ngl", "$gpuLayers") } else { @("-ngl", "0", "--no-mmproj-offload") }
$systemPrompt = "You identify one forest organism from an image. Do not think step by step. Do not output <think>. Return JSON only as {`"label_id`":`"<id>`"}."
$userPrompt = "<__media__>Classify the forest organism. If uncertain or out of taxonomy, return {`"label_id`":`"unknown`"}."

$started = Get-Date
Write-Host "profile=$Profile"
Write-Host "model=$ModelPath"
Write-Host "projector=$ProjectorPath"
Write-Host "image=$ImagePath"
Write-Host "gpu_layers=$gpuLayers image_tokens=$ImageTokens predict=$Predict"

& $cli `
    -m $ModelPath `
    --mmproj $ProjectorPath `
    --image $ImagePath `
    -sys $systemPrompt `
    -p $userPrompt `
    -n $Predict `
    --temp 0 `
    --image-min-tokens $ImageTokens `
    --image-max-tokens $ImageTokens `
    @deviceArgs

$elapsed = (Get-Date) - $started
Write-Host "elapsed_seconds=$([Math]::Round($elapsed.TotalSeconds, 3))"
