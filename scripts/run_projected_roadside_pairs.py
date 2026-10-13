from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image
from pyproj import Transformer
from pyproj.transformer import TransformerGroup

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mm_link.geometry import build_R_w_imu_applanix_ned321_to_enu, compose_pose  # noqa: E402
from mm_link.io import load_extrinsics_xml  # noqa: E402
from mm_link.api import _project_world_to_pano_pixels_np  # noqa: E402
from mm_link.types import ProjectionConfig  # noqa: E402

from complete_semantic_attributes import (  # noqa: E402
    CODE_LABELS,
    DISTANCE_LABELS,
    dino_candidate_valid,
    load_risk_ranks,
    object_code_from_category,
)


DISTANCE_CODES = {label: code for code, label in DISTANCE_LABELS.items()}


def frame_id_from_name(name: str) -> int | None:
    match = re.search(r"_(\d+)\.(?:jpg|jpeg|png)$", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def load_lookup(path: Path, folder_name: str) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("Frame Folder") == folder_name:
                rows[int(row["Frame ID"])] = row
    return rows


def resolve_las(dataset_root: Path, folder_name: str, cloud_ref: str) -> Path:
    cloud_stem = Path(str(cloud_ref).replace("\\", "/")).stem
    folder_dir = dataset_root / folder_name
    matches = [p for p in sorted(folder_dir.rglob(f"{cloud_stem}.las")) if "elipsoidal" not in p.name.lower()]
    if not matches:
        matches = sorted(folder_dir.rglob(f"{cloud_stem}.las"))
    if not matches:
        raise FileNotFoundError(f"Cannot resolve LAS for {cloud_ref}")
    return matches[0]


def build_geoid_transformer() -> Transformer:
    src_crs = "EPSG:4937"
    dst_crs = "EPSG:4258+5782"
    group = TransformerGroup(src_crs, dst_crs, always_xy=True)
    if not group.best_available:
        raise RuntimeError("EGM08-REDNAP geoid grid is unavailable to PROJ.")
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def geoid_corrected_row(row: dict[str, str], transformer: Transformer | None) -> dict[str, str]:
    if transformer is None:
        return row
    corrected = dict(row)
    lon = float(row["Lon"])
    lat = float(row["Lat"])
    h_ellip = float(row["Z"])
    _, _, h_orthometric = transformer.transform(lon, lat, h_ellip)
    corrected["Z"] = str(float(h_orthometric))
    return corrected


def read_las_arrays(path: Path) -> tuple[np.ndarray, np.ndarray]:
    try:
        import laspy

        las = laspy.read(path)
        xyz = np.column_stack((np.asarray(las.x), np.asarray(las.y), np.asarray(las.z))).astype(float, copy=False)
        intensity = np.asarray(getattr(las, "intensity", np.zeros(len(xyz))), dtype=float)
        return xyz, intensity
    except Exception:
        from mm_link.io import load_las_points

        xyz_list, intensity_list = load_las_points(str(path))
        xyz = np.asarray(xyz_list, dtype=float)
        intensity = np.asarray(intensity_list if intensity_list is not None else np.zeros(len(xyz)), dtype=float)
        return xyz, intensity


def unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n else v


def forward_lateral(roll: float, pitch: float, heading: float) -> tuple[np.ndarray, np.ndarray]:
    r = build_R_w_imu_applanix_ned321_to_enu(roll, pitch, heading)
    forward = unit(np.asarray([r[0][0], r[1][0]], dtype=float))
    lateral = np.asarray([-forward[1], forward[0]], dtype=float)
    return forward, lateral


def contiguous_interval_around_zero(centers: np.ndarray, occupied: np.ndarray) -> tuple[float, float] | None:
    if not np.any(occupied):
        return None
    zero_idx = int(np.argmin(np.abs(centers)))
    if not occupied[zero_idx]:
        occupied_indices = np.flatnonzero(occupied)
        zero_idx = int(occupied_indices[np.argmin(np.abs(centers[occupied_indices]))])
    left = right = zero_idx
    while left - 1 >= 0 and occupied[left - 1]:
        left -= 1
    while right + 1 < len(occupied) and occupied[right + 1]:
        right += 1
    step = float(np.median(np.diff(centers))) if len(centers) > 1 else 0.25
    return float(centers[left] - step / 2.0), float(centers[right] + step / 2.0)


def distance_label(distance_m: float) -> str:
    if distance_m < 1.0:
        return "0 to <1m"
    if distance_m < 5.0:
        return "1 to <5m"
    if distance_m < 10.0:
        return "5 to <10m"
    return ">=10m"


def detection_min_confidence(
    code: str,
    *,
    side: str,
    min_confidence: float,
    barrier_min_confidence: float,
    rigid_min_confidence: float,
    terrain_min_confidence: float,
    driver_barrier_min_confidence: float | None,
    passenger_barrier_min_confidence: float | None,
    driver_rigid_min_confidence: float | None,
    passenger_rigid_min_confidence: float | None,
) -> float:
    if code in {"1", "2", "3", "4"}:
        if side == "driver" and driver_barrier_min_confidence is not None:
            return driver_barrier_min_confidence
        if side == "passenger" and passenger_barrier_min_confidence is not None:
            return passenger_barrier_min_confidence
        return barrier_min_confidence
    if code in {"6", "7", "8", "9", "10"}:
        return terrain_min_confidence
    if code in {"11", "12", "13", "14", "15", "16"}:
        if side == "driver" and driver_rigid_min_confidence is not None:
            return driver_rigid_min_confidence
        if side == "passenger" and passenger_rigid_min_confidence is not None:
            return passenger_rigid_min_confidence
        return rigid_min_confidence
    return min_confidence


def load_detections(
    path: Path,
    *,
    min_confidence: float,
    barrier_min_confidence: float,
    rigid_min_confidence: float,
    terrain_min_confidence: float,
    driver_barrier_min_confidence: float | None,
    passenger_barrier_min_confidence: float | None,
    driver_rigid_min_confidence: float | None,
    passenger_rigid_min_confidence: float | None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for image in payload.get("images", []):
        image_name = str(image.get("image_name") or Path(str(image.get("image_path", ""))).name)
        stem = Path(image_name).stem
        for side in image.get("sides", []):
            side_name = str(side.get("side", "")).strip().lower()
            if side_name not in {"driver", "passenger"}:
                continue
            objects: list[dict[str, Any]] = []
            for obj in side.get("objects", []):
                if not isinstance(obj, dict):
                    continue
                confidence = float(obj.get("confidence", 0.0) or 0.0)
                code = object_code_from_category(str(obj.get("irap_category", "")))
                if code is None or code == "17":
                    continue
                threshold = detection_min_confidence(
                    code,
                    side=side_name,
                    min_confidence=min_confidence,
                    barrier_min_confidence=barrier_min_confidence,
                    rigid_min_confidence=rigid_min_confidence,
                    terrain_min_confidence=terrain_min_confidence,
                    driver_barrier_min_confidence=driver_barrier_min_confidence,
                    passenger_barrier_min_confidence=passenger_barrier_min_confidence,
                    driver_rigid_min_confidence=driver_rigid_min_confidence,
                    passenger_rigid_min_confidence=passenger_rigid_min_confidence,
                )
                if confidence < threshold:
                    continue
                valid, reason = dino_candidate_valid(obj, code)
                if not valid:
                    item = dict(obj)
                    item["skip_reason"] = reason
                    continue
                item = dict(obj)
                item["projection_min_confidence"] = threshold
                objects.append(item)
            out[(stem, side_name)] = objects
    return out


def road_interval_for_frame(
    xyz: np.ndarray,
    row: dict[str, str],
    *,
    local_radius_m: float,
    longitudinal_window_m: float,
    lateral_search_m: float,
    bin_m: float,
) -> dict[str, Any]:
    cam_xy = np.asarray([float(row["X"]), float(row["Y"])], dtype=float)
    forward, lateral = forward_lateral(float(row["Roll"]), float(row["Pitch"]), float(row["Heading"]))
    delta_xy = xyz[:, :2] - cam_xy
    radial = np.linalg.norm(delta_xy, axis=1)
    local_mask = radial <= local_radius_m
    local = xyz[local_mask]
    if len(local) == 0:
        raise ValueError("No local LAS points inside radius")
    local_delta = local[:, :2] - cam_xy
    s = local_delta @ forward
    l = local_delta @ lateral
    corridor_mask = (np.abs(s) <= longitudinal_window_m) & (np.abs(l) <= lateral_search_m)
    if np.count_nonzero(corridor_mask) >= 100:
        ground_z = float(np.percentile(local[:, 2][corridor_mask], 12))
    else:
        ground_z = float(np.percentile(local[:, 2], 12))
    z_rel = local[:, 2] - ground_z
    section_mask = corridor_mask & (z_rel >= -0.25) & (z_rel <= 0.35)
    section_l = l[section_mask]
    section_z = z_rel[section_mask]

    centers = np.arange(-lateral_search_m + bin_m / 2.0, lateral_search_m, bin_m)
    occupied = np.zeros(len(centers), dtype=bool)
    roughness_values = np.full(len(centers), np.nan)
    counts = np.zeros(len(centers), dtype=int)
    for j, center in enumerate(centers):
        m = (section_l >= center - bin_m / 2.0) & (section_l < center + bin_m / 2.0)
        counts[j] = int(np.count_nonzero(m))
        if counts[j] >= 12:
            z_band = section_z[m]
            roughness = float(np.percentile(z_band, 90) - np.percentile(z_band, 10))
            roughness_values[j] = roughness
            occupied[j] = roughness <= 0.20
    interval = contiguous_interval_around_zero(centers, occupied)
    if interval is None:
        valid_roughness = roughness_values[np.isfinite(roughness_values)]
        if len(valid_roughness) > 0:
            adaptive_threshold = min(0.50, max(0.30, float(np.percentile(valid_roughness, 65))))
            occupied = np.isfinite(roughness_values) & (counts >= 12) & (roughness_values <= adaptive_threshold)
            interval = contiguous_interval_around_zero(centers, occupied)
    if interval is None:
        raise ValueError("No road interval found")
    return {
        "road_left": interval[0],
        "road_right": interval[1],
        "ground_z": ground_z,
        "forward": forward,
        "lateral": lateral,
    }


def project_local_points(
    xyz: np.ndarray,
    row: dict[str, str],
    image_path: Path,
    extrinsics: tuple[tuple[float, float, float, float], ...],
    *,
    max_distance_m: float,
    config: ProjectionConfig,
) -> dict[str, Any]:
    with Image.open(image_path) as image:
        image_size = (int(image.width), int(image.height))
    r_w_imu = build_R_w_imu_applanix_ned321_to_enu(float(row["Roll"]), float(row["Pitch"]), float(row["Heading"]))
    t_w_cam, r_w_cam = compose_pose(
        (float(row["X"]), float(row["Y"]), float(row["Z"])),
        r_w_imu,
        extrinsics,
        invert_extrinsics=config.invert_extrinsics,
    )
    delta = xyz - np.asarray(t_w_cam, dtype=float)
    radial = np.linalg.norm(delta, axis=1)
    local_idx = np.flatnonzero(radial <= max_distance_m)
    points = xyz[local_idx]
    v_top, v_bottom = config.resolved_vertical_bounds(image_size[1])
    uvs, valid = _project_world_to_pano_pixels_np(
        points,
        t_w_cam,
        r_w_cam,
        image_size,
        v_top=v_top,
        v_bottom=v_bottom,
        flip_pano_u=config.flip_pano_u,
    )
    uv_array = np.asarray(uvs, dtype=float)
    if uv_array.size == 0:
        uv_array = np.empty((0, 2), dtype=float)
    return {"indices": local_idx, "points": points, "uvs": uv_array, "valid": np.asarray(valid, dtype=bool)}


def candidate_distance(
    obj: dict[str, Any],
    side: str,
    projected: dict[str, Any],
    frame_geom: dict[str, Any],
    *,
    min_points: int,
) -> dict[str, Any] | None:
    bbox = obj.get("bbox_xyxy") or [0, 0, 0, 0]
    x1, y1, x2, y2 = [float(v) for v in bbox]
    uvs = projected["uvs"]
    valid = projected["valid"]
    mask = valid & (uvs[:, 0] >= x1) & (uvs[:, 0] <= x2) & (uvs[:, 1] >= y1) & (uvs[:, 1] <= y2)
    if int(np.count_nonzero(mask)) < min_points:
        return None
    points = projected["points"][mask]
    cam_xy = np.asarray([float(frame_geom["row"]["X"]), float(frame_geom["row"]["Y"])], dtype=float)
    local_delta = points[:, :2] - cam_xy
    lateral_values = local_delta @ frame_geom["lateral"]
    z_rel = points[:, 2] - float(frame_geom["ground_z"])
    sign = 1.0 if side == "driver" else -1.0
    edge = float(frame_geom["road_right"] if side == "driver" else frame_geom["road_left"])
    side_mask = ((lateral_values - edge) * sign) > 0
    code = object_code_from_category(str(obj.get("irap_category", "")))
    if code in {"1", "2", "3", "4", "11", "12", "13", "14", "15", "16"}:
        side_mask &= z_rel >= 0.15
    if int(np.count_nonzero(side_mask)) < min_points:
        side_mask = ((lateral_values - edge) * sign) > 0
    if int(np.count_nonzero(side_mask)) < min_points:
        return None
    gap = np.abs(lateral_values[side_mask] - edge)
    distance_m = max(0.0, float(np.percentile(gap, 5)))
    return {
        "distance_m": distance_m,
        "projected_point_count": int(np.count_nonzero(mask)),
        "side_point_count": int(np.count_nonzero(side_mask)),
    }


def bbox_shape(obj: dict[str, Any]) -> dict[str, float]:
    bbox = obj.get("bbox_xyxy") or [0, 0, 0, 0]
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except Exception:
        x1 = y1 = x2 = y2 = 0.0
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": max(0.0, x2 - x1),
        "height": max(0.0, y2 - y1),
        "bottom": y2,
        "area": max(0.0, x2 - x1) * max(0.0, y2 - y1),
    }


def driver_guardrail_ribbon(candidate: dict[str, Any]) -> bool:
    if str(candidate.get("side", "")) != "driver":
        return False
    if int(candidate.get("object_code", -1)) not in {1, 2, 3, 4}:
        return False
    shape = bbox_shape(candidate)
    return (
        shape["x1"] <= 1510
        and shape["width"] >= 480
        and 55 <= shape["height"] <= 160
        and 555 <= shape["bottom"] <= 685
    )


def select_candidate(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    guardrails = [c for c in candidates if driver_guardrail_ribbon(c)]
    if guardrails:
        best_conf = max(float(c.get("confidence", 0.0) or 0.0) for c in guardrails)
        metal_like = [
            c for c in guardrails
            if int(c.get("object_code", -1)) == 1 and float(c.get("confidence", 0.0) or 0.0) >= best_conf - 0.12
        ]
        pool = metal_like or guardrails
        pool.sort(key=lambda c: (float(c["distance_m"]), -float(c.get("confidence", 0.0) or 0.0), int(c["risk_rank"])))
        selected = pool[0]
        return selected, "driver_guardrail_ribbon_over_terrain"

    candidates.sort(key=lambda c: (int(c["risk_rank"]), float(c["distance_m"]), -float(c["confidence"])))
    return candidates[0], "risk_rank_distance_confidence"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project DINO roadside bboxes to LAS and select iRAP object-distance pairs.")
    parser.add_argument("--detections-json", required=True)
    parser.add_argument("--lookup-csv", default="lookup_dataset_filtered_corrected.csv")
    parser.add_argument("--dataset-root", default="Dataset")
    parser.add_argument("--folder-name", default="01_N3")
    parser.add_argument("--images-csv", required=True, help="Prediction/codes CSV with folder_name, frame_id, image_path.")
    parser.add_argument("--extrinsics", default="Dataset/01_N3/ladybug_13185920_20200219_095143_Portugal_000-000.xml")
    parser.add_argument("--risk-hierarchy-csv", default=None)
    parser.add_argument("--geoid-correction", choices=["egm08_rednap", "none"], default="egm08_rednap")
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument("--barrier-min-confidence", type=float, default=None)
    parser.add_argument("--rigid-min-confidence", type=float, default=None)
    parser.add_argument("--terrain-min-confidence", type=float, default=None)
    parser.add_argument("--driver-barrier-min-confidence", type=float, default=None)
    parser.add_argument("--passenger-barrier-min-confidence", type=float, default=None)
    parser.add_argument("--driver-rigid-min-confidence", type=float, default=None)
    parser.add_argument("--passenger-rigid-min-confidence", type=float, default=None)
    parser.add_argument("--max-distance-m", type=float, default=45.0)
    parser.add_argument("--min-points", type=int, default=3)
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--local-radius-m", type=float, default=60.0)
    parser.add_argument("--longitudinal-window-m", type=float, default=18.0)
    parser.add_argument("--lateral-search-m", type=float, default=14.0)
    parser.add_argument("--bin-m", type=float, default=0.25)
    parser.add_argument(
        "--flip-pano-u",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the panorama horizontal flip convention for projection (default: true).",
    )
    parser.add_argument("--bbox-offset-x", type=float, default=0.0)
    parser.add_argument("--bbox-offset-y", type=float, default=0.0)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root)
    lookup = load_lookup(Path(args.lookup_csv), args.folder_name)
    barrier_min_confidence = args.barrier_min_confidence if args.barrier_min_confidence is not None else args.min_confidence
    rigid_min_confidence = args.rigid_min_confidence if args.rigid_min_confidence is not None else args.min_confidence
    terrain_min_confidence = args.terrain_min_confidence if args.terrain_min_confidence is not None else args.min_confidence
    detections = load_detections(
        Path(args.detections_json),
        min_confidence=args.min_confidence,
        barrier_min_confidence=barrier_min_confidence,
        rigid_min_confidence=rigid_min_confidence,
        terrain_min_confidence=terrain_min_confidence,
        driver_barrier_min_confidence=args.driver_barrier_min_confidence,
        passenger_barrier_min_confidence=args.passenger_barrier_min_confidence,
        driver_rigid_min_confidence=args.driver_rigid_min_confidence,
        passenger_rigid_min_confidence=args.passenger_rigid_min_confidence,
    )
    risk_ranks = load_risk_ranks(args.risk_hierarchy_csv)
    images_df = pd.read_csv(args.images_csv, keep_default_na=False)
    extrinsics = load_extrinsics_xml(str(Path(args.extrinsics)))
    geoid_transformer = build_geoid_transformer() if args.geoid_correction == "egm08_rednap" else None
    config = ProjectionConfig(flip_pano_u=args.flip_pano_u)

    image_rows: list[dict[str, Any]] = []
    for _, row in images_df.iterrows():
        if str(row.get("folder_name", "")).strip() != args.folder_name:
            continue
        frame_id = int(row["frame_id"])
        if frame_id not in lookup:
            continue
        image_rows.append(
            {
                "folder_name": args.folder_name,
                "frame_id": frame_id,
                "image_path": str(row["image_path"]),
                "lookup": lookup[frame_id],
            }
        )

    by_las: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in image_rows:
        las = resolve_las(dataset_root, args.folder_name, item["lookup"]["Point Cloud File"])
        item["las_path"] = str(las)
        by_las[str(las)].append(item)

    pair_rank_hits = 0
    outputs: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for las_text, rows in sorted(by_las.items()):
        las_path = Path(las_text)
        xyz, _intensity = read_las_arrays(las_path)
        for frame_pos, item in enumerate(rows, start=1):
            image_path = Path(item["image_path"])
            stem = image_path.stem
            if not detections.get((stem, "driver")) and not detections.get((stem, "passenger")):
                continue
            if args.progress_every > 0 and frame_pos % args.progress_every == 0:
                print(f"processing {las_path.name}: frame {frame_pos}/{len(rows)}", flush=True)
            lookup_row = geoid_corrected_row(item["lookup"], geoid_transformer)
            try:
                road = road_interval_for_frame(
                    xyz,
                    lookup_row,
                    local_radius_m=args.local_radius_m,
                    longitudinal_window_m=args.longitudinal_window_m,
                    lateral_search_m=args.lateral_search_m,
                    bin_m=args.bin_m,
                )
                road["row"] = lookup_row
                projected = project_local_points(
                    xyz,
                    lookup_row,
                    image_path,
                    extrinsics,
                    max_distance_m=args.max_distance_m,
                    config=config,
                )
                if args.bbox_offset_x or args.bbox_offset_y:
                    projected["uvs"] = projected["uvs"] + np.asarray([args.bbox_offset_x, args.bbox_offset_y], dtype=float)
            except Exception as exc:
                errors.append({"frame_id": item["frame_id"], "image_path": str(image_path), "error": str(exc)})
                continue

            for side in ("driver", "passenger"):
                candidates: list[dict[str, Any]] = []
                for obj_index, obj in enumerate(detections.get((stem, side), [])):
                    code = object_code_from_category(str(obj.get("irap_category", "")))
                    if code is None:
                        continue
                    dist = candidate_distance(obj, side, projected, road, min_points=args.min_points)
                    if dist is None:
                        continue
                    label = CODE_LABELS["Roadside object"][int(code)]
                    dist_label = distance_label(float(dist["distance_m"]))
                    rank = risk_ranks.get((dist_label, label), 999)
                    if rank != 999:
                        pair_rank_hits += 1
                    candidate = {
                        "folder_name": args.folder_name,
                        "frame_id": item["frame_id"],
                        "image_path": str(image_path),
                        "image_name": image_path.name,
                        "side": side,
                        "object_code": int(code),
                        "object_category": label,
                        "distance_code": int(DISTANCE_CODES[dist_label]),
                        "distance_category": dist_label,
                        "distance_m": round(float(dist["distance_m"]), 3),
                        "risk_rank": int(rank),
                        "confidence": round(float(obj.get("confidence", 0.0) or 0.0), 4),
                        "bbox_xyxy": obj.get("bbox_xyxy"),
                        "object_index": obj_index,
                        **dist,
                    }
                    candidates.append(candidate)
                    candidate_rows.append(candidate)
                if candidates:
                    selected, selection_reason = select_candidate(candidates)
                else:
                    continue
                selected = dict(selected)
                selected["candidates_considered"] = candidates
                selected["selection_reason"] = selection_reason
                outputs.append(selected)

    payload = {
        "mode": "projected_roadside_pairs",
        "settings": {
            "folder_name": args.folder_name,
            "detections_json": str(Path(args.detections_json)),
            "min_confidence": args.min_confidence,
            "barrier_min_confidence": barrier_min_confidence,
            "rigid_min_confidence": rigid_min_confidence,
            "terrain_min_confidence": terrain_min_confidence,
            "driver_barrier_min_confidence": args.driver_barrier_min_confidence,
            "passenger_barrier_min_confidence": args.passenger_barrier_min_confidence,
            "driver_rigid_min_confidence": args.driver_rigid_min_confidence,
            "passenger_rigid_min_confidence": args.passenger_rigid_min_confidence,
            "max_distance_m": args.max_distance_m,
            "min_points": args.min_points,
            "flip_pano_u": args.flip_pano_u,
            "bbox_offset_x": args.bbox_offset_x,
            "bbox_offset_y": args.bbox_offset_y,
        },
        "counts": {
            "images": len(image_rows),
            "side_results": len(outputs),
            "candidate_pairs": len(candidate_rows),
            "risk_rank_hits": pair_rank_hits,
            "errors": len(errors),
        },
        "results": outputs,
        "errors": errors,
    }
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(candidate_rows).to_csv(out_csv, index=False, encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
