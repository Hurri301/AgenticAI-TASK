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

def score(name: str, pred: list[int]) -> dict[str, object]:
    gt = df["gt_code"].astype(int).tolist()
    return {
        "method": name,
        "n": len(gt),
        "positive_predictions": int(sum(x == 2 for x in pred)),
        "accuracy": accuracy_score(gt, pred),
        "macro_f1": f1_score(gt, pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(gt, pred, average="weighted", zero_division=0),
        "tn_fp_fn_tp": confusion_matrix(gt, pred, labels=[1, 2]).ravel().tolist(),
    }

out = []
for threshold in (0.05, 0.10, 0.15):
    base = (df["max_conf"] >= threshold).astype(int).mul(1).add(1).tolist()
    out.append(score(f"frame threshold {threshold:.2f}", base))
    for radius in (1, 2, 3):
        for minimum in (1, 2):
            pred = []
            for i, row in df.iterrows():
                group = df[df["folder"] == row["folder"]]
                pos = group.index.get_loc(i)
                lo, hi = max(0, pos - radius), min(len(group), pos + radius + 1)
                local = group.iloc[lo:hi]
                hits = int((local["max_conf"] >= threshold).sum())
                pred.append(2 if hits >= minimum else 1)
            out.append(score(f"temporal threshold {threshold:.2f} radius {radius} min_hits {minimum}", pred))

result = pd.DataFrame(out)
result.to_csv(ROOT / "temporal_variants_comparable_468.csv", index=False)
print(result.to_string(index=False))
