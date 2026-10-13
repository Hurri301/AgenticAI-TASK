# Input Contract

Use a JSON object as input to `scripts/access_points_router.py`.

## Required Fields

Provide either:

- `items`: list of property-access coding requests, or
- a single request object with the same fields.

Each request should include one of:

- `code`
- `label`
- `commercial_present`
- `residential_count`

## Optional Fields

- `attribute`: defaults to `Property access points`
- `candidate_accesses`: list of detected candidate accesses
- `rejected_candidates`: list of rejected access-like features
- `evidence_frames`
- `segment_id`, `image`, `image_id`
- `confidence`
- `uncertainties`

## Output Shape

Each result includes `attribute`, `col_id`, `cat_id`, `category`, `commercial_present`, `residential_count`, candidate evidence, and `trace.input`.
