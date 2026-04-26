from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common import (
    ASSISTANT_STYLE_FULL_JSON,
    PROMPT_STYLE_LEGACY_FULL_JSON,
    SUPPORTED_ASSISTANT_STYLES,
    SUPPORTED_PROMPT_STYLES,
    build_training_example_from_label,
    load_species_manifest,
    read_jsonl,
    training_label_catalog,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert split metadata into ms-swift multimodal JSONL.")
    parser.add_argument("--splits-dir", type=Path, default=Path("data/splits"), help="Directory with *_records.jsonl")
    parser.add_argument("--manifest", type=Path, required=True, help="Species manifest CSV")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Directory for final train/val/test JSONL")
    parser.add_argument(
        "--prompt-style",
        choices=SUPPORTED_PROMPT_STYLES,
        default=PROMPT_STYLE_LEGACY_FULL_JSON,
        help="Conversation template style to emit.",
    )
    parser.add_argument(
        "--assistant-style",
        choices=SUPPORTED_ASSISTANT_STYLES,
        default=ASSISTANT_STYLE_FULL_JSON,
        help="Assistant payload style to emit.",
    )
    parser.add_argument(
        "--collapse-internal-unknown",
        action="store_true",
        help="Collapse internal UNK_* labels back to public unknown in assistant responses.",
    )
    return parser.parse_args()


def prepare_examples(
    split_path: Path,
    catalog: dict[str, dict[str, str]],
    *,
    prompt_style: str,
    assistant_style: str,
    collapse_internal_unknown: bool,
) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    for row in read_jsonl(split_path):
        image_path = Path(str(row["image_path"]))
        if not image_path.exists():
            raise FileNotFoundError(f"Image path referenced by {split_path} does not exist: {image_path}")
        label_id = str(row["label_id"])
        examples.append(
            build_training_example_from_label(
                image_path=image_path,
                label_id=label_id,
                catalog=catalog,
                prompt_style=prompt_style,
                assistant_style=assistant_style,
                collapse_internal_unknown=collapse_internal_unknown,
            )
        )
    return examples


def main() -> int:
    args = parse_args()
    entries = load_species_manifest(args.manifest)
    catalog = training_label_catalog(entries)

    for split_name in ("train", "val", "test", "dev"):
        split_path = args.splits_dir / f"{split_name}_records.jsonl"
        if not split_path.exists():
            continue
        examples = prepare_examples(
            split_path,
            catalog,
            prompt_style=args.prompt_style,
            assistant_style=args.assistant_style,
            collapse_internal_unknown=args.collapse_internal_unknown,
        )
        write_jsonl(args.output_dir / f"{split_name}.jsonl", examples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
