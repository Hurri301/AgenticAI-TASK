from __future__ import annotations

import math

from .geometry import matvec3, transpose3


def project_world_to_pano_pixels(
    points_w,
    t_w_cam,
    R_w_cam,
    image_size,
    *,
    v_top: float,
    v_bottom: float,
    flip_pano_u: bool,
):
    W, H = image_size
    R_cw = transpose3(R_w_cam)
    out_uv = []
    valid = []
    for p in points_w:
        dx, dy, dz = float(p[0] - t_w_cam[0]), float(p[1] - t_w_cam[1]), float(p[2] - t_w_cam[2])
        xc, yc, zc = matvec3(R_cw, (dx, dy, dz))
        n = math.sqrt(xc * xc + yc * yc + zc * zc)
        if n <= 1e-12:
            out_uv.append((0.0, 0.0))
            valid.append(False)
            continue
        xh, yh, zh = xc / n, yc / n, zc / n
        yaw = math.atan2(yh, xh)
        if flip_pano_u:
            yaw = -yaw
        pitch = math.atan2(zh, math.sqrt(xh * xh + yh * yh))
        u = (((yaw + math.pi) / (2.0 * math.pi)) * W) % W
        v = v_top + ((math.pi / 2.0 - pitch) / math.pi) * (v_bottom - v_top)
        v = max(0.0, min(H - 1.0, v))
        out_uv.append((float(u), float(v)))
        valid.append(True)
    return out_uv, valid


def minimum_circular_interval(us, width: int):
    if not us:
        return 0.0, 0.0
    if len(us) == 1:
        return float(us[0]), float(us[0])
    ang = sorted((u / width) * 2.0 * math.pi for u in us)
    max_gap = -1.0
    max_i = 0
    n = len(ang)
    for i in range(n):
        a0 = ang[i]
        a1 = ang[(i + 1) % n] + (2.0 * math.pi if i == n - 1 else 0.0)
        gap = a1 - a0
        if gap > max_gap:
            max_gap = gap
            max_i = i
    start = ang[(max_i + 1) % n]
    end = ang[max_i]
    u0 = float((start / (2.0 * math.pi)) * width) % width
    u1 = float((end / (2.0 * math.pi)) * width) % width
    return u0, u1
