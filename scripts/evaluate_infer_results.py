#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL row in {path} at line {line_no}: {exc}") from exc
    return rows


def find_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    while start != -1:
        depth = 0
        for idx in range(start, len(text)):
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[start:idx + 1]
                    try:
                        payload = json.loads(snippet)
                    except json.JSONDecodeError:
                        break
                    return payload if isinstance(payload, dict) else None
        start = text.find("{", start + 1)
    return None


def extract_label_id(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "invalid_json"
    label_id = payload.get("label_id")
    if not isinstance(label_id, str) or not label_id.strip():
        return "missing_label"
    return label_id.strip()


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def collapse_labels(labels: list[str], collapse_map: dict[str, str]) -> list[str]:
    return [collapse_map.get(label_id, label_id) for label_id in labels]


def build_metrics(labels: list[str], preds: list[str], known_labels: list[str]) -> dict[str, Any]:
    all_metric_labels = sorted(set(known_labels) | set(labels) | set(preds))
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for truth, pred in zip(labels, preds):
        confusion[truth][pred] += 1

    per_class: dict[str, dict[str, Any]] = {}
    f1_known: list[float] = []
    f1_all: list[float] = []

    for label in all_metric_labels:
        tp = confusion[label][label]
        fp = sum(confusion[truth][label] for truth in all_metric_labels if truth != label)
        fn = sum(count for pred, count in confusion[label].items() if pred != label)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        support = sum(confusion[label].values())
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        f1_all.append(f1)
        if label != "unknown" and label in known_labels:
            f1_known.append(f1)

    accuracy = safe_div(sum(int(t == p) for t, p in zip(labels, preds)), len(labels))
    unknown_metrics = per_class.get("unknown", {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0})

    top_confusions: list[dict[str, Any]] = []
    for truth in known_labels:
        for pred, count in confusion.get(truth, {}).items():
            if pred != truth:
                top_confusions.append({"truth": truth, "pred": pred, "count": count})
    top_confusions.sort(key=lambda item: item["count"], reverse=True)

    return {
        "accuracy": accuracy,
        "macro_f1_known": safe_div(sum(f1_known), len(f1_known)),
        "macro_f1_all": safe_div(sum(f1_all), len(f1_all)),
        "unknown_precision": unknown_metrics["precision"],
        "unknown_recall": unknown_metrics["recall"],
        "unknown_f1": unknown_metrics["f1"],
        "per_class": per_class,
        "top_confusions": top_confusions[:25],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NaturaVision inference results.")
    parser.add_argument("--results", required=True, help="Path to the JSONL output from swift infer.")
    parser.add_argument("--labels-json", required=True, help="Path to labels.json used for the dataset.")
    parser.add_argument("--output", required=True, help="Where to write the evaluation summary JSON.")
    args = parser.parse_args()

    results_path = Path(args.results).resolve()
    labels_path = Path(args.labels_json).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(results_path)
    labels_catalog = json.loads(labels_path.read_text(encoding="utf-8"))
    known_labels = [label for label in labels_catalog["supported_labels"] if label != "unknown"]
    collapse_map = labels_catalog.get("collapse_to_public", {})

    truths: list[str] = []
    preds: list[str] = []
    valid_json = 0
    exact_json = 0
    invalid_examples: list[dict[str, Any]] = []

    for row in rows:
        label_payload = find_json_object(row.get("labels", ""))
        pred_payload = find_json_object(row.get("response", ""))
        truth = extract_label_id(label_payload)
        pred = extract_label_id(pred_payload)
        truths.append(truth)
        preds.append(pred)
        if pred_payload is not None:
            valid_json += 1
        if row.get("labels") == row.get("response"):
            exact_json += 1
        if pred_payload is None or pred in {"invalid_json", "missing_label"}:
            invalid_examples.append(
                {
                    "image": (row.get("images") or [None])[0],
                    "labels": row.get("labels"),
                    "response": row.get("response"),
                }
            )

    collapsed_truths = collapse_labels(truths, collapse_map)
    collapsed_preds = collapse_labels(preds, collapse_map)
    metrics = build_metrics(collapsed_truths, collapsed_preds, known_labels)
    summary = {
        "num_examples": len(rows),
        "valid_json_rate": safe_div(valid_json, len(rows)),
        "exact_json_match_rate": safe_div(exact_json, len(rows)),
        **metrics,
        "invalid_examples": invalid_examples[:50],
    }

    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "num_examples": summary["num_examples"],
            "valid_json_rate": round(summary["valid_json_rate"], 4),
            "exact_json_match_rate": round(summary["exact_json_match_rate"], 4),
            "accuracy": round(summary["accuracy"], 4),
            "macro_f1_known": round(summary["macro_f1_known"], 4),
            "unknown_recall": round(summary["unknown_recall"], 4),
            "output": str(output_path),
        },
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
