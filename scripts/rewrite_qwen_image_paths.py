from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite NaturaVision Qwen JSONL image paths for a new root.")
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Directory with train/val/test JSONL files.")
    parser.add_argument(
        "--image-root",
        type=str,
        required=True,
        help="Absolute POSIX path that should prefix all image references, e.g. /home/ubuntu/naturavision_dataset/images",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def normalize_image_reference(image_ref: str, image_root: str) -> str:
    normalized = image_ref.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if "images" in parts:
        image_index = parts.index("images")
        relative_parts = parts[image_index + 1 :]
    elif "raw_cache" in parts:
        cache_index = parts.index("raw_cache")
        relative_parts = parts[cache_index + 1 :]
    else:
        relative_parts = parts[-2:]
    relative = PurePosixPath(*relative_parts)
    return str(PurePosixPath(image_root.rstrip("/")) / relative)


def main() -> int:
    args = parse_args()
    for split_name in ("train", "val", "test", "dev"):
        split_path = args.dataset_dir / f"{split_name}.jsonl"
        if not split_path.exists():
            continue
        rewritten_rows: list[dict[str, object]] = []
        for row in read_jsonl(split_path):
            rewritten = dict(row)
            rewritten["images"] = [normalize_image_reference(str(image_ref), args.image_root) for image_ref in row["images"]]
            rewritten_rows.append(rewritten)
        write_jsonl(split_path, rewritten_rows)
        print(f"Rewrote image paths in {split_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
