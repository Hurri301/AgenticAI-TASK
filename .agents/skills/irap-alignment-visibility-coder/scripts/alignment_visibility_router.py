#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code iRAP alignment and visibility attributes.")
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


def infer_code(attribute: str, item: dict[str, Any], warnings: list[str]) -> tuple[int | None, str]:
    if attribute == "Curvature":
        cls = norm(item.get("curvature_class"))
        aliases = {
            "straight": 1,
            "straight or gently curving": 1,
            "gentle": 1,
            "gently curving": 1,
            "moderate": 2,
            "sharp": 3,
            "very sharp": 4,
        }
        if cls in aliases:
            return aliases[cls], "curvature_class"
        if item.get("radius_m") is not None:
            radius = float(item["radius_m"])
            warnings.append("Curvature radius_m was mapped with project heuristic thresholds, not manual thresholds")
            if radius >= 800:
                return 1, "project_heuristic"
            if radius >= 400:
                return 2, "project_heuristic"
            if radius >= 100:
                return 3, "project_heuristic"
            return 4, "project_heuristic"
    if attribute == "Sight distance":
        if "sight_distance_adequate" in item:
            return (1 if bool(item["sight_distance_adequate"]) else 2), "sight_distance_adequate"
        if "visibility_restricted" in item:
            return (2 if bool(item["visibility_restricted"]) else 1), "visibility_restricted"
    warnings.append(f"Could not infer code for {attribute}; provide code, label, or supported evidence field")
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
        "geometry_metrics": item.get("geometry_metrics", {}),
        "visual_evidence": item.get("visual_evidence", item.get("evidence", [])),
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
    mappings = read_json(skill_root / "references" / "cat_ids.json")
    items = request.get("items")
    if not isinstance(items, list):
        raise ValueError("Input must contain an items list")
    warnings: list[str] = []
    results = [code_item(item, mappings, warnings) for item in items if isinstance(item, dict)]
    output = {
        "mode": "irap_alignment_visibility_coding",
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
