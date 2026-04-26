from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common import (
    ASSISTANT_STYLE_FULL_JSON,
    ASSISTANT_STYLE_LABEL_ONLY,
    INTERNAL_UNKNOWN_LABELS,
    PROMPT_STYLE_LEGACY_FULL_JSON,
    PROMPT_STYLE_STRICT_LABEL_ONLY,
    PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY,
    ensure_parent,
    label_catalog,
    load_species_manifest,
    training_label_catalog,
    write_jsonl,
)
from scripts.prepare_qwen_examples import prepare_examples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build prompt-only ablation datasets from NaturaVision split records.")
    parser.add_argument("--splits-dir", type=Path, required=True, help="Directory with *_records.jsonl files.")
    parser.add_argument("--manifest", type=Path, required=True, help="Species manifest CSV.")
    parser.add_argument("--output-root", type=Path, default=Path("data/ablations"), help="Output directory root.")
    parser.add_argument(
        "--include-internal-unknown",
        action="store_true",
        help="Include internal UNK_* labels in prompts and labels.json. Leave off for prompt-only A/B on old checkpoints.",
    )
    return parser.parse_args()


def write_labels(path: Path, manifest_path: Path, *, include_internal_unknown: bool) -> None:
    entries = load_species_manifest(manifest_path)
    known_labels = [entry.label_id for entry in entries]
    by_id = training_label_catalog(entries) if include_internal_unknown else label_catalog(entries)
    training_supported_labels = known_labels + list(INTERNAL_UNKNOWN_LABELS) if include_internal_unknown else known_labels + ["unknown"]
    collapse_to_public = {label_id: "unknown" for label_id in INTERNAL_UNKNOWN_LABELS} if include_internal_unknown else {}
    payload = {
        "supported_labels": known_labels + ["unknown"],
        "training_supported_labels": training_supported_labels,
        "collapse_to_public": collapse_to_public,
        "by_id": by_id,
    }
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    entries = load_species_manifest(args.manifest)
    catalog = training_label_catalog(entries) if args.include_internal_unknown else label_catalog(entries)
    variants = {
        "legacy_full_json": (PROMPT_STYLE_LEGACY_FULL_JSON, ASSISTANT_STYLE_FULL_JSON),
        "strict_label_only": (PROMPT_STYLE_STRICT_LABEL_ONLY, ASSISTANT_STYLE_LABEL_ONLY),
        "strict_label_only_with_taxonomy": (
            PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY,
            ASSISTANT_STYLE_LABEL_ONLY,
        ),
    }

    for variant_name, (prompt_style, assistant_style) in variants.items():
        variant_dir = args.output_root / variant_name
        variant_dir.mkdir(parents=True, exist_ok=True)
        write_labels(variant_dir / "labels.json", args.manifest, include_internal_unknown=args.include_internal_unknown)
        for split_name in ("train", "val", "test", "dev"):
            split_path = args.splits_dir / f"{split_name}_records.jsonl"
            if not split_path.exists():
                continue
            examples = prepare_examples(
                split_path,
                catalog,
                prompt_style=prompt_style,
                assistant_style=assistant_style,
                collapse_internal_unknown=not args.include_internal_unknown,
            )
            write_jsonl(variant_dir / f"{split_name}.jsonl", examples)
            print(f"Wrote {variant_dir / f'{split_name}.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
