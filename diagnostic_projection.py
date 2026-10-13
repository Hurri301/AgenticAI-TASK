#!/usr/bin/env python3
"""Diagnostic projection smoke utility using clean mm_link defaults."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mm_link import ProjectionConfig, bbox_to_point_indices, point_indices_to_bbox


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--poses", required=True)
    ap.add_argument("--extrinsics", required=True)
    ap.add_argument("--las", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--image-id", required=True)
    ap.add_argument("--outdir", default="artifacts")
    ap.add_argument("--pose-model", default="applanix_ned321")
    ap.add_argument("--invert-extrinsics", choices=["true", "false"], default="true")
    ap.add_argument("--flip-pano-u", choices=["true", "false"], default="true")
    ap.add_argument("--v-top", type=float, default=None)
    ap.add_argument("--v-bottom", type=float, default=None)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cfg = ProjectionConfig(
        pose_model=args.pose_model,
        invert_extrinsics=args.invert_extrinsics == "true",
        flip_pano_u=args.flip_pano_u == "true",
        v_top=args.v_top,
        v_bottom=args.v_bottom,
    )

    full_bbox = (0, 0, 999999, 999999)
    mode_a = bbox_to_point_indices(
        args.poses, args.extrinsics, args.las, args.image, args.image_id, full_bbox, max_points=20000, config=cfg
    )
    subset = mode_a["indices"][: min(200, len(mode_a["indices"]))]
    mode_b = point_indices_to_bbox(args.poses, args.extrinsics, args.las, args.image, args.image_id, subset, config=cfg)

    payload = {
        "mode_a_stats": mode_a["stats"],
        "subset_size": int(len(subset)),
        "mode_b_bbox_xyxy": mode_b["bbox_xyxy"],
        "mode_b_stats": mode_b["stats"],
    }

    out_path = outdir / "diagnostic_summary.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
