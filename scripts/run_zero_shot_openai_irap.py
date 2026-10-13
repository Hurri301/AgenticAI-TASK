#!/usr/bin/env python
"""Run keyless zero-shot road-attribute coding over an image folder.

This script does not call the OpenAI API or any external API and does not read
ground truth labels. It uses local image-processing evidence as a conservative
zero-shot visual baseline for the 17 road attributes.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


MODEL = "local-cv-zero-shot-heuristic"
METHOD = "zero_shot_keyless_local_visual_heuristic"
DEFAULT_RUN_ID = f"zero_shot_keyless_local_visual_{datetime.now().strftime('%Y-%m-%d')}"


ATTRIBUTES = [
    "Area type",
    "Street lighting",
    "Service road",
    "Delineation",
    "Number of lanes",
    "Median Type",
    "Lane width",
    "Paved shoulder - drivers side",
    "Paved shoulder - passenger side",
    "Sidewalk - passenger side",
    "Property access points",
    "Curvature",
    "Sight distance",
    "Roadside severity - driver side distance",
    "Roadside severity - driver side object",
    "Roadside severity - passenger side distance",
    "Roadside severity - passenger side object",
]

IRAP_EXPORT_ATTRIBUTES = [
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


CATEGORIES = {
    "Area type": {"1": "Rural", "2": "Urban"},
    "Street lighting": {"1": "Not present", "2": "Present"},
    "Service road": {"1": "Not present", "2": "Present"},
    "Delineation": {"1": "Adequate", "2": "Poor"},
    "Number of lanes": {
        "1": "One",
        "2": "Two",
        "3": "Three",
        "4": "Four or more",
        "5": "Two and one",
        "6": "Three and two",
    },
    "Median Type": {
        "1": "Safety barrier - metal",
        "2": "Safety barrier - concrete",
        "3": "Physical median width >=20m",
        "4": "Physical median width 10 to <20m",
        "5": "Physical median width 5 to <10m",
        "6": "Physical median width 1 to <5m",
        "7": "Physical median width 0 to <1m",
        "8": "Continuous central turning lane",
        "9": "Flexible posts",
        "10": "Central hatching >1m",
        "11": "Centre line",
        "12": "Safety barrier - motorcycle friendly",
        "13": "One way",
        "14": "Wide centre line 0.3m to 1m",
        "15": "Safety barrier - wire rope",
    },
    "Lane width": {
        "1": "Wide >=3.25m",
        "2": "Medium 2.75m to <3.25m",
        "3": "Narrow 0m to <2.75m",
    },
    "Paved shoulder - drivers side": {
        "1": "Wide >=2.4m",
        "2": "Medium 1m to <2.4m",
        "3": "Narrow 0m to <1m",
        "4": "None",
    },
    "Paved shoulder - passenger side": {
        "1": "Wide >=2.4m",
        "2": "Medium 1m to <2.4m",
        "3": "Narrow 0m to <1m",
        "4": "None",
    },
    "Sidewalk - passenger side": {
        "1": "Sidewalk with barrier",
        "2": "Sidewalk >=3m from road",
        "3": "Sidewalk 1m to <3m from road",
        "4": "Sidewalk 0m to <1m from road",
        "5": "None",
        "6": "Informal path >=1m",
        "7": "Informal path 0m to <1m",
    },
    "Property access points": {
        "1": "Commercial access >=1",
        "2": "Residential access >=3",
        "3": "Residential access <3",
        "4": "None",
    },
    "Curvature": {
        "1": "Straight or gently curving",
        "2": "Moderate",
        "3": "Sharp",
        "4": "Very sharp",
    },
    "Sight distance": {"1": "Adequate", "2": "Poor"},
    "Roadside severity - driver side distance": {
        "1": "0 to <1m",
        "2": "1 to <5m",
        "3": "5 to <10m",
        "4": ">=10m",
    },
    "Roadside severity - passenger side distance": {
        "1": "0 to <1m",
        "2": "1 to <5m",
        "3": "5 to <10m",
        "4": ">=10m",
    },
    "Roadside severity - driver side object": {
        "10": "Cliff",
        "11": "Tree >=10cm",
        "12": "Rigid sign, post or pole >=10cm",
        "15": "Unprotected safety barrier end",
        "5": "Aggressive vertical face",
        "6": "Upwards slope - roll over",
        "8": "Deep drainage ditch",
        "9": "Downwards slope",
        "16": "Low rigid object >=20cm high",
        "13": "Rigid structure or building",
        "7": "Upwards slope - no roll over",
        "14": "Semi-rigid structure or building",
        "2": "Safety barrier - concrete",
        "1": "Safety barrier - metal",
        "4": "Safety barrier - wire rope",
        "3": "Safety barrier - motorcycle friendly",
        "17": "No object",
    },
    "Roadside severity - passenger side object": {
        "10": "Cliff",
        "11": "Tree >=10cm",
        "12": "Rigid sign, post or pole >=10cm",
        "15": "Unprotected safety barrier end",
        "5": "Aggressive vertical face",
        "6": "Upwards slope - roll over",
        "8": "Deep drainage ditch",
        "9": "Downwards slope",
        "16": "Low rigid object >=20cm high",
        "13": "Rigid structure or building",
        "7": "Upwards slope - no roll over",
        "14": "Semi-rigid structure or building",
        "2": "Safety barrier - concrete",
        "1": "Safety barrier - metal",
        "4": "Safety barrier - wire rope",
        "3": "Safety barrier - motorcycle friendly",
        "17": "No object",
    },
}


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def image_id(path: Path, dataset_root: Path) -> str:
    rel = path.relative_to(dataset_root).with_suffix("")
    safe = "_".join(rel.parts)
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in safe)


def list_images(dataset_root: Path) -> list[Path]:
    return sorted(
        (p for p in dataset_root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: p.relative_to(dataset_root).as_posix().lower(),
    )


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def folder_name(path: Path, dataset_root: Path) -> str:
    rel = path.relative_to(dataset_root)
    return rel.parts[0] if len(rel.parts) > 1 else ""


def build_prompt(image_path: Path, dataset_root: Path) -> str:
    rel_path = image_path.relative_to(dataset_root).as_posix()
    category_lines = []
    for attr in ATTRIBUTES:
        cats = "; ".join(f"{cid}: {cat}" for cid, cat in CATEGORIES[attr].items())
        category_lines.append(f"- {attr}: {cats}")
    return f"""Use only visible evidence from this image: {rel_path}

