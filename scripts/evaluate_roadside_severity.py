from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_GT_CSV = REPO_ROOT / "Dataset" / "GroundTruth.csv"
DEFAULT_DATASET_ROOT = REPO_ROOT / "Dataset" / "02_A23_DESCENDENTE"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "roadside_severity_eval"

TARGET_COLUMNS = [
    "Roadside severity - driver side object",
    "Roadside severity - passenger side object",
    "Roadside severity - drivers side distance",
    "Roadside severity - passenger side distance",
]

# The workbook currently exposes the passenger-side codebook for objects and distance.
# Those codes are used symmetrically for both sides in GroundTruth.csv, so we reuse them here.
OBJECT_CODEBOOK = {
    "1": "Safety barrier - metal",
    "2": "Safety barrier - concrete",
    "3": "Safety barrier - motorcycle friendly",
    "4": "Safety barrier - wire rope",
    "5": "Aggressive vertical face",
    "6": "Upwards slope - (15deg to 75deg)",
    "7": "Upwards slope - (>=75deg)",
    "8": "Deep drainage ditch",
    "9": "Downwards slope (> -15deg)",
    "10": "Cliff",
    "11": "Tree >=10cm",
    "12": "Non-frangible sign/post/pole >=10cm",
    "13": "Rigid structure/bridge or building",
    "14": "Semi-rigid structure or building",
    "15": "Unprotected safety barrier end",
    "16": "Large boulders >=20cm high",
    "17": "No object",
}

DISTANCE_CODEBOOK = {
    "1": "0 to <1m",
    "2": "1 to <5m",
    "3": "5 to <10m",
    "4": ">=10m",
}

PROMPT_CODE_PAIRS = [
    ("metal guardrail", "1"),
    ("concrete barrier", "2"),
    ("motorcycle friendly barrier", "3"),
    ("wire rope barrier", "4"),
    ("vertical rock face", "5"),
    ("upward slope", "6"),
    ("steep upward slope", "7"),
    ("drainage ditch", "8"),
    ("downward slope", "9"),
    ("cliff", "10"),
    ("tree", "11"),
    ("traffic sign", "12"),
    ("utility pole", "12"),
    ("pole", "12"),
    ("post", "12"),
    ("bridge", "13"),
    ("building", "13"),
    ("rigid structure", "13"),
    ("semi-rigid structure", "14"),
    ("guardrail end", "15"),
    ("barrier end", "15"),
    ("large boulder", "16"),
    ("boulder", "16"),
]

FALLBACK_LABEL_CODE = {
    "guardrail": "1",
    "barrier": "2",
    "ditch": "8",
    "drainage": "8",
    "slope": "6",
    "cliff": "10",
    "tree": "11",
    "sign": "12",
    "pole": "12",
    "post": "12",
    "building": "13",
    "bridge": "13",
    "structure": "13",
    "rock": "16",
    "boulder": "16",
}


@dataclass(frozen=True)
class Candidate:
    side: str
    code: str
    label: str
    score: float
    distance_code: str
    distance_label: str
    box_xyxy: tuple[int, int, int, int]


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def dataset_name_variants(dataset_root: Path) -> set[str]:
    raw = dataset_root.name.strip()
    spaced = raw.replace("_", " ")
    collapsed = re.sub(r"\s+", " ", spaced).strip()
    return {
        normalize_key(raw),
        normalize_key(spaced),
        normalize_key(collapsed),
    }


def load_ground_truth_rows(gt_csv: Path, dataset_root: Path, image_name: str | None) -> list[dict[str, str]]:
    keys = dataset_name_variants(dataset_root)
    with gt_csv.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    filtered = [row for row in rows if normalize_key(row.get("Folder_name", "")) in keys]
    if image_name:
        filtered = [row for row in filtered if row.get("Image number", "").strip() == image_name]
    return filtered


