# Input Contract

Use a JSON object as input to `scripts/visual_context_router.py`.

## Required Fields

- `items`: list of attribute coding requests.

Each item must include:

- `attribute`: one of `Area type`, `Street lighting`, `Service road`, `Delineation`

Each item should include at least one of:

- `code`: exact iRAP Cat ID
- `label`: exact or close category label
- attribute-specific booleans:
  - `urban_context`
  - `lighting_present`
  - `service_road_present`
  - `delineation_adequate`
- `evidence`: string or list of visual evidence notes

## Optional Fields

- `image`, `image_id`, `frame_id`, `segment_id`
- `confidence`
- `uncertainties`

## Output Shape

Top-level output includes:

- `mode`
- `artifacts`
- `counts`
- `items`
- `warnings`

Each result includes:

- `attribute`
- `col_id`
- `cat_id`
- `category`
- `confidence`
- `evidence`
- `trace.input`
