# Input Contract

Use a JSON object as input to `scripts/alignment_visibility_router.py`.

## Required Fields

- `items`: list of attribute coding requests.

Each item must include:

- `attribute`: `Curvature` or `Sight distance`

For `Curvature`, provide one of:

- `code`
- `label`
- `curvature_class`
- `radius_m` if project heuristic bucketing is acceptable

For `Sight distance`, provide one of:

- `code`
- `label`
- `sight_distance_adequate`
- `visibility_restricted`

## Optional Fields

- `geometry_metrics`
- `visual_evidence`
- `trajectory_window_m`
- `image`, `image_id`, `frame_id`, `segment_id`
- `confidence`
- `uncertainties`

## Output Shape

Each result includes `attribute`, `col_id`, `cat_id`, `category`, `geometry_metrics`, `visual_evidence`, `confidence`, `rule_source`, and `trace.input`.