def build_image_index(dataset_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in dataset_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            index[path.name.lower()] = path
    return index


def resolve_image_path(row: dict[str, str], image_index: dict[str, Path]) -> Path:
    image_name = row["Image number"].strip()
    path = image_index.get(image_name.lower())
    if path is None:
        raise FileNotFoundError(f"Image not found for GT row: {image_name}")
    return path


def resolve_las_path(dataset_root: Path, cloud_name: str) -> Path | None:
    stem = Path(cloud_name).stem
    direct = dataset_root / stem / f"{stem}.las"
    if direct.exists():
        return direct
    matches = list(dataset_root.rglob(f"{stem}.las"))
    return matches[0] if matches else None


def object_prompts() -> list[str]:
    return [prompt for prompt, _ in PROMPT_CODE_PAIRS]


def label_to_object_code(label: str) -> str | None:
    label_norm = normalize_key(label)
    for prompt, code in PROMPT_CODE_PAIRS:
        prompt_norm = normalize_key(prompt)
        if prompt_norm in label_norm or label_norm in prompt_norm:
            return code
    for token, code in FALLBACK_LABEL_CODE.items():
        if normalize_key(token) in label_norm:
            return code
    return None


def distance_code_from_box(box_xyxy: tuple[int, int, int, int], image_size: tuple[int, int]) -> str:
    x1, y1, x2, y2 = box_xyxy
    width, height = image_size
    box_w = max(1.0, float(x2 - x1))
    box_h = max(1.0, float(y2 - y1))
    box_area = box_w * box_h

    height_ratio = box_h / max(1.0, float(height))
    bottom_ratio = y2 / max(1.0, float(height))
    area_ratio = box_area / max(1.0, float(width * height))

    proximity = (0.5 * height_ratio) + (0.35 * bottom_ratio) + (0.15 * min(1.0, area_ratio * 60.0))
    if proximity >= 0.58:
        return "1"
    if proximity >= 0.32:
        return "2"
    if proximity >= 0.16:
        return "3"
    return "4"


def assign_side(
    box_xyxy: tuple[int, int, int, int],
    image_width: int,
    driver_side: str,
    center_ignore_frac: float,
) -> str | None:
    x1, _, x2, _ = box_xyxy
    cx = (x1 + x2) / 2.0
    center = image_width / 2.0
    ignore = image_width * center_ignore_frac / 2.0
    if abs(cx - center) <= ignore:
        return None

    is_left = cx < center
    if driver_side == "left":
        return "driver" if is_left else "passenger"
    return "passenger" if is_left else "driver"


def build_candidates(
    detections,
    image_size: tuple[int, int],
    driver_side: str,
    center_ignore_frac: float,
) -> list[Candidate]:
    width, _ = image_size
    out: list[Candidate] = []
    for det in detections:
        code = label_to_object_code(det.label)
        if code is None:
            continue
        side = assign_side(det.box_xyxy, width, driver_side, center_ignore_frac)
        if side is None:
            continue
        dist_code = distance_code_from_box(det.box_xyxy, image_size)
        out.append(
            Candidate(
                side=side,
                code=code,
                label=OBJECT_CODEBOOK.get(code, det.label),
                score=float(det.score),
                distance_code=dist_code,
                distance_label=DISTANCE_CODEBOOK[dist_code],
                box_xyxy=det.box_xyxy,
            )
        )
    return out


def choose_best_candidate(candidates: Iterable[Candidate], side: str) -> Candidate | None:
    side_candidates = [c for c in candidates if c.side == side]
    if not side_candidates:
        return None
    side_candidates.sort(
        key=lambda c: (
            int(c.distance_code),
            -c.score,
            -(c.box_xyxy[3] - c.box_xyxy[1]),
        )
    )
    return side_candidates[0]


def predicted_fields(best: Candidate | None) -> dict[str, str | float | list[int] | None]:
    if best is None:
        return {
            "object_code": "17",
            "object_label": OBJECT_CODEBOOK["17"],
            "distance_code": "4",
            "distance_label": DISTANCE_CODEBOOK["4"],
            "score": None,
            "box_xyxy": None,
        }
    return {
        "object_code": best.code,
        "object_label": best.label,
        "distance_code": best.distance_code,
        "distance_label": best.distance_label,
        "score": round(best.score, 4),
        "box_xyxy": list(best.box_xyxy),
    }


def comparison_record(row: dict[str, str], image_path: Path, las_path: Path | None, candidates: list[Candidate]) -> dict[str, object]:
    driver_best = choose_best_candidate(candidates, "driver")
    passenger_best = choose_best_candidate(candidates, "passenger")
    driver_pred = predicted_fields(driver_best)
    passenger_pred = predicted_fields(passenger_best)

    gt_driver_obj = row["Roadside severity - driver side object"].strip()
    gt_passenger_obj = row["Roadside severity - passenger side object"].strip()
    gt_driver_dist = row["Roadside severity - drivers side distance"].strip()
    gt_passenger_dist = row["Roadside severity - passenger side distance"].strip()

    return {
        "folder_name": row["Folder_name"],
        "image_number": row["Image number"],
        "image_path": str(image_path),
        "cloud_name": row["cloud_name"],
        "las_path": str(las_path) if las_path is not None else "",
        "traj_index_start": row["traj_index_start"],
        "traj_index_end": row["traj_index_end"],
        "gt_driver_object_code": gt_driver_obj,
        "gt_driver_object_label": OBJECT_CODEBOOK.get(gt_driver_obj, "Unknown"),
        "pred_driver_object_code": driver_pred["object_code"],
        "pred_driver_object_label": driver_pred["object_label"],
        "driver_object_match": gt_driver_obj == driver_pred["object_code"],
        "gt_passenger_object_code": gt_passenger_obj,
        "gt_passenger_object_label": OBJECT_CODEBOOK.get(gt_passenger_obj, "Unknown"),
        "pred_passenger_object_code": passenger_pred["object_code"],
        "pred_passenger_object_label": passenger_pred["object_label"],
        "passenger_object_match": gt_passenger_obj == passenger_pred["object_code"],
        "gt_driver_distance_code": gt_driver_dist,
        "gt_driver_distance_label": DISTANCE_CODEBOOK.get(gt_driver_dist, "Unknown"),
        "pred_driver_distance_code": driver_pred["distance_code"],
        "pred_driver_distance_label": driver_pred["distance_label"],
        "driver_distance_match": gt_driver_dist == driver_pred["distance_code"],
        "gt_passenger_distance_code": gt_passenger_dist,
        "gt_passenger_distance_label": DISTANCE_CODEBOOK.get(gt_passenger_dist, "Unknown"),
        "pred_passenger_distance_code": passenger_pred["distance_code"],
        "pred_passenger_distance_label": passenger_pred["distance_label"],
        "passenger_distance_match": gt_passenger_dist == passenger_pred["distance_code"],
        "driver_score": driver_pred["score"],
        "passenger_score": passenger_pred["score"],
        "driver_box_xyxy": json.dumps(driver_pred["box_xyxy"]) if driver_pred["box_xyxy"] is not None else "",
        "passenger_box_xyxy": json.dumps(passenger_pred["box_xyxy"]) if passenger_pred["box_xyxy"] is not None else "",
        "n_candidates_total": len(candidates),
        "n_driver_candidates": sum(1 for c in candidates if c.side == "driver"),
        "n_passenger_candidates": sum(1 for c in candidates if c.side == "passenger"),
    }


def save_summary(records: list[dict[str, object]], out_dir: Path) -> None:
    total = len(records)

    def accuracy(key: str) -> float:
        return (sum(1 for row in records if row[key]) / total) if total else 0.0

    summary = {
        "n_images": total,
        "driver_object_accuracy": round(accuracy("driver_object_match"), 4),
        "passenger_object_accuracy": round(accuracy("passenger_object_match"), 4),
        "driver_distance_accuracy": round(accuracy("driver_distance_match"), 4),
        "passenger_distance_accuracy": round(accuracy("passenger_distance_match"), 4),
        "target_columns": TARGET_COLUMNS,
        "notes": [
            "Object and distance predictions are heuristic first-pass estimates.",
            "Side assignment assumes the panorama center is forward-facing.",
            "Distance classes are estimated from 2D box geometry, not metric LiDAR distance.",
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_comparisons_csv(records: list[dict[str, object]], out_path: Path) -> None:
    if not records:
        return
    fieldnames = list(records[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def default_device(explicit_device: str | None) -> str:
    import torch

    if explicit_device:
        return explicit_device
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate roadside severity GT attributes with a first-pass detection heuristic.")
    ap.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Path to one dataset folder, e.g. Dataset/02_A23_DESCENDENTE",
    )
    ap.add_argument("--gt-csv", default=str(DEFAULT_GT_CSV), help="Ground truth CSV path")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Where to write comparison outputs")
    ap.add_argument("--image-name", default=None, help="Optional single image name from GT, e.g. Panoramic_002_4620.png")
    ap.add_argument("--limit", type=int, default=None, help="Optional max number of GT rows to evaluate")
    ap.add_argument("--device", default=None, help="cuda | mps | cpu (auto if omitted)")
    ap.add_argument("--box-th", type=float, default=0.25)
    ap.add_argument("--text-th", type=float, default=0.25)
    ap.add_argument("--driver-side", choices=["left", "right"], default="left")
    ap.add_argument("--center-ignore-frac", type=float, default=0.08, help="Ignore detections near the image center split")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    gt_csv = Path(args.gt_csv).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_ground_truth_rows(gt_csv, dataset_root, args.image_name)
    if args.limit is not None:
        rows = rows[: max(0, args.limit)]
    if not rows:
        raise ValueError(f"No GT rows found for dataset folder: {dataset_root.name}")

    from detect_roadside_severity import GroundingDINODetector, load_image_rgb

    image_index = build_image_index(dataset_root)
    detector = GroundingDINODetector(device=default_device(args.device))
    prompts = object_prompts()

    records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for row in rows:
        try:
            image_path = resolve_image_path(row, image_index)
            las_path = resolve_las_path(dataset_root, row["cloud_name"])
            image_rgb = load_image_rgb(str(image_path))
            h, w = image_rgb.shape[:2]
            detections = detector.detect(
                image_rgb=image_rgb,
                prompts=prompts,
                box_threshold=args.box_th,
                text_threshold=args.text_th,
            )
            candidates = build_candidates(
                detections=detections,
                image_size=(w, h),
                driver_side=args.driver_side,
                center_ignore_frac=args.center_ignore_frac,
            )
            records.append(comparison_record(row, image_path, las_path, candidates))
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {
                    "image_number": row.get("Image number", ""),
                    "error": str(exc),
                }
            )

    write_comparisons_csv(records, out_dir / "comparisons.csv")
    save_summary(records, out_dir)
    (out_dir / "failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")

    print(f"Saved comparisons: {out_dir / 'comparisons.csv'}")
    print(f"Saved summary:     {out_dir / 'summary.json'}")
    print(f"Saved failures:    {out_dir / 'failures.json'}")
    print(f"Evaluated images:  {len(records)}")
    print(f"Failed images:     {len(failures)}")


if __name__ == "__main__":
    main()
