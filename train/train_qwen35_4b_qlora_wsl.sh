#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-Qwen/Qwen3.5-4B}"
SWIFT_CMD="${SWIFT_CMD:-swift}"
PYTHON_BIN="${PYTHON_BIN:-python}"
DATA_DIR="${DATA_DIR:-/home/${USER}/naturavision-data}"
TRAIN_FILE="${TRAIN_FILE:-${DATA_DIR}/train.jsonl}"
VAL_FILE="${VAL_FILE:-${DATA_DIR}/val.jsonl}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/home/${USER}/runs-wsl}"
STAGE1_DIR="${STAGE1_DIR:-${OUTPUT_ROOT}/qwen35-qlora-aligner}"
STAGE2_DIR="${STAGE2_DIR:-${OUTPUT_ROOT}/qwen35-qlora-forest}"
MAX_PIXELS="${MAX_PIXELS:-200704}"
MAX_LENGTH="${MAX_LENGTH:-768}"
ATTN_IMPL="${ATTN_IMPL:-flash_attn}"
PADDING_FREE="${PADDING_FREE:-true}"
TARGET_MODULES="${TARGET_MODULES:-all-linear}"
TARGET_REGEX="${TARGET_REGEX:-}"
LORA_RANK="${LORA_RANK:-8}"
LORA_ALPHA="${LORA_ALPHA:-32}"
USE_RSLORA="${USE_RSLORA:-true}"
LORAP_LR_RATIO="${LORAP_LR_RATIO:-16}"
USE_LIGER_KERNEL="${USE_LIGER_KERNEL:-false}"
TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-1}"
EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-1}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-32}"
EVAL_STEPS="${EVAL_STEPS:-100}"
SAVE_STEPS="${SAVE_STEPS:-100}"
SAVE_TOTAL_LIMIT="${SAVE_TOTAL_LIMIT:-2}"
LOGGING_STEPS="${LOGGING_STEPS:-5}"
STAGE1_EPOCHS="${STAGE1_EPOCHS:-1}"
STAGE2_EPOCHS="${STAGE2_EPOCHS:-2}"
STAGE1_LR="${STAGE1_LR:-5e-5}"
STAGE2_LR="${STAGE2_LR:-1e-4}"
TORCH_DTYPE="${TORCH_DTYPE:-bfloat16}"
SEED="${SEED:-23}"
QUANT_METHOD="${QUANT_METHOD:-bnb}"
QUANT_BITS="${QUANT_BITS:-4}"
BNB_4BIT_QUANT_TYPE="${BNB_4BIT_QUANT_TYPE:-nf4}"
BNB_4BIT_USE_DOUBLE_QUANT="${BNB_4BIT_USE_DOUBLE_QUANT:-true}"
BNB_4BIT_COMPUTE_DTYPE="${BNB_4BIT_COMPUTE_DTYPE:-bfloat16}"
GRADIENT_CHECKPOINTING="${GRADIENT_CHECKPOINTING:-true}"
VIT_GRADIENT_CHECKPOINTING="${VIT_GRADIENT_CHECKPOINTING:-false}"
DATASET_NUM_PROC="${DATASET_NUM_PROC:-4}"
DATALOADER_NUM_WORKERS="${DATALOADER_NUM_WORKERS:-4}"
WARMUP_RATIO="${WARMUP_RATIO:-0.05}"
STAGE1_MAX_STEPS="${STAGE1_MAX_STEPS:--1}"
STAGE2_MAX_STEPS="${STAGE2_MAX_STEPS:--1}"
MIN_FREE_VRAM_MIB="${MIN_FREE_VRAM_MIB:-10752}"
OOM_PROFILE="${OOM_PROFILE:-base}"
PYTORCH_CUDA_ALLOC_CONF_VALUE="${PYTORCH_CUDA_ALLOC_CONF_VALUE:-expandable_segments:True}"
HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Required file not found: $path" >&2
    exit 1
  fi
}

latest_checkpoint() {
  local root="$1"
  local latest=""
  if [[ -d "${root}/last" ]]; then
    latest="${root}/last"
  else
    latest="$(find "$root" -type d -name 'checkpoint-*' | sort -V | tail -n 1 || true)"
  fi
  if [[ -z "$latest" ]]; then
    echo "Could not find a checkpoint under $root" >&2
    exit 1
  fi
  printf '%s\n' "$latest"
}

checkpoint_global_step() {
  local checkpoint_dir="$1"
  local trainer_state="${checkpoint_dir}/trainer_state.json"
  if [[ ! -f "$trainer_state" ]]; then
    echo "Could not find trainer_state.json under $checkpoint_dir" >&2
    exit 1
  fi
  "$PYTHON_BIN" - "$trainer_state" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

print(int(data.get("global_step", 0)))
PY
}

as_positive_int() {
  local value="$1"
  if [[ "$value" =~ ^[0-9]+$ ]] && (( value > 0 )); then
    printf '%s\n' "$value"
  else
    echo "Expected a positive integer, got: $value" >&2
    exit 1
  fi
}