Code all 17 road attributes using the allowed categories. This local runner
approximates the zero-shot decision with image-processing evidence only.

Allowed categories:
{chr(10).join(category_lines)}
"""


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(stripped.lstrip())
        return obj


def validate_record(record: dict[str, Any]) -> list[str]:
    errors = []
    results = record.get("results", [])
    if len(results) != len(ATTRIBUTES):
        errors.append(f"expected {len(ATTRIBUTES)} attributes, got {len(results)}")
    seen = {r.get("attribute") for r in results}
    missing = [a for a in ATTRIBUTES if a not in seen]
    if missing:
        errors.append(f"missing attributes: {missing}")
    for result in results:
        attr = result.get("attribute")
        cat_id = str(result.get("cat_id"))
        category = result.get("category")
        if attr in CATEGORIES and cat_id not in CATEGORIES[attr]:
            errors.append(f"{attr}: invalid cat_id {cat_id}")
        elif attr in CATEGORIES and CATEGORIES[attr][cat_id] != category:
            errors.append(f"{attr}: cat_id/category mismatch {cat_id} != {category}")
    return errors


def ratio(mask: np.ndarray) -> float:
    return float(np.count_nonzero(mask)) / float(mask.size) if mask.size else 0.0


def region(arr: np.ndarray, y0: float, y1: float, x0: float, x1: float) -> np.ndarray:
    h, w = arr.shape[:2]
    return arr[int(h * y0): int(h * y1), int(w * x0): int(w * x1)]


def load_features(image_path: Path) -> dict[str, Any]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"cannot read image: {image_path}")
    img = cv2.resize(img, (640, 320), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    hue = hsv[:, :, 0]
    green = ((hue >= 35) & (hue <= 95) & (sat > 45) & (val > 35))
    pavement = (sat < 70) & (val > 45) & (val < 235)
    bright = val > 190
    white_mark = (sat < 45) & (val > 175)
    yellow_mark = (hue >= 18) & (hue <= 38) & (sat > 55) & (val > 110)
    marking = white_mark | yellow_mark

    edges = cv2.Canny(gray, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=30, maxLineGap=8)
    vertical_lines = 0
    slanted_lines = 0
    horizontal_lines = 0
    if lines is not None:
        for line in lines[:, 0, :]:
            x1, y1, x2, y2 = [int(v) for v in line]
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            angle = min(angle, 180 - angle)
            length = float(np.hypot(x2 - x1, y2 - y1))
            if length < 25:
                continue
            if angle > 70:
                vertical_lines += 1
            elif angle < 18:
                horizontal_lines += 1
            else:
                slanted_lines += 1

    lower = np.s_[160:320, :]
    mid_lower = np.s_[160:320, 160:480]
    center = np.s_[96:288, 224:416]
    left_side = np.s_[112:320, 0:224]
    right_side = np.s_[112:320, 416:640]
    far_left_lower = np.s_[176:320, 0:160]
    far_right_lower = np.s_[176:320, 480:640]

    return {
        "green_total": ratio(green),
        "green_left": ratio(green[left_side]),
        "green_right": ratio(green[right_side]),
        "green_center": ratio(green[center]),
        "pavement_lower": ratio(pavement[lower]),
        "pavement_center_lower": ratio(pavement[mid_lower]),
        "pavement_left": ratio(pavement[left_side]),
        "pavement_right": ratio(pavement[right_side]),
        "pavement_far_left": ratio(pavement[far_left_lower]),
        "pavement_far_right": ratio(pavement[far_right_lower]),
        "marking_lower": ratio(marking[lower]),
        "marking_center": ratio(marking[center]),
        "bright_upper": ratio(bright[:150, :]),
        "edge_density": ratio(edges),
        "vertical_lines": vertical_lines,
        "slanted_lines": slanted_lines,
        "horizontal_lines": horizontal_lines,
    }


def result(attribute: str, cat_id: int, confidence: float, evidence: str, note: str | None = None) -> dict[str, Any]:
    category = CATEGORIES[attribute][str(cat_id)]
    confidence = max(0.01, min(0.95, confidence))
    return {
        "attribute": attribute,
        "cat_id": cat_id,
        "category": category,
        "predicted_value": category,
        "confidence": round(confidence, 3),
        "evidence_summary": evidence,
        "measurement_note": note,
    }


def shoulder_code(pavement_ratio: float, side: str) -> tuple[int, float, str]:
    if pavement_ratio > 0.62:
        return 2, 0.42, f"{side} side has a broad paved-looking band outside the central road area."
    if pavement_ratio > 0.42:
        return 3, 0.38, f"{side} side has a narrow paved-looking edge band."
    return 4, 0.36, f"{side} side has limited paved shoulder evidence in the side region."


def roadside_pair(features: dict[str, Any], side: str) -> tuple[tuple[int, float, str], tuple[int, float, str]]:
    green_key = "green_right" if side == "driver" else "green_left"
    pave_key = "pavement_right" if side == "driver" else "pavement_left"
    green = features[green_key]
    paved = features[pave_key]
    if green > 0.24:
        return (
            (2, 0.4, f"{side} side vegetation/tree-colour mass is close to the road edge."),
            (11, 0.42, f"{side} side contains substantial vegetation likely to include trees or trunks."),
        )
    if paved > 0.58 and features["horizontal_lines"] > 8:
        return (
            (2, 0.36, f"{side} side has a near-road paved/linear roadside feature."),
            (1, 0.34, f"{side} side linear low feature is most consistent with a metal safety barrier."),
        )
    if paved > 0.5:
        return (
            (3, 0.32, f"{side} side has some roadside paved/rigid surface but weak fixed-object evidence."),
            (16, 0.28, f"{side} side low rigid object evidence is weak and image-only."),
        )
    return (
        (4, 0.34, f"{side} side has no strong close fixed-object evidence from local visual features."),
        (17, 0.36, f"{side} side lacks a clear roadside hazard candidate in the side region."),
    )


def classify(features: dict[str, Any]) -> list[dict[str, Any]]:
    urban_score = (1 - features["green_total"]) * 0.45 + min(features["edge_density"] * 8, 0.35) + min(features["vertical_lines"] / 80, 0.2)
    urban = urban_score > 0.47
    lighting = features["vertical_lines"] > 28 and features["bright_upper"] > 0.035
    service = (features["pavement_far_left"] > 0.58 or features["pavement_far_right"] > 0.58) and features["green_total"] < 0.32
    delineation = features["marking_lower"] > 0.012 or features["horizontal_lines"] + features["slanted_lines"] > 18

    road_width = features["pavement_center_lower"]
    if road_width > 0.78:
        lanes = 4
    elif road_width > 0.64:
        lanes = 2
    elif road_width > 0.45:
        lanes = 2
    else:
        lanes = 1

    if features["marking_center"] > 0.02 and road_width > 0.7:
        median = 14
        median_ev = "central bright marking and broad paved carriageway suggest a wide centre line."
    elif features["marking_center"] > 0.008:
        median = 11
        median_ev = "central bright marking suggests a centre line."
    elif road_width > 0.78:
        median = 13
        median_ev = "broad paved carriageway with weak opposing-flow marking evidence suggests one-way/divided context."
    else:
        median = 11
        median_ev = "centre-line category is the conservative undivided-road fallback from weak median evidence."

    lane_width = 1 if road_width > 0.75 and lanes <= 2 else 2 if road_width > 0.48 else 3
    driver_shoulder = shoulder_code(features["pavement_right"], "driver")
    passenger_shoulder = shoulder_code(features["pavement_left"], "passenger")

    if features["pavement_left"] > 0.58 and features["green_left"] < 0.22:
        sidewalk = (4, 0.33, "passenger side has a paved strip near the road edge.")
    elif features["green_left"] > 0.32 and features["pavement_left"] > 0.36:
        sidewalk = (7, 0.28, "passenger side has mixed vegetation and paved/path-like texture.")
    else:
        sidewalk = (5, 0.36, "passenger side lacks a continuous sidewalk/path signal.")

    if urban and (features["pavement_far_left"] > 0.5 or features["pavement_far_right"] > 0.5):
        access = (3, 0.32, "built-up/low-green scene with side paved areas suggests limited property access.")
    else:
        access = (4, 0.38, "no strong driveway or direct property-access visual signal from local features.")

    if features["slanted_lines"] > 36:
        curvature = (2, 0.34, "many slanted road/edge lines suggest some curvature or alignment change.")
    else:
        curvature = (1, 0.42, "dominant road-edge geometry is consistent with straight or gentle curvature.")

    sight_poor = features["green_center"] > 0.38 and features["edge_density"] > 0.07
    driver_dist, driver_obj = roadside_pair(features, "driver")
    passenger_dist, passenger_obj = roadside_pair(features, "passenger")

    return [
        result("Area type", 2 if urban else 1, 0.44 if urban else 0.46, f"green_total={features['green_total']:.3f}, edge_density={features['edge_density']:.3f}, vertical_lines={features['vertical_lines']}."),
        result("Street lighting", 2 if lighting else 1, 0.32 if lighting else 0.42, f"vertical_lines={features['vertical_lines']}, bright_upper={features['bright_upper']:.3f}; lamp evidence is heuristic."),
        result("Service road", 2 if service else 1, 0.31 if service else 0.41, f"far-side pavement ratios left/right={features['pavement_far_left']:.3f}/{features['pavement_far_right']:.3f}."),
        result("Delineation", 1 if delineation else 2, 0.45 if delineation else 0.36, f"marking_lower={features['marking_lower']:.3f}, detected line count={features['horizontal_lines'] + features['slanted_lines']}."),
        result("Number of lanes", lanes, 0.36 if lanes != 2 else 0.42, f"central lower pavement ratio={road_width:.3f}; lane count is visual heuristic."),
        result("Median Type", median, 0.34, median_ev),
        result("Lane width", lane_width, 0.34, f"central lower pavement ratio={road_width:.3f} with estimated lanes={lanes}.", "visual_estimate_no_lidar"),
        result("Paved shoulder - drivers side", driver_shoulder[0], driver_shoulder[1], driver_shoulder[2], "visual_estimate_no_lidar"),
        result("Paved shoulder - passenger side", passenger_shoulder[0], passenger_shoulder[1], passenger_shoulder[2], "visual_estimate_no_lidar"),
        result("Sidewalk - passenger side", sidewalk[0], sidewalk[1], sidewalk[2], "visual_estimate_no_lidar"),
        result("Property access points", access[0], access[1], access[2]),
        result("Curvature", curvature[0], curvature[1], curvature[2], "visual_estimate_no_trajectory"),
        result("Sight distance", 2 if sight_poor else 1, 0.31 if sight_poor else 0.39, f"center vegetation ratio={features['green_center']:.3f}, edge_density={features['edge_density']:.3f}.", "visual_estimate_no_trajectory"),
        result("Roadside severity - driver side distance", driver_dist[0], driver_dist[1], driver_dist[2], "visual_estimate_no_lidar"),
        result("Roadside severity - driver side object", driver_obj[0], driver_obj[1], driver_obj[2]),
        result("Roadside severity - passenger side distance", passenger_dist[0], passenger_dist[1], passenger_dist[2], "visual_estimate_no_lidar"),
        result("Roadside severity - passenger side object", passenger_obj[0], passenger_obj[1], passenger_obj[2]),
    ]


def code_image(image_path: Path, dataset_root: Path) -> dict[str, Any]:
    features = load_features(image_path)
    rel_path = image_path.relative_to(dataset_root).as_posix()
    record = {
        "segment_id": image_id(image_path, dataset_root),
        "folder_name": folder_name(image_path, dataset_root),
        "image_name": image_path.name,
        "image_path": rel_path,
        "method": METHOD,
        "model": MODEL,
        "ground_truth_used": False,
        "scene_summary": "Local keyless visual-heuristic zero-shot coding from image pixels.",
        "features": features,
        "prompt": build_prompt(image_path, dataset_root),
        "results": classify(features),
    }
    record["validation_errors"] = validate_record(record)
    return record


def load_results(results_path: Path) -> list[dict[str, Any]]:
    if not results_path.exists():
        return []
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return list(data.get("records", []))
    if isinstance(data, list):
        return data
    return []


def save_results(results_path: Path, records: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    payload = {"manifest": manifest, "record_count": len(records), "records": records}
    results_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def done_ids(records: list[dict[str, Any]]) -> set[str]:
    return {str(record.get("segment_id")) for record in records if record.get("segment_id")}


def attr_slug(attribute: str) -> str:
    return (
        attribute.lower()
        .replace(" - ", "_")
        .replace(" ", "_")
        .replace("/", "_")
        .replace(">=", "gte")
        .replace("<", "lt")
        .replace("-", "_")
    )


def write_wide_csv(records: list[dict[str, Any]], csv_path: Path) -> None:
    fieldnames = ["segment_id", "folder_name", "image_name", "image_path", "method", "model"]
    for attribute in ATTRIBUTES:
        slug = attr_slug(attribute)
        fieldnames.extend([f"{slug}_predicted_value", f"{slug}_confidence", f"{slug}_cat_id", f"{slug}_evidence"])

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {
                "segment_id": record.get("segment_id"),
                "folder_name": record.get("folder_name"),
                "image_name": record.get("image_name"),
                "image_path": record.get("image_path"),
                "method": record.get("method"),
                "model": record.get("model"),
            }
            by_attr = {result.get("attribute"): result for result in record.get("results", [])}
            for attribute in ATTRIBUTES:
                slug = attr_slug(attribute)
                attr_result = by_attr.get(attribute, {})
                row[f"{slug}_predicted_value"] = attr_result.get("predicted_value", attr_result.get("category"))
                row[f"{slug}_confidence"] = attr_result.get("confidence")
                row[f"{slug}_cat_id"] = attr_result.get("cat_id")
                row[f"{slug}_evidence"] = attr_result.get("evidence_summary", "")
            writer.writerow(row)


def write_irap_code_tables(records: list[dict[str, Any]], out_dir: Path) -> None:
    codes_csv = out_dir / "predicted_irap_codes.csv"
    detailed_csv = out_dir / "predicted_irap_codes_with_categories_confidence.csv"
    long_csv = out_dir / "predicted_irap_codes_long.csv"
    summary_path = out_dir / "prediction_export_summary.json"

    code_fields = ["segment_id", "folder_name", "image_name", "image_path", "model", "method"] + [
        f"pred_{slug}_cat_id" for _, slug in IRAP_EXPORT_ATTRIBUTES
    ]
    detail_fields = ["segment_id", "folder_name", "image_name", "image_path", "model", "method"]
    for _, slug in IRAP_EXPORT_ATTRIBUTES:
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
                "folder_name",
                "image_name",
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
            base = {
                "segment_id": record.get("segment_id"),
                "folder_name": record.get("folder_name"),
                "image_name": record.get("image_name"),
                "image_path": record.get("image_path"),
                "model": record.get("model"),
                "method": record.get("method"),
            }
            by_attr = {result.get("attribute"): result for result in record.get("results", [])}
            code_row = dict(base)
            detail_row = dict(base)
            for attribute, slug in IRAP_EXPORT_ATTRIBUTES:
                attr_result = by_attr.get(attribute, {})
                cat_id = attr_result.get("cat_id")
                category = attr_result.get("category")
                confidence = attr_result.get("confidence")
                code_row[f"pred_{slug}_cat_id"] = cat_id
                detail_row[f"pred_{slug}_cat_id"] = cat_id
                detail_row[f"pred_{slug}_category"] = category
                detail_row[f"pred_{slug}_confidence"] = confidence
                long_writer.writerow(
                    {
                        **base,
                        "attribute": attribute,
                        "predicted_cat_id": cat_id,
                        "predicted_category": category,
                        "confidence": confidence,
                        "evidence_summary": attr_result.get("evidence_summary", ""),
                        "measurement_note": attr_result.get("measurement_note"),
                    }
                )
            code_writer.writerow(code_row)
            detail_writer.writerow(detail_row)

    summary = {
        "ground_truth_used": False,
        "external_api_used": False,
        "record_count": len(records),
        "attribute_count": len(IRAP_EXPORT_ATTRIBUTES),
        "wide_codes_csv": str(codes_csv),
        "wide_detailed_csv": str(detailed_csv),
        "long_csv": str(long_csv),
        "compare_script_compatible": "scripts/compare_zero_shot_predictions_to_gt.py",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_progress(records: list[dict[str, Any]], out_dir: Path, manifest: dict[str, Any]) -> None:
    save_results(out_dir / "results.json", records, manifest)
    write_wide_csv(records, out_dir / "zero_shot_17_attribute_wide.csv")
    write_irap_code_tables(records, out_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="Dataset-images-only")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    out_dir = Path(args.out_dir or Path("artifacts") / args.run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = list_images(dataset_root)
    if args.limit is not None:
        images = images[: args.limit]

    manifest = {
        "run_id": args.run_id,
        "method": METHOD,
        "model": MODEL,
        "created_date": datetime.now().isoformat(timespec="seconds"),
        "dataset_root": str(dataset_root),
        "ground_truth_used": False,
        "external_api_used": False,
        "api_key_required": False,
        "image_count": len(images),
        "folder_counts": {
            folder: sum(1 for p in images if folder_name(p, dataset_root) == folder)
            for folder in sorted({folder_name(p, dataset_root) for p in images})
        },
        "attributes": ATTRIBUTES,
        "outputs": {
            "wide_csv": str(out_dir / "zero_shot_17_attribute_wide.csv"),
            "results_json": str(out_dir / "results.json"),
        },
        "runtime_note": "Keyless local visual heuristic baseline; no external API and no ground truth labels used.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Run ID: {args.run_id}")
    print(f"Images selected: {len(images)}")
    print(f"Output directory: {out_dir}")

    if args.dry_run:
        print("Dry run complete. No images processed.")
        return 0

    records = [] if args.no_resume else load_results(out_dir / "results.json")
    processed = done_ids(records)

    for idx, image_path in enumerate(images, start=1):
        segment_id = image_id(image_path, dataset_root)
        if segment_id in processed:
            print(f"[{idx}/{len(images)}] skip existing {segment_id}", flush=True)
            continue
        try:
            record = code_image(image_path, dataset_root)
            records.append(record)
            processed.add(segment_id)
            print(f"[{idx}/{len(images)}] saved {segment_id}", flush=True)
        except Exception as exc:
            print(f"[{idx}/{len(images)}] ERROR {segment_id}: {type(exc).__name__}: {exc}", flush=True)
        finally:
            write_progress(records, out_dir, manifest)

    write_progress(records, out_dir, manifest)
    print(f"Wide CSV: {out_dir / 'zero_shot_17_attribute_wide.csv'}")
    print(f"iRAP code CSV: {out_dir / 'predicted_irap_codes.csv'}")
    print(f"Detailed iRAP CSV: {out_dir / 'predicted_irap_codes_with_categories_confidence.csv'}")
    print(f"Long iRAP CSV: {out_dir / 'predicted_irap_codes_long.csv'}")
    print(f"Results JSON: {out_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
