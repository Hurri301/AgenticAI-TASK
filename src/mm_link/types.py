from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ImagePose:
    image_id: str
    t_img: float
    e: float
    n: float
    h: float
    roll: float
    pitch: float
    heading: float


@dataclass(frozen=True)
class Calibration:
    T_imu_cam: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class ProjectionConfig:
    pose_model: str = "applanix_ned321"
    invert_extrinsics: bool = True
    flip_pano_u: bool = True
    v_top: Optional[float] = None
    v_bottom: Optional[float] = None

    def resolved_vertical_bounds(self, image_height: int) -> tuple[float, float]:
        # Backward compatibility: (0,0) means full image.
        if self.v_top == 0 and self.v_bottom == 0:
            return 0.0, float(image_height)
        top = 0.0 if self.v_top is None else float(self.v_top)
        bottom = float(image_height) if self.v_bottom is None else float(self.v_bottom)
        if bottom <= top:
            return 0.0, float(image_height)
        return top, bottom
