from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score
from ultralytics import YOLO


def frame_number(name: str) -> int:
    match = re.search(r"_(\d+)\.(?:png|jpg|jpeg)$", name, re.I)
    return int(match.group(1)) if match else -1


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-9)


def tile_specs(width: int, height: int, tile_width: int, overlap: int, crop_y2: int) -> list[tuple[int, int, int, int]]:
    y2 = min(height, crop_y2)
    tile_width = min(width, tile_width)
    if width <= tile_width:
        return [(0, 0, width, y2)]
    step = max(1, tile_width - overlap)
    specs = [(0, 0, width, y2)]
    x = 0
    while x < width:
        x2 = min(width, x + tile_width)
        specs.append((x, 0, x2, y2))
        if x2 == width:
            break
        x += step
    return specs


def predict_image(model: YOLO, path: Path, conf: float, imgsz: int, device: str, tile_width: int, overlap: int, crop_y2: int) -> list[dict[str, Any]]:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    detections: list[dict[str, Any]] = []
    for x1, y1, x2, y2 in tile_specs(width, height, tile_width, overlap, crop_y2):
        tile = np.asarray(image.crop((x1, y1, x2, y2)))
        result = model.predict(tile, conf=conf, imgsz=imgsz, device=device, verbose=False, save=False)[0]
        names = result.names
        if result.boxes is None:
            continue
        for box, score, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
            label = str(names[int(cls)])
            if label.lower() != "street light":
                continue
            bx1, by1, bx2, by2 = box
            detections.append({
                "label": label,
                "confidence": float(score),
                "bbox_xyxy": [bx1 + x1, by1 + y1, bx2 + x1, by2 + y1],
            })
    kept: list[dict[str, Any]] = []
    for det in sorted(detections, key=lambda d: d["confidence"], reverse=True):
        if not any(iou(det["bbox_xyxy"], old["bbox_xyxy"]) >= 0.55 for old in kept):
            kept.append(det)
    return kept


def score(gt: list[int], pred: list[int]) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(gt, pred),
        "macro_f1": f1_score(gt, pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(gt, pred, average="weighted", zero_division=0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--ground-truth", default="GroundTruth.csv")
    parser.add_argument("--dataset-root", default="Dataset")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--thresholds", default="0.05,0.10,0.15,0.25")
    parser.add_argument("--imgsz", type=int, default=1536)
    parser.add_argument("--device", default="0")
    parser.add_argument("--tile-width", type=int, default=768)
    parser.add_argument("--tile-overlap", type=int, default=256)
    parser.add_argument("--crop-y2", type=int, default=1024)
    parser.add_argument("--temporal-radius", type=int, default=4)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt = pd.read_csv(args.ground_truth)[["Folder_name", "Image number", "Street lighting"]].copy()
    gt["image_name"] = gt["Image number"].astype(str).map(lambda x: Path(x).with_suffix(".jpg").name)
    paths = []
    for _, row in gt.iterrows():
        candidates = list((Path(args.dataset_root) / str(row["Folder_name"])).rglob(row["image_name"]))
        if not candidates:
            fallback_name = Path(str(row["Image number"])).with_suffix(".jpg").name
            candidates = list((Path(args.dataset_root) / str(row["Folder_name"])).rglob(fallback_name))
        if not candidates:
            candidates = list(Path(args.dataset_root).rglob(row["image_name"]))
        paths.append(candidates[0] if candidates else None)
    gt["image_path"] = [str(p) if p else "" for p in paths]
    gt = gt[gt["Folder_name"] != "01_N4"].reset_index(drop=True)
    if gt["image_path"].eq("").any():
        raise RuntimeError("Could not resolve all comparable images")

    model = YOLO(args.model)
    base_threshold = min(float(x) for x in args.thresholds.split(","))
    rows = []
    for i, row in gt.iterrows():
        print(f"[{i + 1}/{len(gt)}] {row['Folder_name']} {row['image_name']}", flush=True)
        rows.append({
            "folder": row["Folder_name"], "image_name": row["image_name"], "image_path": row["image_path"],
            "frame_number": frame_number(row["image_name"]), "gt_code": int(row["Street lighting"]),
            "detections": predict_image(model, Path(row["image_path"]), base_threshold, args.imgsz, args.device, args.tile_width, args.tile_overlap, args.crop_y2),
        })

    thresholds = [float(x) for x in args.thresholds.split(",")]
    for threshold in thresholds:
        key = f"pred_{threshold:.2f}"
        for row in rows:
            row[key] = 2 if any(d["confidence"] >= threshold for d in row["detections"]) else 1

    metric_rows = []
    gt_values = [r["gt_code"] for r in rows]
    for threshold in thresholds:
        pred = [r[f"pred_{threshold:.2f}"] for r in rows]
        metric_rows.append({"method": f"Open Images YOLO Street light threshold {threshold:.2f}", "correct": sum(a == b for a, b in zip(gt_values, pred)), **score(gt_values, pred)})

    temporal_key = f"pred_{base_threshold:.2f}"
    temporal = [r[temporal_key] for r in rows]
    for group in {}.fromkeys(r["folder"] for r in rows):
        local = [r for r in rows if r["folder"] == group]
        local.sort(key=lambda r: r["frame_number"])
        for i, row in enumerate(local):
            neighborhood = local[max(0, i - args.temporal_radius): min(len(local), i + args.temporal_radius + 1)]
            if any(r[temporal_key] == 2 for r in neighborhood):
                temporal[rows.index(row)] = 2
    metric_rows.append({"method": f"Open Images YOLO temporal threshold {base_threshold:.2f} radius {args.temporal_radius}", "correct": sum(a == b for a, b in zip(gt_values, temporal)), **score(gt_values, temporal)})

    (out_dir / "detections.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    pd.DataFrame([{k: v for k, v in r.items() if k != "detections"} for r in rows]).to_csv(out_dir / "predictions.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(out_dir / "metrics.csv", index=False)
    print(json.dumps(metric_rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
