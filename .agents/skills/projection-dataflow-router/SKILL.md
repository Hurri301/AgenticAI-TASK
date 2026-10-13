---
name: projection-dataflow-router
description: Route 2D-to-3D and 3D-to-2D projection workflows between panorama image bounding boxes and LAS point-cloud indices, and return traceable JSON outputs. Use when a task needs bbox-to-points (image bbox to 3D indices) or points-to-bbox (point indices/full cloud to image bbox) using the demo data paths in this repository.
---

# Projection Dataflow Router

Use this skill to decide projection direction, load the correct demo source data, execute the correct script, and return traceable JSON.
Read [input contract](references/input_contract.md) before running.

## Workflow

1. Read the input payload and detect mode.
- Use `bbox_to_points` when payload has `bboxes` or `bbox`.
- Use `points_to_bbox` when payload has `indices`, `indices_file`, or `use_full_cloud`.

2. Run the router script.
- Script path: `scripts/projection_router.py`
- It calls repository scripts:
  - `scripts/bbox_to_points.py`
  - `scripts/points_to_bbox.py`

3. Return JSON result.
- Keep `trace` object in each item to preserve input lineage.
- For bbox inputs, include the original bbox metadata and mapped indices.
- For index/full-cloud inputs, include source metadata and resulting bbox.

## Commands

Run bbox input JSON:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\projection-dataflow-router\scripts\projection_router.py `
  --input-json ".\.agents\skills\projection-dataflow-router\references\example_bbox_input.json" `
  --out-json "artifacts\projection_bbox_to_points.json"
```

Run indices input JSON:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\projection-dataflow-router\scripts\projection_router.py `
  --input-json ".\.agents\skills\projection-dataflow-router\references\example_indices_input.json" `
  --out-json "artifacts\projection_points_to_bbox.json"
```

## Defaults (Demo Mode)

- `poses`: `data/Trajectories/01_N3.CSV`
- `extrinsics`: `data/Calibration/calib1.xml`
- `las`: `data/point_cloud/cloud_test.las`
- `image`: `data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png`
- `image_id`: `ladybug_panoramic_000108.jpg`

## Output Rules

1. Always return valid JSON.
2. Keep one result item per input entity (bbox item or points request).
3. Preserve user-provided metadata under `trace.input`.
4. Report failures per item under `error` without dropping other items.
