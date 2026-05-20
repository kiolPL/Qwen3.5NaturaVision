from __future__ import annotations

import argparse
import importlib.metadata as importlib_metadata
import shutil
import sys
from pathlib import Path


DEFAULT_TRANSFORMERS_SRC = Path(r"C:\tmp\transformers-main\src")
DEFAULT_HF_HUB_SRC = Path(r"C:\tmp\huggingface-hub-main\src")
DEFAULT_BASE_MODEL = Path(r"D:\NaturaVisionPortable\wsl_recovery\qwen35_4b_snapshot")
DEFAULT_ADAPTER = Path(
    r"D:\NaturaVisionPortable\wsl_recovery\home\kiol\runs-v2-full-clean-r1"
    r"\qwen35-qlora-forest\v0-20260424-170332\checkpoint-1359"
)
DEFAULT_OUTPUT = Path(r"D:\NaturaVisionPortable\wsl_recovery\merged_qwen35_4b_naturavision")
PROCESSOR_FALLBACK_FILES = (
    ".gitattributes",
    "chat_template.jinja",
    "LICENSE",
    "merges.txt",
    "preprocessor_config.json",
    "README.md",
    "tokenizer.json",
    "tokenizer_config.json",
    "video_preprocessor_config.json",
    "vocab.json",
)


def add_local_source_overrides(transformers_src: Path, hf_hub_src: Path) -> None:
    if hf_hub_src.exists():
        sys.path.insert(0, str(hf_hub_src))
    if transformers_src.exists():
        sys.path.insert(0, str(transformers_src))

    # The embedded Python has an older installed huggingface_hub distribution.
    # Source imports work, but Transformers checks package metadata before import.
    real_version = importlib_metadata.version

    def patched_version(name: str) -> str:
        if name in {"huggingface-hub", "huggingface_hub"} and hf_hub_src.exists():
            return "1.5.0"
        return real_version(name)

    importlib_metadata.version = patched_version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge the NaturaVision Qwen3.5 PEFT adapter into the base model.")
    parser.add_argument("--base-model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--transformers-src", type=Path, default=DEFAULT_TRANSFORMERS_SRC)
    parser.add_argument("--hf-hub-src", type=Path, default=DEFAULT_HF_HUB_SRC)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def copy_processor_fallback(base_model: Path, output: Path) -> None:
    for file_name in PROCESSOR_FALLBACK_FILES:
        source = base_model / file_name
        if source.exists():
            shutil.copy2(source, output / file_name)


def main() -> None:
    args = parse_args()
    add_local_source_overrides(args.transformers_src, args.hf_hub_src)

    import torch
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoProcessor

    if not args.base_model.exists():
        raise FileNotFoundError(f"Base model folder does not exist: {args.base_model}")
    if not args.adapter.exists():
        raise FileNotFoundError(f"Adapter folder does not exist: {args.adapter}")
    if args.output.exists() and args.overwrite:
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Loading base model from: {args.base_model}", flush=True)
    base_model = AutoModelForImageTextToText.from_pretrained(
        args.base_model,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        local_files_only=True,
        trust_remote_code=True,
    )

    print(f"Loading adapter from: {args.adapter}", flush=True)
    peft_model = PeftModel.from_pretrained(base_model, args.adapter, local_files_only=True)

    print("Merging adapter into base model...", flush=True)
    merged_model = peft_model.merge_and_unload()

    print(f"Saving merged model to: {args.output}", flush=True)
    merged_model.save_pretrained(args.output, safe_serialization=True, max_shard_size="5GB")

    print("Saving processor/tokenizer files...", flush=True)
    try:
        processor = AutoProcessor.from_pretrained(
            args.base_model,
            local_files_only=True,
            trust_remote_code=True,
        )
        processor.save_pretrained(args.output)
    except ImportError as exc:
        print(f"AutoProcessor unavailable ({exc}). Copying processor files directly.", flush=True)
        copy_processor_fallback(args.base_model, args.output)

    print("Merge complete.", flush=True)


if __name__ == "__main__":
    main()
