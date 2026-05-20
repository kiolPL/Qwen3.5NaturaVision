# NaturaVision

Local fine-tuning pipeline for a compact Qwen 3.5 vision-language model that identifies 40 common Polish and Central-European forest plants and mushrooms, plus an `unknown` fallback.

## Model target

- Base model: `Qwen/Qwen3.5-4B`
- Primary phone quant: `Q4_K_M`
- Higher-quality optional quant: `Q5_K_M`
- Fallback for tighter RAM budgets: rerun the same recipe with `MODEL_ID=Qwen/Qwen3.5-2B`, then export `Q4_K_M`

## What is included

- `data/species_manifest.csv`: fixed starter taxonomy for 20 plant taxa and 20 fungal taxa.
- `scripts/build_inat_subset.py`: builds a licensed iNaturalist subset, prioritizing Poland inside Europe.
- `scripts/make_splits.py`: creates balanced train/validation/test metadata splits.
- `scripts/prepare_qwen_examples.py`: converts split metadata into the official ms-swift multimodal JSONL format.
- `scripts/make_prompt_ablation_sets.py`: builds prompt-only A/B datasets for the current checkpoint.
- `scripts/validate_dataset.py`: checks labels, file existence, attribution coverage, duplicate observations, and class counts.
- `scripts/pack_portable_dataset.py`: copies the finished dataset into a portable cloud bundle and rewrites image paths.
- `scripts/rewrite_qwen_image_paths.py`: rewrites portable bundle image paths to a new absolute Linux root.
- `scripts/make_smoke_subset.py`: creates a small smoke-test dataset bundle before a full cloud run.
- `train/train_qwen35_4b_lora.sh`: two-stage LoRA recipe for `Qwen/Qwen3.5-4B`.
- `train/bootstrap_wsl_qlora.sh`: WSL2 bootstrap for local `RTX 4070 12 GB` QLoRA runs.
- `train/train_qwen35_4b_qlora_wsl.sh`: two-stage local `4-bit` QLoRA recipe for `Qwen/Qwen3.5-4B`.
- `train/train_qwen35_4b_qlora_smoke_wsl.sh`: short local smoke test before a full WSL run.
- `train/train_qwen35_4b_qlora_liger_smoke_wsl.sh`: optional Liger-kernel smoke A/B before enabling it in a longer run.
- `train/train_qwen35_4b_qlora_canary_wsl.sh`: local `Stage 2` canary run on the full dataset.
- `train/bootstrap_lambda.sh`: Linux bootstrap for a Lambda multi-GPU training box.
- `train/train_qwen35_4b_lora_lambda.sh`: conservative multi-GPU launcher for a `4x A100` Lambda run.
- `train/train_qwen35_4b_smoke_lambda.sh`: short end-to-end smoke test before the full cloud run.
- `train/export_gguf.sh`: merges LoRA weights and quantizes the merged checkpoint to GGUF.
- `desktop-app/`: Windows WPF desktop client for local GGUF inference through `llama-mtmd-cli.exe`.
- `docs/wsl_4070_qlora_runbook.md`: step-by-step local WSL2 runbook for `RTX 4070 12 GB`.
- `docs/lambda_a100_runbook.md`: step-by-step cloud runbook for the recommended Lambda setup.

## Setup

Install the data-prep dependency set with:

```bash
pip install -r requirements-data.txt
```

Install the training stack with:

```bash
pip install -r requirements-train.txt
```

For the local `WSL2 + RTX 4070 12 GB` path, use:

```bash
bash train/bootstrap_wsl_qlora.sh
```

## Quick desktop demo

The easiest way to run the finished project is the Windows desktop app in `desktop-app/`.

Requirements for the verified local setup:

- Windows 11 on x64,
- .NET 9 SDK,
- NVIDIA GPU with current drivers,
- CUDA-enabled `llama.cpp` build with `llama-mtmd-cli.exe`,
- exported NaturaVision GGUF model and multimodal projector.

