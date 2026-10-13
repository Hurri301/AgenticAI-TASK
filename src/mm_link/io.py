from __future__ import annotations

import csv
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from .types import ImagePose


def load_poses_csv(path: str) -> dict[str, ImagePose]:
    poses: dict[str, ImagePose] = {}
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            image_id = row.get("Name", str(i))
            poses[image_id] = ImagePose(
                image_id=image_id,
                t_img=float(row["Time"]),
                e=float(row["X"]),
                n=float(row["Y"]),
                h=float(row["Z"]),
                roll=float(row["roll"]),
                pitch=float(row["pitch"]),
                heading=float(row["heading"]),
            )
    return poses


def load_extrinsics_xml(path: str) -> tuple[tuple[float, float, float, float], ...]:
    root = ET.parse(path).getroot()
    node = root.find("IMU2LB_Extrinsics")
    if node is None:
        raise ValueError("Cannot find IMU2LB_Extrinsics node")
    data_node = node.find("data")
    if data_node is None or not data_node.text:
        raise ValueError("Cannot parse extrinsics matrix data")
    vals = [float(v) for v in data_node.text.split()]
    if len(vals) != 16:
        raise ValueError(f"Expected 16 matrix values, found {len(vals)}")
    return tuple(tuple(vals[i * 4 + j] for j in range(4)) for i in range(4))


def load_image_size(path: str) -> tuple[int, int]:
    p = Path(path)
    if p.suffix.lower() in {".jpg", ".jpeg"}:
        from PIL import Image

        with Image.open(p) as image:
            return int(image.width), int(image.height)
    if p.suffix.lower() != ".png":
        raise ValueError("Only PNG/JPEG supported")
    with p.open("rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Not a PNG file")
        _len = struct.unpack(">I", f.read(4))[0]
        chunk = f.read(4)
        if chunk != b"IHDR":
            raise ValueError("PNG missing IHDR")
        data = f.read(13)
        w, h = struct.unpack(">II", data[:8])
        return int(w), int(h)


def load_las_points(path: str):
    p = Path(path)
    with p.open("rb") as f:
        hdr = f.read(375)
        if hdr[:4] != b"LASF":
            raise ValueError("Invalid LAS signature")
        offset_to_point_data = struct.unpack_from("<I", hdr, 96)[0]
        point_format = hdr[104]
        record_length = struct.unpack_from("<H", hdr, 105)[0]
        point_count = struct.unpack_from("<I", hdr, 107)[0]
        x_scale, y_scale, z_scale = struct.unpack_from("<ddd", hdr, 131)
        x_off, y_off, z_off = struct.unpack_from("<ddd", hdr, 155)
        f.seek(offset_to_point_data)

        xyz = []
        intensity = []
        has_intensity = point_format in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

        for _ in range(point_count):
            rec = f.read(record_length)
            if len(rec) < record_length:
                break
            Xi, Yi, Zi = struct.unpack_from("<iii", rec, 0)
            xyz.append((Xi * x_scale + x_off, Yi * y_scale + y_off, Zi * z_scale + z_off))
            intensity.append(struct.unpack_from("<H", rec, 12)[0] if has_intensity else 0)

    return xyz, (intensity if has_intensity else None)


def export_subset_las(las_path: str, indices, out_path: str) -> None:
    selected = set(int(i) for i in indices)
    with open(las_path, "rb") as src:
        header = src.read(375)
        if header[:4] != b"LASF":
            raise ValueError("Invalid LAS signature")
        offset_to_point_data = struct.unpack_from("<I", header, 96)[0]
        record_length = struct.unpack_from("<H", header, 105)[0]
        point_count = struct.unpack_from("<I", header, 107)[0]
        vlr_blob = src.read(max(0, offset_to_point_data - 375))
        records = []
        for idx in range(point_count):
            rec = src.read(record_length)
            if len(rec) < record_length:
                break
            if idx in selected:
                records.append(rec)
    out_header = bytearray(header)
    struct.pack_into("<I", out_header, 107, len(records))
    with open(out_path, "wb") as dst:
        dst.write(out_header)
        dst.write(vlr_blob)
        for rec in records:
            dst.write(rec)
