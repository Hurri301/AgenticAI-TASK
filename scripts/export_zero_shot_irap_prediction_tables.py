#!/usr/bin/env python
"""Export comparison-ready iRAP prediction tables from finalized zero-shot JSONL."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ATTRIBUTES = [
    ("Area type", "area_type"),
    ("Street lighting", "street_lighting"),
    ("Service road", "service_road"),
    ("Delineation", "delineation"),
    ("Number of lanes", "number_of_lanes"),
    ("Median Type", "median_type"),
    ("Lane width", "lane_width"),
    ("Paved shoulder - drivers side", "paved_shoulder_driver_side"),
    ("Paved shoulder - passenger side", "paved_shoulder_passenger_side"),
    ("Sidewalk - passenger side", "sidewalk_passenger_side"),
    ("Property access points", "property_access_points"),
    ("Curvature", "curvature"),
    ("Sight distance", "sight_distance"),
    ("Roadside severity - driver side distance", "roadside_severity_driver_distance"),
    ("Roadside severity - driver side object", "roadside_severity_driver_object"),
    ("Roadside severity - passenger side distance", "roadside_severity_passenger_distance"),
    ("Roadside severity - passenger side object", "roadside_severity_passenger_object"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    jsonl_path = run_dir / "zero_shot_17_attribute_results.final.jsonl"
    codes_csv = run_dir / "predicted_irap_codes.csv"
    detailed_csv = run_dir / "predicted_irap_codes_with_categories_confidence.csv"
    long_csv = run_dir / "predicted_irap_codes_long.csv"
    summary_path = run_dir / "prediction_export_summary.json"

    records = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    code_fields = ["segment_id", "image_path", "model", "method"] + [
        f"pred_{slug}_cat_id" for _, slug in ATTRIBUTES
    ]
    detail_fields = ["segment_id", "image_path", "model", "method"]
    for _, slug in ATTRIBUTES:
        detail_fields.extend(
            [
                f"pred_{slug}_cat_id",
                f"pred_{slug}_category",
                f"pred_{slug}_confidence",
            ]
        )

    with codes_csv.open("w", newline="", encoding="utf-8") as f_codes, detailed_csv.open(
        "w", newline="", encoding="utf-8"
    ) as f_details, long_csv.open("w", newline="", encoding="utf-8") as f_long:
        code_writer = csv.DictWriter(f_codes, fieldnames=code_fields)
        detail_writer = csv.DictWriter(f_details, fieldnames=detail_fields)
        long_writer = csv.DictWriter(
            f_long,
            fieldnames=[
                "segment_id",
                "image_path",
                "model",
                "method",
                "attribute",
                "predicted_cat_id",
                "predicted_category",
                "confidence",
                "evidence_summary",
                "measurement_note",
            ],
        )
        code_writer.writeheader()
        detail_writer.writeheader()
        long_writer.writeheader()

        for record in records:
            by_attr = {r["attribute"]: r for r in record["results"]}
            base = {
                "segment_id": record["segment_id"],
                "image_path": record["image_path"],
                "model": record["model"],
                "method": record["method"],
            }
            code_row = dict(base)
            detail_row = dict(base)
            for attr, slug in ATTRIBUTES:
                result = by_attr[attr]
                code_row[f"pred_{slug}_cat_id"] = result["cat_id"]
                detail_row[f"pred_{slug}_cat_id"] = result["cat_id"]
                detail_row[f"pred_{slug}_category"] = result["category"]
                detail_row[f"pred_{slug}_confidence"] = result.get("confidence")
                long_writer.writerow(
                    {
                        **base,
                        "attribute": attr,
                        "predicted_cat_id": result["cat_id"],
                        "predicted_category": result["category"],
                        "confidence": result.get("confidence"),
                        "evidence_summary": result.get("evidence_summary"),
                        "measurement_note": result.get("measurement_note"),
                    }
                )
            code_writer.writerow(code_row)
            detail_writer.writerow(detail_row)

    summary = {
        "ground_truth_used": False,
        "source_jsonl": str(jsonl_path),
        "record_count": len(records),
        "attribute_count": len(ATTRIBUTES),
        "wide_codes_csv": str(codes_csv),
        "wide_detailed_csv": str(detailed_csv),
        "long_csv": str(long_csv),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
