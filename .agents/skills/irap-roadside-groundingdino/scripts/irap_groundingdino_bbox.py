#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torchvision.ops import box_convert

import groundingdino.datasets.transforms as T
from groundingdino.models import build_model
from groundingdino.util.misc import clean_state_dict
from groundingdino.util.slconfig import SLConfig
from groundingdino.util.utils import get_phrases_from_posmap

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SIDE_CROPS = {
    # Include the visible lower road surface, stopping before the bonnet/black artifact.
    "passenger": (1, 260, 600, 920),
    "driver": (1481, 260, 2048, 920),
}

IRAP_CATEGORIES = [
    "Cliff",
    "Tree >=10cm",
    "Rigid sign, post or pole >=10cm",
    "Unprotected safety barrier end",
    "Aggressive vertical face",
    "Upwards slope - roll over",
    "Deep drainage ditch",
    "Downwards slope",
    "Low rigid object >=20cm high",
    "Rigid structure or building",
    "Upwards slope - no roll over",
    "Semi-rigid structure or building",
    "Safety barrier - concrete",
    "Safety barrier - metal",
    "Safety barrier - wire rope",
    "Safety barrier - motorcycle friendly",
    "No object",
]
NO_OBJECT_CATEGORY = "No object"


@dataclass(frozen=True)
class ObjectHint:
    irap_category: str
    description: str
    dino_label: str


DEFAULT_HINTS = [
    ObjectHint("Cliff", "cliff edge", "cliff"),
    ObjectHint("Tree >=10cm", "tree trunk", "tree trunk"),
    ObjectHint("Rigid sign, post or pole >=10cm", "sign pole", "sign pole"),
    ObjectHint("Unprotected safety barrier end", "barrier end", "guardrail end"),
    ObjectHint("Aggressive vertical face", "rock face", "rock face"),
    ObjectHint("Upwards slope - roll over", "earth embankment", "earth embankment"),
    ObjectHint("Deep drainage ditch", "deep ditch", "drainage ditch"),
    ObjectHint("Downwards slope", "steep roadside drop", "steep slope"),
    ObjectHint("Low rigid object >=20cm high", "low concrete wall", "low wall"),
    ObjectHint("Rigid structure or building", "retaining wall", "retaining wall"),
    ObjectHint("Upwards slope - no roll over", "steep cut slope", "steep cut slope"),
    ObjectHint("Semi-rigid structure or building", "brick boundary wall", "brick wall"),
    ObjectHint("Safety barrier - concrete", "concrete barrier", "concrete barrier"),
    ObjectHint("Safety barrier - metal", "metal guardrail", "metal guardrail"),
    ObjectHint("Safety barrier - wire rope", "wire rope barrier", "wire rope barrier"),
    ObjectHint("Safety barrier - motorcycle friendly", "motorcycle barrier rail", "motorcycle barrier"),
]

NORMALIZED_CATEGORY_LOOKUP = {
    " ".join(category.lower().replace("≥", ">=").split()): category for category in IRAP_CATEGORIES
}

GROUNDINGDINO_TRANSFORM = T.Compose(
    [
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)


def canonical_category_name(raw: str) -> str:
    key = " ".join(raw.strip().lower().replace("≥", ">=").split())
    if key not in NORMALIZED_CATEGORY_LOOKUP:
        raise ValueError(
            f"Unknown iRAP category '{raw}'. Use one of: {', '.join(IRAP_CATEGORIES)}"
        )
    return NORMALIZED_CATEGORY_LOOKUP[key]


def resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "`--device cuda` was requested but CUDA is unavailable. Use `--device cpu` or `--device auto`."
        )
    return requested


def find_repo_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        return root

    candidates = [Path.cwd().resolve(), Path(__file__).resolve()]
    for start in candidates:
        chain = [start] + list(start.parents)
        for item in chain:
            if (item / "GroundingDINO").is_dir():
                return item
    raise FileNotFoundError(
        "Could not find repository root containing a 'GroundingDINO' directory. "
        "Pass --repo-root explicitly."
    )


def default_config_path(repo_root: Path) -> Path:
    return repo_root / "GroundingDINO" / "groundingdino" / "config" / "GroundingDINO_SwinT_OGC.py"


def default_checkpoint_path(repo_root: Path) -> Path:
    return repo_root / "GroundingDINO" / "weights" / "groundingdino_swint_ogc.pth"


