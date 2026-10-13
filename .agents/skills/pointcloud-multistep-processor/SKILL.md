---
name: pointcloud-multistep-processor
description: Execute multi-step 3D point-cloud processing workflows using repository tools for segmentation, euclidean clustering, minimum-distance measurement, and segmented-cloud visualization, with traceable JSON outputs per input entity. Use when tasks involve modifying, segmenting, processing, or analyzing LAS point clouds through two or more dependent steps, including roadside-object-to-road distance workflows.
---

# Pointcloud Multistep Processor

Use this skill to route multi-step LAS workflows and preserve lineage from input items to final results.
Read [input contract](references/input_contract.md) before running.

## Workflow

1. Detect mode and normalize settings.
- `segment`: run road/ground/non-ground segmentation.
- `cluster`: run euclidean clustering on full cloud or candidate indices.
- `distance`: compute minimum 3D distance for each pair of index sets.
- `roadside_distance_to_road`: segment (or reuse segmentation metadata), choose `road` or `ground` as reference, then compute one distance per object set.

2. Route through `scripts/pointcloud_workflow_router.py`.
- Calls repository scripts:
  - `scripts/segment_road_cloud.py`
  - `scripts/pointcloud/cluster_euclidean.py`
  - `scripts/pointcloud/min_cluster_distance.py`
  - optional `scripts/visualize_segmented_cloud.py`

3. Keep intermediate artifacts traceable.
- One run directory per invocation under the requested `outdir`.
- Inline indices are materialized under `<run_dir>/inputs`.
- Output keeps `trace.input` per object/pair and resolved source files.

4. Keep final outputs JSON-native and fault-tolerant.
- One result item per input item.
- Per-item failures are reported under `error` without dropping successful items.

## Commands

Run roadside object-to-road distances:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\pointcloud-multistep-processor\scripts\pointcloud_workflow_router.py `
  --input-json ".\.agents\skills\pointcloud-multistep-processor\references\example_roadside_distance_input.json" `
  --out-json "artifacts\pointcloud_workflows\roadside_distance_results.json"
```

Run pairwise distances:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\pointcloud-multistep-processor\scripts\pointcloud_workflow_router.py `
  --input-json ".\.agents\skills\pointcloud-multistep-processor\references\example_distance_input.json" `
  --out-json "artifacts\pointcloud_workflows\distance_results.json"
```

Run clustering over a candidate index set:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\pointcloud-multistep-processor\scripts\pointcloud_workflow_router.py `
  --input-json ".\.agents\skills\pointcloud-multistep-processor\references\example_cluster_input.json" `
  --out-json "artifacts\pointcloud_workflows\cluster_results.json"
```

Run segmentation only:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\pointcloud-multistep-processor\scripts\pointcloud_workflow_router.py `
  --input-json ".\.agents\skills\pointcloud-multistep-processor\references\example_segment_input.json" `
  --out-json "artifacts\pointcloud_workflows\segment_results.json"
```

## Defaults

- `las`: `data/point_cloud/cloud_test.las`
- `outdir`: `artifacts/pointcloud_workflows`
- `reference_class` (roadside mode): `road`
- `distance_backend`: `auto`
- `Run segmentation parameters`: --trajectory-resample-m 1.0 --window-length-m 40 --window-overlap-m 30 --merge-vote-threshold 0.47 --road-profile-min-points 10 --max-missing-bins-local 5 --road-profile-smoothing-bins 3 --road-long-bin-m 1.25 --road-max-roughness-m 0.065 --road-interior-max-roughness-m 0.10 --road-flat-threshold-m 0.10 --branch-mode on --branch-prominence-ratio 0.35
## Output Rules

1. Always return valid JSON.
2. Preserve user metadata and original item payload under `trace.input`.
3. Preserve resolved source paths (`indices_file`, manifest cluster references, generated inline files).
4. In roadside workflows, keep segmentation metadata path and selected reference class in the output.
5. Keep the road/ground relation explicit: road is a subset of ground; choose `reference_class=ground` when full ground reference is needed.
