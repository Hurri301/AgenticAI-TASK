from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix


ROOT = Path("artifacts/streetlight_yolov11x_temporal_experiment_2026-10-06")
rows = json.loads((ROOT / "detections.json").read_text(encoding="utf-8"))
rows = [r for r in rows if r["folder"] != "01_N4"]
df = pd.DataFrame(rows)
df["max_conf"] = df["detections"].map(lambda ds: max((d["confidence"] for d in ds), default=0.0))

THRESHOLD = 0.15
RADIUS = 3

def metrics(gt: list[int], pred: list[int]) -> dict[str, float | int | str]:
    cm = confusion_matrix(gt, pred, labels=[1, 2]).ravel().tolist()
    return {
        "n": len(gt),
        "positive_predictions": int(sum(x == 2 for x in pred)),
        "accuracy": accuracy_score(gt, pred),
        "macro_f1": f1_score(gt, pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(gt, pred, average="weighted", zero_division=0),
        "tn_fp_fn_tp": str(cm),
    }

output = []
for folder, group in df.groupby("folder", sort=True):
    group = group.sort_values("frame_number").reset_index(drop=True)
    gt = group["gt_code"].astype(int).tolist()
    frame_pred = [2 if x >= THRESHOLD else 1 for x in group["max_conf"]]
    temporal_pred = []
    for i in range(len(group)):
        lo, hi = max(0, i - RADIUS), min(len(group), i + RADIUS + 1)
        hits = int((group.iloc[lo:hi]["max_conf"] >= THRESHOLD).sum())
        temporal_pred.append(2 if hits >= 1 else 1)
    output.append({"folder": folder, "method": "frame threshold 0.15", **metrics(gt, frame_pred)})
    output.append({"folder": folder, "method": "temporal radius 3 threshold 0.15", **metrics(gt, temporal_pred)})

result = pd.DataFrame(output)
result.to_csv(ROOT / "independent_route_validation_by_folder.csv", index=False)

summary = []
for method, group in result.groupby("method"):
    # Reconstruct aggregate counts from route-level confusion matrices.
    counts = [0, 0, 0, 0]
    for value in group["tn_fp_fn_tp"]:
        for i, item in enumerate(eval(value)):
            counts[i] += item
    tn, fp, fn, tp = counts
    gt = [1] * (tn + fp) + [2] * (fn + tp)
    pred = [1] * tn + [2] * fp + [1] * fn + [2] * tp
    summary.append({"method": method, **metrics(gt, pred)})
summary_df = pd.DataFrame(summary)
summary_df.to_csv(ROOT / "independent_route_validation_summary.csv", index=False)
print(summary_df.to_string(index=False))
print("\nPer-folder results:")
print(result.to_string(index=False))
