#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code iRAP carriageway layout attributes.")
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
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("–", "-").split())


def category_lookup(block: dict[str, Any]) -> tuple[dict[int, str], dict[str, int]]:
    by_id = {int(item["cat_id"]): str(item["category"]) for item in block["categories"]}
    by_label = {norm(item["category"]): int(item["cat_id"]) for item in block["categories"]}
    return by_id, by_label


def infer_code(attribute: str, item: dict[str, Any], warnings: list[str]) -> tuple[int | None, str]:
    if attribute == "Number of lanes":
        pattern = norm(item.get("lane_pattern"))
        if pattern in {"two and one", "two one"}:
            return 5, "lane_pattern"
        if pattern in {"three and two", "three two"}:
            return 6, "lane_pattern"
        if item.get("lane_count") is not None:
            count = int(item["lane_count"])
            if count <= 1:
                return 1, "lane_count"
            if count == 2:
                return 2, "lane_count"
            if count == 3:
                return 3, "lane_count"
            return 4, "lane_count"
    if attribute == "Median Type":
        median = norm(item.get("median_type") or item.get("separator"))
        aliases = {
            "centre line": 11,
            "center line": 11,
            "wide centre line": 14,
            "wide center line": 14,
            "central hatching": 10,
            "hatching": 10,
            "continuous central turning lane": 8,
            "turning lane": 8,
            "flexible posts": 9,
            "metal barrier": 1,
            "concrete barrier": 2,
            "wire rope barrier": 15,
            "one way": 13,
        }
        if median in aliases:
            return aliases[median], "median_type"
        width = item.get("median_width_m")
        if width is not None:
            w = float(width)
            if w >= 20:
                return 3, "median_width_m"
            if w >= 10:
                return 4, "median_width_m"
            if w >= 5:
                return 5, "median_width_m"
            if w >= 1:
                return 6, "median_width_m"
            return 7, "median_width_m"
    warnings.append(f"Could not infer code for {attribute}; provide code or label")
    return None, "unresolved"


def code_item(item: dict[str, Any], mappings: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    attribute = str(item.get("attribute", "")).strip()
    if attribute not in mappings:
        raise ValueError(f"Unsupported attribute: {attribute}")
    block = mappings[attribute]
    by_id, by_label = category_lookup(block)
    rule_source = "provided"
    if item.get("code") is not None:
        code = int(item["code"])
    elif item.get("label") is not None:
        key = norm(item["label"])
        if key not in by_label:
            raise ValueError(f"Unsupported label for {attribute}: {item['label']}")
        code = by_label[key]
    else:
        code, rule_source = infer_code(attribute, item, warnings)
    if code is None or code not in by_id:
        raise ValueError(f"Unsupported code for {attribute}: {code}")
    return {
        "attribute": attribute,
        "col_id": block["col_id"],
        "cat_id": code,
        "category": by_id[code],
        "confidence": item.get("confidence", "medium" if rule_source == "provided" else "low"),
        "rule_source": rule_source,
        "evidence": item.get("evidence", []),
        "excluded_features": item.get("excluded_features", []),
        "uncertainties": item.get("uncertainties", []),
        "trace": {"input": item},
    }


def main() -> int:
    args = parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    input_path = Path(args.input_json).resolve()
    out_path = Path(args.out_json).resolve()
    request = read_json(input_path)
    mappings = read_json(skill_root / "references" / "cat_ids.json")
    items = request.get("items")
    if not isinstance(items, list):
        raise ValueError("Input must contain an items list")
    warnings: list[str] = []
    results = [code_item(item, mappings, warnings) for item in items if isinstance(item, dict)]
    output = {
        "mode": "irap_carriageway_layout_coding",
        "artifacts": {"input_json": str(input_path), "cat_ids_json": str(skill_root / "references" / "cat_ids.json")},
        "counts": {"items": len(results), "warnings": len(warnings)},
        "items": results,
        "warnings": warnings,
    }
    write_json(out_path, output)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
