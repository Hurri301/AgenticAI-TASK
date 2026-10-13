# Input Contract

Use a JSON object as input to `scripts/projection_router.py`.

## Common fields

- `mode` (optional): `bbox_to_points` or `points_to_bbox`.
- `defaults` (optional object): overrides for demo paths and shared projection settings.
- Common override keys:
  - `poses`, `extrinsics`, `las`, `image`, `image_id`
  - `pose_model`, `invert_extrinsics`, `flip_pano_u`, `v_top`, `v_bottom`
  - `visualize`, `visualization_out`

## bbox_to_points mode

Provide one of:
- `bbox`: single bbox (`"x1,y1,x2,y2"` or `[x1,y1,x2,y2]`)
- `bboxes`: list of bbox entries
- `items`: list of bbox entries

Bbox entry fields:
- `bbox` (required)
- Any custom metadata fields (for traceability), for example `id`, `label`, `source`
- Optional per-item overrides such as `las`, `max_distance_m`, `min_intensity`

## points_to_bbox mode

Provide one of:
- Top-level `indices` or `indices_file` or `use_full_cloud: true`
- `items`: list where each item has exactly one of:
  - `indices`
  - `indices_file`
  - `use_full_cloud: true`

Item metadata fields are preserved under `trace.input`.

## Output shape

The router returns:
- `mode`
- `demo_defaults`
- `result_count`
- `results`: one result per input item

Each result includes:
- `trace` with `item_index` and original input item
- Projection output (`indices` + `bbox_xyxy` + `stats` for bbox mode, or `bbox_xyxy` + `stats` for points mode)
- `error` if that specific item failed
