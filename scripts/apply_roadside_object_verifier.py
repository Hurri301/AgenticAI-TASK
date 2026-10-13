from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

import complete_semantic_attributes as csa


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DINO_JSONS = {
    "01_N3": REPO_ROOT / "artifacts" / "roadside_object_debug_2026-06-04" / "dino_focused_01_N3_all.json",
    "02_A23 DESCENDENTE": REPO_ROOT / "artifacts" / "roadside_object_debug_02_A23_2026-06-05" / "dino_focused_02_A23_all.json",
    "05_N365 NORTE": REPO_ROOT / "artifacts" / "roadside_object_debug_05_N365_NORTE_2026-06-10" / "dino_focused_05_N365_all.json",
    "06_RAMAL N118": REPO_ROOT / "artifacts" / "roadside_object_debug_06_RAMAL_N118_2026-06-22" / "dino_focused_06_RAMAL_N118_all.json",
    "07_N118": REPO_ROOT / "artifacts" / "roadside_object_debug_07_N118_2026-06-26" / "dino_focused_07_N118_all.json",
    "08_N114": REPO_ROOT / "artifacts" / "roadside_object_debug_08_N114_2026-06-26" / "dino_focused_08_N114_all.json",
    "09_CIRCULAR ASCENDENTE": REPO_ROOT / "artifacts" / "roadside_object_debug_09_CIRCULAR_ASCENDENTE_2026-06-26" / "dino_focused_09_CIRCULAR_all.json",
    "16_N243": REPO_ROOT / "artifacts" / "roadside_object_debug_16_N243_2026-06-26" / "dino_focused_16_N243_all.json",
}


def norm_code(value: Any) -> str:
    return csa.norm_code(value)


def load_all_detections() -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    loaded = {}
    for folder_name, path in DEFAULT_DINO_JSONS.items():
        if path.exists():
            loaded[folder_name] = csa.load_roadside_detections(str(path))
    return loaded


def terrain_candidate(
    detections: dict[tuple[str, str], list[dict[str, Any]]],
    image_stem: str,
) -> tuple[str | None, float]:
    candidates: list[tuple[float, str]] = []
    for code, category in [
        ("6", "Upwards slope - roll over"),
        ("8", "Deep drainage ditch"),
        ("9", "Downwards slope"),
    ]:
        for obj in detections.get((image_stem, "driver"), []):
            if csa.object_code_from_category(str(obj.get("irap_category", ""))) != code:
                continue
            confidence = float(obj.get("confidence", 0.0) or 0.0)
            valid, _reason = csa.dino_candidate_valid(obj, code)
            if valid:
                candidates.append((confidence, code))
    if not candidates:
        return None, 0.0
    confidence, code = max(candidates, key=lambda item: item[0])
    return code, confidence


def current_confidence(
    detections: dict[tuple[str, str], list[dict[str, Any]]],
    image_stem: str,
    current_code: str,
) -> float:
    if not current_code:
        return 0.0
    try:
        current_category = csa.CODE_LABELS["Roadside object"].get(int(current_code), "")
    except ValueError:
        return 0.0
    if not current_category:
        return 0.0
    return csa.max_detection_confidence(detections, image_stem, "driver", current_category)


def apply_folder(input_csv: Path, output_dir: Path, detections_by_folder: dict[str, dict[tuple[str, str], list[dict[str, Any]]]]) -> dict[str, Any]:
    df = pd.read_csv(input_csv, keep_default_na=False)
    for attr in csa.ATTRIBUTES:
        if attr in df.columns:
            df[attr] = df[attr].astype(str).map(norm_code)

    debug_rows: list[dict[str, Any]] = []
    changes = 0
    folder_name = str(df["folder_name"].iloc[0]) if not df.empty else input_csv.parent.name
    detections = detections_by_folder.get(folder_name, {})
    attr = "Roadside severity - driver side object"
    for idx, row in df.iterrows():
        current = norm_code(row.get(attr, ""))
        image_stem = Path(str(row["image_path"])).stem
        new_code = current
        reason = ""
        terrain_code, terrain_conf = terrain_candidate(detections, image_stem)
        cur_conf = current_confidence(detections, image_stem, current)
        if (
            current in {"17", "1", "2", "3", "11", "12", "13"}
            and terrain_code is not None
            and terrain_conf >= 0.84
            and terrain_conf >= cur_conf + 0.12
        ):
            new_code = terrain_code
            reason = (
                f"driver-side verifier changed object {current} to {new_code}; "
                f"high-confidence broad terrain candidate={terrain_conf:.3f}; current_conf={cur_conf:.3f}"
            )
            df.at[idx, attr] = new_code
            changes += 1
        debug_rows.append(
            {
                "folder_name": row.get("folder_name", ""),
                "frame_id": row.get("frame_id", ""),
                "image_path": row.get("image_path", ""),
                "driver_object_before": current,
                "driver_object_after": new_code,
                "terrain_candidate": terrain_code or "",
                "terrain_confidence": round(terrain_conf, 4),
                "current_confidence": round(cur_conf, 4),
                "reason": reason,
            }
        )

    label_rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        labels: dict[str, Any] = {
            "folder_name": row["folder_name"],
            "frame_id": row["frame_id"],
            "image_path": row["image_path"],
        }
        for attr_name in csa.ATTRIBUTES:
            code = norm_code(row.get(attr_name, ""))
            if attr_name in csa.CODE_LABELS:
                labels[attr_name] = csa.CODE_LABELS[attr_name].get(int(code), "") if code else ""
            elif attr_name.startswith("Roadside severity") and attr_name.endswith("object"):
                labels[attr_name] = csa.CODE_LABELS["Roadside object"].get(int(code), "") if code else ""
            else:
                labels[attr_name] = code
        label_rows.append(labels)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_codes = output_dir / "predicted_codes_all_attributes.csv"
    out_labels = output_dir / "predicted_labels_all_attributes.csv"
    out_debug = output_dir / "roadside_object_verifier_debug.csv"
    df.to_csv(out_codes, index=False)
    pd.DataFrame(label_rows).to_csv(out_labels, index=False)
    pd.DataFrame(debug_rows).to_csv(out_debug, index=False)

    return {
        "folder_name": folder_name,
        "rows": int(len(df)),
        "driver_object_changes": int(changes),
        "output_csv": str(out_codes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply promoted roadside object verifier to frozen prediction CSVs.")
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    detections_by_folder = load_all_detections()
    summaries = []
    for csv_path in sorted(input_root.glob("*/predicted_codes_all_attributes.csv")):
        summaries.append(apply_folder(csv_path, output_root / csv_path.parent.name, detections_by_folder))

    pd.DataFrame(summaries).to_csv(output_root / "roadside_object_verifier_summary.csv", index=False)
    (output_root / "roadside_object_verifier_summary.json").write_text(
        json.dumps(summaries, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"folders": len(summaries), "output_root": str(output_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
