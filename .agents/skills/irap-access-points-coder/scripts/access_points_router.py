#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code iRAP property access points.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--out-json", required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def category_lookup(block: dict[str, Any]) -> tuple[dict[int, str], dict[str, int]]:
    by_id = {int(item["cat_id"]): str(item["category"]) for item in block["categories"]}
    by_label = {norm(item["category"]): int(item["cat_id"]) for item in block["categories"]}
    return by_id, by_label


def infer_counts(item: dict[str, Any]) -> tuple[bool, int]:
    commercial = bool(item.get("commercial_present", False))
    residential_count_provided = item.get("residential_count") is not None
    residential = int(item.get("residential_count", 0) or 0)
    for candidate in item.get("candidate_accesses", []) or []:
        if not isinstance(candidate, dict):
            continue
        ctype = norm(candidate.get("type"))
        if ctype == "commercial":
            commercial = True
        elif ctype == "residential" and not residential_count_provided:
            residential += 1
    return commercial, residential


def code_item(item: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    block = mapping["Property access points"]
    by_id, by_label = category_lookup(block)
    rule_source = "provided"
    commercial, residential = infer_counts(item)
    if item.get("code") is not None:
        code = int(item["code"])
    elif item.get("label") is not None:
        key = norm(item["label"])
        if key not in by_label:
            raise ValueError(f"Unsupported label: {item['label']}")
        code = by_label[key]
    else:
        rule_source = "access_priority"
        if commercial:
            code = 1
        elif residential >= 3:
            code = 2
        elif residential > 0:
            code = 3
        else:
            code = 4
    if code not in by_id:
        raise ValueError(f"Unsupported code: {code}")
    return {
        "attribute": "Property access points",
        "col_id": block["col_id"],
        "cat_id": code,
        "category": by_id[code],
        "commercial_present": commercial,
        "residential_count": residential,
        "candidate_accesses": item.get("candidate_accesses", []),
        "rejected_candidates": item.get("rejected_candidates", []),
        "evidence_frames": item.get("evidence_frames", []),
        "confidence": item.get("confidence", "medium" if rule_source == "provided" else "low"),
        "rule_source": rule_source,
        "uncertainties": item.get("uncertainties", []),
        "trace": {"input": item},
    }


def main() -> int:
    args = parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    input_path = Path(args.input_json).resolve()
    out_path = Path(args.out_json).resolve()
    request = read_json(input_path)
    mapping = read_json(skill_root / "references" / "cat_ids.json")
    raw_items = request.get("items", [request])
    if not isinstance(raw_items, list):
        raise ValueError("items must be a list")
    results = [code_item(item, mapping) for item in raw_items if isinstance(item, dict)]
    output = {
        "mode": "irap_access_points_coding",
        "artifacts": {"input_json": str(input_path), "cat_ids_json": str(skill_root / "references" / "cat_ids.json")},
        "counts": {"items": len(results), "warnings": 0},
        "items": results,
        "warnings": [],
    }
    write_json(out_path, output)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
