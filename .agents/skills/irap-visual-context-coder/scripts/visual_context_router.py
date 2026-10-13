#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code iRAP visual/context attributes.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--out-json", required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def load_mappings(skill_root: Path) -> dict[str, dict[str, Any]]:
    return read_json(skill_root / "references" / "cat_ids.json")


def category_lookup(block: dict[str, Any]) -> tuple[dict[int, str], dict[str, int]]:
    by_id = {int(item["cat_id"]): str(item["category"]) for item in block["categories"]}
    by_label = {norm(item["category"]): int(item["cat_id"]) for item in block["categories"]}
    return by_id, by_label


def evidence_text(item: dict[str, Any]) -> str:
    evidence = item.get("evidence", "")
    if isinstance(evidence, list):
        return " ".join(str(x) for x in evidence)
    return str(evidence or "")


def infer_code(attribute: str, item: dict[str, Any], warnings: list[str]) -> int | None:
    text = norm(evidence_text(item))
    if attribute == "Area type":
        if "urban_context" in item:
            return 2 if bool(item["urban_context"]) else 1
        if any(word in text for word in ["urban", "commercial", "residential", "buildings", "kerb"]):
            return 2
        if any(word in text for word in ["rural", "open", "farming", "agricultural", "undeveloped"]):
            return 1
    if attribute == "Street lighting" and "lighting_present" in item:
        return 2 if bool(item["lighting_present"]) else 1
    if attribute == "Service road" and "service_road_present" in item:
        return 2 if bool(item["service_road_present"]) else 1
    if attribute == "Delineation" and "delineation_adequate" in item:
        return 1 if bool(item["delineation_adequate"]) else 2
    warnings.append(f"Could not infer code for {attribute}; provide code, label, or attribute-specific boolean")
    return None


def code_item(item: dict[str, Any], mappings: dict[str, dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    attribute = str(item.get("attribute", "")).strip()
    if attribute not in mappings:
        raise ValueError(f"Unsupported attribute: {attribute}")

    block = mappings[attribute]
    by_id, by_label = category_lookup(block)
    code: int | None = None
    rule_source = "provided"

    if item.get("code") is not None:
        code = int(item["code"])
    elif item.get("label") is not None:
        label_key = norm(item["label"])
        if label_key not in by_label:
            raise ValueError(f"Unsupported label for {attribute}: {item['label']}")
        code = by_label[label_key]
    else:
        code = infer_code(attribute, item, warnings)
        rule_source = "inferred"

    if code is None or code not in by_id:
        raise ValueError(f"Unsupported code for {attribute}: {code}")

    return {
        "attribute": attribute,
        "col_id": block.get("col_id"),
        "cat_id": code,
        "category": by_id[code],
        "confidence": item.get("confidence", "medium" if rule_source == "provided" else "low"),
        "rule_source": rule_source,
        "evidence": item.get("evidence", []),
        "uncertainties": item.get("uncertainties", []),
        "trace": {"input": item},
    }


def main() -> int:
    args = parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    input_path = Path(args.input_json).resolve()
    out_path = Path(args.out_json).resolve()
    request = read_json(input_path)
    items = request.get("items")
    if not isinstance(items, list):
        raise ValueError("Input must contain an items list")

    mappings = load_mappings(skill_root)
    warnings: list[str] = []
    results = [code_item(item, mappings, warnings) for item in items if isinstance(item, dict)]
    output = {
        "mode": "irap_visual_context_coding",
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
