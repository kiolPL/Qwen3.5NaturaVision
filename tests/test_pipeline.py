from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common import (
    ASSISTANT_STYLE_LABEL_ONLY,
    PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY,
    build_training_example,
    classify_unknown_subclass,
    load_species_manifest,
    manifest_by_label,
    normalize_license,
    training_label_catalog,
)
from scripts.make_splits import build_split_records
from scripts.prepare_qwen_examples import prepare_examples
from scripts.rewrite_qwen_image_paths import normalize_image_reference


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = REPO_ROOT / "data" / "species_manifest.csv"
        self.entries = load_species_manifest(self.manifest_path)
        self.label_map = manifest_by_label(self.entries)
        self.training_catalog = training_label_catalog(self.entries)

    def test_normalize_license(self) -> None:
        self.assertEqual(normalize_license("CC-BY 4.0"), "CC-BY")
        self.assertEqual(normalize_license("cc_by_nc"), "CC-BY-NC")
        self.assertEqual(normalize_license("CC0"), "CC0")
        self.assertIsNone(normalize_license("all-rights-reserved"))

    def test_build_training_example(self) -> None:
        example = build_training_example(Path("sample.jpg"), self.label_map["PLANT_01"])
        self.assertEqual(example["images"], [str(Path("sample.jpg").resolve())])
        assistant_payload = json.loads(example["messages"][2]["content"])
        self.assertEqual(assistant_payload["label_id"], "PLANT_01")
        self.assertEqual(assistant_payload["scientific_name"], "Pinus sylvestris")

    def test_split_builder_assigns_expected_counts(self) -> None:
        records = []
        for label_id in ("PLANT_01", "unknown"):
            total = 410 if label_id != "unknown" else 3200
            for index in range(total):
                kingdom = "plants"
                if label_id == "unknown" and index % 7 == 0:
                    kingdom = "fungi"
                records.append(
                    {
                        "label_id": label_id,
                        "kingdom": kingdom,
                        "observation_id": f"{label_id}-obs-{index}",
                        "photo_id": f"{label_id}-photo-{index}",
                        "image_path": str(REPO_ROOT / "README.md"),
                    }
                )
        split_records = build_split_records(
            records=records,
            known_label_ids=["PLANT_01"],
            known_split_quotas={"train": 300, "val": 50, "test": 50, "dev": 10},
            unknown_split_quotas={"train": 2000, "val": 400, "test": 400, "dev": 10},
            seed=23,
            hard_negative_extra_per_label=10,
        )
        self.assertEqual(len(split_records["train"]), 2310)
        self.assertEqual(len(split_records["val"]), 450)
        self.assertEqual(len(split_records["test"]), 450)
        self.assertEqual(len(split_records["dev"]), 20)
        self.assertGreater(
            sum(1 for row in split_records["train"] if row["label_id"].startswith("UNK_")),
            0,
        )

    def test_prepare_examples_uses_unknown_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "sample.jpg"
            image_path.write_bytes(b"not-a-real-jpeg")
            split_path = root / "train_records.jsonl"
            split_path.write_text(
                json.dumps(
                    {
                        "label_id": "unknown",
                        "image_path": str(image_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            examples = prepare_examples(
                split_path,
                self.training_catalog,
                prompt_style=PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY,
                assistant_style=ASSISTANT_STYLE_LABEL_ONLY,
                collapse_internal_unknown=False,
            )
            self.assertEqual(len(examples), 1)
            payload = json.loads(examples[0]["messages"][2]["content"])
            self.assertEqual(payload["label_id"], "unknown")
            self.assertIn("Allowed labels:", examples[0]["messages"][0]["content"])

    def test_normalize_image_reference_rewrites_raw_cache_paths(self) -> None:
        rewritten = normalize_image_reference(
            r"D:\InaturalistData\raw_cache\PLANT_01\402734711.jpg",
            "/home/tester/naturavision-data/images",
        )
        self.assertEqual(
            rewritten,
            "/home/tester/naturavision-data/images/PLANT_01/402734711.jpg",
        )

    def test_classify_unknown_subclass_prefers_kingdom_specific_labels(self) -> None:
        self.assertEqual(
            classify_unknown_subclass({"label_id": "unknown", "kingdom": "plants"}),
            "UNK_NON_TARGET_PLANT",
        )
        self.assertEqual(
            classify_unknown_subclass({"label_id": "unknown", "kingdom": "fungi"}),
            "UNK_NON_TARGET_FUNGUS",
        )
        self.assertEqual(
            classify_unknown_subclass({"label_id": "unknown", "kingdom": ""}),
            "UNK_OTHER_OR_AMBIGUOUS",
        )


if __name__ == "__main__":
    unittest.main()
