$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $PSScriptRoot "NaturaVision.Desktop\NaturaVision.Desktop.csproj"

Set-Location $repoRoot
dotnet run --project $project
