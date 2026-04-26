# WSL2 RTX 4070 QLoRA Runbook

This runbook prepares a local `Qwen/Qwen3.5-4B` training path for a single `RTX 4070 12 GB` using `WSL2 + ms-swift + 4-bit bitsandbytes QLoRA`.

## Why this path

- The official `ms-swift` `Qwen3.5-4B` dense LoRA example uses `4 x 20 GiB`, so the existing full-precision recipe is not a fit for a single `4070 12 GB`.
- `ms-swift` already matches the current NaturaVision repo, which keeps the local path close to the cloud path.
- `QLoRA` with `bnb` 4-bit quantization is the lightest option that still keeps the `4B` model.
- The improved local recipe now also uses `flash_attn + padding_free + rsLoRA + LoRA+`, with an optional `Liger Kernel` smoke A/B.

References:
- [ms-swift Quick Start](https://swift.readthedocs.io/en/v3.5/GetStarted/Quick-start.html)
- [Qwen3.5 Best Practices](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3_5-Best-Practice.html)
- [ms-swift Command Line Parameters](https://swift.readthedocs.io/en/v4.0/Instruction/Command-line-parameters.html)

## 1. WSL requirements

Use:

- `WSL2`
- `Ubuntu 22.04`
- current NVIDIA Windows driver with WSL CUDA support

Inside WSL, confirm the GPU is visible:

```bash
nvidia-smi
```

## 2. Build the improved v2 dataset

From Windows, regenerate the local training dataset with the improved split policy:

```powershell
& ".\.venv-train\Scripts\python.exe" scripts\make_splits.py --records-csv data\records.csv --manifest data\species_manifest.csv --output-dir data\v2\splits --labels-out data\v2\labels.json
& ".\.venv-train\Scripts\python.exe" scripts\prepare_qwen_examples.py --splits-dir data\v2\splits --manifest data\species_manifest.csv --output-dir data\v2 --prompt-style strict_label_only_with_taxonomy --assistant-style label_only
```

This creates:

- `data/v2/train.jsonl`
- `data/v2/val.jsonl`
- `data/v2/test.jsonl`
- `data/v2/dev.jsonl`

Optional prompt-only A/B sets for the current checkpoint:

```powershell
& ".\.venv-train\Scripts\python.exe" scripts\make_prompt_ablation_sets.py --splits-dir data\splits --manifest data\species_manifest.csv --output-root data\ablations\current_checkpoint
```

## 3. Create a portable local dataset

From Windows, build a portable dataset bundle outside OneDrive:

```powershell
& ".\.venv-train\Scripts\python.exe" scripts\pack_portable_dataset.py --source-dir data\v2 --output-dir D:\NaturaVisionWSL\portable_dataset
```

Do not train from `C:` or `OneDrive`. Keep the copy step simple and move the dataset into the Linux filesystem:

```bash
mkdir -p ~/naturavision-data
cp -r /mnt/d/NaturaVisionWSL/portable_dataset/. ~/naturavision-data/
```

Rewrite image paths to absolute Linux paths:

```bash
python scripts/rewrite_qwen_image_paths.py \
  --dataset-dir /home/$USER/naturavision-data \
  --image-root /home/$USER/naturavision-data/images
```

## 4. Bootstrap the WSL environment

From the repo root inside WSL:

```bash
bash train/bootstrap_wsl_qlora.sh
source .venv-train-wsl/bin/activate
```

To also test the optional memory/speed pilot:

```bash
INSTALL_LIGER_KERNEL=1 bash train/bootstrap_wsl_qlora.sh
```

Preflight:

```bash
nvidia-smi
python - <<'PY'
import bitsandbytes as bnb
import torch
print("cuda", torch.cuda.is_available())
print("device", torch.cuda.get_device_name(0))
print("bnb", getattr(bnb, "__version__", "unknown"))
free, total = torch.cuda.mem_get_info()
print("free_gib", round(free / 1024**3, 2))
print("total_gib", round(total / 1024**3, 2))
import importlib.util
print("flash_attn", importlib.util.find_spec("flash_attn") is not None)
print("liger_kernel", importlib.util.find_spec("liger_kernel") is not None)
PY
```

Start a run only if at least `10.5 GiB` VRAM is free.

## 5. Smoke test

Create a small dataset:

```bash
python scripts/make_smoke_subset.py \
  --source-dir /home/$USER/naturavision-data \
  --output-dir /home/$USER/naturavision-data-smoke
```

Run the smoke test:

```bash
DATA_DIR=/home/$USER/naturavision-data-smoke \
OUTPUT_ROOT=/home/$USER/runs-smoke-wsl \
bash train/train_qwen35_4b_qlora_smoke_wsl.sh
```

Acceptance:

- both stages start and save checkpoints
- no `CUDA out of memory`
- validation step runs

Optional Liger smoke A/B:

```bash
DATA_DIR=/home/$USER/naturavision-data-smoke \
OUTPUT_ROOT=/home/$USER/runs-smoke-wsl-liger \
bash train/train_qwen35_4b_qlora_liger_smoke_wsl.sh
```

Only enable `USE_LIGER_KERNEL=true` in longer runs if the dedicated Liger smoke passes cleanly.

## 6. Canary run

After the smoke test succeeds, run a short `Stage 2` canary on the full dataset:

```bash
DATA_DIR=/home/$USER/naturavision-data \
OUTPUT_ROOT=/home/$USER/runs-canary-wsl \
bash train/train_qwen35_4b_qlora_canary_wsl.sh
```

Acceptance:

- `Stage 1` completes
- `Stage 2` survives `100-200` steps
- loss trends down

## 7. Full training

```bash
DATA_DIR=/home/$USER/naturavision-data \
OUTPUT_ROOT=/home/$USER/runs-wsl \
bash train/train_qwen35_4b_qlora_wsl.sh
```

Default local settings:

- `per_device_train_batch_size=1`
- `gradient_accumulation_steps=32`
- `max_pixels=200704`
- `max_length=768`
- `attn_impl=flash_attn`
- `padding_free=true`
- `use_rslora=true`
- `lorap_lr_ratio=16`
- `gradient_checkpointing=true`
- `vit_gradient_checkpointing=false`
- `dataloader_num_workers=4`
- `dataset_num_proc=4`

Checkpoint selection should now happen on generative metrics from `dev.jsonl`, not only on teacher-forced `eval_loss`.

## 8. OOM ladder

If the default profile still runs out of memory, retry with:

1. Smaller image budget:

```bash
OOM_PROFILE=oom1 bash train/train_qwen35_4b_qlora_wsl.sh
```

2. Smaller image budget plus shorter text length:

```bash
OOM_PROFILE=oom2 bash train/train_qwen35_4b_qlora_wsl.sh
```

3. Smaller image budget, shorter text length, and narrower LoRA target modules:

```bash
OOM_PROFILE=oom3 bash train/train_qwen35_4b_qlora_wsl.sh
```

Only if all three profiles fail should the local path switch to `Qwen/Qwen3.5-2B`.

## 9. What to keep

Keep these artifacts for the final project write-up and CV:

- the exact training script
- the runbook
- smoke and canary logs
- final checkpoints
- validation metrics
- generative dev-set metrics
- prompt-ablation results from `data/ablations/current_checkpoint`
- the note that the local training path used `WSL2 + RTX 4070 12 GB + 4-bit QLoRA`
