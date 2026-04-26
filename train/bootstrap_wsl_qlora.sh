#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-train-wsl}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"
APT_PACKAGES="${APT_PACKAGES:-python3 python3-venv python3-pip git build-essential}"
INSTALL_FLASH_ATTN="${INSTALL_FLASH_ATTN:-1}"
INSTALL_LIGER_KERNEL="${INSTALL_LIGER_KERNEL:-0}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This bootstrap script must run inside WSL2 or Linux." >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y $APT_PACKAGES
  PYTHON_BIN="python3"
fi

TMP_VENV_CHECK_DIR="$(mktemp -d)"
if ! "$PYTHON_BIN" -m venv "${TMP_VENV_CHECK_DIR}/check" >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3-venv python3.10-venv python3-pip
fi
rm -rf "$TMP_VENV_CHECK_DIR"

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install torch torchvision torchaudio --index-url "$TORCH_INDEX_URL"
python -m pip install -r requirements-train.txt
python -m pip install packaging ninja
if [[ "$INSTALL_FLASH_ATTN" == "1" ]]; then
  python -m pip install flash-attn --no-build-isolation
fi
if [[ "$INSTALL_LIGER_KERNEL" == "1" ]]; then
  python -m pip install liger-kernel
fi

swift sft -h >/dev/null

python - <<'PY'
import importlib.util
import bitsandbytes as bnb
import torch

print("torch", torch.__version__)
print("cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0))
    free, total = torch.cuda.mem_get_info()
    print("free_gb", round(free / 1024**3, 2))
    print("total_gb", round(total / 1024**3, 2))
print("bitsandbytes", getattr(bnb, "__version__", "unknown"))
print("flash_attn", importlib.util.find_spec("flash_attn") is not None)
print("liger_kernel", importlib.util.find_spec("liger_kernel") is not None)
PY

echo "WSL QLoRA environment is ready in ${VENV_DIR}."
