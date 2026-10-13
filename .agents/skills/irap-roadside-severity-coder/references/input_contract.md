# Input Contract

Use a JSON object as input to `scripts/roadside_severity_router.py`.

## Required Fields

- `images`: list of image entries. Each entry may be:
  - string image path, or
  - object with:
    - `image` (or `image_path`) required
    - `image_id` optional (defaults to filename)
    - optional projection overrides (`poses`, `extrinsics`, `las`, `pose_model`, etc.)

## Optional Fields

- `side`: `driver`, `passenger`, or `both` (default `both`)
- `work_dir`: folder for intermediate JSON and index artifacts
- `groundingdino` object:
  - `hints_json`, `merge_default_hints`, `repo_root`, `config_file`, `checkpoint_path`
  - `device`, `box_threshold`, `text_threshold`, `max_detections_per_hint`, `dedup_iou`
  - `semantic_label_overrides_json`: optional JSON file mapping iRAP category -> simplified detector label
  - `semantic_label_overrides`: optional inline object mapping iRAP category -> simplified detector label
- `projection_defaults` object:
  - keys supported by `projection-dataflow-router` defaults (for example `poses`, `extrinsics`, `las`)
- `distance_defaults` object:
  - keys supported by `pointcloud-multistep-processor` roadside mode
  - common keys: `las`, `outdir`, `segmentation_metadata`, `reference_class`, `distance_backend`

## Reusing Existing Artifacts (Skip Steps)

- `detections_json`: skip GroundingDINO run and reuse this detections file
- `projection_json`: skip projection run and reuse this projection output
- `distance_json`: skip distance run and reuse this distance output

## Output Shape

Top-level output includes:

- `columns`: coding field IDs (`RS_D` distance, `RS_O` object)
- `artifacts`: paths to input/output artifacts used in the run
- `hints_source`: one of `generated`, `provided`, `reused_detections`
- `effective_hints_by_side`: exact hints used for detector execution after semantic simplification
- `hints_autocorrections`: list of description/label adjustments applied before detection
- `bbox_visualizations`: rendered bbox overlay image paths from GroundingDINO detections
- `explainability`: concise natural-language summary JSON (also saved to `artifacts.explainability_json`)
- `counts`: high-level step counts
- `images`: one entry per image, each with side-level coded result
- `warnings`: per-item non-fatal issues

Each side result includes:

- `rs_d`: `{ col_id, cat_id, category }`
- `rs_o`: `{ col_id, cat_id, category }`
- `risk_rank`: selected hierarchy rank
- `distance_m`: numeric distance to reference class (if available)
- `candidates_considered`: ranked candidate list used for selection
