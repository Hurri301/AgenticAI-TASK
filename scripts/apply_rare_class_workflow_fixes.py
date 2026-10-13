from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

import complete_semantic_attributes as csa


REPO_ROOT = Path(__file__).resolve().parents[1]


def norm_code(value: Any) -> str:
    return csa.norm_code(value)


def median_rare_refinement(current: str, ev: csa.ImageEvidence) -> tuple[str, str | None]:
    """Recover rare median classes from global visual evidence without GT."""
    if current != "11":
        return current, None
    if (
        ev.passenger.paved_ratio >= 0.60
        and ev.driver.paved_ratio >= 0.58
        and ev.passenger.green_ratio <= 0.10
        and ev.road_marking_ratio <= 0.26
        and ev.bright_wall_ratio >= 0.42
        and ev.passenger.sidewalk_ratio >= 0.34
    ):
        return (
            "13",
            "one-way / separated-flow median refinement: broad paved corridor, low centre-line demand, built/separated frontage evidence",
        )
    if (
        ev.road_marking_ratio >= 0.52
        and ev.asphalt_ratio >= 0.46
        and ev.passenger.sidewalk_ratio >= 0.36
        and ev.passenger.green_ratio <= 0.10
        and ev.bright_wall_ratio >= 0.40
    ):
        return "10", "central hatching refinement: high centre marking density with broad paved carriageway"
    if (
        0.12 <= ev.road_marking_ratio < 0.22
        and ev.asphalt_ratio >= 0.56
        and ev.passenger.paved_ratio >= 0.70
        and ev.driver.paved_ratio >= 0.70
        and ev.passenger.green_ratio <= 0.09
    ):
        return "14", "wide centre-line refinement: broad paved carriageway with low-to-moderate centre marking ratio"
    return current, None


def access_candidate(ev: csa.ImageEvidence) -> bool:
    """Conservative direct-access candidate from passenger-side frontage evidence."""
    return (
        ev.passenger.paved_ratio >= 0.60
        and ev.passenger.green_ratio <= 0.08
        and ev.passenger.sidewalk_ratio >= 0.40
        and (ev.passenger.bright_wall_ratio >= 0.44 or ev.bright_wall_ratio >= 0.44)
    )


def apply_folder(input_csv: Path, output_dir: Path, enable_median_experiment: bool) -> dict[str, Any]:
    df = pd.read_csv(input_csv, keep_default_na=False)
    for attr in csa.ATTRIBUTES:
        if attr in df.columns:
            df[attr] = df[attr].astype(str).map(norm_code)
    debug_rows: list[dict[str, Any]] = []
    evidence_by_index: dict[int, csa.ImageEvidence] = {}

    for idx, row in df.iterrows():
        image_path = REPO_ROOT / str(row["image_path"])
        ev = csa.image_evidence(image_path, int(row["frame_id"]), str(row["folder_name"]))
        evidence_by_index[int(idx)] = ev
        median_before = norm_code(row.get("Median Type", ""))
        median_after, median_reason = (
            median_rare_refinement(median_before, ev)
            if enable_median_experiment
            else (median_before, None)
        )
        if median_reason:
            df.at[idx, "Median Type"] = median_after
        debug_rows.append(
            {
                "folder_name": row["folder_name"],
                "frame_id": row["frame_id"],
                "image_path": row["image_path"],
                "median_before": median_before,
                "median_after": norm_code(df.at[idx, "Median Type"]),
                "median_reason": median_reason or "",
                "access_before": norm_code(row.get("Property access points", "")),
                "access_after": norm_code(row.get("Property access points", "")),
                "access_reason": "",
                "passenger_paved": round(ev.passenger.paved_ratio, 4),
                "passenger_green": round(ev.passenger.green_ratio, 4),
                "passenger_sidewalk": round(ev.passenger.sidewalk_ratio, 4),
                "passenger_wall": round(ev.passenger.bright_wall_ratio, 4),
                "bright_wall": round(ev.bright_wall_ratio, 4),
                "road_marking": round(ev.road_marking_ratio, 4),
                "asphalt": round(ev.asphalt_ratio, 4),
            }
        )

    # Segment/adjacent-frame access recovery. This intentionally runs after local frame evidence is cached.
    for folder_name, group in df.groupby("folder_name", sort=False):
        ordered = group.copy()
        ordered["_frame_int"] = ordered["frame_id"].astype(int)
        ordered = ordered.sort_values("_frame_int")
        idxs = list(ordered.index)
        candidates = [int(access_candidate(evidence_by_index[int(idx)])) for idx in idxs]
        for pos, idx in enumerate(idxs):
            current = norm_code(df.at[idx, "Property access points"])
            if current == "1":
                continue
            lo = max(0, pos - 3)
            hi = min(len(candidates), pos + 4)
            seq_count = sum(candidates[lo:hi])
            reason = ""
            if seq_count >= 4 and current != "2":
                df.at[idx, "Property access points"] = "2"
                reason = f"adjacent-frame residential access recovery; candidate_count_window={seq_count}"
            elif seq_count >= 3 and current == "4":
                df.at[idx, "Property access points"] = "3"
                reason = f"adjacent-frame limited residential access recovery; candidate_count_window={seq_count}"
            if reason:
                debug_rows[int(idx)]["access_after"] = norm_code(df.at[idx, "Property access points"])
                debug_rows[int(idx)]["access_reason"] = reason

    label_rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        labels: dict[str, Any] = {
            "folder_name": row["folder_name"],
            "frame_id": row["frame_id"],
            "image_path": row["image_path"],
        }
        for attr in csa.ATTRIBUTES:
            code = norm_code(row.get(attr, ""))
            if attr in csa.CODE_LABELS:
                labels[attr] = csa.CODE_LABELS[attr].get(int(code), "") if code else ""
            elif attr.startswith("Roadside severity") and attr.endswith("object"):
                labels[attr] = csa.CODE_LABELS["Roadside object"].get(int(code), "") if code else ""
            else:
                labels[attr] = code
        label_rows.append(labels)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_codes = output_dir / "predicted_codes_all_attributes.csv"
    out_labels = output_dir / "predicted_labels_all_attributes.csv"
    out_debug = output_dir / "rare_class_workflow_debug.csv"
    df.to_csv(out_codes, index=False)
    pd.DataFrame(label_rows).to_csv(out_labels, index=False)
    pd.DataFrame(debug_rows).to_csv(out_debug, index=False)

    return {
        "folder_name": str(df["folder_name"].iloc[0]) if not df.empty else input_csv.parent.name,
        "rows": int(len(df)),
        "median_changes": int(sum(1 for row in debug_rows if row["median_before"] != row["median_after"])),
        "access_changes": int(sum(1 for row in debug_rows if row["access_before"] != row["access_after"])),
        "output_csv": str(out_codes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply global rare-class workflow refinements to frozen prediction CSVs.")
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--enable-median-experiment",
        action="store_true",
        help="Also apply experimental rare median refinements. Off by default because v1 harmed centre-line precision.",
    )
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    summaries = []
    for csv_path in sorted(input_root.glob("*/predicted_codes_all_attributes.csv")):
        summaries.append(apply_folder(csv_path, output_root / csv_path.parent.name, args.enable_median_experiment))

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(output_root / "rare_class_workflow_summary.csv", index=False)
    (output_root / "rare_class_workflow_summary.json").write_text(
        json.dumps(summaries, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"folders": len(summaries), "output_root": str(output_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
