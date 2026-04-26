#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/${USER}/Project-NaturaVision-wsl}"
VENV_DIR="${VENV_DIR:-${REPO_DIR}/.venv-train-wsl}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Virtual environment not found: ${VENV_DIR}" >&2
  exit 1
fi

cd "${REPO_DIR}"
. "${VENV_DIR}/bin/activate"

export OUTPUT_ROOT="${OUTPUT_ROOT:-/home/${USER}/runs-v2-full-r3}"
export DATA_DIR="${DATA_DIR:-/home/${USER}/naturavision-data-v2-r1}"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
export ATTN_IMPL="${ATTN_IMPL:-sdpa}"
export PADDING_FREE="${PADDING_FREE:-false}"
export USE_LIGER_KERNEL="${USE_LIGER_KERNEL:-false}"
export USE_RSLORA="${USE_RSLORA:-true}"
export LORAP_LR_RATIO="${LORAP_LR_RATIO:-16}"
export MIN_FREE_VRAM_MIB="${MIN_FREE_VRAM_MIB:-9000}"
export EVAL_STEPS="${EVAL_STEPS:-200}"
export SAVE_STEPS="${SAVE_STEPS:-200}"
export STAGE2_EPOCHS="${STAGE2_EPOCHS:-2}"

bash train/train_qwen35_4b_qlora_wsl.sh
