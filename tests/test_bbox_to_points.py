from mm_link.api import bbox_to_point_indices
from mm_link.io import load_las_points

POSES = "data/Trajectories/01_N3.CSV"
EXTR = "data/Calibration/calib1.xml"
LAS = "data/point_cloud/cloud_test_markings.las"
IMG = "data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png"
IMG_ID = "ladybug_panoramic_000108.jpg"


def test_bbox_to_point_indices_in_range_and_pixels_inside_bbox():
    bbox = (0, 0, 7999, 3999)
    result = bbox_to_point_indices(
        POSES,
        EXTR,
        LAS,
        IMG,
        IMG_ID,
        bbox,
        max_points=5000,
        return_pixels=True,
    )
    idx = result["indices"]
    px = result["pixels"]
    xyz, _ = load_las_points(LAS)
    assert all(i >= 0 for i in idx)
    assert all(i < len(xyz) for i in idx)
    x0, y0, x1, y1 = bbox
    assert all(x0 <= u <= x1 and y0 <= v <= y1 for (u, v) in px)
