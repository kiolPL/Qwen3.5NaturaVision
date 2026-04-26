#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
DATA_DIR="${DATA_DIR:-${HOME}/naturavision-data-v2-clean-r1}"
DATASET_SPLIT="${DATASET_SPLIT:-val}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-${HOME}/runs-v2-full-clean-r1/qwen35-qlora-forest/best}"
USE_ADAPTERS="${USE_ADAPTERS:-true}"
RESULT_PATH="${RESULT_PATH:-${HOME}/runs-v2-full-clean-r1/eval/${DATASET_SPLIT}_infer_results_nothink.jsonl}"
SUMMARY_PATH="${SUMMARY_PATH:-${REPO_DIR}/output/eval/v2_full_clean_r1_${DATASET_SPLIT}_summary_nothink.json}"
LOG_PATH="${LOG_PATH:-${REPO_DIR}/logs/v2_full_clean_r1_${DATASET_SPLIT}_eval_nothink.log}"
MAX_BATCH_SIZE="${MAX_BATCH_SIZE:-2}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-64}"
MAX_LENGTH="${MAX_LENGTH:-1280}"
MAX_PIXELS="${MAX_PIXELS:-150528}"

mkdir -p "$(dirname "$LOG_PATH")"
exec > >(tee -a "$LOG_PATH") 2>&1

cd "$REPO_DIR"
source .venv-train-wsl/bin/activate

echo "[$(date -Is)] Starting v2 full-clean-r1 generative $DATASET_SPLIT evaluation"
echo "Dataset: $DATA_DIR/$DATASET_SPLIT.jsonl"
echo "Use adapters: $USE_ADAPTERS"
echo "Checkpoint: $CHECKPOINT_DIR"
echo "Results: $RESULT_PATH"
echo "Summary: $SUMMARY_PATH"

adapter_args=()
if [[ "$USE_ADAPTERS" == "true" && -n "$CHECKPOINT_DIR" ]]; then
  adapter_args=(--adapters "$CHECKPOINT_DIR")
fi

swift infer \
  --model Qwen/Qwen3.5-4B \
  --use_hf true \
  --val_dataset "$DATA_DIR/$DATASET_SPLIT.jsonl" \
  --load_from_cache_file true \
  --torch_dtype bfloat16 \
  --quant_method bnb \
  --quant_bits 4 \
  --bnb_4bit_quant_type nf4 \
  --bnb_4bit_use_double_quant true \
  --bnb_4bit_compute_dtype bfloat16 \
  --infer_backend transformers \
  "${adapter_args[@]}" \
  --max_length "$MAX_LENGTH" \
  --max_pixels "$MAX_PIXELS" \
  --enable_thinking false \
  --max_new_tokens "$MAX_NEW_TOKENS" \
  --temperature 0 \
  --top_k 1 \
  --top_p 1 \
  --max_batch_size "$MAX_BATCH_SIZE" \
  --result_path "$RESULT_PATH"

python "${REPO_DIR}/scripts/evaluate_infer_results.py" \
  --results "$RESULT_PATH" \
  --labels-json "$DATA_DIR/labels.json" \
  --output "$SUMMARY_PATH"

echo "[$(date -Is)] Finished v2 full-clean-r1 generative $DATASET_SPLIT evaluation"