apply_oom_profile() {
  case "$OOM_PROFILE" in
    base)
      ;;
    oom1)
      MAX_PIXELS=150528
      ;;
    oom2)
      MAX_PIXELS=150528
      MAX_LENGTH=640
      ;;
    oom3)
      MAX_PIXELS=150528
      MAX_LENGTH=640
      TARGET_REGEX='^(language_model).*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$'
      ;;
    *)
      echo "Unsupported OOM_PROFILE: $OOM_PROFILE" >&2
      exit 1
      ;;
  esac
}

ensure_linux_environment() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This script must run inside WSL2 or Linux." >&2
    exit 1
  fi
  if [[ "$DATA_DIR" == /mnt/* ]]; then
    echo "DATA_DIR must live inside the Linux filesystem, not under /mnt/." >&2
    exit 1
  fi
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia-smi is required inside WSL2." >&2
    exit 1
  fi
  if ! command -v "$SWIFT_CMD" >/dev/null 2>&1; then
    echo "swift command not found. Activate the WSL training venv first." >&2
    exit 1
  fi
  if [[ "$PADDING_FREE" == "true" && "$ATTN_IMPL" != "flash_attn" ]]; then
    echo "padding_free requires ATTN_IMPL=flash_attn." >&2
    exit 1
  fi
}

check_python_stack() {
  ATTN_IMPL="$ATTN_IMPL" USE_LIGER_KERNEL="$USE_LIGER_KERNEL" "$PYTHON_BIN" - <<'PY'
import importlib.util
import os

import bitsandbytes as bnb
import torch

assert torch.cuda.is_available(), "CUDA is not available in this environment."
attn_impl = os.environ["ATTN_IMPL"]
use_liger = os.environ["USE_LIGER_KERNEL"].lower() == "true"
if attn_impl == "flash_attn":
    assert importlib.util.find_spec("flash_attn") is not None, "flash_attn is required for ATTN_IMPL=flash_attn."
if use_liger:
    assert importlib.util.find_spec("liger_kernel") is not None, "liger-kernel is required when USE_LIGER_KERNEL=true."
print("torch", torch.__version__)
print("bitsandbytes", getattr(bnb, "__version__", "unknown"))
print("device", torch.cuda.get_device_name(0))
print("attn_impl", attn_impl)
print("use_liger_kernel", use_liger)
PY
}

check_free_vram() {
  local free_mib
  free_mib="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -n 1 | tr -d '[:space:]')"
  if [[ -z "$free_mib" ]]; then
    echo "Could not read free VRAM from nvidia-smi." >&2
    exit 1
  fi
  if (( free_mib < MIN_FREE_VRAM_MIB )); then
    echo "Only ${free_mib} MiB free VRAM detected. Need at least ${MIN_FREE_VRAM_MIB} MiB before starting." >&2
    exit 1
  fi
  echo "Free VRAM before training: ${free_mib} MiB"
}

run_stage() {
  local output_dir="$1"
  shift
  HF_HUB_DISABLE_XET="$HF_HUB_DISABLE_XET" \
  PYTORCH_CUDA_ALLOC_CONF="$PYTORCH_CUDA_ALLOC_CONF_VALUE" \
  "$SWIFT_CMD" sft \
    "${common_args[@]}" \
    --output_dir "$output_dir" \
    "$@"
}

apply_oom_profile
ensure_linux_environment
require_file "$TRAIN_FILE"
require_file "$VAL_FILE"
check_python_stack
check_free_vram
mkdir -p "$STAGE1_DIR" "$STAGE2_DIR"

common_args=(
  --model "$MODEL_ID"
  --use_hf true
  --dataset "$TRAIN_FILE"
  --val_dataset "$VAL_FILE"
  --load_from_cache_file true
  --torch_dtype "$TORCH_DTYPE"
  --quant_method "$QUANT_METHOD"
  --quant_bits "$QUANT_BITS"
  --bnb_4bit_quant_type "$BNB_4BIT_QUANT_TYPE"
  --bnb_4bit_use_double_quant "$BNB_4BIT_USE_DOUBLE_QUANT"
  --bnb_4bit_compute_dtype "$BNB_4BIT_COMPUTE_DTYPE"
  --attn_impl "$ATTN_IMPL"
  --tuner_type lora
  --target_modules "$TARGET_MODULES"
  --lora_rank "$LORA_RANK"
  --lora_alpha "$LORA_ALPHA"
  --use_rslora "$USE_RSLORA"
  --lorap_lr_ratio "$LORAP_LR_RATIO"
  --use_liger_kernel "$USE_LIGER_KERNEL"
  --per_device_train_batch_size "$TRAIN_BATCH_SIZE"
  --per_device_eval_batch_size "$EVAL_BATCH_SIZE"
  --gradient_accumulation_steps "$GRAD_ACCUM_STEPS"
  --gradient_checkpointing "$GRADIENT_CHECKPOINTING"
  --vit_gradient_checkpointing "$VIT_GRADIENT_CHECKPOINTING"
  --max_length "$MAX_LENGTH"
  --max_pixels "$MAX_PIXELS"
  --add_non_thinking_prefix true
  --loss_scale ignore_empty_think
  --eval_steps "$EVAL_STEPS"
  --save_steps "$SAVE_STEPS"
  --save_total_limit "$SAVE_TOTAL_LIMIT"
  --logging_steps "$LOGGING_STEPS"
  --seed "$SEED"
  --warmup_ratio "$WARMUP_RATIO"
  --dataset_num_proc "$DATASET_NUM_PROC"
  --dataloader_num_workers "$DATALOADER_NUM_WORKERS"
  --group_by_length true
  --padding_free "$PADDING_FREE"
  --create_checkpoint_symlink true
)

if [[ -n "$TARGET_REGEX" ]]; then
  common_args+=( --target_regex "$TARGET_REGEX" )
fi

stage1_args=(
  --freeze_llm true
  --freeze_vit true
  --freeze_aligner false
  --learning_rate "$STAGE1_LR"
  --num_train_epochs "$STAGE1_EPOCHS"
)

if [[ "$STAGE1_MAX_STEPS" != "-1" ]]; then
  stage1_args+=( --max_steps "$STAGE1_MAX_STEPS" )
fi

echo "Starting Stage 1 on ${MODEL_ID} with OOM_PROFILE=${OOM_PROFILE}"
echo "Stage 1 target modules: ${TARGET_MODULES}"
if [[ -n "$TARGET_REGEX" ]]; then
  echo "Stage 1 target regex: ${TARGET_REGEX}"
fi
echo "Stage 1 max_pixels=${MAX_PIXELS} max_length=${MAX_LENGTH} attn_impl=${ATTN_IMPL} padding_free=${PADDING_FREE} use_rslora=${USE_RSLORA} lorap_lr_ratio=${LORAP_LR_RATIO} use_liger_kernel=${USE_LIGER_KERNEL}"
run_stage "$STAGE1_DIR" "${stage1_args[@]}"

STAGE1_CHECKPOINT="$(latest_checkpoint "$STAGE1_DIR")"
STAGE1_GLOBAL_STEP="$(checkpoint_global_step "$STAGE1_CHECKPOINT")"
STAGE1_EPOCHS_INT="$(as_positive_int "$STAGE1_EPOCHS")"
STAGE2_EPOCHS_INT="$(as_positive_int "$STAGE2_EPOCHS")"
STAGE2_TOTAL_EPOCHS=$(( STAGE1_EPOCHS_INT + STAGE2_EPOCHS_INT ))

stage2_args=(
  --resume_from_checkpoint "$STAGE1_CHECKPOINT"
  --resume_only_model true
  --ignore_data_skip true
  --freeze_llm false
  --freeze_vit true
  --freeze_aligner false
  --learning_rate "$STAGE2_LR"
  --num_train_epochs "$STAGE2_TOTAL_EPOCHS"
)

if [[ "$STAGE2_MAX_STEPS" != "-1" ]]; then
  STAGE2_EFFECTIVE_MAX_STEPS=$(( STAGE1_GLOBAL_STEP + STAGE2_MAX_STEPS ))
else
  STAGE1_STEPS_PER_EPOCH=$(( STAGE1_GLOBAL_STEP / STAGE1_EPOCHS_INT ))
  STAGE2_ADDITIONAL_STEPS=$(( STAGE1_STEPS_PER_EPOCH * STAGE2_EPOCHS_INT ))
  STAGE2_EFFECTIVE_MAX_STEPS=$(( STAGE1_GLOBAL_STEP + STAGE2_ADDITIONAL_STEPS ))
fi
stage2_args+=( --max_steps "$STAGE2_EFFECTIVE_MAX_STEPS" )

echo "Starting Stage 2 from ${STAGE1_CHECKPOINT}"
if [[ "$STAGE2_MAX_STEPS" != "-1" ]]; then
  echo "Stage 2 will run ${STAGE2_MAX_STEPS} additional steps (effective max_steps=${STAGE2_EFFECTIVE_MAX_STEPS})"
else
  echo "Stage 2 inferred ${STAGE2_ADDITIONAL_STEPS} additional steps from Stage 1 (effective max_steps=${STAGE2_EFFECTIVE_MAX_STEPS}, total epochs=${STAGE2_TOTAL_EPOCHS})"
fi
echo "Stage 2 max_pixels=${MAX_PIXELS} max_length=${MAX_LENGTH} attn_impl=${ATTN_IMPL} padding_free=${PADDING_FREE} use_rslora=${USE_RSLORA} lorap_lr_ratio=${LORAP_LR_RATIO} use_liger_kernel=${USE_LIGER_KERNEL}"
run_stage "$STAGE2_DIR" "${stage2_args[@]}"

echo "Training finished."
echo "Stage 1 checkpoint: $STAGE1_CHECKPOINT"
echo "Stage 2 checkpoint: $(latest_checkpoint "$STAGE2_DIR")"
