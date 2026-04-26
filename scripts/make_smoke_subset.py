from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a small smoke-test NaturaVision dataset bundle.")
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory with train/val/test JSONL files.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Smoke dataset output directory.")
    parser.add_argument("--train-count", type=int, default=128, help="Number of training examples.")
    parser.add_argument("--val-count", type=int, default=32, help="Number of validation examples.")
    parser.add_argument("--test-count", type=int, default=32, help="Number of test examples.")
    parser.add_argument("--dev-count", type=int, default=16, help="Number of development examples.")
    return parser.parse_args()


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def limited_rows(path: Path, limit: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in read_jsonl(path):
        rows.append(row)
        if len(rows) >= limit:
            break
    if len(rows) < limit:
        raise ValueError(f"Requested {limit} rows from {path}, found only {len(rows)}")
    return rows


def copy_metadata_files(source_dir: Path, output_dir: Path) -> None:
    for name in ("labels.json", "species_manifest.csv", "attribution.csv", "records.csv"):
        source = source_dir / name
        if source.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output_dir / name)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    copy_metadata_files(args.source_dir, args.output_dir)

    quotas = {"train": args.train_count, "val": args.val_count, "test": args.test_count}
    if (args.source_dir / "dev.jsonl").exists() and args.dev_count > 0:
        quotas["dev"] = args.dev_count
    for split_name, count in quotas.items():
        rows = limited_rows(args.source_dir / f"{split_name}.jsonl", count)
        write_jsonl(args.output_dir / f"{split_name}.jsonl", rows)
        print(f"Wrote {len(rows)} rows to {args.output_dir / f'{split_name}.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
