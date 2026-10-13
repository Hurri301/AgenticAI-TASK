#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code iRAP width and side-facility attributes.")
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


def width_code(attribute: str, item: dict[str, Any], warnings: list[str]) -> tuple[int | None, str, float | None]:
    if bool(item.get("none")):
        if attribute.startswith("Paved shoulder"):
            return 4, "none", None
        if attribute == "Sidewalk - passenger side":
            return 5, "none", None
    if item.get("width_m") is None:
        warnings.append(f"Missing width_m for {attribute}")
        return None, "unresolved", None
    width = float(item["width_m"])
    if attribute == "Lane width":
        if width >= 3.25:
            return 1, "width_m", width
        if width >= 2.75:
            return 2, "width_m", width
        return 3, "width_m", width
    if attribute.startswith("Paved shoulder"):
        if bool(item.get("visual_narrow_paved_shoulder_present")):
            return 3, "visual_zoom_narrow_paved_strip", width
        if width <= 0.05:
            return 4, "width_m_none_threshold", width
        if width >= 2.4:
            return 1, "width_m", width
        if width >= 1.0:
            return 2, "width_m", width
        return 3, "width_m", width
    return None, "unresolved", width


def require_true(item: dict[str, Any], field: str, reason: str) -> None:
    if item.get(field) is not True:
        raise ValueError(f"{field}=true is required {reason}")


def sidewalk_code(item: dict[str, Any], warnings: list[str]) -> tuple[int | None, str, float | None]:
    side = norm(item.get("side") or "passenger")
    if side != "passenger":
        raise ValueError("Sidewalk - passenger side must use side=passenger")
    if bool(item.get("review_required")):
        raise ValueError("review_required=true: do not force a final sidewalk Cat ID")
    semantic_source = norm(item.get("semantic_inference_source"))
    allowed_sources = {"vlm", "segmentation", "vlm segmentation", "manual review"}
    if semantic_source not in allowed_sources:
        raise ValueError(
            "semantic_inference_source must be vlm, segmentation, vlm_segmentation, or manual_review; "
            "color/texture heuristics cannot finalize sidewalk semantics"
        )
    require_true(item, "passenger_crop_reviewed", "for evidence-derived sidewalk coding")
    require_true(item, "continuous_segment_reviewed", "before finalizing sidewalk presence")

    if bool(item.get("none")) or item.get("facility_present") is False:
        return 5, "passenger_crop_no_continuous_facility", None

    if item.get("continuous_over_segment") is False:
        if not bool(item.get("pedestrian_flow_evidence")):
            return 5, "not_continuous_over_segment", None

    facility = norm(item.get("facility_type"))
    distance = item.get("distance_from_road_m")
    measured = None if distance is None else float(distance)
    if measured is not None and measured < 0:
        raise ValueError("distance_from_road_m must be non-negative")

    partly_blocked_informal = (
        bool(item.get("partially_blocked"))
        and not bool(item.get("pedestrians_forced_onto_road"))
    )
    if partly_blocked_informal:
        facility = "informal path"

    barrier_qualifies = (
        bool(item.get("barrier_present"))
        and bool(item.get("barrier_restrains_vehicle"))
        and not bool(item.get("curb_only"))
    )
    if bool(item.get("barrier_present")) and not barrier_qualifies:
        warnings.append("Barrier evidence rejected: a kerb or non-restraining separator is not Cat ID 1")

    formal = facility in {"sidewalk", "formal sidewalk", "footpath"}
    informal = facility in {"informal path", "informal"}
    if formal:
        if item.get("purpose_built") is False or item.get("all_weather_surface") is False:
            raise ValueError("Formal sidewalk requires purpose_built and all_weather_surface evidence")
        if item.get("continuous_over_segment") is not True:
            raise ValueError("Formal sidewalk requires continuous_over_segment=true")
        if barrier_qualifies:
            return 1, "vehicle_restraining_barrier", measured
    if facility in {"informal path", "informal"}:
        if not (bool(item.get("pedestrian_flow_evidence")) or partly_blocked_informal):
            raise ValueError("Informal path requires pedestrian_flow_evidence or a qualifying partial obstruction")
        if measured is None:
            raise ValueError("Informal path requires distance_from_road_m; do not default to Cat ID 6")
        return (6 if measured >= 1.0 else 7), "facility_type_distance", measured
    if formal:
        if measured is None:
            raise ValueError("Sidewalk requires distance_from_road_m unless a qualifying physical barrier exists")
        if measured >= 3.0:
            return 2, "distance_from_road_m", measured
        if measured >= 1.0:
            return 3, "distance_from_road_m", measured
        return 4, "distance_from_road_m", measured
    warnings.append("Could not infer Sidewalk - passenger side; provide reviewed passenger-side evidence")
    return None, "unresolved", measured


def code_item(item: dict[str, Any], mappings: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    attribute = str(item.get("attribute", "")).strip()
    if attribute not in mappings:
        raise ValueError(f"Unsupported attribute: {attribute}")
    block = mappings[attribute]
    by_id, by_label = category_lookup(block)
    measured = None
    rule_source = "provided"
    if item.get("code") is not None:
        code = int(item["code"])
    elif item.get("label") is not None:
        key = norm(item["label"])
        if key not in by_label:
            raise ValueError(f"Unsupported label for {attribute}: {item['label']}")
        code = by_label[key]
    elif attribute == "Sidewalk - passenger side":
        code, rule_source, measured = sidewalk_code(item, warnings)
    else:
        code, rule_source, measured = width_code(attribute, item, warnings)
    if code is None or code not in by_id:
        raise ValueError(f"Unsupported code for {attribute}: {code}")
    return {
        "attribute": attribute,
        "side": "passenger" if attribute == "Sidewalk - passenger side" else item.get("side"),
        "col_id": block["col_id"],
        "cat_id": code,
        "category": by_id[code],
        "measured_meters": measured,
        "measurement_source": item.get("measurement_source"),
        "confidence": item.get("confidence", "medium" if rule_source == "provided" else "low"),
        "rule_source": rule_source,
        "evidence": item.get("evidence", []),
        "uncertainties": item.get("uncertainties", []),
        "rejected_alternatives": item.get("rejected_alternatives", []),
        "review_artifacts": {
            "passenger_context_crop": item.get("passenger_context_crop"),
            "passenger_focus_crop": item.get("passenger_focus_crop"),
            "crop_xyxy": item.get("crop_xyxy"),
        } if attribute == "Sidewalk - passenger side" else {},
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
        "mode": "irap_width_facility_coding",
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
