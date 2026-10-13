from __future__ import annotations


def parse_bbox(text: str) -> tuple[int, int, int, int]:
    vals = [int(v.strip()) for v in text.split(",")]
    if len(vals) != 4:
        raise ValueError("bbox must be x1,y1,x2,y2")
    return vals[0], vals[1], vals[2], vals[3]


def parse_indices(text: str) -> list[int]:
    vals = [v.strip() for v in text.split(",") if v.strip()]
    return [int(v) for v in vals]
