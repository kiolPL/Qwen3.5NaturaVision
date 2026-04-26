#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-Qwen/Qwen3.5-4B}"
SWIFT_CMD="${SWIFT_CMD:-swift}"
DATA_DIR="${DATA_DIR:-data}"
TRAIN_FILE="${TRAIN_FILE:-${DATA_DIR}/train.jsonl}"
VAL_FILE="${VAL_FILE:-${DATA_DIR}/val.jsonl}"
OUTPUT_ROOT="${OUTPUT_ROOT:-runs-lambda}"
STAGE1_DIR="${STAGE1_DIR:-${OUTPUT_ROOT}/qwen35-aligner}"
STAGE2_DIR="${STAGE2_DIR:-${OUTPUT_ROOT}/qwen35-forest}"
MAX_PIXELS="${MAX_PIXELS:-1003520}"
MAX_LENGTH="${MAX_LENGTH:-1024}"
VIDEO_MAX_PIXELS="${VIDEO_MAX_PIXELS:-50176}"
FPS_MAX_FRAMES="${FPS_MAX_FRAMES:-12}"
LORA_RANK="${LORA_RANK:-8}"
LORA_ALPHA="${LORA_ALPHA:-32}"
TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-1}"
EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-1}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-4}"
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
NPROC_PER_NODE="${NPROC_PER_NODE:-4}"
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"
DEEPSPEED_STAGE="${DEEPSPEED_STAGE:-zero2}"
DATASET_NUM_PROC="${DATASET_NUM_PROC:-8}"
DATALOADER_NUM_WORKERS="${DATALOADER_NUM_WORKERS:-8}"
WARMUP_RATIO="${WARMUP_RATIO:-0.05}"
STAGE1_MAX_STEPS="${STAGE1_MAX_STEPS:--1}"
STAGE2_MAX_STEPS="${STAGE2_MAX_STEPS:--1}"
PYTORCH_CUDA_ALLOC_CONF_VALUE="${PYTORCH_CUDA_ALLOC_CONF_VALUE:-expandable_segments:True}"

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

run_stage() {
  local output_dir="$1"
  shift
  PYTORCH_CUDA_ALLOC_CONF="$PYTORCH_CUDA_ALLOC_CONF_VALUE" \
  NPROC_PER_NODE="$NPROC_PER_NODE" \
  CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES" \
  VIDEO_MAX_PIXELS="$VIDEO_MAX_PIXELS" \
  FPS_MAX_FRAMES="$FPS_MAX_FRAMES" \
  "$SWIFT_CMD" sft \
    "${common_args[@]}" \
    --output_dir "$output_dir" \
    "$@"
}

require_file "$TRAIN_FILE"
require_file "$VAL_FILE"
mkdir -p "$STAGE1_DIR" "$STAGE2_DIR"

common_args=(
  --model "$MODEL_ID"
  --use_hf true
  --dataset "$TRAIN_FILE"
  --val_dataset "$VAL_FILE"
  --load_from_cache_file true
  --torch_dtype "$TORCH_DTYPE"
  --tuner_type lora
  --target_modules all-linear
  --lora_rank "$LORA_RANK"
  --lora_alpha "$LORA_ALPHA"
  --per_device_train_batch_size "$TRAIN_BATCH_SIZE"
  --per_device_eval_batch_size "$EVAL_BATCH_SIZE"
  --gradient_accumulation_steps "$GRAD_ACCUM_STEPS"
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
  --deepspeed "$DEEPSPEED_STAGE"
  --create_checkpoint_symlink true
)

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

echo "Starting Stage 1 on ${MODEL_ID} with ${NPROC_PER_NODE} GPUs..."
run_stage "$STAGE1_DIR" "${stage1_args[@]}"

STAGE1_CHECKPOINT="$(latest_checkpoint "$STAGE1_DIR")"

stage2_args=(
  --resume_from_checkpoint "$STAGE1_CHECKPOINT"
  --resume_only_model true
  --ignore_data_skip true
  --freeze_llm false
  --freeze_vit true
  --freeze_aligner false
  --learning_rate "$STAGE2_LR"
  --num_train_epochs "$STAGE2_EPOCHS"
)

if [[ "$STAGE2_MAX_STEPS" != "-1" ]]; then
  stage2_args+=( --max_steps "$STAGE2_MAX_STEPS" )
fi

echo "Starting Stage 2 from ${STAGE1_CHECKPOINT}..."
run_stage "$STAGE2_DIR" "${stage2_args[@]}"

echo "Training finished."
echo "Stage 1 checkpoint: $STAGE1_CHECKPOINT"
echo "Stage 2 checkpoint: $(latest_checkpoint "$STAGE2_DIR")"