def resolve_path(path_like: str) -> Path:
    path = Path(path_like).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def resolve_image_inputs(raw_inputs: list[str]) -> list[Path]:
    results: list[Path] = []
    seen: set[Path] = set()

    for raw in raw_inputs:
        entry = Path(raw).expanduser()
        matched: list[Path] = []
        if any(token in raw for token in ["*", "?", "["]):
            matched = [Path(item).resolve() for item in glob.glob(raw)]
        elif entry.is_dir():
            matched = sorted(
                [
                    p.resolve()
                    for p in entry.iterdir()
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
                ]
            )
        elif entry.is_file():
            matched = [entry.resolve()]
        else:
            raise FileNotFoundError(f"Image input not found: {raw}")

        for path in matched:
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if path not in seen:
                results.append(path)
                seen.add(path)

    if not results:
        raise FileNotFoundError("No image files were resolved from --images inputs.")
    return results


def load_image_rgb(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def crop_by_side(image_rgb: np.ndarray, side: str) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    h, w = image_rgb.shape[:2]
    x0, y0, x1, y1 = SIDE_CROPS[side]

    x0 = int(max(0, min(x0, max(w - 1, 0))))
    y0 = int(max(0, min(y0, max(h - 1, 0))))
    x1 = int(max(x0 + 1, min(x1, w)))
    y1 = int(max(y0 + 1, min(y1, h)))

    crop = image_rgb[y0:y1, x0:x1]
    return crop, (x0, y0, x1, y1)


def preprocess_image_for_groundingdino(image_rgb: np.ndarray) -> torch.Tensor:
    image_pillow = Image.fromarray(image_rgb)
    transformed, _ = GROUNDINGDINO_TRANSFORM(image_pillow, None)
    return transformed


def load_model(config_file: Path, checkpoint_file: Path, device: str):
    args = SLConfig.fromfile(str(config_file))
    args.device = device
    model = build_model(args)

    checkpoint = torch.load(str(checkpoint_file), map_location="cpu")
    state = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
    model.load_state_dict(clean_state_dict(state), strict=False)
    model.eval()
    return model.to(device)


def preprocess_caption(caption: str) -> str:
    text = caption.lower().strip()
    return text if text.endswith(".") else f"{text}."


def predict_caption(
    model: Any,
    image_tensor: torch.Tensor,
    caption: str,
    box_threshold: float,
    text_threshold: float,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor, list[str]]:
    prompt = preprocess_caption(caption)
    tensor = image_tensor.to(device)

    with torch.no_grad():
        outputs = model(tensor[None], captions=[prompt])

    prediction_logits = outputs["pred_logits"].cpu().sigmoid()[0]
    prediction_boxes = outputs["pred_boxes"].cpu()[0]

    keep_mask = prediction_logits.max(dim=1)[0] > box_threshold
    logits = prediction_logits[keep_mask]
    boxes = prediction_boxes[keep_mask]

    tokenizer = model.tokenizer
    tokenized = tokenizer(prompt)
    phrases = [
        get_phrases_from_posmap(logit > text_threshold, tokenized, tokenizer).replace(".", "")
        for logit in logits
    ]
    return boxes, logits.max(dim=1)[0], phrases


def cxcywh_to_xyxy_pixel(boxes: torch.Tensor, width: int, height: int) -> torch.Tensor:
    if boxes.numel() == 0:
        return torch.zeros((0, 4), dtype=torch.int64)
    scale = torch.tensor([width, height, width, height], dtype=boxes.dtype)
    boxes_abs = boxes * scale
    xyxy = box_convert(boxes_abs, in_fmt="cxcywh", out_fmt="xyxy")
    max_x = max(width - 1, 0)
    max_y = max(height - 1, 0)
    xyxy[:, 0::2] = xyxy[:, 0::2].clamp(0, max_x)
    xyxy[:, 1::2] = xyxy[:, 1::2].clamp(0, max_y)
    return xyxy.round().to(dtype=torch.int64)


def iou_xyxy(box_a: list[int], box_b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def deduplicate_objects(objects: list[dict[str, Any]], iou_threshold: float) -> list[dict[str, Any]]:
    ranked = sorted(objects, key=lambda item: item.get("confidence", 0.0), reverse=True)
    kept: list[dict[str, Any]] = []
    for item in ranked:
        bbox = item.get("bbox_xyxy")
        if bbox is None:
            kept.append(item)
            continue
        duplicate = False
        for existing in kept:
            if existing.get("irap_category") != item.get("irap_category"):
                continue
            existing_bbox = existing.get("bbox_xyxy")
            if existing_bbox is None:
                continue
            if iou_xyxy(bbox, existing_bbox) >= iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept


def normalize_hint_item(raw: Any) -> ObjectHint:
    if not isinstance(raw, dict):
        raise ValueError("Hint entries must be objects with iRAP category and description.")

    raw_category = str(raw.get("irap_category", raw.get("category", ""))).strip()
    raw_description = str(raw.get("description", raw.get("object_description", ""))).strip()
    raw_label = str(raw.get("dino_label", raw.get("label", raw_description))).strip()

    if not raw_category:
        raise ValueError("Hint entry is missing 'irap_category'.")
    if not raw_description:
        raise ValueError("Hint entry is missing 'description'.")
    if not raw_label:
        raise ValueError("Hint entry is missing 'dino_label' (or a fallback label field).")

    category = canonical_category_name(raw_category)
    if category == NO_OBJECT_CATEGORY:
        raise ValueError("'No object' should not be provided as a detection hint.")

    words = [part for part in raw_description.split(" ") if part]
    if len(words) < 2 or len(words) > 4:
        raise ValueError(
            f"Hint description '{raw_description}' should be 2-4 words for best prompt quality."
        )

    return ObjectHint(irap_category=category, description=raw_description, dino_label=raw_label)


def parse_hint_list(raw: Any) -> list[ObjectHint]:
    if not isinstance(raw, list):
        raise ValueError("Hints must be a JSON array.")
    return [normalize_hint_item(item) for item in raw]


def load_hints_by_side(hints_json: Path | None, sides: list[str], merge_defaults: bool) -> dict[str, list[ObjectHint]]:
    defaults = list(DEFAULT_HINTS)
    if hints_json is None:
        return {side: list(defaults) for side in sides}

    with hints_json.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    side_hints: dict[str, list[ObjectHint]] = {side: [] for side in sides}

    if isinstance(payload, list):
        parsed = parse_hint_list(payload)
        for side in sides:
            side_hints[side] = list(parsed)
    elif isinstance(payload, dict):
        if "objects" in payload:
            parsed = parse_hint_list(payload["objects"])
            for side in sides:
                side_hints[side] = list(parsed)
        else:
            raw_both = payload.get("both")
            both_hints = parse_hint_list(raw_both) if raw_both is not None else []
            for side in sides:
                raw_side = payload.get(side)
                if raw_side is not None:
                    side_hints[side] = parse_hint_list(raw_side)
                else:
                    side_hints[side] = list(both_hints)
    else:
        raise ValueError("Hints JSON must be either an array or object.")

    for side in sides:
        hints = side_hints[side]
        if merge_defaults:
            hints = list(defaults) + hints
        side_hints[side] = hints

    return side_hints


def detect_on_side(
    model: Any,
    image_rgb: np.ndarray,
    side: str,
    hints: list[ObjectHint],
    box_threshold: float,
    text_threshold: float,
    max_detections_per_hint: int,
    device: str,
    dedup_iou: float,
) -> dict[str, Any]:
    crop_rgb, crop_xyxy = crop_by_side(image_rgb, side)
    crop_h, crop_w = crop_rgb.shape[:2]
    crop_tensor = preprocess_image_for_groundingdino(crop_rgb)
    offset_x, offset_y = crop_xyxy[0], crop_xyxy[1]

    objects: list[dict[str, Any]] = []
    for hint in hints:
        boxes, scores, phrases = predict_caption(
            model=model,
            image_tensor=crop_tensor,
            caption=hint.dino_label,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            device=device,
        )
        boxes_xyxy = cxcywh_to_xyxy_pixel(boxes, width=crop_w, height=crop_h)

        for idx, (box, score, phrase) in enumerate(zip(boxes_xyxy.tolist(), scores.tolist(), phrases)):
            if idx >= max_detections_per_hint:
                break
            x1, y1, x2, y2 = [int(value) for value in box]
            full_bbox = [x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y]
            objects.append(
                {
                    "irap_category": hint.irap_category,
                    "object_description": hint.description,
                    "groundingdino_label": hint.dino_label,
                    "detected_phrase": str(phrase),
                    "confidence": float(score),
                    "bbox_xyxy": full_bbox,
                }
            )

    objects = deduplicate_objects(objects, iou_threshold=dedup_iou)
    if not objects:
        objects = [
            {
                "irap_category": NO_OBJECT_CATEGORY,
                "object_description": "no roadside object",
                "groundingdino_label": None,
                "detected_phrase": None,
                "confidence": None,
                "bbox_xyxy": None,
            }
        ]

    return {
        "side": side,
        "crop_xyxy": list(crop_xyxy),
        "objects": objects,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect iRAP roadside object categories with side-aware cropping and GroundingDINO."
    )
    parser.add_argument(
        "--images",
        nargs="+",
        required=True,
        help="Image paths, wildcard patterns, or directories with images.",
    )
    parser.add_argument(
        "--side",
        choices=["driver", "passenger", "both"],
        default="both",
        help="Road side to evaluate. Default: both.",
    )
    parser.add_argument("--out-json", required=True, help="Output JSON path.")
    parser.add_argument(
        "--hints-json",
        default=None,
        help=(
            "Optional hints file. Supports: "
            "(1) top-level array of hints, "
            "(2) {'objects': [...]}, "
            "(3) {'driver': [...], 'passenger': [...], 'both': [...]}."
        ),
    )
    parser.add_argument(
        "--merge-default-hints",
        action="store_true",
        help="Merge defaults with --hints-json entries.",
    )
    parser.add_argument("--repo-root", default=None, help="Repository root containing GroundingDINO/.")
    parser.add_argument(
        "--config-file",
        default=None,
        help="GroundingDINO config path. Defaults to GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=None,
        help="GroundingDINO checkpoint path. Defaults to GroundingDINO/weights/groundingdino_swint_ogc.pth",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Inference device. auto => cuda when available, otherwise cpu.",
    )
    parser.add_argument("--box-threshold", type=float, default=0.35, help="GroundingDINO box threshold.")
    parser.add_argument("--text-threshold", type=float, default=0.25, help="GroundingDINO text threshold.")
    parser.add_argument(
        "--max-detections-per-hint",
        type=int,
        default=3,
        help="Maximum detections retained per prompt hint.",
    )
    parser.add_argument(
        "--dedup-iou",
        type=float,
        default=0.7,
        help="IoU threshold used to remove duplicate boxes within the same iRAP category.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        device = resolve_device(args.device)
        repo_root = find_repo_root(args.repo_root)
        image_paths = resolve_image_inputs(args.images)
        out_json = resolve_path(args.out_json)
        hints_path = resolve_path(args.hints_json) if args.hints_json else None
        sides = ["driver", "passenger"] if args.side == "both" else [args.side]

        config_file = resolve_path(args.config_file) if args.config_file else default_config_path(repo_root)
        checkpoint_path = (
            resolve_path(args.checkpoint_path) if args.checkpoint_path else default_checkpoint_path(repo_root)
        )

        if not config_file.is_file():
            raise FileNotFoundError(f"GroundingDINO config file not found: {config_file}")
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"GroundingDINO checkpoint file not found: {checkpoint_path}")
        if hints_path and not hints_path.is_file():
            raise FileNotFoundError(f"Hints file not found: {hints_path}")

        hints_by_side = load_hints_by_side(
            hints_json=hints_path,
            sides=sides,
            merge_defaults=args.merge_default_hints,
        )

        model = load_model(config_file=config_file, checkpoint_file=checkpoint_path, device=device)

        images_out: list[dict[str, Any]] = []
        for image_path in image_paths:
            image_rgb = load_image_rgb(image_path)
            side_results = [
                detect_on_side(
                    model=model,
                    image_rgb=image_rgb,
                    side=side,
                    hints=hints_by_side[side],
                    box_threshold=args.box_threshold,
                    text_threshold=args.text_threshold,
                    max_detections_per_hint=args.max_detections_per_hint,
                    device=device,
                    dedup_iou=args.dedup_iou,
                )
                for side in sides
            ]
            images_out.append(
                {
                    "image_name": image_path.name,
                    "image_path": str(image_path),
                    "sides": side_results,
                }
            )

        payload = {
            "images": images_out,
            "settings": {
                "device": device,
                "box_threshold": float(args.box_threshold),
                "text_threshold": float(args.text_threshold),
                "max_detections_per_hint": int(args.max_detections_per_hint),
                "dedup_iou": float(args.dedup_iou),
                "side_mode": args.side,
                "driver_crop_xyxy": list(SIDE_CROPS["driver"]),
                "passenger_crop_xyxy": list(SIDE_CROPS["passenger"]),
                "config_file": str(config_file),
                "checkpoint_path": str(checkpoint_path),
                "hints_json": str(hints_path) if hints_path else None,
                "merge_default_hints": bool(args.merge_default_hints),
            },
        }

        out_json.parent.mkdir(parents=True, exist_ok=True)
        with out_json.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")

        print(f"Wrote iRAP detection JSON: {out_json}")
        print(f"Processed images: {len(image_paths)}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
