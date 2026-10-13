from __future__ import annotations

import math
import struct
from typing import Any

import numpy as np

from .geometry import build_R_w_imu_applanix_ned321_to_enu, compose_pose
from .io import load_extrinsics_xml, load_image_size, load_las_points, load_poses_csv
from .visualization import save_point_overlay
from .projection import minimum_circular_interval, project_world_to_pano_pixels
from .types import ProjectionConfig


def _resolve_config(config: ProjectionConfig | None) -> ProjectionConfig:
    return config if config is not None else ProjectionConfig()


def _pose_for_image(poses_csv: str, extrinsics_xml: str, image_id: str, image_size: tuple[int, int], config: ProjectionConfig):
    poses = load_poses_csv(poses_csv)
    if image_id not in poses:
        raise KeyError(f"Image ID not found in poses CSV: {image_id}")
    p = poses[image_id]
    if config.pose_model != "applanix_ned321":
        raise ValueError("Only pose_model='applanix_ned321' is supported in clean API")
    R_w_imu = build_R_w_imu_applanix_ned321_to_enu(p.roll, p.pitch, p.heading)
    T_imu_cam = load_extrinsics_xml(extrinsics_xml)
    t_w_cam, R_w_cam = compose_pose((p.e, p.n, p.h), R_w_imu, T_imu_cam, invert_extrinsics=config.invert_extrinsics)
    v_top, v_bottom = config.resolved_vertical_bounds(image_size[1])
    return t_w_cam, R_w_cam, v_top, v_bottom



def _intensities_for_indices(intensity, indices):
    if intensity is None:
        return [0 for _ in indices]
    return [intensity[int(i)] for i in indices]


def _project_world_to_pano_pixels_np(
    points_w: np.ndarray,
    t_w_cam,
    R_w_cam,
    image_size: tuple[int, int],
    *,
    v_top: float,
    v_bottom: float,
    flip_pano_u: bool,
) -> tuple[list[tuple[float, float]], list[bool]]:
    W, H = image_size
    R_cw = np.asarray(R_w_cam, dtype=np.float64).T
    d = points_w - np.asarray(t_w_cam, dtype=np.float64)
    cam = d @ R_cw.T
    norm = np.linalg.norm(cam, axis=1)
    ok = norm > 1e-12
    uvs = np.zeros((len(points_w), 2), dtype=np.float64)
    if np.any(ok):
        unit = cam[ok] / norm[ok, None]
        yaw = np.arctan2(unit[:, 1], unit[:, 0])
        if flip_pano_u:
            yaw = -yaw
        pitch = np.arctan2(unit[:, 2], np.sqrt(unit[:, 0] * unit[:, 0] + unit[:, 1] * unit[:, 1]))
        uvs[ok, 0] = (((yaw + math.pi) / (2.0 * math.pi)) * W) % W
        v = v_top + ((math.pi / 2.0 - pitch) / math.pi) * (v_bottom - v_top)
        uvs[ok, 1] = np.clip(v, 0.0, H - 1.0)
    return [(float(u), float(v)) for u, v in uvs], [bool(v) for v in ok]