The model weights are not stored in this Git repository. Download them from the project Hugging Face repository and place them in the default local folder, or choose different paths in the app under `Ustawienia`:

```powershell
hf download kiolPL/naturavision `
  forest-taxa-qwen35-4b-q4_k_m-fixed.gguf `
  forest-taxa-qwen35-4b-mmproj-f16.gguf `
  --local-dir D:\NaturaVisionPortable\wsl_recovery\gguf
```

The app defaults to these paths on the development workstation:

```text
C:\tmp\llama-b9245-bin-win-cuda-13.1-x64\llama-mtmd-cli.exe
D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q4_k_m-fixed.gguf
D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-mmproj-f16.gguf
D:\NaturaVisionPortable\portable_dataset\test.jsonl
```

Run the app from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop-app\run-desktop.ps1
```

In the UI:

- use `Wybierz` to load a JPG/PNG/WebP image,
- use `Zrzut ekranu` to capture an object from the screen through the Windows snipping overlay,
- use `Rozpoznaj` to run the local model,
- expand `Wynik` to see the predicted class, species photo, short Polish description and source link,
- expand `Katalog` to browse all supported taxa,
- expand `Ustawienia` only when changing runner/model/test paths.

### Snapdragon / Windows on Arm note

The WPF interface should run on a Windows on Arm laptop such as a Vivobook S15 with Snapdragon X Elite and 32 GB RAM, but the verified inference setup will not run there unchanged. The current runner path uses an x64 CUDA `llama.cpp` build for an NVIDIA RTX GPU. Snapdragon machines do not provide CUDA, so they need a separate Windows Arm64 `llama.cpp` build, ideally with CPU/OpenCL support for Adreno, and a separate performance smoke test. The 32 GB RAM budget is enough for the Q4 model files, but this is a porting target, not the default deployment path.

## Data flow

