from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common import (
    HARD_NEGATIVE_PAIRS,
    INTERNAL_UNKNOWN_LABELS,
    classify_unknown_subclass,
    ensure_parent,
    load_species_manifest,
    public_label_id,
    training_label_catalog,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create balanced NaturaVision split manifests.")
    parser.add_argument("--records-csv", type=Path, required=True, help="CSV emitted by build_inat_subset.py")
    parser.add_argument("--manifest", type=Path, required=True, help="Species manifest CSV")
    parser.add_argument("--output-dir", type=Path, default=Path("data/splits"), help="Split metadata directory")
    parser.add_argument("--labels-out", type=Path, default=Path("data/labels.json"), help="Label catalog path")
    parser.add_argument("--seed", type=int, default=23, help="Random seed")
    parser.add_argument("--train-per-target", type=int, default=300, help="Train examples per known label")
    parser.add_argument("--val-per-target", type=int, default=50, help="Validation examples per known label")
    parser.add_argument("--test-per-target", type=int, default=50, help="Test examples per known label")
    parser.add_argument("--dev-per-target", type=int, default=10, help="Development examples per known label")
    parser.add_argument("--unknown-train", type=int, default=2000, help="Train unknown examples")
    parser.add_argument("--unknown-val", type=int, default=400, help="Validation unknown examples")
    parser.add_argument("--unknown-test", type=int, default=400, help="Test unknown examples")
    parser.add_argument("--unknown-dev", type=int, default=10, help="Development unknown examples")
    parser.add_argument(
        "--hard-negative-extra-per-label",
        type=int,
        default=60,
        help="How many extra train rows to duplicate for each hard-negative label.",
    )
    return parser.parse_args()


def load_records_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError(f"No records were found in {path}")
    return rows


def known_quotas(args: argparse.Namespace) -> dict[str, int]:
    return {
        "train": args.train_per_target,
        "val": args.val_per_target,
        "test": args.test_per_target,
        "dev": args.dev_per_target,
    }


def unknown_quotas(args: argparse.Namespace) -> dict[str, int]:
    return {
        "train": args.unknown_train,
        "val": args.unknown_val,
        "test": args.unknown_test,
        "dev": args.unknown_dev,
    }


def annotate_row(row: dict[str, str], label_id: str, split_name: str) -> dict[str, str]:
    annotated = dict(row)
    annotated["source_label_id"] = row["label_id"]
    annotated["label_id"] = label_id
    annotated["public_label_id"] = public_label_id(label_id)
    annotated["split"] = split_name
    return annotated


def proportional_allocation(capacities: dict[str, int], total_required: int) -> dict[str, int]:
    if total_required == 0:
        return {label_id: 0 for label_id in capacities}
    total_capacity = sum(capacities.values())
    if total_capacity < total_required:
        raise ValueError(f"Need {total_required} unknown rows, found only {total_capacity}")

    allocations = {label_id: int(total_required * capacity / total_capacity) for label_id, capacity in capacities.items()}
    remainder = total_required - sum(allocations.values())
    ranking = sorted(
        capacities.items(),
        key=lambda item: ((total_required * item[1] / total_capacity) - allocations[item[0]], item[1]),
        reverse=True,
    )
    for label_id, capacity in ranking:
        if remainder <= 0:
            break
        if allocations[label_id] < capacity:
            allocations[label_id] += 1
            remainder -= 1

    if remainder != 0:
        raise ValueError(f"Could not allocate the requested {total_required} rows across {capacities}")
    return allocations


def duplicate_hard_negative_rows(
    train_rows: list[dict[str, str]],
    extra_per_label: int,
    seed: int,
) -> list[dict[str, str]]:
    if extra_per_label <= 0:
        return train_rows

    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in train_rows:
        grouped[row["label_id"]].append(row)

    augmented = list(train_rows)
    hard_negative_labels = sorted({label_id for pair in HARD_NEGATIVE_PAIRS for label_id in pair})
    for label_id in hard_negative_labels:
        bucket = grouped.get(label_id, [])
        if not bucket:
            continue
        sample_size = min(extra_per_label, len(bucket))
        for row in rng.sample(bucket, sample_size):
            duplicated = dict(row)
            duplicated["repeat_reason"] = "hard_negative_oversample"
            augmented.append(duplicated)
    return augmented


def build_split_records(
    records: list[dict[str, str]],
    known_label_ids: list[str],
    known_split_quotas: dict[str, int],
    unknown_split_quotas: dict[str, int],
    seed: int,
    hard_negative_extra_per_label: int,
) -> dict[str, list[dict[str, str]]]:
    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in records:
        effective_label_id = row["label_id"]
        if effective_label_id == "unknown":
            effective_label_id = classify_unknown_subclass(row)
        grouped[effective_label_id].append(row)

    split_names = tuple(known_split_quotas.keys())
    split_records = {split_name: [] for split_name in split_names}
    shortages: list[str] = []

    for label_id in known_label_ids:
        quotas = known_split_quotas
        bucket = list(grouped.get(label_id, []))
        rng.shuffle(bucket)
        required = sum(quotas.values())
        if len(bucket) < required:
            shortages.append(f"{label_id} needs {required}, found {len(bucket)}")
            continue

        start = 0
        for split_name in split_names:
            count = quotas[split_name]
            slice_rows = bucket[start : start + count]
            for row in slice_rows:
                split_records[split_name].append(annotate_row(row, label_id, split_name))
            start += count

    unknown_buckets = {}
    for label_id in INTERNAL_UNKNOWN_LABELS:
        bucket = list(grouped.get(label_id, []))
        rng.shuffle(bucket)
        if bucket:
            unknown_buckets[label_id] = bucket

    if not unknown_buckets:
        shortages.append("No unknown rows were available for any internal UNK_* subclass")

    if unknown_buckets:
        for split_name in split_names:
            capacities = {label_id: len(rows) for label_id, rows in unknown_buckets.items()}
            allocations = proportional_allocation(capacities, unknown_split_quotas[split_name])
            for label_id, count in allocations.items():
                slice_rows = unknown_buckets[label_id][:count]
                unknown_buckets[label_id] = unknown_buckets[label_id][count:]
                for row in slice_rows:
                    split_records[split_name].append(annotate_row(row, label_id, split_name))

    if shortages:
        shortage_text = "; ".join(shortages)
        raise ValueError(f"Not enough data to build the requested splits: {shortage_text}")

    observation_to_split: dict[str, str] = {}
    for split_name, rows in split_records.items():
        for row in rows:
            observation_id = row["observation_id"]
            previous_split = observation_to_split.get(observation_id)
            if previous_split is not None and previous_split != split_name:
                raise ValueError(
                    f"Observation {observation_id} appears in multiple splits: {previous_split} and {split_name}"
                )
            observation_to_split[observation_id] = split_name

    split_records["train"] = duplicate_hard_negative_rows(
        split_records["train"],
        extra_per_label=hard_negative_extra_per_label,
        seed=seed,
    )
    return split_records


def write_labels(path: Path, manifest_path: Path) -> None:
    entries = load_species_manifest(manifest_path)
    known_labels = [entry.label_id for entry in entries]
    payload = {
        "supported_labels": known_labels + ["unknown"],
        "training_supported_labels": known_labels + list(INTERNAL_UNKNOWN_LABELS),
        "collapse_to_public": {label_id: "unknown" for label_id in INTERNAL_UNKNOWN_LABELS},
        "by_id": training_label_catalog(entries),
    }
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    args = parse_args()
    entries = load_species_manifest(args.manifest)
    records = load_records_csv(args.records_csv)
    split_records = build_split_records(
        records=records,
        known_label_ids=[entry.label_id for entry in entries],
        known_split_quotas=known_quotas(args),
        unknown_split_quotas=unknown_quotas(args),
        seed=args.seed,
        hard_negative_extra_per_label=args.hard_negative_extra_per_label,
    )

    for split_name, rows in split_records.items():
        output_path = args.output_dir / f"{split_name}_records.jsonl"
        write_jsonl(output_path, rows)
    write_labels(args.labels_out, args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
