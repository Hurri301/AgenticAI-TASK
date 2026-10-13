# Input Contract

Use a JSON object as input to `scripts/pointcloud_workflow_router.py`.

## Common fields

- `mode` (optional but recommended): `segment`, `cluster`, `distance`, `roadside_distance_to_road`
- `defaults` (optional object): shared defaults for `las`, `outdir`, `distance_backend`, `reference_class`
- `las` (optional): LAS path; defaults to `data/point_cloud/cloud_test.las`
- `outdir` (optional): base output folder for per-run artifacts
- `run_id` (optional): custom run folder name

## Mode: `segment`

Goal: segment LAS into `not-ground`, `ground`, `road`.

Fields:
- `mode`: `segment`
- `las` (optional)
- `segmentation_metadata` (optional): skip execution and reuse existing metadata JSON
- `trajectory` (optional): trajectory file passed to segmentation script
- `out_las` (optional): classified LAS output path
- `segment_prefix` (optional): output prefix
- `segment_outdir` (optional): segmentation output dir
- `segment_flags` (optional object): extra `segment_road_cloud.py` CLI flags (`snake_case` keys become `--kebab-case`)

## Mode: `cluster`

Goal: euclidean clustering on full cloud or candidate index subset.

Fields:
- `mode`: `cluster`
- `las` (optional)
- Exactly zero or one candidate source:
  - `indices`: inline index list/string
  - `indices_file`: path to index file
- `distance_threshold_m` (optional)
- `min_cluster_size` (optional)
- `cluster_backend` (optional): `auto`, `scipy`, or `python`
- `cluster_prefix` (optional)
- `cluster_outdir` (optional)
- `cluster_flags` (optional object): extra cluster CLI flags

## Mode: `distance`

Goal: minimum 3D distance per pair.

Fields:
- `mode`: `distance`
- `las` (optional)
- `distance_backend` (optional)
- `pairs` (required list)

Each pair must provide exactly one source per side (`a` and `b`):
- `indices_a` / `indices_b` (inline)
- `indices_a_file` / `indices_b_file` (file path)
- `cluster_a` / `cluster_b` objects:
  - `manifest` or `clusters_manifest`
  - `cluster_id`
- Or shared-manifest shorthand:
  - `clusters_manifest`
  - `cluster_a_id`
  - `cluster_b_id`

Any custom pair metadata is preserved in `trace.input`.

## Mode: `roadside_distance_to_road`

Goal: distance from each object set to road/ground reference.

Fields:
- `mode`: `roadside_distance_to_road`
- `las` (optional)
- `segmentation_metadata` (optional): reuse existing segmentation metadata instead of rerunning segmentation
- `reference_class` (optional): `road`, `ground`, or `not-ground`; default `road`
- `distance_backend` (optional)
- `objects` (or `items`) required list

Each object must provide exactly one source:
- `indices`
- `indices_file`
- `cluster` object with `manifest` (or `clusters_manifest`) + `cluster_id`

Optional visualization:
- `visualize_segmented_cloud` (bool)
- `visualization_backend` (`open3d`, `tk`, or `auto`)
- `visualization_flags` (extra visualize CLI flags)

## Output Shape

Top-level output includes:
- `mode`
- `input_json`
- `defaults`
- `run` (`run_id`, `run_dir`, `inputs_dir`, `steps_dir`, `repo_root`)

Per-mode outputs:
- `segment`: `segmentation`
- `cluster`: `clustering`
- `distance`: `result_count`, `results`
- `roadside_distance_to_road`: `segmentation`, `reference_class`, `reference_indices_file`, `result_count`, `results`, `visualization`

Traceability guarantees:
- One result per input object/pair.
- Original payload item preserved under `trace.input`.
- Resolved source files are included (`resolved_source` or `resolved_sources`).
- Inline indices are written to run-local files and referenced in output.
