from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

import complete_semantic_attributes as csa
from run_zero_shot_openai_irap import CATEGORIES as ATTRIBUTE_CATEGORIES


ATTRIBUTES = csa.ATTRIBUTES
MACRO_F1_METHOD = (
    "For each attribute, macro-F1 is calculated across the valid categories defined "
    "for that attribute, and the resulting 17 attribute-level macro-F1 values are "
    "averaged using equal weight across attributes."
)
ABSENT_CLASS_RULE = (
    "Categories absent from both the reference and prediction sets are excluded from "
    "that attribute's macro-F1 calculation. Categories present in the reference data "
    "but never predicted receive an F1 score of zero. Undefined precision or recall "
    "divisions are set to zero."
)


def norm_folder(value: Any) -> str:
    text = str(value).strip().upper()
    text = re.sub(r"[_\s]+", " ", text)
    return text


def norm_code(value: Any) -> str:
    return csa.norm_code(value)


def frame_from_image_number(value: Any) -> int | None:
    text = str(value)
    match = re.search(r"(\d+)(?=\.(?:png|jpg|jpeg)$)", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def class_sort_key(value: str) -> tuple[int, Any]:
    text = str(value)
    return (0, int(text)) if text.isdigit() else (1, text)


def valid_codes_for_attribute(attribute: str) -> set[str]:
    categories = ATTRIBUTE_CATEGORIES.get(attribute, {})
    return {str(code) for code in categories}


def metric_rows(
    pairs: list[tuple[str, str]],
    attribute: str,
    valid_codes: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    gt_counts = Counter(gt for gt, _ in pairs)
    pred_counts = Counter(pred for _, pred in pairs)
    observed_codes = set(gt_counts) | set(pred_counts)
    candidate_codes = set(valid_codes or set()) | observed_codes
    # Exclude categories absent from both reference and prediction for this slice.
    class_codes = sorted((code for code in candidate_codes if code in observed_codes), key=class_sort_key)
    per_class = []
    confusion = []
    correct = sum(1 for gt, pred in pairs if gt == pred)
    for gt, pred in Counter(pairs).items():
        confusion.append({"attribute": attribute, "gt_code": gt[0], "pred_code": gt[1], "count": pred})
    macro_p = macro_r = macro_f1 = 0.0
    weighted_p = weighted_r = weighted_f1 = 0.0
    total_support = len(pairs)
    for code in class_codes:
        tp = sum(1 for gt, pred in pairs if gt == code and pred == code)
        fp = sum(1 for gt, pred in pairs if gt != code and pred == code)
        fn = sum(1 for gt, pred in pairs if gt == code and pred != code)
        precision, recall, f1 = prf(tp, fp, fn)
        support_gt = gt_counts.get(code, 0)
        support_pred = pred_counts.get(code, 0)
        macro_p += precision
        macro_r += recall
        macro_f1 += f1
        weighted_p += precision * support_gt
        weighted_r += recall * support_gt
        weighted_f1 += f1 * support_gt
        per_class.append(
            {
                "attribute": attribute,
                "class_code": code,
                "class_label": ATTRIBUTE_CATEGORIES.get(attribute, {}).get(str(code), ""),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "support_gt": support_gt,
                "support_pred": support_pred,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    n_classes = max(1, len(class_codes))
    summary = {
        "attribute": attribute,
        "support": total_support,
        "correct": correct,
        "accuracy": correct / total_support if total_support else 0.0,
        "micro_precision": correct / total_support if total_support else 0.0,
        "micro_recall": correct / total_support if total_support else 0.0,
        "micro_f1": correct / total_support if total_support else 0.0,
        "macro_precision": macro_p / n_classes,
        "macro_recall": macro_r / n_classes,
        "macro_f1": macro_f1 / n_classes,
        "weighted_precision": weighted_p / total_support if total_support else 0.0,
        "weighted_recall": weighted_r / total_support if total_support else 0.0,
        "weighted_f1": weighted_f1 / total_support if total_support else 0.0,
        "class_count": len(class_codes),
        "valid_category_count": len(valid_codes or class_codes),
    }
    return summary, per_class, confusion


def load_predictions(predictions_root: Path) -> pd.DataFrame:
    frames = []
    for csv_path in sorted(predictions_root.glob("*/predicted_codes_all_attributes.csv")):
        frames.append(pd.read_csv(csv_path, keep_default_na=False))
    if not frames:
        raise FileNotFoundError(f"No predicted_codes_all_attributes.csv files found under {predictions_root}")
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate full-dataset iRAP prediction metrics.")
    parser.add_argument("--predictions-root", required=True)
    parser.add_argument("--ground-truth-csv", default="GroundTruth.csv")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    pred = load_predictions(Path(args.predictions_root))
    gt = pd.read_csv(args.ground_truth_csv, keep_default_na=False)
    gt["_frame_id"] = gt["Image number"].map(frame_from_image_number)
    gt["_folder_norm"] = gt["Folder_name"].map(norm_folder)
    gt_map = {
        (row["_folder_norm"], int(row["_frame_id"])): row
        for _, row in gt.iterrows()
        if pd.notna(row["_frame_id"])
    }

    cell_rows = []
    matched_keys = set()
    for _, prow in pred.iterrows():
        frame_id = int(prow["frame_id"])
        folder_norm = norm_folder(prow["folder_name"])
        gt_row = gt_map.get((folder_norm, frame_id))
        if gt_row is None:
            continue
        matched_keys.add((folder_norm, frame_id))
        for attr in ATTRIBUTES:
            gt_code = norm_code(gt_row.get(attr, ""))
            pred_code = norm_code(prow.get(attr, ""))
            if not gt_code or not pred_code:
                continue
            cell_rows.append(
                {
                    "folder_name": gt_row["Folder_name"],
                    "frame_id": frame_id,
                    "attribute": attr,
                    "gt_code": gt_code,
                    "pred_code": pred_code,
                    "correct": int(gt_code == pred_code),
                    "image_path": prow.get("image_path", ""),
                }
            )

    cell = pd.DataFrame(cell_rows)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell.to_csv(out_dir / "cell_level_comparison.csv", index=False)

    attr_summaries = []
    per_class_rows = []
    confusion_rows = []
    for attr in ATTRIBUTES:
        sub = cell[cell["attribute"] == attr]
        pairs = list(zip(sub["gt_code"].astype(str), sub["pred_code"].astype(str)))
        summary, per_class, confusion = metric_rows(pairs, attr, valid_codes_for_attribute(attr))
        attr_summaries.append(summary)
        per_class_rows.extend(per_class)
        confusion_rows.extend(confusion)

    attr_df = pd.DataFrame(attr_summaries).sort_values("macro_f1")
    attr_df.to_csv(out_dir / "attribute_metrics_summary.csv", index=False)
    pd.DataFrame(per_class_rows).to_csv(out_dir / "per_class_metrics.csv", index=False)
    pd.DataFrame(confusion_rows).to_csv(out_dir / "confusion_matrix_long.csv", index=False)

    folder_rows = []
    for folder, sub in cell.groupby("folder_name", sort=False):
        labelled_pairs = [
            (f"{row.attribute}::{row.gt_code}", f"{row.attribute}::{row.pred_code}")
            for row in sub.itertuples(index=False)
        ]
        labelled_summary, _, _ = metric_rows(labelled_pairs, "__attribute_category__")
        folder_attr_macro_f1 = []
        folder_attr_weighted_f1 = []
        for attr in ATTRIBUTES:
            attr_sub = sub[sub["attribute"] == attr]
            if attr_sub.empty:
                continue
            attr_pairs = list(zip(attr_sub["gt_code"].astype(str), attr_sub["pred_code"].astype(str)))
            attr_summary, _, _ = metric_rows(attr_pairs, attr, valid_codes_for_attribute(attr))
            folder_attr_macro_f1.append(attr_summary["macro_f1"])
            folder_attr_weighted_f1.append(attr_summary["weighted_f1"])
        folder_rows.append(
            {
                "folder_name": folder,
                "matched_gt_frames": sub["frame_id"].nunique(),
                "support_cells": len(sub),
                "correct_cells": int(sub["correct"].sum()),
                "accuracy_micro_f1": labelled_summary["accuracy"],
                "macro_precision_attribute_category": labelled_summary["macro_precision"],
                "macro_recall_attribute_category": labelled_summary["macro_recall"],
                "macro_f1_attribute_category": labelled_summary["macro_f1"],
                "weighted_precision_attribute_category": labelled_summary["weighted_precision"],
                "weighted_recall_attribute_category": labelled_summary["weighted_recall"],
                "weighted_f1_attribute_category": labelled_summary["weighted_f1"],
                "mean_attribute_macro_f1": sum(folder_attr_macro_f1) / len(folder_attr_macro_f1)
                if folder_attr_macro_f1
                else 0.0,
                "mean_attribute_weighted_f1": sum(folder_attr_weighted_f1) / len(folder_attr_weighted_f1)
                if folder_attr_weighted_f1
                else 0.0,
            }
        )
    pd.DataFrame(folder_rows).to_csv(out_dir / "folder_metrics_summary.csv", index=False)

    labelled_pairs = [
        (f"{row.attribute}::{row.gt_code}", f"{row.attribute}::{row.pred_code}")
        for row in cell.itertuples(index=False)
    ]
    labelled_summary, _, _ = metric_rows(labelled_pairs, "__attribute_category__")
    overall = {
        "macro_f1_method": MACRO_F1_METHOD,
        "absent_class_rule": ABSENT_CLASS_RULE,
        "predicted_rows_total": int(len(pred)),
        "matched_gt_frames": int(len(matched_keys)),
        "comparable_cells": int(len(cell)),
        "correct_cells": int(cell["correct"].sum()),
        "accuracy_micro_precision_recall_f1": labelled_summary["accuracy"],
        "macro_precision_attribute_category_all_cells": labelled_summary["macro_precision"],
        "macro_recall_attribute_category_all_cells": labelled_summary["macro_recall"],
        "macro_f1_attribute_category_all_cells": labelled_summary["macro_f1"],
        "weighted_precision_attribute_category_all_cells": labelled_summary["weighted_precision"],
        "weighted_recall_attribute_category_all_cells": labelled_summary["weighted_recall"],
        "weighted_f1_attribute_category_all_cells": labelled_summary["weighted_f1"],
        "mean_attribute_macro_f1": float(attr_df["macro_f1"].mean()),
        "mean_attribute_weighted_f1": float(attr_df["weighted_f1"].mean()),
    }
    (out_dir / "overall_metrics_summary.json").write_text(json.dumps(overall, indent=2), encoding="utf-8")
    print(json.dumps(overall, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
