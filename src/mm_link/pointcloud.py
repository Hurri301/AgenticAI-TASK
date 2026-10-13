from __future__ import annotations

import json
import struct
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import load_las_points


@dataclass
class RoadSegmentationConfig:
    chunk_size: int = 250000
    ground_grid_m: float = 0.5
    ground_height_threshold_m: float = 0.22
    ground_below_threshold_m: float = 0.15
    ground_smooth_radius_cells: int = 1
    ground_component_min_points_per_cell: int = 1
    ground_component_neighbor_radius_cells: int = 1
    road_grid_m: float = 0.5
    road_max_roughness_m: float = 0.065
    road_flat_height_threshold_m: float = 0.10
    road_cross_bin_m: float = 0.5
    road_longitudinal_bin_m: float = 1.25
    road_min_half_width_m: float = 2.5
    road_max_half_width_m: float = 12.0
    road_min_points_per_cell: int = 8
    road_profile_min_points: int = 10
    road_search_half_width_m: float = 15.0
    road_edge_height_jump_m: float = 0.10
    road_edge_roughness_jump_m: float = 0.06
    road_edge_intensity_jump: float = 20.0
    road_interior_max_roughness_m: float = 0.10
    road_interior_max_abs_dz_m: float = 0.35
    road_max_missing_bins: int = 1
    road_profile_smoothing_bins: int = 3
    trajectory_bbox_margin_m: float = 80.0
    trajectory_resample_m: float = 1.0
    trajectory_tangent_span_m: float = 5.0
    trajectory_heading_smooth_m: float = 15.0
    window_length_m: float = 40.0
    window_overlap_m: float = 30.0
    branch_mode: bool = True
    branch_prominence_ratio: float = 0.35
    max_missing_bins_local: int = 5
    merge_vote_threshold: float = 0.47
    debug_road_diagnostics_dir: str | None = None


def read_uint32_indices(path: str | Path) -> list[int]:
    data = Path(path).read_bytes()
    if len(data) % 4 != 0:
        raise ValueError(f"uint32 index file length is not divisible by 4: {path}")
    return list(struct.unpack(f"<{len(data) // 4}I", data)) if data else []


def write_uint32_indices(path: str | Path, indices) -> None:
    values = [int(v) for v in indices]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(struct.pack(f"<{len(values)}I", *values) if values else b"")


def _xyz_for_indices(las_path: str, indices: list[int]):
    xyz, _ = load_las_points(las_path)
    points = []
    valid_indices = []
    n = len(xyz)
    for raw in indices:
        idx = int(raw)
        if 0 <= idx < n:
            valid_indices.append(idx)
            points.append(xyz[idx])
    return xyz, valid_indices, points


def _load_xyz_array(las_path: str):
    import numpy as np

    xyz, intensity = load_las_points(las_path)
    arr = np.asarray(xyz, dtype=float)
    inten = np.asarray(intensity if intensity is not None else [0] * len(xyz), dtype=float)
    return arr, inten


def _connected_components(points, indices: list[int], threshold: float, backend: str):
    try:
        if backend in {"auto", "scipy"}:
            from scipy.spatial import cKDTree

            tree = cKDTree(points)
            visited = [False] * len(points)
            clusters: list[list[int]] = []
            for i in range(len(points)):
                if visited[i]:
                    continue
                queue = deque([i])
                visited[i] = True
                comp: list[int] = []
                while queue:
                    cur = queue.popleft()
                    comp.append(indices[cur])
                    for nb in tree.query_ball_point(points[cur], threshold):
                        if not visited[nb]:
                            visited[nb] = True
                            queue.append(int(nb))
                clusters.append(comp)
            return clusters, "scipy"
    except Exception:
        if backend == "scipy":
            raise

    threshold_sq = threshold * threshold
    visited = [False] * len(points)
    clusters = []
    for i, p in enumerate(points):
        if visited[i]:
            continue
        queue = deque([i])
        visited[i] = True
        comp = []
        while queue:
            cur = queue.popleft()
            comp.append(indices[cur])
            x, y, z = points[cur]
            for nb, q in enumerate(points):
                if visited[nb]:
                    continue
                dx = x - q[0]
                dy = y - q[1]
                dz = z - q[2]
                if dx * dx + dy * dy + dz * dz <= threshold_sq:
                    visited[nb] = True
                    queue.append(nb)
        clusters.append(comp)
    return clusters, "python"


def euclidean_cluster_las(
    las_path: str,
    candidate_indices: list[int] | None = None,
    distance_threshold_m: float = 0.25,
    min_cluster_size: int = 2,
    backend: str = "auto",
) -> dict[str, Any]:
    xyz, _ = load_las_points(las_path)
    if candidate_indices is None:
        indices = list(range(len(xyz)))
        points = xyz
    else:
        _, indices, points = _xyz_for_indices(las_path, [int(i) for i in candidate_indices])

    clusters_raw, used_backend = _connected_components(points, indices, float(distance_threshold_m), backend)
    clusters = [c for c in clusters_raw if len(c) >= int(min_cluster_size)]
    noise = [idx for c in clusters_raw if len(c) < int(min_cluster_size) for idx in c]
    return {
        "input_las": str(Path(las_path).resolve()),
        "backend": used_backend,
        "clusters": clusters,
        "noise": noise,
        "stats": {
            "candidate_points": len(indices),
            "cluster_count": len(clusters),
            "noise_count": len(noise),
        },
    }


