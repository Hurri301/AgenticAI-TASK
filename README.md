# Multimodal iRAP Attribute-Coding Workflow

This repository contains the reproducible source code, prompts, attribute
rules and tests for the multimodal agentic iRAP road-attribute coding study.
It also contains the reusable 2D-to-3D projection package used to link
panoramic-image detections with mobile-LiDAR point clouds.

## Repository boundaries

Raw panoramas, LiDAR point clouds, trajectory files, model weights, API keys
and generated experiment outputs are deliberately excluded from version
control. The raw data are large and may be subject to institutional or
geospatial-data restrictions. Reproduction therefore requires access to the
same 468-observation dataset, the corresponding calibration/trajectory files,
the stated model checkpoints and the required multimodal-model APIs.

See `REPRODUCIBILITY.md` for the public-repository workflow, environment
setup, expected input layout, experiment commands and output files.

---

## 2D↔3D Linking for Ladybug Panoramas and LiDAR

Clean API and CLIs for deterministic linking between:
- Ladybug equirectangular panoramic images
- Lynx/Optech LAS point clouds

## Public Python API

`src/mm_link/api.py` exposes two high-level functions:

- `bbox_to_point_indices(...)`
  - Input: image bbox `(x_min, y_min, x_max, y_max)`
  - Output: LAS record indices whose projections fall inside the bbox

- `point_indices_to_bbox(...)`
  - Input: LAS record indices
  - Output: image bbox enclosing their projected pixels

Defaults are dataset-friendly and require no expert flags:
- `pose_model='applanix_ned321'`
- `invert_extrinsics=True`
- `flip_pano_u=True`
- `v_top=None, v_bottom=None` (full image height)

Backward-compatibility behavior: passing `v_top=0` and `v_bottom=0` is interpreted as full height.

## Installation

```bash
pip install -e .
```

After installation, run scripts directly with plain `python scripts/...` commands.

## CLI quickstart

### Mode A: bbox → point indices

```bash
python scripts/bbox_to_points.py \
  --poses data/Trajectories/01_N3.CSV \
  --extrinsics data/Calibration/calib1.xml \
  --las data/point_cloud/cloud_test_markings.las \
  --image data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png \
  --image-id ladybug_panoramic_000108.jpg \
  --bbox 3000,1500,3600,2200
```

Optional filters:
- `--max-distance-m`: Euclidean distance from camera center in world coordinates.
- `--min-intensity`: minimum LAS intensity threshold.
- `--out-las`: export selected subset preserving original LAS record bytes.
- `--visualize`: generate an overlay panorama with projected selected points false-colored by LAS intensity.
- `--visualization-out`: output image path for the overlay PNG.

Visualization example:
```bash
python scripts/bbox_to_points.py \
  --poses data/Trajectories/01_N3.CSV \
  --extrinsics data/Calibration/calib1.xml \
  --las data/point_cloud/cloud_test_markings.las \
  --image data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png \
  --image-id ladybug_panoramic_000108.jpg \
  --bbox 0,0,2047,1023 \
  --visualize \
  --visualization-out artifacts/mode_a_overlay.png
```

### Mode B: point indices → bbox

```bash
python scripts/points_to_bbox.py \
  --poses data/Trajectories/01_N3.CSV \
  --extrinsics data/Calibration/calib1.xml \
  --las data/point_cloud/cloud_test_markings.las \
  --image data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png \
  --image-id ladybug_panoramic_000108.jpg \
  --indices 1,2,3,4
```

You can also pass `--indices-file` (one index per line) and optionally `--out-json`.

Visualization options for Mode B:
- `--visualize`: generate an overlay panorama with projected valid points false-colored by LAS intensity.
- `--visualization-out`: output image path for the overlay PNG.

Visualization example:
```bash
python scripts/points_to_bbox.py \
  --poses data/Trajectories/01_N3.CSV \
  --extrinsics data/Calibration/calib1.xml \
  --las data/point_cloud/cloud_test_markings.las \
  --image data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png \
  --image-id ladybug_panoramic_000108.jpg \
  --indices 1,2,3,4 \
  --visualize \
  --visualization-out artifacts/mode_b_overlay.png
```


### Run test suite (new user quick jump)

Use the test files in `tests/` directly with `pytest`:

```bash
python -m pytest tests/test_projection_sanity.py -q
python -m pytest tests/test_bbox_to_points.py -q
python -m pytest tests/test_points_to_bbox.py -q
```

Or run everything in the folder:

```bash
python -m pytest tests -q
```

## Bbox and index semantics

- Bbox format is pixel-space `x1,y1,x2,y2` with image origin at top-left.
- Returned indices are **original LAS record order indices** (stable, index-preserving).
- Filters are applied before bbox selection for speed.

## Overriding config for other datasets

```python
from mm_link import ProjectionConfig, bbox_to_point_indices

cfg = ProjectionConfig(
    pose_model="applanix_ned321",
    invert_extrinsics=False,
    flip_pano_u=False,
    v_top=200,
    v_bottom=3700,
)

result = bbox_to_point_indices(..., config=cfg)
```

All projection math is centralized in `src/mm_link/projection.py`.
No auto-crop or micro-calibration refinement is used.
