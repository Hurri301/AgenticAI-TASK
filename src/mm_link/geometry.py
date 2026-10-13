from __future__ import annotations

import math


def matmul3(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def transpose3(r):
    return tuple(tuple(r[j][i] for j in range(3)) for i in range(3))


def matvec3(r, v):
    return tuple(sum(r[i][k] * v[k] for k in range(3)) for i in range(3))


def matmul4(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def invert_transform(T):
    R = tuple(tuple(T[i][j] for j in range(3)) for i in range(3))
    t = (T[0][3], T[1][3], T[2][3])
    Rt = transpose3(R)
    tinv = tuple(-sum(Rt[i][k] * t[k] for k in range(3)) for i in range(3))
    return (
        (Rt[0][0], Rt[0][1], Rt[0][2], tinv[0]),
        (Rt[1][0], Rt[1][1], Rt[1][2], tinv[1]),
        (Rt[2][0], Rt[2][1], Rt[2][2], tinv[2]),
        (0.0, 0.0, 0.0, 1.0),
    )


def build_R_w_imu_applanix_ned321_to_enu(roll: float, pitch: float, heading: float):
    r, p, h = math.radians(roll), math.radians(pitch), math.radians(heading)
    cx, sx = math.cos(r), math.sin(r)
    cy, sy = math.cos(p), math.sin(p)
    cz, sz = math.cos(h), math.sin(h)

    Rx = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    Ry = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    Rz = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))

    R_ned_from_body = matmul3(matmul3(Rz, Ry), Rx)
    M_ned_to_enu = ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0))
    return matmul3(M_ned_to_enu, R_ned_from_body)


def compose_pose(t_w_imu, R_w_imu, T_imu_cam, invert_extrinsics=True):
    T_w_imu = (
        (R_w_imu[0][0], R_w_imu[0][1], R_w_imu[0][2], t_w_imu[0]),
        (R_w_imu[1][0], R_w_imu[1][1], R_w_imu[1][2], t_w_imu[1]),
        (R_w_imu[2][0], R_w_imu[2][1], R_w_imu[2][2], t_w_imu[2]),
        (0.0, 0.0, 0.0, 1.0),
    )
    T_imu_from_cam = invert_transform(T_imu_cam) if invert_extrinsics else T_imu_cam
    T_w_cam = matmul4(T_w_imu, T_imu_from_cam)
    R_w_cam = tuple(tuple(T_w_cam[i][j] for j in range(3)) for i in range(3))
    t_w_cam = (T_w_cam[0][3], T_w_cam[1][3], T_w_cam[2][3])
    return t_w_cam, R_w_cam
