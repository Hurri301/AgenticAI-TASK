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

OBJECT_CLASSES = {
    "Tree": 11,
    "Building": 13,
    "Traffic sign": 12,
    "Street light": 12,
}
ATTRS = {
    "driver": "Roadside severity - driver side object",
    "passenger": "Roadside severity - passenger side object",
}


def frame_number(name: str) -> int:
    match = re.search(r"_(\d+)\.(?:png|jpg|jpeg)$", name, re.I)
    return int(match.group(1)) if match else -1


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, by2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-9)


def tiles(width: int, height: int, tile_width: int = 768, overlap: int = 256) -> list[tuple[int, int, int, int]]:
    y2 = min(height, 1024)
    if width <= tile_width:
        return [(0, 0, width, y2)]
    specs = [(0, 0, width, y2)]
    step = tile_width - overlap
    x = 0
    while x < width:
        x2 = min(width, x + tile_width)
        specs.append((x, 0, x2, y2))
        if x2 == width:
            break
        x += step
    return specs


def detect(model: YOLO, path: Path, device: str, imgsz: int, conf: float) -> list[dict[str, Any]]:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    found: list[dict[str, Any]] = []
    for x1, y1, x2, y2 in tiles(width, height):
        tile = np.asarray(image.crop((x1, y1, x2, y2)))
        result = model.predict(tile, conf=conf, imgsz=imgsz, device=device, verbose=False, save=False)[0]
        for box, score, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
            label = str(result.names[int(cls)])
            if label not in OBJECT_CLASSES:
                continue
            bx1, by1, bx2, by2 = box
            found.append({"label": label, "code": OBJECT_CLASSES[label], "confidence": float(score), "bbox": [bx1 + x1, by1 + y1, bx2 + x1, by2 + y1]})
    kept: list[dict[str, Any]] = []
    for item in sorted(found, key=lambda x: x["confidence"], reverse=True):
        if not any(item["label"] == old["label"] and iou(item["bbox"], old["bbox"]) >= 0.55 for old in kept):
            kept.append(item)
    return kept


def side_of(bbox: list[float], width: int) -> str | None:
    center = (bbox[0] + bbox[2]) / 2
    if abs(center - width / 2) < width * 0.08:
        return None
    return "driver" if center < width / 2 else "passenger"


def metric(gt: pd.Series, pred: pd.Series) -> dict[str, float]:
    return {
        "correct": int((gt.astype(int) == pred.astype(int)).sum()),
        "accuracy": accuracy_score(gt, pred),
        "macro_f1": f1_score(gt, pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(gt, pred, average="weighted", zero_division=0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ground-truth", default="GroundTruth.csv")
    ap.add_argument("--dataset-root", default="Dataset")
    ap.add_argument("--baseline-root", default="artifacts/final_delivery_2026-07-01/predictions_final")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--imgsz", type=int, default=1536)
    ap.add_argument("--device", default="0")
    ap.add_argument("--inference-conf", type=float, default=0.05)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt = pd.read_csv(args.ground_truth)
    gt = gt[gt["Folder_name"] != "01_N4"].copy()
    gt["image_name"] = gt["Image number"].astype(str).map(lambda x: Path(x).with_suffix(".jpg").name)
    paths = []
    for _, row in gt.iterrows():
        candidates = list((Path(args.dataset_root) / str(row["Folder_name"])).rglob(row["image_name"]))
        if not candidates:
            candidates = list(Path(args.dataset_root).rglob(row["image_name"]))
        paths.append(candidates[0] if candidates else None)
    gt["image_path"] = [str(p) if p else "" for p in paths]
    if gt["image_path"].eq("").any():
        raise RuntimeError("Could not resolve all images")

    # Load the existing final-delivery codes so YOLO acts as a supplementary tool.
    baseline_parts = []
    folder_map = {"02_A23_DESCENDENTE": "02_A23 DESCENDENTE", "05_N365_NORTE": "05_N365 NORTE", "06_RAMAL_N118": "06_RAMAL N118", "09_CIRCULAR_ASCENDENTE": "09_CIRCULAR ASCENDENTE"}
    for path in Path(args.baseline_root).glob("*/predicted_codes_all_attributes.csv"):
        frame = pd.read_csv(path)
        frame["Folder_name"] = frame["folder_name"].replace(folder_map)
        frame["frame_id"] = frame["frame_id"].astype(str)
        baseline_parts.append(frame[["Folder_name", "frame_id", *ATTRS.values()]])
    baseline = pd.concat(baseline_parts, ignore_index=True).drop_duplicates(["Folder_name", "frame_id"])
    gt["frame_id"] = gt["Image number"].astype(str).str.extract(r"_(\d+)\.[^.]+$", expand=False)
    baseline["frame_id"] = baseline["frame_id"].str.extract(r"(\d+)$", expand=False)
    joined = gt.merge(baseline, on=["Folder_name", "frame_id"], how="inner", suffixes=("_gt", "_base"))

    model = YOLO(args.model)
    rows = []
    for i, row in joined.iterrows():
        detections = detect(model, Path(row["image_path"]), args.device, args.imgsz, args.inference_conf)
        image_width = Image.open(row["image_path"]).size[0]
        side_candidates = {"driver": [], "passenger": []}
        for det in detections:
            side = side_of(det["bbox"], image_width)
            if side:
                side_candidates[side].append(det)
        rows.append({
            "Folder_name": row["Folder_name"], "frame_id": row["frame_id"], "image_path": row["image_path"],
            "detections": detections,
            "driver_candidates": side_candidates["driver"], "passenger_candidates": side_candidates["passenger"],
        })
        print(f"[{len(rows)}/{len(joined)}] {row['Folder_name']} {row['frame_id']}", flush=True)

    detections_by_key = {(r["Folder_name"], r["frame_id"]): r for r in rows}
    records = []
    for _, row in joined.iterrows():
        extra = detections_by_key[(row["Folder_name"], row["frame_id"])]
        rec = {"Folder_name": row["Folder_name"], "frame_id": row["frame_id"]}
        for side, attr in ATTRS.items():
            for threshold in (0.20, 0.30, 0.40, 0.50):
                candidates = [d for d in extra[f"{side}_candidates"] if d["confidence"] >= threshold]
                rec[f"{side}_yolo_{threshold:.2f}"] = max(candidates, key=lambda d: d["confidence"])["code"] if candidates else 17
                base_code = int(row[f"{attr}_base"])
                rec[f"{side}_supplement_{threshold:.2f}"] = rec[f"{side}_yolo_{threshold:.2f}"] if base_code == 17 and candidates else base_code
            rec[f"{side}_baseline"] = int(row[f"{attr}_base"])
            rec[f"{side}_gt"] = int(row[f"{attr}_gt"])
        records.append(rec)

    out = pd.DataFrame(records)
    out.to_csv(out_dir / "openimages_roadside_predictions.csv", index=False)
    metrics = []
    for side, attr in ATTRS.items():
        for threshold in (0.20, 0.30, 0.40, 0.50):
            for variant in ("yolo", "supplement"):
                pred = out[f"{side}_{variant}_{threshold:.2f}"]
                metrics.append({"side": side, "variant": variant, "threshold": threshold, **metric(out[f"{side}_gt"], pred)})
        metrics.append({"side": side, "variant": "baseline", "threshold": None, **metric(out[f"{side}_gt"], out[f"{side}_baseline"])})
    pd.DataFrame(metrics).to_csv(out_dir / "metrics.csv", index=False)
    print(pd.DataFrame(metrics).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
