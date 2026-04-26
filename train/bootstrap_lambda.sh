#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-train-linux}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip git build-essential
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install torch torchvision torchaudio --index-url "$TORCH_INDEX_URL"
python -m pip install -U ms-swift "transformers==5.2.*" "qwen_vl_utils>=0.0.14" peft accelerate datasets sentencepiece deepspeed

swift sft -h >/dev/null

python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0))
    free, total = torch.cuda.mem_get_info()
    print("free_gb", round(free / 1024**3, 2))
    print("total_gb", round(total / 1024**3, 2))
PY

echo "Lambda training environment is ready in ${VENV_DIR}."
