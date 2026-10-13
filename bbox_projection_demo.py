#!/usr/bin/env python3
"""Deprecated demo retained as a small wrapper around clean API."""

from __future__ import annotations

import argparse
import json

from mm_link import ProjectionConfig, bbox_to_point_indices


def main() -> None:
    ap = argparse.ArgumentParser(description="Simple bbox projection demo (non-interactive)")
    ap.add_argument("--poses", required=True)
    ap.add_argument("--extrinsics", required=True)
    ap.add_argument("--las", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--image-id", required=True)
    ap.add_argument("--bbox", required=True, help="x1,y1,x2,y2")
    args = ap.parse_args()

    x1, y1, x2, y2 = [int(v.strip()) for v in args.bbox.split(",")]
    result = bbox_to_point_indices(
        args.poses,
        args.extrinsics,
        args.las,
        args.image,
        args.image_id,
        (x1, y1, x2, y2),
        config=ProjectionConfig(),
    )
    print(json.dumps({"indices_count": int(result["indices"].size), "stats": result["stats"]}, indent=2))


if __name__ == "__main__":
    main()
