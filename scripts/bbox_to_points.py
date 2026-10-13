#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from mm_link import ProjectionConfig, bbox_to_point_indices, export_subset_las
from mm_link.utils import parse_bbox


def main() -> None:
    ap = argparse.ArgumentParser(description="Mode A: panorama bbox -> LAS point indices")
    ap.add_argument("--poses", required=True)
    ap.add_argument("--extrinsics", required=True)
    ap.add_argument("--las", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--image-id", required=True)
    ap.add_argument("--bbox", required=True, help="x1,y1,x2,y2")
    ap.add_argument("--max-distance-m", type=float, default=None)
    ap.add_argument("--min-intensity", type=int, default=None)
    ap.add_argument("--out-las", default=None)
    ap.add_argument("--pose-model", default="applanix_ned321")
    ap.add_argument("--invert-extrinsics", choices=["true", "false"], default="true")
    ap.add_argument("--flip-pano-u", choices=["true", "false"], default="true")
    ap.add_argument("--v-top", type=float, default=None)
    ap.add_argument("--v-bottom", type=float, default=None)
    ap.add_argument("--visualize", action="store_true", help="Save a panorama overlay with projected points false-colored by intensity")
    ap.add_argument("--visualization-out", default=None, help="Output path for visualization image")
    args = ap.parse_args()

    cfg = ProjectionConfig(
        pose_model=args.pose_model,
        invert_extrinsics=args.invert_extrinsics == "true",
        flip_pano_u=args.flip_pano_u == "true",
        v_top=args.v_top,
        v_bottom=args.v_bottom,
    )

    result = bbox_to_point_indices(
        args.poses,
        args.extrinsics,
        args.las,
        args.image,
        args.image_id,
        parse_bbox(args.bbox),
        max_distance_m=args.max_distance_m,
        min_intensity=args.min_intensity,
        config=cfg,
        visualize=args.visualize,
        visualization_out=args.visualization_out,
    )

    if args.out_las and len(result["indices"]) > 0:
        export_subset_las(args.las, result["indices"], args.out_las)

    serializable = {
        "indices": [int(i) for i in result["indices"]],
        "bbox_xyxy": parse_bbox(args.bbox),
        "stats": result["stats"],
    }
    if args.visualize:
        serializable["visualization_path"] = result.get("visualization_path")
    print(json.dumps(serializable, indent=2))


if __name__ == "__main__":
    main()