1. Download the iNaturalist open-data metadata snapshot from the official registry:
   [iNaturalist Licensed Observation Images](https://registry.opendata.aws/inaturalist-open-data/)
2. Extract the metadata files into `data/metadata/`
3. Build the curated image pool:

```bash
python scripts/build_inat_subset.py \
  --metadata-dir data/metadata \
  --species-manifest data/species_manifest.csv \
  --output-dir data
```

4. Create balanced splits:

```bash
python scripts/make_splits.py \
  --records-csv data/records.csv \
  --manifest data/species_manifest.csv \
  --output-dir data/splits \
  --labels-out data/labels.json
```

For the improved local-training path, also build the v2 splits with a `dev` set, internal `UNK_*` labels, and hard-negative oversampling:

```bash
python scripts/make_splits.py \
  --records-csv data/records.csv \
  --manifest data/species_manifest.csv \
  --output-dir data/v2/splits \
  --labels-out data/v2/labels.json
```

5. Convert the split records into ms-swift JSONL:

```bash
python scripts/prepare_qwen_examples.py \
  --splits-dir data/splits \
  --manifest data/species_manifest.csv \
  --output-dir data
```

For the improved v2 training target:

```bash
python scripts/prepare_qwen_examples.py \
  --splits-dir data/v2/splits \
  --manifest data/species_manifest.csv \
  --output-dir data/v2 \
  --prompt-style strict_label_only_with_taxonomy \
  --assistant-style label_only
```

For prompt-only A/B on the current checkpoint:

```bash
python scripts/make_prompt_ablation_sets.py \
  --splits-dir data/splits \
  --manifest data/species_manifest.csv \
  --output-root data/ablations/current_checkpoint
```

6. Validate the prepared dataset:

```bash
python scripts/validate_dataset.py \
  --manifest data/species_manifest.csv \
  --attribution-csv data/attribution.csv \
  --splits-dir data/splits \
  --qwen-dir data
```

7. Fine-tune and export:

```bash
bash train/train_qwen35_4b_lora.sh
bash train/export_gguf.sh
```

## Local WSL run

For the single-GPU local path, first create a portable dataset copy outside OneDrive, copy it into the WSL Linux filesystem, and rewrite image paths to the Linux root:

```powershell
& ".\.venv-train\Scripts\python.exe" scripts\pack_portable_dataset.py --source-dir data --output-dir D:\NaturaVisionWSL\portable_dataset
```

```bash
cp -r /mnt/d/NaturaVisionWSL/portable_dataset/. ~/naturavision-data/
python scripts/rewrite_qwen_image_paths.py \
  --dataset-dir /home/$USER/naturavision-data \
  --image-root /home/$USER/naturavision-data/images
python scripts/make_smoke_subset.py \
  --source-dir /home/$USER/naturavision-data \
  --output-dir /home/$USER/naturavision-data-smoke
bash train/train_qwen35_4b_qlora_smoke_wsl.sh
bash train/train_qwen35_4b_qlora_liger_smoke_wsl.sh
bash train/train_qwen35_4b_qlora_canary_wsl.sh
bash train/train_qwen35_4b_qlora_wsl.sh
```

Use the OOM ladder if the default profile is still too large:

```bash
OOM_PROFILE=oom1 bash train/train_qwen35_4b_qlora_wsl.sh
OOM_PROFILE=oom2 bash train/train_qwen35_4b_qlora_wsl.sh
OOM_PROFILE=oom3 bash train/train_qwen35_4b_qlora_wsl.sh
```

See `docs/wsl_4070_qlora_runbook.md` for the full step-by-step local flow.

## Cloud run

For the recommended luxury/reliable training path on `Lambda 4x A100 40 GB`, use:

```bash
python scripts/pack_portable_dataset.py --source-dir data --output-dir artifacts/portable_dataset
bash train/bootstrap_lambda.sh
bash train/train_qwen35_4b_smoke_lambda.sh
bash train/train_qwen35_4b_lora_lambda.sh
```

See `docs/lambda_a100_runbook.md` for the full step-by-step process, including upload, path rewriting, smoke testing, and budgeting.

## Android app

The repository now also includes a starter Android client in:

```text
android-app/
```

It is a Kotlin + Jetpack Compose application with:

- gallery and quick camera image input,
- a result screen for species predictions,
- a mock inference backend for UI work before the final checkpoint is ready,
- a dedicated `LocalModelRunner` interface where the on-device model can be plugged in later.

See:

- `android-app/README.md`

for the integration notes and the exact future hook point for the local model.

## Desktop app

The repository also includes a Windows desktop client in:

```text
desktop-app/
```

It is a WPF application that runs the exported GGUF model with `llama-mtmd-cli.exe`, supports native Windows screen snips as image input, shows the full supported taxonomy with cached Polish descriptions and images, maps generated `label_id` values back to species metadata, and includes a small test-suite button for quick smoke checks on `test.jsonl`. On the current workstation it defaults to the CUDA 13.1 `llama.cpp` build in `C:\tmp\llama-b9245-bin-win-cuda-13.1-x64` with `GPU layers = 99`.

Run it with:

```powershell
.\desktop-app\run-desktop.ps1
```

## Notes

- `scripts/build_inat_subset.py` accepts research-grade and verifiable observations after normalizing the snapshot quality fields.
- Poland is prioritized before the rest of Europe, but the script still fills shortages from the wider European pool.
- The shell training script keeps the base model configurable through `MODEL_ID`, so you can rerun the same recipe for `Qwen/Qwen3.5-2B` if you decide the real phone target is the 8 GB S23 Ultra variant.
- The local WSL recipe is designed for `RTX 4070 12 GB`, defaults to `flash_attn + padding_free + rsLoRA + LoRA+`, and checks for at least `10.5 GiB` free VRAM before training starts.
- `data/v2/` contains the improved local-training target: minimal `label_id` JSON, internal `UNK_*` subclasses, hard-negative oversampling, and a small `dev.jsonl` for generation-first checkpoint selection.
- The GGUF export script assumes a `llama.cpp` checkout is available locally. Some multimodal-capable revisions may emit an additional projector GGUF alongside the main model GGUF; keep that artifact with the quantized model if it appears.
