#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from mm_link import ProjectionConfig, point_indices_to_bbox
from mm_link.utils import parse_indices


def main() -> None:
    ap = argparse.ArgumentParser(description="Mode B: LAS indices -> panorama bbox")
    ap.add_argument("--poses", required=True)
    ap.add_argument("--extrinsics", required=True)
    ap.add_argument("--las", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--image-id", required=True)
    ap.add_argument("--indices", default=None)
    ap.add_argument("--indices-file", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--pose-model", default="applanix_ned321")
    ap.add_argument("--invert-extrinsics", choices=["true", "false"], default="true")
    ap.add_argument("--flip-pano-u", choices=["true", "false"], default="true")
    ap.add_argument("--v-top", type=float, default=None)
    ap.add_argument("--v-bottom", type=float, default=None)
    ap.add_argument("--visualize", action="store_true", help="Save a panorama overlay with projected points false-colored by intensity")
    ap.add_argument("--visualization-out", default=None, help="Output path for visualization image")
    args = ap.parse_args()

    if bool(args.indices) == bool(args.indices_file):
        raise ValueError("Use exactly one of --indices or --indices-file")

    if args.indices:
        indices = parse_indices(args.indices)
    else:
        with open(args.indices_file, "r", encoding="utf-8") as f:
            indices = [int(line.strip()) for line in f if line.strip()]

    cfg = ProjectionConfig(
        pose_model=args.pose_model,
        invert_extrinsics=args.invert_extrinsics == "true",
        flip_pano_u=args.flip_pano_u == "true",
        v_top=args.v_top,
        v_bottom=args.v_bottom,
    )

    result = point_indices_to_bbox(
        args.poses,
        args.extrinsics,
        args.las,
        args.image,
        args.image_id,
        indices,
        config=cfg,
        visualize=args.visualize,
        visualization_out=args.visualization_out,
    )

    output = {"bbox_xyxy": result["bbox_xyxy"], "stats": result["stats"]}
    if args.visualize:
        output["visualization_path"] = result.get("visualization_path")
    text = json.dumps(output, indent=2)
    print(text)
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
