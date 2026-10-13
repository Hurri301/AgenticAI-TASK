# Input Contract

Use a JSON object as input to `scripts/carriageway_layout_router.py`.

## Required Fields

- `items`: list of attribute coding requests.

Each item must include:

- `attribute`: `Number of lanes` or `Median Type`

For `Number of lanes`, provide one of:

- `code`
- `label`
- `lane_count`: numeric through-lane count
- `lane_pattern`: `two_and_one` or `three_and_two`

For `Median Type`, provide one of:

- `code`
- `label`
- `median_type`
- `median_width_m` with optional `separator`

## Optional Fields

- `image`, `image_id`, `frame_id`, `segment_id`
- `evidence`
- `excluded_features`
- `confidence`
- `uncertainties`

## Output Shape

Each result includes `attribute`, `col_id`, `cat_id`, `category`, `confidence`, `evidence`, `excluded_features`, and `trace.input`.
