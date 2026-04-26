from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy NaturaVision training data into a portable bundle.")
    parser.add_argument("--source-dir", type=Path, default=Path("data"), help="Directory with train/val/test JSONL files.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/portable_dataset"),
        help="Portable dataset bundle directory.",
    )
    parser.add_argument(
        "--image-prefix",
        type=str,
        default="",
        help="Optional image path prefix to write into the JSONL files. Defaults to relative images/... paths.",
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


def portable_image_path(output_dir: Path, source_image: Path) -> tuple[Path, str]:
    label_id = source_image.parent.name or "misc"
    destination = output_dir / "images" / label_id / source_image.name
    relative = destination.relative_to(output_dir).as_posix()
    return destination, relative


def final_image_reference(relative_path: str, image_prefix: str) -> str:
    if not image_prefix:
        return relative_path
    prefix = image_prefix.rstrip("/\\")
    return f"{prefix}/{relative_path}".replace("\\", "/")


def copy_supporting_files(source_dir: Path, output_dir: Path) -> None:
    for name in ("labels.json", "species_manifest.csv", "attribution.csv", "records.csv"):
        source = source_dir / name
        if not source.exists() and source_dir.parent.exists():
            parent_candidate = source_dir.parent / name
            if parent_candidate.exists():
                source = parent_candidate
        if source.exists():
            destination = output_dir / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def copy_split_metadata(source_dir: Path, output_dir: Path) -> None:
    source_splits = source_dir / "splits"
    if not source_splits.exists():
        return
    destination_splits = output_dir / "splits"
    destination_splits.mkdir(parents=True, exist_ok=True)
    for source in source_splits.glob("*_records.jsonl"):
        shutil.copy2(source, destination_splits / source.name)


def copy_image_if_needed(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    shutil.copy2(source, destination)


def rewrite_qwen_split(source_path: Path, output_dir: Path, image_prefix: str) -> int:
    rewritten_rows: list[dict[str, object]] = []
    copied = 0
    for row in read_jsonl(source_path):
        images = [Path(str(image_path)) for image_path in row.get("images", [])]
        rewritten_images: list[str] = []
        for image_path in images:
            if not image_path.exists():
                raise FileNotFoundError(f"Referenced image does not exist: {image_path}")
            portable_path, relative_path = portable_image_path(output_dir, image_path)
            copy_image_if_needed(image_path, portable_path)
            rewritten_images.append(final_image_reference(relative_path, image_prefix))
        copied += len(images)
        rewritten = dict(row)
        rewritten["images"] = rewritten_images
        rewritten_rows.append(rewritten)
    write_jsonl(output_dir / source_path.name, rewritten_rows)
    return copied


def summarize_bundle(output_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for split_name in ("train", "val", "test", "dev"):
        split_path = output_dir / f"{split_name}.jsonl"
        if not split_path.exists():
            continue
        with split_path.open("r", encoding="utf-8") as handle:
            counts[split_name] = sum(1 for line in handle if line.strip())
    return counts


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    copy_supporting_files(args.source_dir, args.output_dir)
    copy_split_metadata(args.source_dir, args.output_dir)

    total_images = 0
    for split_name in ("train", "val", "test", "dev"):
        source_split = args.source_dir / f"{split_name}.jsonl"
        if split_name in {"train", "val", "test"} and not source_split.exists():
            raise FileNotFoundError(f"Expected split file not found: {source_split}")
        if not source_split.exists():
            continue
        total_images += rewrite_qwen_split(source_split, args.output_dir, args.image_prefix)

    summary = summarize_bundle(args.output_dir)
    print(
        "Portable dataset bundle ready at "
        f"{args.output_dir} with {summary.get('train', 0)}/{summary.get('val', 0)}/{summary.get('test', 0)} "
        f"examples in train/val/test and {summary.get('dev', 0)} in dev."
    )
    print(f"Copied image references: {total_images}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
