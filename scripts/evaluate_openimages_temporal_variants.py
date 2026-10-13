import json
from pathlib import Path
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

rows = json.loads(Path('artifacts/streetlight_model_pilot_2026-10-08/openimages_full/detections.json').read_text())
df = pd.DataFrame(rows)
df['max_conf'] = df.detections.map(lambda ds: max((d['confidence'] for d in ds), default=0.0))
gt = df.gt_code.astype(int).tolist()
out = []
for threshold in (0.05, 0.10, 0.15):
    for radius in (1, 2, 3, 4):
        for min_hits in (1, 2, 3):
            pred = []
            for i, row in df.iterrows():
                group = df[df.folder == row.folder]
                pos = group.index.get_loc(i)
                local = group.iloc[max(0, pos - radius):min(len(group), pos + radius + 1)]
                hits = int((local.max_conf >= threshold).sum())
                pred.append(2 if hits >= min_hits else 1)
            out.append({
                'threshold': threshold, 'radius': radius, 'min_hits': min_hits,
                'correct': sum(a == b for a, b in zip(gt, pred)),
                'accuracy': accuracy_score(gt, pred),
                'macro_f1': f1_score(gt, pred, average='macro', zero_division=0),
                'weighted_f1': f1_score(gt, pred, average='weighted', zero_division=0),
                'confusion': confusion_matrix(gt, pred, labels=[1, 2]).ravel().tolist(),
            })
result = pd.DataFrame(out).sort_values(['macro_f1', 'accuracy'], ascending=False)
result.to_csv('artifacts/streetlight_model_pilot_2026-10-08/openimages_full/temporal_variants.csv', index=False)
print(result.head(15).to_string(index=False))