def _project_filtered_candidates(
    poses_csv: str,
    extrinsics_xml: str,
    las_path: str,
    image_path: str,
    image_id: str,
    *,
    max_distance_m: float | None,
    min_intensity: int | None,
    max_points: int | None,
    config: ProjectionConfig,
) -> dict[str, Any]:
    """Project candidate LAS points into a panorama once for multi-bbox filtering.

    The multi-image demo expects this shared helper so it can project the cloud
    one time and then count points for several 2D boxes. Keep this behavior
    aligned with bbox_to_point_indices.
    """
    image_size = load_image_size(image_path)
    t_w_cam, R_w_cam, v_top, v_bottom = _pose_for_image(poses_csv, extrinsics_xml, image_id, image_size, config)

    with open(las_path, "rb") as f:
        hdr = f.read(375)
    if hdr[:4] != b"LASF":
        raise ValueError("Invalid LAS signature")
    offset_to_point_data = struct.unpack_from("<I", hdr, 96)[0]
    record_length = struct.unpack_from("<H", hdr, 105)[0]
    point_count = struct.unpack_from("<I", hdr, 107)[0]
    x_scale, y_scale, z_scale = struct.unpack_from("<ddd", hdr, 131)
    x_off, y_off, z_off = struct.unpack_from("<ddd", hdr, 155)

    dtype = np.dtype(
        {
            "names": ["X", "Y", "Z", "intensity"],
            "formats": ["<i4", "<i4", "<i4", "<u2"],
            "offsets": [0, 4, 8, 12],
            "itemsize": record_length,
        }
    )
    cloud = np.memmap(las_path, dtype=dtype, mode="r", offset=offset_to_point_data, shape=(point_count,))

    candidates: list[int] = []
    uvs: list[tuple[float, float]] = []
    valid: list[bool] = []
    selected_intensity: list[int] = []
    chunk_size = 1_000_000
    for start in range(0, point_count, chunk_size):
        stop = min(start + chunk_size, point_count)
        xs = cloud["X"][start:stop].astype(np.float64) * x_scale + x_off
        ys = cloud["Y"][start:stop].astype(np.float64) * y_scale + y_off
        zs = cloud["Z"][start:stop].astype(np.float64) * z_scale + z_off
        mask = np.ones(stop - start, dtype=bool)
        if max_distance_m is not None:
            dx = xs - t_w_cam[0]
            dy = ys - t_w_cam[1]
            dz = zs - t_w_cam[2]
            mask &= (dx * dx + dy * dy + dz * dz) <= (max_distance_m * max_distance_m)
        if min_intensity is not None:
            mask &= cloud["intensity"][start:stop] >= min_intensity
        local = np.nonzero(mask)[0]
        if len(local) == 0:
            continue
        if max_points is not None:
            remaining = max_points - len(candidates)
            if remaining <= 0:
                break
            local = local[:remaining]
        points = np.column_stack((xs[local], ys[local], zs[local]))
        chunk_uvs, chunk_valid = _project_world_to_pano_pixels_np(
            points,
            t_w_cam,
            R_w_cam,
            image_size,
            v_top=v_top,
            v_bottom=v_bottom,
            flip_pano_u=config.flip_pano_u,
        )
        candidates.extend((start + int(i)) for i in local)
        uvs.extend(chunk_uvs)
        valid.extend(chunk_valid)
        selected_intensity.extend(int(v) for v in cloud["intensity"][start:stop][local])
        if max_points is not None and len(candidates) >= max_points:
            break
    intensity = dict(zip(candidates, selected_intensity))
    return {
        "candidates": candidates,
        "uvs": uvs,
        "valid": valid,
        "intensity": intensity,
    }


