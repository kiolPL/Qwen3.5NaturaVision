#!/usr/bin/env bash
set -euo pipefail

SWIFT_CMD="${SWIFT_CMD:-swift}"
PYTHON_BIN="${PYTHON_BIN:-python}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-$HOME/src/llama.cpp}"
OUTPUT_ROOT="${OUTPUT_ROOT:-runs}"
STAGE2_DIR="${STAGE2_DIR:-${OUTPUT_ROOT}/qwen35-forest}"
MERGED_DIR="${MERGED_DIR:-artifacts/merged/qwen35-4b-forest}"
GGUF_DIR="${GGUF_DIR:-artifacts/gguf}"
MODEL_SLUG="${MODEL_SLUG:-forest-taxa-qwen35-4b}"
FALLBACK_2B_MERGED_DIR="${FALLBACK_2B_MERGED_DIR:-}"

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

require_executable() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    echo "Required executable not found or not executable: $path" >&2
    exit 1
  fi
}

quantize_model() {
  local merged_dir="$1"
  local model_slug="$2"
  local output_dir="$3"
  local f16_path="${output_dir}/${model_slug}-f16.gguf"
  local q4_path="${output_dir}/${model_slug}-q4_k_m.gguf"
  local q5_path="${output_dir}/${model_slug}-q5_k_m.gguf"

  mkdir -p "$output_dir"
  "$PYTHON_BIN" "${LLAMA_CPP_DIR}/convert_hf_to_gguf.py" "$merged_dir" --outtype f16 --outfile "$f16_path"
  "${LLAMA_CPP_DIR}/build/bin/llama-quantize" "$f16_path" "$q4_path" Q4_K_M
  "${LLAMA_CPP_DIR}/build/bin/llama-quantize" "$f16_path" "$q5_path" Q5_K_M

  local projector
  projector="$(find "$output_dir" "$merged_dir" -maxdepth 2 -type f -name '*mmproj*.gguf' 2>/dev/null | head -n 1 || true)"
  if [[ -n "$projector" && "$projector" != "${output_dir}/${model_slug}-mmproj.gguf" ]]; then
    cp "$projector" "${output_dir}/${model_slug}-mmproj.gguf"
  fi
}

mkdir -p "$MERGED_DIR" "$GGUF_DIR"
require_executable "${LLAMA_CPP_DIR}/build/bin/llama-quantize"

CHECKPOINT_DIR="$(latest_checkpoint "$STAGE2_DIR")"

"$SWIFT_CMD" export \
  --adapters "$CHECKPOINT_DIR" \
  --merge_lora true \
  --use_hf true \
  --output_dir "$MERGED_DIR"

quantize_model "$MERGED_DIR" "$MODEL_SLUG" "$GGUF_DIR"

if [[ -n "$FALLBACK_2B_MERGED_DIR" ]]; then
  quantize_model "$FALLBACK_2B_MERGED_DIR" "forest-taxa-qwen35-2b" "$GGUF_DIR"
fi

echo "GGUF export complete in $GGUF_DIR"