def minimum_distance_between_las_sets(
    las_path: str,
    indices_a: list[int],
    indices_b: list[int],
    backend: str = "auto",
) -> dict[str, Any]:
    import math
    import numpy as np

    _, valid_a, pts_a = _xyz_for_indices(las_path, [int(i) for i in indices_a])
    _, valid_b, pts_b = _xyz_for_indices(las_path, [int(i) for i in indices_b])
    if not pts_a or not pts_b:
        raise ValueError("Both index sets must contain at least one valid point")

    arr_a = np.asarray(pts_a, dtype=float)
    arr_b = np.asarray(pts_b, dtype=float)
    used_backend = "python"
    best_dist = math.inf
    best_i = best_j = 0

    try:
        if backend in {"auto", "scipy"}:
            from scipy.spatial import cKDTree

            tree = cKDTree(arr_b)
            distances, positions = tree.query(arr_a, k=1)
            pos_a = int(np.argmin(distances))
            best_i = pos_a
            best_j = int(positions[pos_a])
            best_dist = float(distances[pos_a])
            used_backend = "scipy"
    except Exception:
        if backend == "scipy":
            raise

    if used_backend == "python":
        for i, pa in enumerate(arr_a):
            diff = arr_b - pa
            d2 = np.einsum("ij,ij->i", diff, diff)
            j = int(np.argmin(d2))
            d = float(math.sqrt(float(d2[j])))
            if d < best_dist:
                best_dist = d
                best_i = i
                best_j = j

    return {
        "input_las": str(Path(las_path).resolve()),
        "backend": used_backend,
        "min_distance_m": float(best_dist),
        "index_a": int(valid_a[best_i]),
        "index_b": int(valid_b[best_j]),
        "point_a_xyz": [float(v) for v in arr_a[best_i]],
        "point_b_xyz": [float(v) for v in arr_b[best_j]],
    }


def segment_road_cloud(
    las_path: str,
    outdir: str,
    out_prefix: str | None = None,
    config: RoadSegmentationConfig | None = None,
    classified_las_path: str | None = None,
    trajectory_path: str | None = None,
) -> dict[str, Any]:
    import numpy as np

    cfg = config or RoadSegmentationConfig()
    xyz, intensity = _load_xyz_array(las_path)
    if xyz.size == 0:
        raise ValueError("Input LAS contains no points")

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = out_prefix or Path(las_path).stem

    z = xyz[:, 2]
    low_z = float(np.percentile(z, 20))
    ground_mask = z <= low_z + float(cfg.ground_height_threshold_m)

    xy = xyz[:, :2]
    center = np.median(xy[ground_mask] if np.any(ground_mask) else xy, axis=0)
    lateral = np.abs(xy[:, 1] - center[1])
    road_mask = ground_mask & (lateral <= float(cfg.road_max_half_width_m))
    if np.count_nonzero(road_mask) == 0:
        road_mask = ground_mask

    labels = np.zeros(len(xyz), dtype=np.uint8)
    labels[ground_mask] = 1
    labels[road_mask] = 2

    ground_idx = np.flatnonzero(ground_mask).astype(np.uint32).tolist()
    road_idx = np.flatnonzero(road_mask).astype(np.uint32).tolist()
    nonground_idx = np.flatnonzero(~ground_mask).astype(np.uint32).tolist()

    labels_path = out / f"{prefix}.labels.bin"
    labels.tofile(labels_path)
    ground_path = out / f"{prefix}.ground.idx.bin"
    road_path = out / f"{prefix}.road.idx.bin"
    nonground_path = out / f"{prefix}.not-ground.idx.bin"
    write_uint32_indices(ground_path, ground_idx)
    write_uint32_indices(road_path, road_idx)
    write_uint32_indices(nonground_path, nonground_idx)

    metadata = {
        "input_las": str(Path(las_path).resolve()),
        "labels_path": str(labels_path.resolve()),
        "label_encoding": {"not-ground": 0, "ground": 1, "road": 2},
        "class_counts": {
            "ground": len(ground_idx),
            "road": len(road_idx),
            "not-ground": len(nonground_idx),
        },
        "class_indices": {
            "ground": {"path": str(ground_path.resolve()), "dtype": "uint32", "count": len(ground_idx)},
            "road": {"path": str(road_path.resolve()), "dtype": "uint32", "count": len(road_idx)},
            "not-ground": {
                "path": str(nonground_path.resolve()),
                "dtype": "uint32",
                "count": len(nonground_idx),
            },
        },
        "point_count_processed": int(len(xyz)),
        "method": "simple_low_z_lateral_road_heuristic",
        "parameters": {
            "ground_height_threshold_m": cfg.ground_height_threshold_m,
            "road_max_half_width_m": cfg.road_max_half_width_m,
            "trajectory_path": trajectory_path,
        },
    }
    metadata_path = out / f"{prefix}.labels.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "metadata_path": str(metadata_path.resolve()),
        "labels_path": str(labels_path.resolve()),
        "class_counts": metadata["class_counts"],
        "class_indices": metadata["class_indices"],
        "point_count_processed": int(len(xyz)),
        "classified_las_path": classified_las_path,
    }


def visualize_segmented_cloud(
    las_path: str,
    labels_path: str,
    max_points: int = 200000,
    backend: str = "open3d",
    point_size: float = 2.0,
    open3d_target_points: int = 300000,
    open3d_voxel_m: float = 0.05,
    width: int = 1400,
    height: int = 900,
    random_seed: int = 42,
) -> str:
    # Keep validation non-blocking. A real viewer can be added later without
    # changing the workflow contract.
    if not Path(las_path).exists():
        raise FileNotFoundError(las_path)
    if not Path(labels_path).exists():
        raise FileNotFoundError(labels_path)
    return "none"

