from __future__ import annotations

from pathlib import Path


def _intensity_to_rgb(level: float) -> tuple[int, int, int]:
    x = max(0.0, min(1.0, level))
    if x < 0.25:
        t = x / 0.25
        return 0, int(255 * t), 255
    if x < 0.5:
        t = (x - 0.25) / 0.25
        return 0, 255, int(255 * (1.0 - t))
    if x < 0.75:
        t = (x - 0.5) / 0.25
        return int(255 * t), 255, 0
    t = (x - 0.75) / 0.25
    return 255, int(255 * (1.0 - t)), 0


def save_point_overlay(
    image_path: str,
    out_path: str,
    pixels,
    intensities,
    *,
    bbox_xyxy: tuple[int, int, int, int] | None = None,
) -> str:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Visualization requires pillow. Install with: pip install pillow") from exc

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    px = [(float(u), float(v)) for (u, v) in pixels]
    vals = [float(i) for i in intensities]
    if len(px) != len(vals):
        raise ValueError("pixels and intensities must have the same length")

    if vals:
        lo = min(vals)
        hi = max(vals)
        span = hi - lo
        for (u, v), inten in zip(px, vals):
            level = 0.5 if span <= 1e-9 else (inten - lo) / span
            color = _intensity_to_rgb(level)
            r = 2
            draw.ellipse((u - r, v - r, u + r, v + r), fill=color, outline=(0, 0, 0))

    if bbox_xyxy is not None:
        x0, y0, x1, y1 = bbox_xyxy
        draw.rectangle((x0, y0, x1, y1), outline=(255, 255, 255), width=3)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)

