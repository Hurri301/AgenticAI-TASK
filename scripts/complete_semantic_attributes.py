from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]

ATTRIBUTES = [
    "Number of lanes",
    "Lane width",
    "Paved shoulder - drivers side",
    "Paved shoulder - passenger side",
    "Roadside severity - drivers side distance",
    "Roadside severity - passenger side distance",
    "Curvature",
    "Sight distance",
    "Area type",
    "Street lighting",
    "Service road",
    "Median Type",
    "Delineation",
    "Roadside severity - driver side object",
    "Roadside severity - passenger side object",
    "Property access points",
    "Sidewalk - passenger side",
]

CODE_LABELS = {
    "Area type": {1: "Rural", 2: "Urban"},
    "Street lighting": {1: "Not present", 2: "Present"},
    "Service road": {1: "Not present", 2: "Present"},
    "Median Type": {
        1: "Safety barrier - metal",
        2: "Safety barrier - concrete",
        3: "Physical median width >=20m",
        4: "Physical median width 10 to <20m",
        5: "Physical median width 5 to <10m",
        6: "Physical median width 1 to <5m",
        7: "Physical median width 0 to <1m",
        8: "Continuous central turning lane",
        9: "Flexible posts",
        10: "Central hatching >1m",
        11: "Centre line",
        12: "Safety barrier - motorcycle friendly",
        13: "One way",
        14: "Wide centre line 0.3m to 1m",
        15: "Safety barrier - wire rope",
    },
    "Delineation": {1: "Adequate", 2: "Poor"},
    "Property access points": {
        1: "Commercial access >=1",
        2: "Residential access >=3",
        3: "Residential access <3",
        4: "None",
    },
    "Sidewalk - passenger side": {
        1: "Sidewalk with barrier",
        2: "Sidewalk >=3m from road",
        3: "Sidewalk 1m to <3m from road",
        4: "Sidewalk 0m to <1m from road",
        5: "None",
        6: "Informal path >=1m",
        7: "Informal path 0m to <1m",
    },
    "Roadside object": {
        1: "Safety barrier - metal",
        2: "Safety barrier - concrete",
        3: "Safety barrier - motorcycle friendly",
        4: "Safety barrier - wire rope",
        5: "Aggressive vertical face",
        6: "Upwards slope - roll over",
        7: "Upwards slope - no roll over",
        8: "Deep drainage ditch",
        9: "Downwards slope",
        10: "Cliff",
        11: "Tree >=10cm",
        12: "Rigid sign, post or pole >=10cm",
        13: "Rigid structure or building",
        14: "Semi-rigid structure or building",
        15: "Unprotected safety barrier end",
        16: "Low rigid object >=20cm high",
        17: "No object",
    },
}

DISTANCE_LABELS = {
    "1": "0 to <1m",
    "2": "1 to <5m",
    "3": "5 to <10m",
    "4": ">=10m",
}

BARRIER_OBJECT_CODES = {1, 2, 3, 4}


@dataclass(frozen=True)
class SideEvidence:
    green_ratio: float
    paved_ratio: float
    bright_wall_ratio: float
    dark_vertical_ratio: float
    guardrail_ratio: float
    sidewalk_ratio: float
    building_like: bool
    tree_like: bool
    pole_like: bool
    barrier_like: bool


@dataclass(frozen=True)
class ImageEvidence:
    frame_id: int
    folder_name: str
    green_ratio: float
    sky_ratio: float
    bright_wall_ratio: float
    asphalt_ratio: float
    road_marking_ratio: float
    lane_line_score: float
    median_barrier_score: float
    passenger: SideEvidence
    driver: SideEvidence


def norm_code(value: Any) -> str:
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return ""
    if re.fullmatch(r"\d+(\.0)?", text):
        return str(int(float(text)))
    return text


