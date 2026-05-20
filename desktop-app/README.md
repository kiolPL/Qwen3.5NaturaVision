# NaturaVision Desktop

Windows desktop client for running the exported NaturaVision GGUF model through `llama-mtmd-cli.exe`.

## What it does

- selects a local JPG/PNG/WebP image,
- captures a rectangular screen snip through the native Windows screen clipping overlay,
- runs the local multimodal GGUF model and projector,
- parses the generated `label_id`,
- maps the label to the full species catalog from `data/v2/labels.json`,
- shows a short Wikipedia description and cached species image in the result panel,
- shows all supported plant and fungi classes with cached Polish descriptions and images,
- runs a small smoke-style test suite against `test.jsonl`.

## Default local paths

The app is prefilled for the current workstation layout:

- `C:\tmp\llama-b9245-bin-win-cuda-13.1-x64`
- `D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q4_k_m-fixed.gguf`
- `D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-mmproj-f16.gguf`
- `D:\NaturaVisionPortable\portable_dataset\test.jsonl`

The default llama.cpp path is the CUDA 13.1 Windows build and `GPU layers` defaults to `99` for RTX 4070 acceleration. Set `GPU layers` to `0` only when falling back to a CPU-only build.

The default inference profile uses `image tokens = 1024`, `ctx = 4096`, `flash-attn = on`, deterministic sampling, and a JSON schema file that restricts output to valid `label_id` values.

The current `Q4_K_M` GGUF is the verified desktop path. The available `F16` GGUF artifact currently fails to load in `llama.cpp` with a missing tensor error, so it should be re-exported before using it as the desktop default.

## Run

From the repository root:

```powershell
.\desktop-app\run-desktop.ps1
```

Or directly:

```powershell
dotnet run --project .\desktop-app\NaturaVision.Desktop\NaturaVision.Desktop.csproj
```

## First launch checklist

1. Install the .NET 9 SDK.
2. Download or build a multimodal `llama.cpp` package that contains `llama-mtmd-cli.exe`.
3. Download the NaturaVision GGUF model and projector from Hugging Face:

```powershell
hf download kiolPL/naturavision `
  forest-taxa-qwen35-4b-q4_k_m-fixed.gguf `
  forest-taxa-qwen35-4b-mmproj-f16.gguf `
  --local-dir D:\NaturaVisionPortable\wsl_recovery\gguf
```

4. Start the app:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop-app\run-desktop.ps1
```

5. If your paths differ from the defaults, expand `Ustawienia` and update:

- `Runner`: folder containing `llama-mtmd-cli.exe`,
- `Model`: quantized GGUF model,
- `Projektor`: multimodal projector GGUF,
- `Zestaw testowy`: optional `test.jsonl` used by the test-suite button.

6. Choose an image or use `Zrzut ekranu`, then click `Rozpoznaj`.

## Hardware notes

The verified setup is an x64 Windows PC with an NVIDIA RTX GPU and CUDA-enabled `llama.cpp`.

On Windows on Arm machines such as Snapdragon X Elite laptops, the WPF UI should be portable, but the model runner is not plug-and-play because the default `llama.cpp` binary is x64 CUDA. For that target, build or download a native Windows Arm64 `llama.cpp` binary with CPU/OpenCL support, point the app to that runner, and run a short smoke test before using the test suite.

## Refresh taxonomy media

Polish taxonomy descriptions are cached from Polish Wikipedia via the MediaWiki API. Images are cached from Wikimedia where available and filled from the local iNaturalist dataset when Wikimedia rate-limits image downloads.

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\download_taxonomy_media.ps1 -SkipImages -DelaySeconds 1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\fill_taxonomy_media_images_from_dataset.ps1
```
