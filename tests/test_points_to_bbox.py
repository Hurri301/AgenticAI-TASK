from mm_link.api import bbox_to_point_indices, point_indices_to_bbox

POSES = "data/Trajectories/01_N3.CSV"
EXTR = "data/Calibration/calib1.xml"
LAS = "data/point_cloud/cloud_test_markings.las"
IMG = "data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png"
IMG_ID = "ladybug_panoramic_000108.jpg"


def _u_in_bbox(u: float, x0: int, x1: int) -> bool:
    if x0 <= x1:
        return x0 <= u <= x1
    return (u >= x0) or (u <= x1)


def test_point_indices_to_bbox_encloses_projected_pixels():
    selected = bbox_to_point_indices(
        POSES,
        EXTR,
        LAS,
        IMG,
        IMG_ID,
        (0, 0, 7999, 3999),
        max_points=2000,
    )["indices"]

    assert len(selected) > 0
    pick = selected[: min(100, len(selected))]
    result = point_indices_to_bbox(POSES, EXTR, LAS, IMG, IMG_ID, pick, return_pixels=True)
    x0, y0, x1, y1 = result["bbox_xyxy"]
    pixels = result["pixels"]
    for u, v in pixels:
        assert _u_in_bbox(float(u), x0, x1)
        assert y0 <= float(v) <= y1