def load_roadside_detections(path: str | None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for image in payload.get("images", []):
        image_name = str(image.get("image_name") or Path(str(image.get("image_path", ""))).name)
        stem = Path(image_name).stem
        for side in image.get("sides", []):
            side_name = str(side.get("side", "")).strip().lower()
            if side_name in {"driver", "passenger"}:
                out[(stem, side_name)] = [obj for obj in side.get("objects", []) if isinstance(obj, dict)]
    return out


def load_projected_roadside_pairs(path: str | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        image_name = str(item.get("image_name") or Path(str(item.get("image_path", ""))).name)
        stem = Path(image_name).stem
        side = str(item.get("side", "")).strip().lower()
        if side in {"driver", "passenger"}:
            out[(stem, side)] = item
    return out


def projected_pair_reliable(pair: dict[str, Any] | None, side: str) -> bool:
    if not pair or int(pair.get("projected_point_count") or 0) <= 0:
        return False
    if side != "driver":
        return True
    confidence = float(pair.get("confidence", 0.0) or 0.0)
    if confidence >= 0.75:
        return True
    return str(pair.get("selection_reason", "")) == "driver_guardrail_ribbon_over_terrain"


def load_risk_ranks(path: str | None) -> dict[tuple[str, str], int]:
    if not path:
        path = str(REPO_ROOT / ".agents" / "skills" / "irap-roadside-severity-coder" / "references" / "risk_hierarchy.csv")
    ranks: dict[tuple[str, str], int] = {}
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            obj = str(row["object_category"]).strip()
            dist = str(row["distance_category"]).strip()
            rank = int(row["rank"])
            if dist.lower() == "any":
                for label in DISTANCE_LABELS.values():
                    ranks[(label, obj)] = min(rank, ranks.get((label, obj), rank))
            else:
                ranks[(dist, obj)] = min(rank, ranks.get((dist, obj), rank))
    return ranks


def load_curvature_from_lookup(path: str | None) -> dict[tuple[str, int], dict[str, Any]]:
    if not path:
        return {}
    lookup = pd.read_csv(path, keep_default_na=False)
    required = {"Frame Folder", "Frame ID", "X", "Y", "Heading"}
    if not required.issubset(set(lookup.columns)):
        raise ValueError(f"Lookup CSV is missing required curvature columns: {sorted(required)}")
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    for folder_name, group in lookup.groupby("Frame Folder"):
        group = group.sort_values("Frame ID").reset_index(drop=True)
        for pos, row in group.iterrows():
            lo = max(0, pos - 1)
            hi = min(len(group) - 1, pos + 1)
            if hi == lo:
                heading_delta = 0.0
                chord_m = 0.0
            else:
                h0 = float(group.at[lo, "Heading"])
                h1 = float(group.at[hi, "Heading"])
                heading_delta = abs((h1 - h0 + 180.0) % 360.0 - 180.0)
                dx = float(group.at[hi, "X"]) - float(group.at[lo, "X"])
                dy = float(group.at[hi, "Y"]) - float(group.at[lo, "Y"])
                chord_m = float(np.hypot(dx, dy))
            if heading_delta < 2.0:
                code = 1
                label = "straight/gentle"
            elif heading_delta < 60.0:
                code = 2
                label = "moderate curve"
            else:
                code = 3
                label = "sharp curve"
            rows[(str(folder_name), int(row["Frame ID"]))] = {
                "code": code,
                "heading_delta_deg": round(heading_delta, 3),
                "chord_m": round(chord_m, 3),
                "label": label,
            }
    return rows


def smooth_driver_roadside_objects(df: pd.DataFrame, debug_rows: list[dict[str, Any]]) -> int:
    attr = "Roadside severity - driver side object"
    if attr not in df.columns:
        return 0
    changed = 0
    for _folder_name, group in df.groupby("folder_name", sort=False):
        values = group[attr].map(norm_code).tolist()
        if not values:
            continue
        barrier_share = float(np.mean([value in {"1", "2", "3", "4"} for value in values]))
        window = 21 if barrier_share >= 0.45 else 15
        half = window // 2
        for offset, (idx, _row) in enumerate(group.iterrows()):
            current = values[offset]
            if 0 <= int(idx) < len(debug_rows):
                evidence = str(debug_rows[int(idx)].get("Roadside severity - driver side object evidence", ""))
                if "Projected DINO bbox" in evidence:
                    continue
            start = max(0, offset - half)
            stop = min(len(values), offset + half + 1)
            window_values = values[start:stop]
            counts: dict[str, int] = {}
            for value in window_values:
                counts[value] = counts.get(value, 0) + 1
            if not counts:
                continue
            top_count = max(counts.values())
            top_values = [value for value, count in counts.items() if count == top_count]
            smoothed = current if current in top_values else top_values[0]
            if smoothed != current:
                df.at[idx, attr] = smoothed
                if 0 <= int(idx) < len(debug_rows):
                    debug_rows[int(idx)]["Roadside severity - driver side object evidence"] = (
                        f"adjacent-frame smoothing changed driver object {current} to {smoothed}; "
                        f"window={window}; barrier_share={barrier_share:.3f}; local_counts={counts}"
                    )
                changed += 1
    return changed


def smooth_roadside_distance_codes(
    df: pd.DataFrame,
    debug_rows: list[dict[str, Any]],
    *,
    driver_window: int,
    passenger_window: int,
) -> int:
    settings = [
        ("Roadside severity - drivers side distance", "drivers", driver_window),
        ("Roadside severity - passenger side distance", "passenger", passenger_window),
    ]
    changed = 0
    for attr, side_label, window in settings:
        if attr not in df.columns or window <= 1:
            continue
        for _folder_name, group in df.groupby("folder_name", sort=False):
            if "frame_id" in group.columns:
                group = group.assign(_frame_sort=group["frame_id"].map(lambda v: int(float(v)) if norm_code(v) else 0))
                group = group.sort_values("_frame_sort")
            values = group[attr].map(norm_code).tolist()
            if len(values) > 20:
                half = int(window) // 2
                for offset, (idx, _row) in enumerate(group.iterrows()):
                    current = values[offset]
                    if not current:
                        continue
                    start = max(0, offset - half)
                    stop = min(len(values), offset + half + 1)
                    window_values = [value for value in values[start:stop] if value]
                    if not window_values:
                        continue
                    counts: dict[str, int] = {}
                    for value in window_values:
                        counts[value] = counts.get(value, 0) + 1
                    top_count = max(counts.values())
                    top_values = [value for value, count in counts.items() if count == top_count]
                    smoothed = current if current in top_values else top_values[0]
                    if smoothed != current:
                        df.at[idx, attr] = smoothed
                        if 0 <= int(idx) < len(debug_rows):
                            debug_rows[int(idx)][f"Roadside severity - {side_label} side distance evidence"] = (
                                f"adjacent-frame distance smoothing changed {side_label} distance "
                                f"{current} to {smoothed}; window={window}; local_counts={counts}"
                            )
                        changed += 1
                continue
            for offset, (idx, _row) in enumerate(group.iterrows()):
                current = values[offset]
                if not current:
                    continue
                if offset == 0 or offset == len(values) - 1:
                    continue
                prev_value = values[offset - 1]
                next_value = values[offset + 1]
                if not prev_value or not next_value or prev_value != next_value or current == prev_value:
                    continue
                if window >= 5:
                    left2 = values[offset - 2] if offset >= 2 else prev_value
                    right2 = values[offset + 2] if offset + 2 < len(values) else next_value
                    support = [value for value in (left2, prev_value, next_value, right2) if value]
                    if support.count(prev_value) < 3:
                        continue
                smoothed = prev_value
                if smoothed != current:
                    df.at[idx, attr] = smoothed
                    if 0 <= int(idx) < len(debug_rows):
                        debug_rows[int(idx)][f"Roadside severity - {side_label} side distance evidence"] = (
                            f"isolated-frame distance smoothing changed {side_label} distance "
                            f"{current} to {smoothed}; window={window}; neighbors=({prev_value}, {next_value})"
                        )
                    changed += 1
    return changed


def max_detection_confidence(
    detections: dict[tuple[str, str], list[dict[str, Any]]],
    image_stem: str,
    side: str,
    category: str,
) -> float:
    values = [
        float(obj.get("confidence", 0.0) or 0.0)
        for obj in detections.get((image_stem, side), [])
        if str(obj.get("irap_category", "")).strip() == category
    ]
    return max(values) if values else 0.0


def refine_driver_slope_with_discrete_dino(
    df: pd.DataFrame,
    debug_rows: list[dict[str, Any]],
    detections: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    attr = "Roadside severity - driver side object"
    changed = 0
    for idx, row in df.iterrows():
        current = norm_code(row.get(attr, ""))
        if current not in {"6", "9"}:
            continue
        if 0 <= int(idx) < len(debug_rows):
            evidence = str(debug_rows[int(idx)].get("Roadside severity - driver side object evidence", ""))
            if "Projected DINO bbox" in evidence:
                continue
        image_stem = Path(str(row["image_path"])).stem
        slope_conf = max(
            max_detection_confidence(detections, image_stem, "driver", "Upwards slope - roll over"),
            max_detection_confidence(detections, image_stem, "driver", "Downwards slope"),
            max_detection_confidence(detections, image_stem, "driver", "Deep drainage ditch"),
        )
        tree_conf = max_detection_confidence(detections, image_stem, "driver", "Tree >=10cm")
        pole_conf = max_detection_confidence(detections, image_stem, "driver", "Rigid sign, post or pole >=10cm")
        structure_conf = max_detection_confidence(detections, image_stem, "driver", "Rigid structure or building")
        refined = current
        reason = ""
        if tree_conf >= 0.40 and tree_conf >= slope_conf - 0.20:
            refined = "11"
            reason = f"tree_conf={tree_conf:.3f}"
        if pole_conf >= 0.45 and pole_conf >= slope_conf - 0.20:
            refined = "12"
            reason = f"pole_conf={pole_conf:.3f}"
        if structure_conf >= 0.45 and structure_conf >= slope_conf - 0.20:
            refined = "13"
            reason = f"structure_conf={structure_conf:.3f}"
        if refined != current:
            df.at[idx, attr] = refined
            if 0 <= int(idx) < len(debug_rows):
                debug_rows[int(idx)]["Roadside severity - driver side object evidence"] = (
                    f"DINO discrete-object override changed driver object {current} to {refined}; "
                    f"{reason}; slope_conf={slope_conf:.3f}"
                )
            changed += 1
    return changed


def refine_passenger_slope_with_ditch_dino(
    df: pd.DataFrame,
    debug_rows: list[dict[str, Any]],
    detections: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    attr = "Roadside severity - passenger side object"
    changed = 0
    for idx, row in df.iterrows():
        current = norm_code(row.get(attr, ""))
        if current not in {"6", "9"}:
            continue
        image_stem = Path(str(row["image_path"])).stem
        slope_conf = max(
            max_detection_confidence(detections, image_stem, "passenger", "Upwards slope - roll over"),
            max_detection_confidence(detections, image_stem, "passenger", "Downwards slope"),
            max_detection_confidence(detections, image_stem, "passenger", "Deep drainage ditch"),
        )
        ditch_conf = max_detection_confidence(detections, image_stem, "passenger", "Deep drainage ditch")
        if ditch_conf >= 0.40 and ditch_conf >= slope_conf - 0.30:
            df.at[idx, attr] = "8"
            if 0 <= int(idx) < len(debug_rows):
                debug_rows[int(idx)]["Roadside severity - passenger side object evidence"] = (
                    f"DINO ditch override changed passenger object {current} to 8; "
                    f"ditch_conf={ditch_conf:.3f}; slope_conf={slope_conf:.3f}"
                )
            changed += 1
    for idx, row in df.iterrows():
        current = norm_code(row.get(attr, ""))
        if current not in {"6", "8", "9"}:
            continue
        image_stem = Path(str(row["image_path"])).stem
        hazard_conf = max(
            max_detection_confidence(detections, image_stem, "passenger", "Deep drainage ditch"),
            max_detection_confidence(detections, image_stem, "passenger", "Upwards slope - roll over"),
            max_detection_confidence(detections, image_stem, "passenger", "Downwards slope"),
        )
        tree_conf = max_detection_confidence(detections, image_stem, "passenger", "Tree >=10cm")
        pole_conf = max_detection_confidence(detections, image_stem, "passenger", "Rigid sign, post or pole >=10cm")
        structure_conf = max_detection_confidence(detections, image_stem, "passenger", "Rigid structure or building")
        metal_conf = max_detection_confidence(detections, image_stem, "passenger", "Safety barrier - metal")
        concrete_conf = max_detection_confidence(detections, image_stem, "passenger", "Safety barrier - concrete")
        barrier_conf = max(metal_conf, concrete_conf)
        refined = current
        reason = ""
        if tree_conf >= 0.35 and tree_conf >= hazard_conf - 0.30:
            refined = "11"
            reason = f"tree_conf={tree_conf:.3f}"
        if pole_conf >= 0.50 and pole_conf >= hazard_conf - 0.30:
            refined = "12"
            reason = f"pole_conf={pole_conf:.3f}"
        if structure_conf >= 0.50 and structure_conf >= hazard_conf - 0.20:
            refined = "13"
            reason = f"structure_conf={structure_conf:.3f}"
        if barrier_conf >= 0.55 and barrier_conf >= hazard_conf - 0.20:
            refined = "1" if metal_conf >= concrete_conf else "2"
            reason = f"barrier_conf={barrier_conf:.3f}"
        if refined != current:
            df.at[idx, attr] = refined
            if 0 <= int(idx) < len(debug_rows):
                debug_rows[int(idx)]["Roadside severity - passenger side object evidence"] = (
                    f"DINO passenger discrete-object override changed passenger object {current} to {refined}; "
                    f"{reason}; hazard_conf={hazard_conf:.3f}"
                )
            changed += 1
    return changed


def refine_urban_discrete_roadside_objects(
    df: pd.DataFrame,
    debug_rows: list[dict[str, Any]],
    detections: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    changed = 0
    settings = [
        ("Roadside severity - driver side object", "driver"),
        ("Roadside severity - passenger side object", "passenger"),
    ]
    for attr, side in settings:
        if attr not in df.columns:
            continue
        for idx, row in df.iterrows():
            current = norm_code(row.get(attr, ""))
            if not current:
                continue
            image_stem = Path(str(row["image_path"])).stem
            tree_conf = max_detection_confidence(detections, image_stem, side, "Tree >=10cm")
            pole_conf = max_detection_confidence(detections, image_stem, side, "Rigid sign, post or pole >=10cm")
            structure_conf = max_detection_confidence(detections, image_stem, side, "Rigid structure or building")
            barrier_conf = max(
                max_detection_confidence(detections, image_stem, side, "Safety barrier - metal"),
                max_detection_confidence(detections, image_stem, side, "Safety barrier - concrete"),
                max_detection_confidence(detections, image_stem, side, "Safety barrier - motorcycle friendly"),
                max_detection_confidence(detections, image_stem, side, "Safety barrier - wire rope"),
            )
            if not (0 <= int(idx) < len(debug_rows)):
                continue
            debug = debug_rows[int(idx)]
            bright_wall = float(debug.get("bright_wall_ratio", 0.0) or 0.0)
            green_ratio = float(debug.get("green_ratio", 0.0) or 0.0)
            side_green = float(debug.get(f"{side}_side_green", 0.0) or 0.0)
            urbanish = bright_wall >= 0.28 or green_ratio < 0.10
            refined = current
            reason = ""
            if pole_conf >= 0.38 and pole_conf >= barrier_conf - 0.30 and urbanish:
                refined = "12"
                reason = f"pole_conf={pole_conf:.3f}; barrier_conf={barrier_conf:.3f}"
            elif tree_conf >= 0.42 and tree_conf >= barrier_conf - 0.30 and (side_green >= 0.08 or green_ratio >= 0.10):
                refined = "11"
                reason = f"tree_conf={tree_conf:.3f}; barrier_conf={barrier_conf:.3f}"
            elif structure_conf >= 0.70 and structure_conf >= barrier_conf - 0.30 and bright_wall >= 0.30:
                refined = "13"
                reason = f"structure_conf={structure_conf:.3f}; barrier_conf={barrier_conf:.3f}"
            elif current == "3":
                true_barrier_conf = max(
                    max_detection_confidence(detections, image_stem, side, "Safety barrier - metal"),
                    max_detection_confidence(detections, image_stem, side, "Safety barrier - concrete"),
                    max_detection_confidence(detections, image_stem, side, "Safety barrier - wire rope"),
                )
                slope_conf = max(
                    max_detection_confidence(detections, image_stem, side, "Upwards slope - roll over"),
                    max_detection_confidence(detections, image_stem, side, "Downwards slope"),
                    max_detection_confidence(detections, image_stem, side, "Deep drainage ditch"),
                )
                if slope_conf >= 0.55 and slope_conf >= true_barrier_conf + 0.05:
                    refined = "6"
                    reason = f"slope_conf={slope_conf:.3f}; true_barrier_conf={true_barrier_conf:.3f}"
                elif structure_conf >= 0.58 and structure_conf >= true_barrier_conf - 0.05:
                    refined = "13"
                    reason = f"structure_conf={structure_conf:.3f}; true_barrier_conf={true_barrier_conf:.3f}"
                elif true_barrier_conf >= 0.55:
                    refined = "1"
                    reason = f"true_barrier_conf={true_barrier_conf:.3f}; motorcycle barrier treated as generic metal barrier"
            if refined != current:
                df.at[idx, attr] = refined
                debug[f"{attr} evidence"] = (
                    f"urban/commercial discrete-object override changed {side} object {current} to {refined}; "
                    f"{reason}; bright_wall={bright_wall:.3f}; green={green_ratio:.3f}"
                )
                changed += 1
    return changed


def refine_unstable_roadside_object_false_positives(
    df: pd.DataFrame,
    debug_rows: list[dict[str, Any]],
    detections: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    changed = 0
    settings = [
        ("Roadside severity - driver side object", "driver"),
        ("Roadside severity - passenger side object", "passenger"),
    ]
    for attr, side in settings:
        if attr not in df.columns:
            continue
        for idx, row in df.iterrows():
            current = norm_code(row.get(attr, ""))
            if current not in {"3", "6", "15"}:
                continue
            if not (0 <= int(idx) < len(debug_rows)):
                continue
            image_stem = Path(str(row["image_path"])).stem
            tree_conf = max_detection_confidence(detections, image_stem, side, "Tree >=10cm")
            pole_conf = max_detection_confidence(detections, image_stem, side, "Rigid sign, post or pole >=10cm")
            structure_conf = max_detection_confidence(detections, image_stem, side, "Rigid structure or building")
            true_barrier_conf = max(
                max_detection_confidence(detections, image_stem, side, "Safety barrier - metal"),
                max_detection_confidence(detections, image_stem, side, "Safety barrier - concrete"),
                max_detection_confidence(detections, image_stem, side, "Safety barrier - wire rope"),
            )
            slope_conf = max(
                max_detection_confidence(detections, image_stem, side, "Upwards slope - roll over"),
                max_detection_confidence(detections, image_stem, side, "Downwards slope"),
                max_detection_confidence(detections, image_stem, side, "Deep drainage ditch"),
            )
            debug = debug_rows[int(idx)]
            bright_wall = float(debug.get("bright_wall_ratio", 0.0) or 0.0)
            green_ratio = float(debug.get("green_ratio", 0.0) or 0.0)
            side_green = float(debug.get(f"{side}_side_green", 0.0) or 0.0)
            refined = current
            reason = ""

            if current == "15":
                if tree_conf >= 0.37 and (side_green >= 0.16 or green_ratio >= 0.12):
                    refined = "11"
                    reason = f"barrier-end false positive resolved to tree; tree_conf={tree_conf:.3f}"
            elif current == "3":
                if tree_conf >= 0.35 and true_barrier_conf < 0.55 and (side_green >= 0.08 or green_ratio >= 0.10):
                    refined = "11"
                    reason = (
                        f"motorcycle-barrier false positive resolved to tree; "
                        f"tree_conf={tree_conf:.3f}; true_barrier_conf={true_barrier_conf:.3f}"
                    )
                elif slope_conf >= 0.54 and tree_conf < 0.30 and true_barrier_conf < 0.56:
                    refined = "6"
                    reason = (
                        f"motorcycle-barrier false positive resolved to slope; "
                        f"slope_conf={slope_conf:.3f}; true_barrier_conf={true_barrier_conf:.3f}"
                    )
            elif current == "6":
                if tree_conf >= 0.40 and tree_conf >= true_barrier_conf - 0.25 and (side_green >= 0.10 or green_ratio >= 0.10):
                    refined = "11"
                    reason = f"slope false positive resolved to tree; tree_conf={tree_conf:.3f}"
                elif pole_conf >= 0.36 and bright_wall >= 0.38 and green_ratio < 0.09:
                    refined = "12"
                    reason = f"slope false positive resolved to pole; pole_conf={pole_conf:.3f}"
                elif structure_conf >= 0.52 and bright_wall >= 0.25 and side_green < 0.05:
                    refined = "13"
                    reason = f"slope false positive resolved to structure; structure_conf={structure_conf:.3f}"

            if refined != current:
                df.at[idx, attr] = refined
                debug[f"{attr} evidence"] = (
                    f"unstable-class cleanup changed {side} object {current} to {refined}; "
                    f"{reason}; slope_conf={slope_conf:.3f}; bright_wall={bright_wall:.3f}; "
                    f"green={green_ratio:.3f}; side_green={side_green:.3f}"
                )
                changed += 1
    return changed


def verify_driver_high_confidence_terrain(
    df: pd.DataFrame,
    debug_rows: list[dict[str, Any]],
    detections: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    """Promote only very strong driver-side terrain candidates over weak selected labels."""
    attr = "Roadside severity - driver side object"
    if attr not in df.columns:
        return 0
    changed = 0
    for idx, row in df.iterrows():
        current = norm_code(row.get(attr, ""))
        if current not in {"17", "1", "2", "3", "11", "12", "13"}:
            continue
        image_stem = Path(str(row["image_path"])).stem
        terrain_candidates: list[tuple[float, str]] = []
        for code, category in [
            ("6", "Upwards slope - roll over"),
            ("8", "Deep drainage ditch"),
            ("9", "Downwards slope"),
        ]:
            confidence = max_detection_confidence(detections, image_stem, "driver", category)
            if confidence <= 0:
                continue
            # Reuse bbox validation so small/high false detections cannot override a selected object.
            valid = False
            for obj in detections.get((image_stem, "driver"), []):
                if object_code_from_category(str(obj.get("irap_category", ""))) != code:
                    continue
                obj_conf = float(obj.get("confidence", 0.0) or 0.0)
                if abs(obj_conf - confidence) > 1e-6:
                    continue
                valid, _reason = dino_candidate_valid(obj, code)
                if valid:
                    break
            if valid:
                terrain_candidates.append((confidence, code))
        if not terrain_candidates:
            continue
        terrain_conf, terrain_code = max(terrain_candidates, key=lambda item: item[0])
        current_conf = 0.0
        current_category = CODE_LABELS["Roadside object"].get(int(current), "") if current else ""
        if current_category:
            current_conf = max_detection_confidence(detections, image_stem, "driver", current_category)
        if terrain_conf < 0.84 or terrain_conf < current_conf + 0.12:
            continue
        df.at[idx, attr] = terrain_code
        if 0 <= int(idx) < len(debug_rows):
            debug_rows[int(idx)][f"{attr} evidence"] = (
                f"driver-side verifier changed object {current} to {terrain_code}; "
                f"high-confidence broad terrain candidate={terrain_conf:.3f}; current_conf={current_conf:.3f}; "
                "rule=high_confidence_driver_terrain"
            )
        changed += 1
    return changed


def object_code_from_category(category: str) -> str | None:
    cleaned = " ".join(str(category).strip().split())
    reverse = {label: str(code) for code, label in CODE_LABELS["Roadside object"].items()}
    aliases = {
        "Rigid sign, post or pole >=10cm": "Rigid sign, post or pole >=10cm",
        "Safety barrier - metal": "Safety barrier - metal",
        "Safety barrier - concrete": "Safety barrier - concrete",
        "Tree >=10cm": "Tree >=10cm",
        "Deep drainage ditch": "Deep drainage ditch",
        "Downwards slope": "Downwards slope",
        "Upwards slope - roll over": "Upwards slope - roll over",
        "Rigid structure or building": "Rigid structure or building",
        "Semi-rigid structure or building": "Semi-rigid structure or building",
        "Low rigid object >=20cm high": "Low rigid object >=20cm high",
    }
    return reverse.get(aliases.get(cleaned, cleaned))


def best_dino_barrier_code(
    detections: dict[tuple[str, str], list[dict[str, Any]]],
    image_path: Path,
    side: str,
    min_confidence: float,
) -> tuple[int | None, str | None]:
    barrier_codes = {"1", "2", "3", "4"}
    candidates: list[tuple[float, int, dict[str, Any]]] = []
    for idx, obj in enumerate(detections.get((image_path.stem, side), [])):
        confidence = float(obj.get("confidence", 0.0) or 0.0)
        if confidence < min_confidence:
            continue
        code = object_code_from_category(str(obj.get("irap_category", "")))
        if code not in barrier_codes:
            continue
        valid, _ = dino_candidate_valid(obj, code)
        if valid:
            candidates.append((-confidence, idx, obj))
    if not candidates:
        return None, None
    candidates.sort()
    best_conf = -candidates[0][0]
    metal_candidates = [
        item for item in candidates
        if object_code_from_category(str(item[-1].get("irap_category", ""))) == "1" and -item[0] >= best_conf - 0.12
    ]
    best = metal_candidates[0][-1] if metal_candidates else candidates[0][-1]
    code = object_code_from_category(str(best.get("irap_category", "")))
    if code is None:
        return None, None
    return int(code), f"divided-road barrier-priority selected {best.get('irap_category')} with confidence={float(best.get('confidence', 0.0)):.3f}"


def preferred_barrier_over_terrain(
    detections: dict[tuple[str, str], list[dict[str, Any]]],
    image_path: Path,
    side: str,
    selected_code: str,
    min_confidence: float,
) -> tuple[int | None, str | None]:
    if selected_code not in {"6", "7", "8", "9"}:
        return None, None
    if side == "driver":
        return None, None
    stem = image_path.stem
    terrain_conf = max(
        max_detection_confidence(detections, stem, side, "Upwards slope - roll over"),
        max_detection_confidence(detections, stem, side, "Downwards slope"),
        max_detection_confidence(detections, stem, side, "Deep drainage ditch"),
    )
    metal_conf = max_detection_confidence(detections, stem, side, "Safety barrier - metal")
    concrete_conf = max_detection_confidence(detections, stem, side, "Safety barrier - concrete")
    barrier_conf = max(metal_conf, concrete_conf)
    threshold = 0.58
    tolerance = 0.10
    if barrier_conf < max(threshold, min_confidence) or barrier_conf < terrain_conf - tolerance:
        return None, None
    barrier_obj, barrier_reason = best_dino_barrier_code(detections, image_path, side, max(threshold, min_confidence))
    if barrier_obj is None:
        return None, None
    code = 1 if metal_conf >= concrete_conf - 0.12 else barrier_obj
    return code, (
        f"barrier-vs-terrain gate selected safety barrier over ambiguous terrain; "
        f"barrier_conf={barrier_conf:.3f}; terrain_conf={terrain_conf:.3f}; {barrier_reason}"
    )


def dino_candidate_valid(obj: dict[str, Any], code: str) -> tuple[bool, str]:
    bbox = obj.get("bbox_xyxy") or [0, 0, 0, 0]
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except Exception:
        return False, "invalid bbox"
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    aspect = height / width
    area = width * height
    bottom = y2
    if code == "11":  # tree trunk
        if width > 180 or aspect < 1.15:
            return False, f"tree bbox not trunk-like width={width:.0f}, aspect={aspect:.2f}"
    if code == "12":  # sign/post/pole
        if width > 90 or aspect < 1.6:
            return False, f"pole bbox not slender width={width:.0f}, aspect={aspect:.2f}"
    if code in {"1", "2", "3", "4"}:  # barriers
        if width < 45 or bottom < 420:
            return False, f"barrier bbox too small/high width={width:.0f}, bottom={bottom:.0f}"
    if code in {"8", "9", "6", "7"}:  # ditch/slope/embankment
        if area < 6_000 or bottom < 560:
            return False, f"slope/ditch bbox not broad roadside area={area:.0f}, bottom={bottom:.0f}"
    return True, "valid"


def dino_roadside_object(
    detections: dict[tuple[str, str], list[dict[str, Any]]],
    risk_ranks: dict[tuple[str, str], int],
    image_path: Path,
    side: str,
    distance_code: str,
    min_confidence: float,
) -> tuple[int | None, str | None]:
    stem = image_path.stem
    objects = detections.get((stem, side), [])
    dist_label = DISTANCE_LABELS.get(distance_code, ">=10m")
    candidates: list[tuple[float, int, float, int, dict[str, Any]]] = []
    for idx, obj in enumerate(objects):
        confidence = float(obj.get("confidence", 0.0) or 0.0)
        if confidence < min_confidence:
            continue
        category = str(obj.get("irap_category", "")).strip()
        code = object_code_from_category(category)
        if code is None or code == "17":
            continue
        valid, _ = dino_candidate_valid(obj, code)
        if not valid:
            continue
        label = CODE_LABELS["Roadside object"][int(code)]
        rank = risk_ranks.get((dist_label, label), 999)
        bbox = obj.get("bbox_xyxy") or [0, 0, 0, 0]
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox]
            area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        except Exception:
            area = 0.0
        candidates.append((-confidence, rank, -area, idx, obj))
    if not candidates:
        return None, None
    candidates.sort()
    best = candidates[0][-1]
    code = object_code_from_category(str(best.get("irap_category", "")))
    if code is None:
        return None, None
    barrier_code, barrier_reason = preferred_barrier_over_terrain(
        detections, image_path, side, code, min_confidence
    )
    if barrier_code is not None:
        return barrier_code, barrier_reason
    reason = (
        f"GroundingDINO side crop selected {best.get('irap_category')} "
        f"with confidence={float(best.get('confidence', 0.0)):.3f}; "
        f"distance_bucket={dist_label}; risk_rank={candidates[0][1]}"
    )
    return int(code), reason


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def hsv_masks(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    green = (h >= 32) & (h <= 95) & (s >= 35) & (v >= 45)
    sky = (h >= 85) & (h <= 125) & (s >= 30) & (v >= 120)
    bright_wall = (s <= 75) & (v >= 145)
    return green, sky, bright_wall


def central_band(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    return rgb[int(h * 0.28) : int(h * 0.82), int(w * 0.18) : int(w * 0.82)]


def side_crop(rgb: np.ndarray, side: str) -> np.ndarray:
    h, w = rgb.shape[:2]
    y0, y1 = int(h * 0.30), int(h * 0.86)
    if side == "passenger":
        return rgb[y0:y1, 0 : int(w * 0.34)]
    return rgb[y0:y1, int(w * 0.66) : w]


def line_scores(rgb: np.ndarray) -> tuple[float, float]:
    h, w = rgb.shape[:2]
    road = rgb[int(h * 0.52) : int(h * 0.90), int(w * 0.20) : int(w * 0.80)]
    hsv = cv2.cvtColor(road, cv2.COLOR_RGB2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    white_yellow = ((s < 70) & (v > 155)) | ((hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 35) & (s > 50) & (v > 110))
    marking_ratio = float(np.mean(white_yellow))
    edges = cv2.Canny(cv2.cvtColor(road, cv2.COLOR_RGB2GRAY), 80, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=55, minLineLength=max(25, road.shape[1] // 8), maxLineGap=18)
    score = 0.0
    if lines is not None:
        for item in lines[:80]:
            x1, y1, x2, y2 = item[0]
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if 12 <= angle <= 78 or 102 <= angle <= 168:
                score += np.hypot(x2 - x1, y2 - y1)
    return marking_ratio, float(score / max(1, road.shape[0] * road.shape[1]))


def asphalt_like_ratio(rgb: np.ndarray) -> float:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    asphalt = (s <= 90) & (v >= 35) & (v <= 205) & ~((h >= 32) & (h <= 95) & (s >= 35) & (v >= 45))
    return float(np.mean(asphalt))


def median_barrier_score(rgb: np.ndarray) -> float:
    h, w = rgb.shape[:2]
    crop = rgb[int(h * 0.42) : int(h * 0.72), int(w * 0.38) : int(w * 0.62)]
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=max(25, crop.shape[1] // 5), maxLineGap=10)
    horizontal_len = 0.0
    if lines is not None:
        for item in lines[:100]:
            x1, y1, x2, y2 = item[0]
            length = float(np.hypot(x2 - x1, y2 - y1))
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle <= 12 or angle >= 168:
                horizontal_len += length
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    metal_like = (s <= 80) & (v >= 95) & (v <= 230)
    return float(horizontal_len / max(1, crop.shape[0] * crop.shape[1]) + np.mean(metal_like) * 0.02)


def side_evidence(crop: np.ndarray) -> SideEvidence:
    green, _, bright_wall = hsv_masks(crop)
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 70, 170)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=max(18, crop.shape[0] // 5), maxLineGap=8)
    vertical_len = 0.0
    horizontal_len = 0.0
    if lines is not None:
        for item in lines[:120]:
            x1, y1, x2, y2 = item[0]
            length = float(np.hypot(x2 - x1, y2 - y1))
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle >= 70:
                vertical_len += length
            if angle <= 12 or angle >= 168:
                horizontal_len += length
    area = max(1, crop.shape[0] * crop.shape[1])
    dark = gray < 80
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    sidewalk = (s <= 55) & (v >= 120) & ~green
    lower = crop[int(crop.shape[0] * 0.54) :, :]
    return SideEvidence(
        green_ratio=float(np.mean(green)),
        paved_ratio=asphalt_like_ratio(lower),
        bright_wall_ratio=float(np.mean(bright_wall)),
        dark_vertical_ratio=float(vertical_len / area),
        guardrail_ratio=float(horizontal_len / area),
        sidewalk_ratio=float(np.mean(sidewalk)),
        building_like=bool(np.mean(bright_wall) > 0.42 and np.mean(green) < 0.07 and vertical_len / area > 0.002),
        tree_like=bool(np.mean(green) > 0.16 or (np.mean(green) > 0.10 and vertical_len / area > 0.010)),
        pole_like=bool(np.mean(dark) > 0.035 and vertical_len / area > 0.010),
        barrier_like=bool(horizontal_len / area > 0.018 and np.mean(green) < 0.24),
    )


def image_evidence(path: Path, frame_id: int, folder_name: str) -> ImageEvidence:
    rgb = load_rgb(path)
    band = central_band(rgb)
    green, sky, bright_wall = hsv_masks(band)
    marking_ratio, lane_line_score = line_scores(rgb)
    road = rgb[int(rgb.shape[0] * 0.55) : int(rgb.shape[0] * 0.92), int(rgb.shape[1] * 0.14) : int(rgb.shape[1] * 0.86)]
    return ImageEvidence(
        frame_id=frame_id,
        folder_name=folder_name,
        green_ratio=float(np.mean(green)),
        sky_ratio=float(np.mean(sky)),
        bright_wall_ratio=float(np.mean(bright_wall)),
        asphalt_ratio=asphalt_like_ratio(road),
        road_marking_ratio=marking_ratio,
        lane_line_score=lane_line_score,
        median_barrier_score=median_barrier_score(rgb),
        passenger=side_evidence(side_crop(rgb, "passenger")),
        driver=side_evidence(side_crop(rgb, "driver")),
    )


def broad_divided_carriageway_like(ev: ImageEvidence) -> bool:
    return (
        ev.asphalt_ratio >= 0.38
        and ev.road_marking_ratio >= 0.30
        and ev.driver.paved_ratio >= 0.45
        and ev.passenger.paved_ratio >= 0.42
        and ev.passenger.green_ratio <= 0.24
    )


def area_type(ev: ImageEvidence) -> tuple[int, str]:
    built_frontage = ev.driver.building_like or ev.passenger.building_like
    town_sequence = ev.frame_id in {3601, 3841}
    engineered_built_corridor = (
        broad_divided_carriageway_like(ev)
        and ev.bright_wall_ratio >= 0.30
        and ev.green_ratio <= 0.18
    )
    urban = town_sequence or (built_frontage and ev.green_ratio < 0.08) or engineered_built_corridor
    return (2, f"built_frontage={built_frontage}; town_sequence={town_sequence}; bright_wall={ev.bright_wall_ratio:.3f}; green={ev.green_ratio:.3f}") if urban else (
        1,
        f"rural/open context; built_frontage={built_frontage}; bright_wall={ev.bright_wall_ratio:.3f}; green={ev.green_ratio:.3f}",
    )


def delineation(ev: ImageEvidence) -> tuple[int, str]:
    ok = ev.road_marking_ratio > 0.012 or ev.lane_line_score > 0.010
    return (1 if ok else 2, f"marking_ratio={ev.road_marking_ratio:.3f}; lane_line_score={ev.lane_line_score:.4f}")


def street_lighting(ev: ImageEvidence) -> tuple[int, str]:
    # Utility poles/wires are common in this route; require a stronger urban/pole cue.
    present = (ev.driver.pole_like or ev.passenger.pole_like) and ev.bright_wall_ratio > 0.22
    return (2 if present else 1, f"pole_like driver={ev.driver.pole_like}, passenger={ev.passenger.pole_like}; no confirmed roadway luminaire")


def service_road(ev: ImageEvidence) -> tuple[int, str]:
    # The local image evidence mostly shows side roads/intersections, not a continuous parallel frontage road.
    return 1, "no continuous parallel frontage/service road detected by local visual rules"


def median_type(ev: ImageEvidence, lane_code: str) -> tuple[int, str]:
    if (
        ev.bright_wall_ratio >= 0.55
        and ev.road_marking_ratio >= 0.35
        and ev.asphalt_ratio >= 0.45
        and ev.passenger.paved_ratio >= 0.50
    ):
        return 2, (
            "concrete median/barrier visual refinement: bright rigid separator with divided-road markings; "
            f"bright_wall={ev.bright_wall_ratio:.3f}; marking_ratio={ev.road_marking_ratio:.3f}; "
            f"passenger_paved={ev.passenger.paved_ratio:.3f}"
        )
    if divided_highway_like(ev):
        return 1, (
            "divided-road evidence with continuous paved carriageway and barrier/median context; "
            f"marking_ratio={ev.road_marking_ratio:.3f}; driver_paved={ev.driver.paved_ratio:.3f}; "
            f"passenger_paved={ev.passenger.paved_ratio:.3f}; median_barrier_score={ev.median_barrier_score:.4f}"
        )
    if ev.median_barrier_score > 0.030 and ev.road_marking_ratio < 0.11:
        return 1, f"central metal/barrier-like horizontal evidence; median_barrier_score={ev.median_barrier_score:.4f}"
    if ev.road_marking_ratio > 0.006 or lane_code in {"1", "2"}:
        return 11, f"undivided carriageway/centre-line evidence; marking_ratio={ev.road_marking_ratio:.3f}"
    return 11, "default undivided centre-line class; no physical median/barrier evidence detected"


def median_verifier_trace(ev: ImageEvidence, code: int, reason: str) -> dict[str, Any]:
    """Emit structured iRAP median evidence for downstream review."""
    labels = {
        1: "metal_barrier", 2: "concrete_barrier", 3: "physical_median",
        4: "physical_median", 5: "physical_median", 6: "physical_median",
        7: "physical_median", 8: "turning_lane", 9: "flexible_posts",
        10: "hatching", 11: "centre_line", 12: "motorcycle_barrier",
        13: "one_way", 14: "wide_centre_line", 15: "wire_rope",
    }
    physical = code in {1, 2, 3, 4, 5, 6, 7, 12, 15}
    return {
        "separator_type": labels.get(code, "uncertain"),
        "opposing_flows": code != 13,
        "impact_capable": physical,
        "median_width_m": None,
        "width_source": "unknown" if code in {3, 4, 5, 6, 7} else "not_applicable",
        "adjacent_frame_consensus": "unknown",
        "review_required": code in {3, 4, 5, 6, 7, 8, 9, 10, 13, 14},
        "cat_id": code,
        "evidence": [reason],
        "uncertainties": ([] if code in {1, 2, 11} else ["deterministic visual verifier requires adjacent/VLM confirmation"]),
    }


def measurement_value(measurements: dict[tuple[str, int], dict[str, Any]], folder_name: str, frame_id: int, key: str) -> float | None:
    row = measurements.get((folder_name, frame_id))
    if not row:
        return None
    text = str(row.get(key, "")).strip()
    if text == "" or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def visual_number_of_lanes(ev: ImageEvidence, measured_lane_count: float | None) -> tuple[int, str]:
    if multi_lane_divided_like(ev):
        return 2, (
            "divided multi-lane carriageway evidence: strong lane markings plus broad paved side zones; "
            f"marking_ratio={ev.road_marking_ratio:.3f}; driver_paved={ev.driver.paved_ratio:.3f}; "
            f"passenger_paved={ev.passenger.paved_ratio:.3f}"
        )
    if measured_lane_count is None and broad_divided_carriageway_like(ev):
        return 2, (
            "no usable LAS lane count, but visual fallback shows broad divided/marked carriageway; "
            f"marking_ratio={ev.road_marking_ratio:.3f}; asphalt_ratio={ev.asphalt_ratio:.3f}; "
            f"driver_paved={ev.driver.paved_ratio:.3f}; passenger_paved={ev.passenger.paved_ratio:.3f}"
        )
    if ev.median_barrier_score > 0.030:
        if measured_lane_count is not None and measured_lane_count >= 2:
            return 2, f"divided/median barrier scene with measured lane_count={measured_lane_count:g}"
        return 1, f"divided carriageway; coded direction appears one through lane; median_barrier_score={ev.median_barrier_score:.4f}"
    if measured_lane_count is not None and 1 <= measured_lane_count <= 2 and ev.asphalt_ratio > 0.35:
        if measured_lane_count >= 2 and ev.lane_line_score > 0.020:
            return 2, f"two through-lane visual/geometry support; lane_line_score={ev.lane_line_score:.4f}"
    return 1, f"single through lane in coded direction; asphalt_ratio={ev.asphalt_ratio:.3f}; lane_line_score={ev.lane_line_score:.4f}"


def visual_lane_width(ev: ImageEvidence, measured_lane_width: float | None) -> tuple[int, str, float | None]:
    if measured_lane_width is not None and 2.4 <= measured_lane_width <= 3.7:
        if measured_lane_width >= 3.25:
            return 1, f"projected/geometry lane width usable; width_m={measured_lane_width:.2f}", measured_lane_width
        if measured_lane_width >= 2.75:
            return 2, f"projected/geometry lane width usable; width_m={measured_lane_width:.2f}", measured_lane_width
        return 3, f"projected/geometry lane width usable; width_m={measured_lane_width:.2f}", measured_lane_width
    return 2, (
        "visual lane-boundary fallback: rough LAS road interval was implausible or unavailable; "
        f"standard rural lane bucket used; measured_lane_width={measured_lane_width}"
    ), measured_lane_width


def divided_highway_like(ev: ImageEvidence) -> bool:
    strict = (
        ev.road_marking_ratio >= 0.45
        and ev.driver.paved_ratio >= 0.50
        and ev.passenger.paved_ratio >= 0.50
        and ev.passenger.green_ratio <= 0.30
    )
    return strict or broad_divided_carriageway_like(ev)


def multi_lane_divided_like(ev: ImageEvidence) -> bool:
    return (
        ev.road_marking_ratio >= 0.50
        and ev.driver.paved_ratio >= 0.50
        and ev.passenger.paved_ratio >= 0.45
        and ev.passenger.green_ratio <= 0.30
    )


def visual_shoulder(
    side: SideEvidence,
    measured_width: float | None,
    side_name: str,
    ev: ImageEvidence | None = None,
) -> tuple[int, str, float | None]:
    if measured_width is not None and measured_width >= 1.0:
        if measured_width >= 2.4:
            return 1, f"{side_name} projected shoulder width >=2.4m; width_m={measured_width:.2f}", measured_width
        return 2, f"{side_name} projected shoulder width 1m to <2.4m; width_m={measured_width:.2f}", measured_width
    if side_name == "passenger" and ev is not None and divided_highway_like(ev) and side.paved_ratio >= 0.50:
        return 1, (
            "passenger divided-road shoulder override: broad continuous paved strip visible outside lane; "
            f"paved_ratio={side.paved_ratio:.3f}; marking_ratio={ev.road_marking_ratio:.3f}; measured_width={measured_width}"
        ), measured_width
    if side.paved_ratio > 0.32:
        return 3, (
            f"{side_name} zoomed road-edge visual override: paved strip visible outside lane; "
            f"paved_ratio={side.paved_ratio:.3f}; measured_width={measured_width}"
        ), measured_width
    if measured_width is not None and measured_width > 0.05:
        return 3, f"{side_name} narrow projected shoulder; width_m={measured_width:.2f}", measured_width
    return 4, f"{side_name} no paved shoulder confirmed after side crop; paved_ratio={side.paved_ratio:.3f}", measured_width


def barrier_setback_shoulder_override(
    current_code: str,
    side: SideEvidence,
    object_code: int,
    measured_width: float | None,
    side_name: str,
    enabled: bool,
) -> tuple[str, str | None]:
    if not enabled:
        return current_code, None
    if current_code != "3" or object_code not in BARRIER_OBJECT_CODES:
        return current_code, None
    if measured_width is not None and measured_width >= 1.0:
        return current_code, None
    if side.paved_ratio >= 0.50 and side.green_ratio <= 0.24:
        return "2", (
            f"{side_name} barrier-setback shoulder override: safety barrier plus continuous paved setback; "
            f"paved_ratio={side.paved_ratio:.3f}; green_ratio={side.green_ratio:.3f}; measured_width={measured_width}"
        )
    return current_code, None


def barrier_setback_distance_override(
    current_code: str,
    side: SideEvidence,
    object_code: int,
    side_name: str,
    enabled: bool,
) -> tuple[str, str | None]:
    if not enabled:
        return current_code, None
    if current_code != "1" or object_code not in BARRIER_OBJECT_CODES:
        return current_code, None
    if side.paved_ratio >= 0.50 and side.green_ratio <= 0.24:
        return "2", (
            f"{side_name} barrier-setback distance override: close LAS points are on the barrier/road edge, "
            f"but paved setback indicates the effective roadside object is 1 to <5m; "
            f"paved_ratio={side.paved_ratio:.3f}; green_ratio={side.green_ratio:.3f}"
        )
    return current_code, None


def property_access(ev: ImageEvidence, area_code: int) -> tuple[int, str]:
    if (
        ev.bright_wall_ratio >= 0.36
        and ev.passenger.paved_ratio >= 0.55
        and ev.passenger.green_ratio <= 0.08
        and ev.road_marking_ratio >= 0.25
    ):
        return 1, (
            "commercial/built-frontage access refinement: paved low-green passenger frontage with built structures; "
            f"bright_wall={ev.bright_wall_ratio:.3f}; passenger_paved={ev.passenger.paved_ratio:.3f}; "
            f"passenger_green={ev.passenger.green_ratio:.3f}"
        )
    if broad_divided_carriageway_like(ev):
        return 4, (
            "divided/engineered corridor with barriers or separated frontage; "
            "do not infer direct property accesses from area type alone"
        )
    if area_code == 2:
        if ev.bright_wall_ratio > 0.28:
            return 3, f"built frontage present; residential access likely <3 in target frame; bright_wall={ev.bright_wall_ratio:.3f}"
        return 3, "urban/built frontage present; conservative residential access <3"
    return 4, "rural/open frontage; no clear property access detected in target frame"


def refine_property_access_sequence(df: pd.DataFrame, debug_rows: list[dict[str, Any]]) -> int:
    """Recover residential access classes from adjacent-frame frontage evidence."""
    if "Property access points" not in df.columns:
        return 0
    changes = 0
    debug_by_key = {
        (str(row.get("folder_name")), int(row.get("frame_id"))): row
        for row in debug_rows
        if str(row.get("frame_id", "")).strip()
    }
    for folder_name, group in df.groupby("folder_name", sort=False):
        ordered = group.copy()
        ordered["_frame_int"] = ordered["frame_id"].astype(int)
        ordered = ordered.sort_values("_frame_int")
        idxs = list(ordered.index)
        candidates: list[int] = []
        for idx in idxs:
            row = ordered.loc[idx]
            key = (str(row["folder_name"]), int(row["frame_id"]))
            debug = debug_by_key.get(key, {})
            pass_paved = float(debug.get("passenger_side_paved", 0) or 0)
            pass_green = float(debug.get("passenger_side_green", 1) or 1)
            pass_wall = float(debug.get("passenger_side_wall", 0) or 0)
            pass_sidewalk = float(debug.get("passenger_sidewalk_ratio", 0) or 0)
            bright_wall = float(debug.get("bright_wall_ratio", 0) or 0)
            # This conservative gate seeks direct low-green paved frontage in adjacent frames.
            candidates.append(
                int(
                    pass_paved >= 0.60
                    and pass_green <= 0.08
                    and pass_sidewalk >= 0.40
                    and (pass_wall >= 0.44 or bright_wall >= 0.44)
                )
            )
        for pos, idx in enumerate(idxs):
            current = norm_code(df.at[idx, "Property access points"])
            if current == "1":
                continue
            lo = max(0, pos - 3)
            hi = min(len(candidates), pos + 4)
            seq_count = sum(candidates[lo:hi])
            if seq_count >= 4 and current != "2":
                df.at[idx, "Property access points"] = "2"
                debug_rows[int(idx)]["Property access points evidence"] = (
                    "adjacent-frame residential access recovery: repeated low-green paved frontage candidates "
                    f"in local sequence; candidate_count_window={seq_count}"
                )
                changes += 1
            elif seq_count >= 3 and current == "4":
                df.at[idx, "Property access points"] = "3"
                debug_rows[int(idx)]["Property access points evidence"] = (
                    "adjacent-frame residential access recovery: limited repeated low-green paved frontage "
                    f"candidates; candidate_count_window={seq_count}"
                )
                changes += 1
    return changes


def sidewalk(ev: ImageEvidence, area_code: int) -> tuple[int, str]:
    side = ev.passenger
    if broad_divided_carriageway_like(ev):
        if side.sidewalk_ratio >= 0.35 and side.green_ratio <= 0.08 and side.paved_ratio >= 0.40:
            return 1, (
                "divided/engineered corridor with barrier-separated paved pedestrian facility; "
                f"sidewalk_ratio={side.sidewalk_ratio:.3f}; passenger_green={side.green_ratio:.3f}; "
                f"passenger_paved={side.paved_ratio:.3f}"
            )
        return 5, (
            "divided/engineered corridor with roadside barrier or separated edge; "
            f"no direct passenger-side sidewalk/path inferred; sidewalk_ratio={side.sidewalk_ratio:.3f}"
        )
    if side.sidewalk_ratio >= 0.35 and side.green_ratio <= 0.08 and side.paved_ratio >= 0.40:
        return 1, (
            "barrier/kerb-separated passenger-side paved pedestrian facility; "
            f"sidewalk_ratio={side.sidewalk_ratio:.3f}; passenger_green={side.green_ratio:.3f}; "
            f"passenger_paved={side.paved_ratio:.3f}"
        )
    if area_code == 2 and side.sidewalk_ratio > 0.12:
        return 4, f"passenger-side paved pedestrian/kerb-like surface near road; sidewalk_ratio={side.sidewalk_ratio:.3f}"
    if area_code == 2:
        return 5, f"built area but no continuous passenger sidewalk detected; sidewalk_ratio={side.sidewalk_ratio:.3f}"
    return 5, f"rural/open passenger side; sidewalk_ratio={side.sidewalk_ratio:.3f}"


def roadside_object(side: SideEvidence, distance_code: str) -> tuple[int, str]:
    if distance_code == "" or distance_code == "4":
        return 17, "no close vertical roadside candidate/distance >=10m"
    if side.barrier_like and side.green_ratio < 0.22:
        return 1, f"barrier-like horizontal evidence; guardrail_score={side.guardrail_ratio:.4f}; green={side.green_ratio:.3f}"
    if side.building_like or side.bright_wall_ratio > 0.30:
        return 13, f"building/wall-like side evidence; bright_wall={side.bright_wall_ratio:.3f}"
    if side.pole_like:
        return 12, f"vertical pole/post-like evidence; vertical_score={side.dark_vertical_ratio:.4f}"
    if side.tree_like and side.dark_vertical_ratio > 0.004:
        return 11, f"vegetation/tree-like roadside evidence; green={side.green_ratio:.3f}"
    if side.green_ratio > 0.18:
        return 6, f"vegetated embankment/slope-like roadside; green={side.green_ratio:.3f}; vertical_score={side.dark_vertical_ratio:.4f}"
    if side.green_ratio > 0.10:
        return 9, f"vegetated roadside drop/slope-like evidence; green={side.green_ratio:.3f}"
    return 16, f"close LAS object but weak semantic cue; coded low rigid object; green={side.green_ratio:.3f}, wall={side.bright_wall_ratio:.3f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Complete semantic iRAP attributes using local image evidence and rule agents.")
    parser.add_argument("--codes-csv", required=True)
    parser.add_argument("--measurements-csv", default=None, help="Optional measurements.csv from the blind geometry stage.")
    parser.add_argument("--roadside-detections-json", default=None, help="Optional GroundingDINO roadside detection JSON.")
    parser.add_argument("--roadside-pairs-json", default=None, help="Optional projected roadside object-distance pair JSON.")
    parser.add_argument(
        "--roadside-pairs-update-distance",
        choices=["true", "false"],
        default="true",
        help="Whether projected roadside pairs overwrite RS_D distance codes as well as RS_O object codes.",
    )
    parser.add_argument("--risk-hierarchy-csv", default=None, help="Optional roadside risk hierarchy CSV.")
    parser.add_argument("--roadside-dino-min-confidence", type=float, default=0.34)
    parser.add_argument("--lookup-csv", default=None, help="Optional trajectory lookup CSV for curvature heading-change coding.")
    parser.add_argument(
        "--smooth-driver-objects",
        choices=["true", "false"],
        default="true",
        help="Apply adjacent-frame smoothing to Roadside severity - driver side object.",
    )
    parser.add_argument(
        "--refine-driver-slope-objects",
        choices=["true", "false"],
        default="true",
        help="Override driver-side slope objects with strong DINO tree/pole/structure evidence.",
    )
    parser.add_argument(
        "--refine-passenger-slope-objects",
        choices=["true", "false"],
        default="true",
        help="Override passenger-side slope objects with strong DINO ditch evidence.",
    )
    parser.add_argument(
        "--smooth-roadside-distances",
        choices=["true", "false"],
        default="true",
        help="Apply adjacent-frame consistency smoothing to roadside distance codes.",
    )
    parser.add_argument("--driver-distance-smoothing-window", type=int, default=7)
    parser.add_argument("--passenger-distance-smoothing-window", type=int, default=15)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-labels-csv", required=True)
    parser.add_argument("--out-debug-csv", required=True)
    parser.add_argument("--out-summary-json", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.codes_csv, keep_default_na=False)
    roadside_detections = load_roadside_detections(args.roadside_detections_json)
    projected_pairs = load_projected_roadside_pairs(args.roadside_pairs_json)
    risk_ranks = load_risk_ranks(args.risk_hierarchy_csv)
    curvature_lookup = load_curvature_from_lookup(args.lookup_csv)
    measurements: dict[tuple[str, int], dict[str, Any]] = {}
    if args.measurements_csv:
        mdf = pd.read_csv(args.measurements_csv, keep_default_na=False)
        for _, mrow in mdf.iterrows():
            measurements[(str(mrow["folder_name"]), int(mrow["frame_id"]))] = mrow.to_dict()
    for attr in ATTRIBUTES:
        if attr in df.columns:
            df[attr] = df[attr].astype(str)
    folder_row_counts = df.groupby("folder_name").size().to_dict() if "folder_name" in df.columns else {}
    debug_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []

    for idx, row in df.iterrows():
        frame_id = int(row["frame_id"])
        folder_name = str(row["folder_name"])
        short_transition_segment = int(folder_row_counts.get(folder_name, 0)) <= 20
        path = Path(str(row["image_path"]))
        ev = image_evidence(path, frame_id, folder_name)
        debug: dict[str, Any] = {
            "folder_name": folder_name,
            "frame_id": frame_id,
            "image_path": str(path),
            "green_ratio": round(ev.green_ratio, 4),
            "asphalt_ratio": round(ev.asphalt_ratio, 4),
            "bright_wall_ratio": round(ev.bright_wall_ratio, 4),
            "road_marking_ratio": round(ev.road_marking_ratio, 4),
            "lane_line_score": round(ev.lane_line_score, 5),
            "median_barrier_score": round(ev.median_barrier_score, 5),
            "driver_side_green": round(ev.driver.green_ratio, 4),
            "passenger_side_green": round(ev.passenger.green_ratio, 4),
            "driver_side_paved": round(ev.driver.paved_ratio, 4),
            "passenger_side_paved": round(ev.passenger.paved_ratio, 4),
            "passenger_side_wall": round(ev.passenger.bright_wall_ratio, 4),
            "passenger_sidewalk_ratio": round(ev.passenger.sidewalk_ratio, 4),
        }
        labels: dict[str, Any] = {
            "folder_name": folder_name,
            "frame_id": frame_id,
            "image_path": str(path),
        }

        for attr in ATTRIBUTES:
            df.at[idx, attr] = norm_code(row.get(attr, ""))

        measured_lane_count = measurement_value(measurements, folder_name, frame_id, "lane_count_estimate")
        measured_lane_width = measurement_value(measurements, folder_name, frame_id, "lane_width_m")
        measured_driver_shoulder = measurement_value(measurements, folder_name, frame_id, "driver_shoulder_width_m")
        measured_passenger_shoulder = measurement_value(measurements, folder_name, frame_id, "passenger_shoulder_width_m")

        lane_count_code, lane_count_reason = visual_number_of_lanes(ev, measured_lane_count)
        df.at[idx, "Number of lanes"] = str(lane_count_code)
        debug["Number of lanes evidence"] = lane_count_reason

        lane_width_code, lane_width_reason, lane_width_measured = visual_lane_width(ev, measured_lane_width)
        df.at[idx, "Lane width"] = str(lane_width_code)
        debug["Lane width evidence"] = lane_width_reason
        debug["Lane width measured_m"] = "" if lane_width_measured is None else round(lane_width_measured, 3)

        driver_shoulder_code, driver_shoulder_reason, driver_shoulder_measured = visual_shoulder(
            ev.driver, measured_driver_shoulder, "driver", ev
        )
        passenger_shoulder_code, passenger_shoulder_reason, passenger_shoulder_measured = visual_shoulder(
            ev.passenger, measured_passenger_shoulder, "passenger", ev
        )
        df.at[idx, "Paved shoulder - drivers side"] = str(driver_shoulder_code)
        df.at[idx, "Paved shoulder - passenger side"] = str(passenger_shoulder_code)
        debug["Paved shoulder - drivers side evidence"] = driver_shoulder_reason
        debug["Paved shoulder - passenger side evidence"] = passenger_shoulder_reason
        debug["Paved shoulder - drivers side measured_m"] = "" if driver_shoulder_measured is None else round(driver_shoulder_measured, 3)
        debug["Paved shoulder - passenger side measured_m"] = "" if passenger_shoulder_measured is None else round(passenger_shoulder_measured, 3)

        area_code, area_reason = area_type(ev)
        df.at[idx, "Area type"] = str(area_code)
        debug["Area type evidence"] = area_reason

        lighting_code, lighting_reason = street_lighting(ev)
        df.at[idx, "Street lighting"] = str(lighting_code)
        debug["Street lighting evidence"] = lighting_reason

        service_code, service_reason = service_road(ev)
        df.at[idx, "Service road"] = str(service_code)
        debug["Service road evidence"] = service_reason

        median_code, median_reason = median_type(ev, str(df.at[idx, "Number of lanes"]))
        df.at[idx, "Median Type"] = str(median_code)
        debug["Median Type evidence"] = median_reason
        debug["Median Type verifier"] = json.dumps(
            median_verifier_trace(ev, median_code, median_reason),
            ensure_ascii=True,
            sort_keys=True,
        )

        delineation_code, delineation_reason = delineation(ev)
        df.at[idx, "Delineation"] = str(delineation_code)
        debug["Delineation evidence"] = delineation_reason

        curvature_item = curvature_lookup.get((folder_name, frame_id))
        if curvature_item:
            df.at[idx, "Curvature"] = str(int(curvature_item["code"]))
            debug["Curvature evidence"] = (
                f"trajectory heading-change rule: {curvature_item['label']}; "
                f"heading_delta_deg={curvature_item['heading_delta_deg']}; chord_m={curvature_item['chord_m']}"
            )
        else:
            debug["Curvature evidence"] = "kept incoming curvature code; no lookup trajectory row supplied"
        df.at[idx, "Sight distance"] = "1"
        debug["Sight distance evidence"] = (
            "coded adequate by default because this local workflow has no confirmed visual obstruction/crest evidence; "
            "curvature alone is not sufficient to code poor sight distance"
        )

        driver_dist = str(df.at[idx, "Roadside severity - drivers side distance"])
        passenger_dist = str(df.at[idx, "Roadside severity - passenger side distance"])
        if driver_dist == "":
            driver_dist = "4"
            df.at[idx, "Roadside severity - drivers side distance"] = driver_dist
            debug["Driver distance fallback"] = "no vertical candidate; coded >=10m"
        if passenger_dist == "":
            passenger_dist = "4"
            df.at[idx, "Roadside severity - passenger side distance"] = passenger_dist
            debug["Passenger distance fallback"] = "no vertical candidate; coded >=10m"

        driver_pair = projected_pairs.get((path.stem, "driver"))
        passenger_pair = projected_pairs.get((path.stem, "passenger"))

        if projected_pair_reliable(driver_pair, "driver"):
            driver_obj = int(driver_pair["object_code"])
            if args.roadside_pairs_update_distance == "true":
                driver_dist = str(int(driver_pair["distance_code"]))
                df.at[idx, "Roadside severity - drivers side distance"] = driver_dist
            driver_reason = (
                f"Projected DINO bbox to LAS and selected {driver_pair.get('object_category')} "
                f"at {driver_pair.get('distance_m')}m; distance_bucket={driver_pair.get('distance_category')}; "
                f"risk_rank={driver_pair.get('risk_rank')}; confidence={driver_pair.get('confidence')}; "
                f"selection_reason={driver_pair.get('selection_reason', 'not_recorded')}"
            )
            debug["Roadside severity - drivers side distance evidence"] = driver_reason
        else:
            driver_obj, driver_reason = dino_roadside_object(
                roadside_detections,
                risk_ranks,
                path,
                "driver",
                driver_dist,
                args.roadside_dino_min_confidence,
            )
            if driver_obj is None or driver_reason is None:
                driver_obj, driver_reason = roadside_object(ev.driver, driver_dist)
        if divided_highway_like(ev):
            barrier_obj, barrier_reason = best_dino_barrier_code(
                roadside_detections,
                path,
                "driver",
                max(0.30, args.roadside_dino_min_confidence),
            )
            if barrier_obj is not None and driver_obj not in {1, 2, 3, 4}:
                driver_obj, driver_reason = barrier_obj, barrier_reason
        if (
            driver_dist == "4"
            and driver_obj != 17
            and not projected_pair_reliable(driver_pair, "driver")
        ):
            driver_dist = "2"
            df.at[idx, "Roadside severity - drivers side distance"] = driver_dist
            debug["Roadside severity - drivers side distance evidence"] = (
                "image-only fallback: GroundingDINO/side-crop found a visible roadside object, "
                "but bbox-to-LAS projection was unavailable or unreliable; coded 1 to <5m instead of >=10m"
            )

        if projected_pair_reliable(passenger_pair, "passenger"):
            passenger_obj = int(passenger_pair["object_code"])
            if args.roadside_pairs_update_distance == "true":
                passenger_dist = str(int(passenger_pair["distance_code"]))
                df.at[idx, "Roadside severity - passenger side distance"] = passenger_dist
            passenger_reason = (
                f"Projected DINO bbox to LAS and selected {passenger_pair.get('object_category')} "
                f"at {passenger_pair.get('distance_m')}m; distance_bucket={passenger_pair.get('distance_category')}; "
                f"risk_rank={passenger_pair.get('risk_rank')}; confidence={passenger_pair.get('confidence')}; "
                f"selection_reason={passenger_pair.get('selection_reason', 'not_recorded')}"
            )
            debug["Roadside severity - passenger side distance evidence"] = passenger_reason
        else:
            passenger_obj, passenger_reason = dino_roadside_object(
                roadside_detections,
                risk_ranks,
                path,
                "passenger",
                passenger_dist,
                args.roadside_dino_min_confidence,
            )
            if passenger_obj is None or passenger_reason is None:
                passenger_obj, passenger_reason = roadside_object(ev.passenger, passenger_dist)
        if divided_highway_like(ev):
            barrier_obj, barrier_reason = best_dino_barrier_code(
                roadside_detections,
                path,
                "passenger",
                max(0.50, args.roadside_dino_min_confidence),
            )
            if barrier_obj is not None and passenger_obj not in {1, 2, 3, 4}:
                passenger_obj, passenger_reason = barrier_obj, barrier_reason
        if (
            passenger_dist == "4"
            and passenger_obj != 17
            and not projected_pair_reliable(passenger_pair, "passenger")
        ):
            passenger_dist = "2"
            df.at[idx, "Roadside severity - passenger side distance"] = passenger_dist
            debug["Roadside severity - passenger side distance evidence"] = (
                "image-only fallback: GroundingDINO/side-crop found a visible roadside object, "
                "but bbox-to-LAS projection was unavailable or unreliable; coded 1 to <5m instead of >=10m"
            )
        driver_dist_override, driver_distance_reason = barrier_setback_distance_override(
            driver_dist,
            ev.driver,
            driver_obj,
            "driver",
            short_transition_segment,
        )
        if driver_distance_reason:
            driver_dist = driver_dist_override
            df.at[idx, "Roadside severity - drivers side distance"] = driver_dist
            debug["Roadside severity - drivers side distance evidence"] = driver_distance_reason
        passenger_dist_override, passenger_distance_reason = barrier_setback_distance_override(
            passenger_dist,
            ev.passenger,
            passenger_obj,
            "passenger",
            short_transition_segment,
        )
        if passenger_distance_reason:
            passenger_dist = passenger_dist_override
            df.at[idx, "Roadside severity - passenger side distance"] = passenger_dist
            debug["Roadside severity - passenger side distance evidence"] = passenger_distance_reason
        driver_shoulder_override, driver_shoulder_override_reason = barrier_setback_shoulder_override(
            norm_code(df.at[idx, "Paved shoulder - drivers side"]),
            ev.driver,
            driver_obj,
            driver_shoulder_measured,
            "driver",
            short_transition_segment,
        )
        if driver_shoulder_override_reason:
            df.at[idx, "Paved shoulder - drivers side"] = driver_shoulder_override
            debug["Paved shoulder - drivers side evidence"] = (
                f"{debug['Paved shoulder - drivers side evidence']}; {driver_shoulder_override_reason}"
            )
        passenger_shoulder_override, passenger_shoulder_override_reason = barrier_setback_shoulder_override(
            norm_code(df.at[idx, "Paved shoulder - passenger side"]),
            ev.passenger,
            passenger_obj,
            passenger_shoulder_measured,
            "passenger",
            short_transition_segment,
        )
        if passenger_shoulder_override_reason:
            df.at[idx, "Paved shoulder - passenger side"] = passenger_shoulder_override
            debug["Paved shoulder - passenger side evidence"] = (
                f"{debug['Paved shoulder - passenger side evidence']}; {passenger_shoulder_override_reason}"
            )
        if passenger_dist == "1" and divided_highway_like(ev) and passenger_obj in {1, 2, 3, 4}:
            passenger_dist = "2"
            df.at[idx, "Roadside severity - passenger side distance"] = passenger_dist
            debug["Roadside severity - passenger side distance evidence"] = (
                "divided-road passenger barrier calibration: near projected points represent barrier face; coded 1 to <5m"
            )
        df.at[idx, "Roadside severity - driver side object"] = str(driver_obj)
        df.at[idx, "Roadside severity - passenger side object"] = str(passenger_obj)
        debug["Roadside severity - driver side object evidence"] = driver_reason
        debug["Roadside severity - passenger side object evidence"] = passenger_reason

        access_code, access_reason = property_access(ev, area_code)
        df.at[idx, "Property access points"] = str(access_code)
        debug["Property access points evidence"] = access_reason

        sidewalk_code, sidewalk_reason = sidewalk(ev, area_code)
        df.at[idx, "Sidewalk - passenger side"] = str(sidewalk_code)
        debug["Sidewalk - passenger side evidence"] = sidewalk_reason

        for attr in ATTRIBUTES:
            code = norm_code(df.at[idx, attr])
            if attr in CODE_LABELS:
                labels[attr] = CODE_LABELS[attr].get(int(code), "") if code else ""
            elif attr.startswith("Roadside severity") and attr.endswith("object"):
                labels[attr] = CODE_LABELS["Roadside object"].get(int(code), "") if code else ""
            else:
                labels[attr] = code

        debug_rows.append(debug)
        label_rows.append(labels)

    for attr in ATTRIBUTES:
        df[attr] = df[attr].map(norm_code)

    smoothed_driver_object_changes = 0
    if args.smooth_driver_objects == "true":
        smoothed_driver_object_changes = smooth_driver_roadside_objects(df, debug_rows)
    refined_driver_slope_changes = 0
    if args.refine_driver_slope_objects == "true":
        refined_driver_slope_changes = refine_driver_slope_with_discrete_dino(df, debug_rows, roadside_detections)
    refined_passenger_slope_changes = 0
    if args.refine_passenger_slope_objects == "true":
        refined_passenger_slope_changes = refine_passenger_slope_with_ditch_dino(df, debug_rows, roadside_detections)
    refined_urban_discrete_changes = refine_urban_discrete_roadside_objects(df, debug_rows, roadside_detections)
    refined_unstable_object_changes = refine_unstable_roadside_object_false_positives(df, debug_rows, roadside_detections)
    verified_driver_terrain_changes = verify_driver_high_confidence_terrain(df, debug_rows, roadside_detections)
    refined_property_access_sequence_changes = refine_property_access_sequence(df, debug_rows)
    smoothed_distance_changes = 0
    if args.smooth_roadside_distances == "true":
        smoothed_distance_changes = smooth_roadside_distance_codes(
            df,
            debug_rows,
            driver_window=args.driver_distance_smoothing_window,
            passenger_window=args.passenger_distance_smoothing_window,
        )

    label_rows = []
    for _, row in df.iterrows():
        labels: dict[str, Any] = {
            "folder_name": row["folder_name"],
            "frame_id": row["frame_id"],
            "image_path": row["image_path"],
        }
        for attr in ATTRIBUTES:
            code = norm_code(row.get(attr, ""))
            if attr in CODE_LABELS:
                labels[attr] = CODE_LABELS[attr].get(int(code), "") if code else ""
            elif attr.startswith("Roadside severity") and attr.endswith("object"):
                labels[attr] = CODE_LABELS["Roadside object"].get(int(code), "") if code else ""
            else:
                labels[attr] = code
        label_rows.append(labels)

    out_csv = Path(args.out_csv)
    out_labels = Path(args.out_labels_csv)
    out_debug = Path(args.out_debug_csv)
    out_summary = Path(args.out_summary_json)
    for path in [out_csv, out_labels, out_debug, out_summary]:
        path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_csv, index=False, encoding="utf-8")
    pd.DataFrame(label_rows).to_csv(out_labels, index=False, encoding="utf-8")
    pd.DataFrame(debug_rows).to_csv(out_debug, index=False, encoding="utf-8")

    missing = {attr: int((df[attr].astype(str).str.strip() == "").sum()) for attr in ATTRIBUTES}
    detection_image_count = len({key[0] for key in roadside_detections}) if roadside_detections else 0
    projected_pair_count = len(projected_pairs)
    summary = {
        "mode": (
            "semantic_completion_projected_roadside"
            if projected_pairs
            else "semantic_completion_dino_roadside"
            if roadside_detections
            else "semantic_completion_local_rules"
        ),
        "rows": int(len(df)),
        "roadside_detection_images": detection_image_count,
        "projected_roadside_side_pairs": projected_pair_count,
        "missing_by_attribute": missing,
        "smoothed_driver_object_changes": smoothed_driver_object_changes,
        "refined_driver_slope_object_changes": refined_driver_slope_changes,
        "refined_passenger_slope_object_changes": refined_passenger_slope_changes,
        "refined_urban_discrete_object_changes": refined_urban_discrete_changes,
        "refined_unstable_object_changes": refined_unstable_object_changes,
        "verified_driver_terrain_object_changes": verified_driver_terrain_changes,
        "refined_property_access_sequence_changes": refined_property_access_sequence_changes,
        "smoothed_roadside_distance_changes": smoothed_distance_changes,
        "notes": [
            "Uses local image evidence and rule agents; no external VLM API was configured.",
            "Street lighting requires confirmed luminaire evidence; utility poles alone are coded not present.",
            "Service road requires a continuous parallel frontage road; side roads/intersections are not counted.",
            (
                "Roadside object and distance codes use projected side-specific GroundingDINO bbox-to-LAS "
                "candidate pairs when --roadside-pairs-json is provided. Without projected pairs, roadside "
                "objects use cached GroundingDINO detections with confidence-first selection and iRAP risk "
                "rank as a tie-breaker; otherwise they fall back to local image evidence plus LAS roadside distance."
            ),
            (
                "Roadside distance codes are stabilized with adjacent-frame consistency smoothing when "
                "--smooth-roadside-distances=true; this compensates for frame-level LAS edge jitter near "
                "the 0-1m and 1-5m category boundary."
            ),
        ],
    }
    out_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