def bbox_to_point_indices(
    poses_csv: str,
    extrinsics_xml: str,
    las_path: str,
    image_path: str,
    image_id: str,
    bbox_xyxy: tuple[int, int, int, int],
    *,
    max_distance_m: float | None = None,
    min_intensity: int | None = None,
    max_points: int | None = None,
    config: ProjectionConfig | None = None,
    return_pixels: bool = False,
    visualize: bool = False,
    visualization_out: str | None = None,
) -> dict[str, Any]:
    cfg = _resolve_config(config)
    image_size = load_image_size(image_path)
    t_w_cam, R_w_cam, v_top, v_bottom = _pose_for_image(poses_csv, extrinsics_xml, image_id, image_size, cfg)

    xyz, intensity = load_las_points(las_path)
    candidates = []
    for i, p in enumerate(xyz):
        if max_distance_m is not None:
            dx, dy, dz = p[0] - t_w_cam[0], p[1] - t_w_cam[1], p[2] - t_w_cam[2]
            if math.sqrt(dx * dx + dy * dy + dz * dz) > max_distance_m:
                continue
        if min_intensity is not None and intensity is not None and intensity[i] < min_intensity:
            continue
        candidates.append(i)
        if max_points is not None and len(candidates) >= max_points:
            break

    points = [xyz[i] for i in candidates]
    uvs, valid = project_world_to_pano_pixels(
        points,
        t_w_cam,
        R_w_cam,
        image_size,
        v_top=v_top,
        v_bottom=v_bottom,
        flip_pano_u=cfg.flip_pano_u,
    )

    x0, y0, x1, y1 = bbox_xyxy
    selected_indices = []
    selected_pixels = []
    projected = 0
    for local_i, ((u, v), ok) in enumerate(zip(uvs, valid)):
        if not ok:
            continue
        projected += 1
        if x0 <= u <= x1 and y0 <= v <= y1:
            selected_indices.append(candidates[local_i])
            selected_pixels.append((u, v))

    out: dict[str, Any] = {
        "indices": selected_indices,
        "stats": {
            "candidates": len(candidates),
            "projected": projected,
            "selected": len(selected_indices),
        },
    }
    if return_pixels:
        out["pixels"] = selected_pixels
    if visualize:
        overlay_path = visualization_out or "bbox_to_points_overlay.png"
        out["visualization_path"] = save_point_overlay(
            image_path,
            overlay_path,
            selected_pixels,
            _intensities_for_indices(intensity, selected_indices),
            bbox_xyxy=bbox_xyxy,
        )
    return out


def point_indices_to_bbox(
    poses_csv: str,
    extrinsics_xml: str,
    las_path: str,
    image_path: str,
    image_id: str,
    indices,
    *,
    config: ProjectionConfig | None = None,
    clamp_to_image: bool = True,
    return_pixels: bool = False,
    visualize: bool = False,
    visualization_out: str | None = None,
) -> dict[str, Any]:
    cfg = _resolve_config(config)
    image_size = load_image_size(image_path)
    W, H = image_size
    t_w_cam, R_w_cam, v_top, v_bottom = _pose_for_image(poses_csv, extrinsics_xml, image_id, image_size, cfg)

    xyz, intensity = load_las_points(las_path)
    idx = [int(i) for i in indices]
    if not idx:
        raise ValueError("indices cannot be empty")
    if min(idx) < 0 or max(idx) >= len(xyz):
        raise IndexError("indices out of LAS record range")

    points = [xyz[i] for i in idx]
    uvs, valid = project_world_to_pano_pixels(
        points, t_w_cam, R_w_cam, image_size, v_top=v_top, v_bottom=v_bottom, flip_pano_u=cfg.flip_pano_u
    )

    good = [uv for uv, ok in zip(uvs, valid) if ok]
    if not good:
        bbox = (0, 0, 0, 0)
    else:
        us = [u for u, _ in good]
        vs = [v for _, v in good]
        u0, u1 = minimum_circular_interval(us, W)
        v0, v1 = min(vs), max(vs)
        if clamp_to_image:
            v0 = max(0.0, min(H - 1.0, v0))
            v1 = max(0.0, min(H - 1.0, v1))
            u0 = max(0.0, min(W - 1.0, u0))
            u1 = max(0.0, min(W - 1.0, u1))
        bbox = (int(math.floor(u0)), int(math.floor(v0)), int(math.ceil(u1)), int(math.ceil(v1)))

    out: dict[str, Any] = {
        "bbox_xyxy": bbox,
        "stats": {"input": len(idx), "valid_projected": sum(1 for x in valid if x)},
    }
    if return_pixels:
        out["pixels"] = uvs
    if visualize:
        good_pixels = [uv for uv, ok in zip(uvs, valid) if ok]
        good_indices = [orig for orig, ok in zip(idx, valid) if ok]
        overlay_path = visualization_out or "points_to_bbox_overlay.png"
        out["visualization_path"] = save_point_overlay(
            image_path,
            overlay_path,
            good_pixels,
            _intensities_for_indices(intensity, good_indices),
            bbox_xyxy=bbox,
        )
    return out
