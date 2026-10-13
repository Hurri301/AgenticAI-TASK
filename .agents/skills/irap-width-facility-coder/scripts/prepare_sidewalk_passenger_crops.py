#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create passenger-side context and road-edge crops for sidewalk coding."
    )
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument(
        "--passenger-side",
        choices=("left", "right"),
        default="left",
        help="Image side containing the passenger roadside; project default is left.",
    )
    parser.add_argument("--context-fraction", type=float, default=0.50)
    parser.add_argument("--focus-fraction", type=float, default=0.30)
    return parser.parse_args()


def crop_bounds(width: int, height: int, side: str, fraction: float) -> tuple[int, int, int, int]:
    crop_width = max(1, min(width, round(width * fraction)))
    if side == "left":
        return 0, 0, crop_width, height
    return width - crop_width, 0, width, height


def validate_fraction(name: str, value: float) -> None:
    if not 0.05 <= value <= 0.95:
        raise ValueError(f"{name} must be between 0.05 and 0.95")


def main() -> int:
    args = parse_args()
    validate_fraction("context_fraction", args.context_fraction)
    validate_fraction("focus_fraction", args.focus_fraction)
    if args.focus_fraction > args.context_fraction:
        raise ValueError("focus_fraction must not exceed context_fraction")

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, object]] = []

    for raw_path in args.images:
        image_path = Path(raw_path).resolve()
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            width, height = image.size
            context_xyxy = crop_bounds(width, height, args.passenger_side, args.context_fraction)
            focus_xyxy = crop_bounds(width, height, args.passenger_side, args.focus_fraction)
            context_path = outdir / f"{image_path.stem}_passenger_context.png"
            focus_path = outdir / f"{image_path.stem}_passenger_focus.png"
            image.crop(context_xyxy).save(context_path)
            image.crop(focus_xyxy).save(focus_path)

        items.append(
            {
                "image": str(image_path),
                "image_size": [width, height],
                "passenger_side": args.passenger_side,
                "orientation_note": (
                    "Project default: rear-facing panorama under right-hand traffic, passenger side is left."
                ),
                "passenger_context_crop": str(context_path),
                "passenger_context_xyxy": list(context_xyxy),
                "passenger_focus_crop": str(focus_path),
                "passenger_focus_xyxy": list(focus_xyxy),
            }
        )

    manifest = {
        "mode": "sidewalk_passenger_crop_preparation",
        "counts": {"images": len(items)},
        "items": items,
    }
    manifest_path = outdir / "sidewalk_passenger_crops.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
