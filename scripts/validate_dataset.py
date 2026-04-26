from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common import load_species_manifest, read_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate NaturaVision split metadata and final JSONL outputs.")
    parser.add_argument("--manifest", type=Path, required=True, help="Species manifest CSV")
    parser.add_argument("--attribution-csv", type=Path, required=True, help="Attribution CSV from build_inat_subset.py")
    parser.add_argument("--splits-dir", type=Path, default=Path("data/splits"), help="Directory with *_records.jsonl")
    parser.add_argument("--qwen-dir", type=Path, default=Path("data"), help="Directory with final train/val/test JSONL")
    parser.add_argument("--train-per-target", type=int, default=300)
    parser.add_argument("--val-per-target", type=int, default=50)
    parser.add_argument("--test-per-target", type=int, default=50)
    parser.add_argument("--unknown-train", type=int, default=2000)
    parser.add_argument("--unknown-val", type=int, default=400)
    parser.add_argument("--unknown-test", type=int, default=400)
    return parser.parse_args()


def load_attribution_index(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["photo_id"] for row in reader}


def expected_count(label_id: str, split_name: str, args: argparse.Namespace) -> int:
    if label_id == "unknown":
        return {"train": args.unknown_train, "val": args.unknown_val, "test": args.unknown_test}[split_name]
    return {"train": args.train_per_target, "val": args.val_per_target, "test": args.test_per_target}[split_name]


def validate_split_metadata(args: argparse.Namespace) -> None:
    entries = load_species_manifest(args.manifest)
    valid_labels = {entry.label_id for entry in entries} | {"unknown"}
    attribution_ids = load_attribution_index(args.attribution_csv)
    seen_observations: dict[str, str] = {}

    for split_name in ("train", "val", "test"):
        counts = Counter()
        split_path = args.splits_dir / f"{split_name}_records.jsonl"
        for row in read_jsonl(split_path):
            label_id = str(row["label_id"])
            if label_id not in valid_labels:
                raise ValueError(f"{split_path} references unknown label_id: {label_id}")

            image_path = Path(str(row["image_path"]))
            if not image_path.exists():
                raise FileNotFoundError(f"{split_path} references a missing image: {image_path}")

            photo_id = str(row["photo_id"])
            if photo_id not in attribution_ids:
                raise ValueError(f"{split_path} references photo_id {photo_id} missing from attribution.csv")

            observation_id = str(row["observation_id"])
            previous_split = seen_observations.get(observation_id)
            if previous_split is not None and previous_split != split_name:
                raise ValueError(
                    f"Observation {observation_id} appears in more than one split: {previous_split}, {split_name}"
                )
            seen_observations[observation_id] = split_name
            counts[label_id] += 1

        for entry in entries:
            expected = expected_count(entry.label_id, split_name, args)
            actual = counts[entry.label_id]
            if actual != expected:
                raise ValueError(f"{split_name} count mismatch for {entry.label_id}: expected {expected}, found {actual}")
        expected_unknown = expected_count("unknown", split_name, args)
        if counts["unknown"] != expected_unknown:
            raise ValueError(
                f"{split_name} count mismatch for unknown: expected {expected_unknown}, found {counts['unknown']}"
            )


def validate_final_jsonl(args: argparse.Namespace) -> None:
    for split_name in ("train", "val", "test"):
        final_path = args.qwen_dir / f"{split_name}.jsonl"
        count = 0
        for row in read_jsonl(final_path):
            if "messages" not in row or "images" not in row:
                raise ValueError(f"{final_path} contains a malformed example without messages/images")
            count += 1
        if count == 0:
            raise ValueError(f"{final_path} is empty")


def main() -> int:
    args = parse_args()
    validate_split_metadata(args)
    validate_final_jsonl(args)
    print("Dataset validation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
