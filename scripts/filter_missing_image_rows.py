from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter JSONL dataset rows that reference missing image files.")
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory containing train/val/test[/dev].jsonl.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where the filtered dataset will be written.")
    parser.add_argument(
        "--splits",
        nargs="*",
        default=("train", "val", "test", "dev"),
        help="Split names to process. Missing split files are skipped.",
    )
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


def row_has_all_images(row: dict[str, object]) -> bool:
    return all(Path(str(image_path)).exists() for image_path in row.get("images", []))


def copy_supporting_files(source_dir: Path, output_dir: Path) -> None:
    for name in ("labels.json", "species_manifest.csv", "attribution.csv", "records.csv"):
        source = source_dir / name
        if source.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output_dir / name)
    splits_dir = source_dir / "splits"
    if splits_dir.exists():
        target = output_dir / "splits"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(splits_dir, target)


def filter_split(source_path: Path, output_path: Path) -> tuple[int, int]:
    kept_rows: list[dict[str, object]] = []
    total = 0
    for row in read_jsonl(source_path):
        total += 1
        if row_has_all_images(row):
            kept_rows.append(row)
    write_jsonl(output_path, kept_rows)
    return total, len(kept_rows)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    copy_supporting_files(args.source_dir, args.output_dir)

    for split_name in args.splits:
        source_path = args.source_dir / f"{split_name}.jsonl"
        if not source_path.exists():
            continue
        output_path = args.output_dir / f"{split_name}.jsonl"
        total, kept = filter_split(source_path, output_path)
        removed = total - kept
        print(f"{split_name}: kept={kept} removed={removed} total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
