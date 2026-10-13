#!/usr/bin/env python
"""Compute precision, recall, F1, and accuracy for zero-shot iRAP predictions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from run_zero_shot_openai_irap import CATEGORIES as ATTRIBUTE_CATEGORIES


MACRO_F1_METHOD = (
    "For each attribute, macro-F1 is calculated across the valid categories defined "
    "for that attribute, and the resulting attribute-level macro-F1 values are "
    "averaged using equal weight across attributes."
)
ABSENT_CLASS_RULE = (
    "Categories absent from both the reference and prediction sets are excluded from "
    "that attribute's macro-F1 calculation. Categories present in the reference data "
    "but never predicted receive an F1 score of zero. Undefined precision or recall "
    "divisions are set to zero."
)


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def compute_metrics(rows: list[dict[str, str]], attribute: str | None = None) -> tuple[dict, list[dict]]:
    observed_labels = {r["ground_truth_cat_id"] for r in rows} | {r["predicted_cat_id"] for r in rows}
    valid_labels = set(ATTRIBUTE_CATEGORIES.get(attribute or "", {}))
    labels = sorted((observed_labels | valid_labels) & observed_labels, key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)))
    total = len(rows)
    correct = sum(1 for r in rows if r["ground_truth_cat_id"] == r["predicted_cat_id"])

    class_rows = []
    weighted_precision = 0.0
    weighted_recall = 0.0
    weighted_f1 = 0.0
    macro_precision_values = []
    macro_recall_values = []
    macro_f1_values = []

    for label in labels:
        tp = sum(1 for r in rows if r["ground_truth_cat_id"] == label and r["predicted_cat_id"] == label)
        fp = sum(1 for r in rows if r["ground_truth_cat_id"] != label and r["predicted_cat_id"] == label)
        fn = sum(1 for r in rows if r["ground_truth_cat_id"] == label and r["predicted_cat_id"] != label)
        support = sum(1 for r in rows if r["ground_truth_cat_id"] == label)
        pred_support = sum(1 for r in rows if r["predicted_cat_id"] == label)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        macro_precision_values.append(precision)
        macro_recall_values.append(recall)
        macro_f1_values.append(f1)
        weighted_precision += precision * support
        weighted_recall += recall * support
        weighted_f1 += f1 * support
        class_rows.append(
            {
                "class_label": label,
                "class_name": ATTRIBUTE_CATEGORIES.get(attribute or "", {}).get(str(label), ""),
                "support": support,
                "predicted_support": pred_support,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    # In single-label complete multiclass classification, micro precision,
    # micro recall, micro F1, and accuracy are identical.
    accuracy = safe_div(correct, total)
    summary = {
        "total": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": accuracy,
        "micro_precision": accuracy,
        "micro_recall": accuracy,
        "micro_f1": accuracy,
        "macro_precision": safe_div(sum(macro_precision_values), len(macro_precision_values)),
        "macro_recall": safe_div(sum(macro_recall_values), len(macro_recall_values)),
        "macro_f1": safe_div(sum(macro_f1_values), len(macro_f1_values)),
        "weighted_precision": safe_div(weighted_precision, total),
        "weighted_recall": safe_div(weighted_recall, total),
        "weighted_f1": safe_div(weighted_f1, total),
        "class_count": len(labels),
        "valid_category_count": len(valid_labels or labels),
    }
    return summary, class_rows


def compute_labelled_pair_metrics(rows: list[dict[str, str]]) -> tuple[dict, list[dict]]:
    labelled_rows = [
        {
            **row,
            "ground_truth_cat_id": f"{row['attribute']}::{row['ground_truth_cat_id']}",
            "predicted_cat_id": f"{row['attribute']}::{row['predicted_cat_id']}",
        }
        for row in rows
    ]
    return compute_metrics(labelled_rows)


def fmt(value: float) -> str:
    return f"{value:.6f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--long-comparison", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.long_comparison, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    by_attribute: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_attribute[row["attribute"]].append(row)

    summary_rows = []
    class_metric_rows = []
    report = {
        "source": args.long_comparison,
        "total_rows": len(rows),
        "macro_f1_method": MACRO_F1_METHOD,
        "absent_class_rule": ABSENT_CLASS_RULE,
        "attributes": {},
    }

    for attribute in sorted(by_attribute):
        summary, class_rows = compute_metrics(by_attribute[attribute], attribute)
        report["attributes"][attribute] = summary
        summary_rows.append({"attribute": attribute, **{k: fmt(v) if isinstance(v, float) else v for k, v in summary.items()}})
        for class_row in class_rows:
            class_metric_rows.append(
                {
                    "attribute": attribute,
                    **{
                        k: fmt(v) if isinstance(v, float) else v
                        for k, v in class_row.items()
                    },
                }
            )

    labelled_summary, _ = compute_labelled_pair_metrics(rows)
    mean_attribute_macro_f1 = safe_div(
        sum(float(summary["macro_f1"]) for summary in report["attributes"].values()),
        len(report["attributes"]),
    )
    mean_attribute_weighted_f1 = safe_div(
        sum(float(summary["weighted_f1"]) for summary in report["attributes"].values()),
        len(report["attributes"]),
    )
    overall_summary = {
        **labelled_summary,
        "macro_precision_attribute_category": labelled_summary["macro_precision"],
        "macro_recall_attribute_category": labelled_summary["macro_recall"],
        "macro_f1_attribute_category": labelled_summary["macro_f1"],
        "weighted_precision_attribute_category": labelled_summary["weighted_precision"],
        "weighted_recall_attribute_category": labelled_summary["weighted_recall"],
        "weighted_f1_attribute_category": labelled_summary["weighted_f1"],
        "mean_attribute_macro_f1": mean_attribute_macro_f1,
        "mean_attribute_weighted_f1": mean_attribute_weighted_f1,
    }
    report["overall"] = overall_summary

    summary_csv = out_dir / "zero_shot_vs_gt_precision_recall_f1_by_attribute.csv"
    class_csv = out_dir / "zero_shot_vs_gt_precision_recall_f1_by_class.csv"
    overall_csv = out_dir / "zero_shot_vs_gt_precision_recall_f1_overall.csv"
    json_path = out_dir / "zero_shot_vs_gt_precision_recall_f1_metrics.json"

    summary_fields = [
        "attribute",
        "total",
        "correct",
        "incorrect",
        "accuracy",
        "micro_precision",
        "micro_recall",
        "micro_f1",
        "macro_precision",
        "macro_recall",
        "macro_f1",
        "weighted_precision",
        "weighted_recall",
        "weighted_f1",
        "class_count",
        "valid_category_count",
    ]
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    class_fields = [
        "attribute",
        "class_label",
        "class_name",
        "support",
        "predicted_support",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
    ]
    with class_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=class_fields)
        writer.writeheader()
        writer.writerows(class_metric_rows)

    with overall_csv.open("w", newline="", encoding="utf-8") as f:
        fields = [k for k in overall_summary]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow({k: fmt(v) if isinstance(v, float) else v for k, v in overall_summary.items()})

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "overall": report["overall"],
                "attribute_metrics_csv": str(summary_csv),
                "class_metrics_csv": str(class_csv),
                "overall_metrics_csv": str(overall_csv),
                "json": str(json_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
