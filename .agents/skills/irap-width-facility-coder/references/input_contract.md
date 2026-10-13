# Input Contract

Use a JSON object as input to `scripts/width_facility_router.py`.

## Required Fields

- `items`: list of attribute coding requests.

Each item must include:

- `attribute`: `Lane width`, `Paved shoulder - drivers side`, `Paved shoulder - passenger side`, or `Sidewalk - passenger side`

Provide one of:

- `code`
- `label`
- `width_m` for lane width and paved shoulder
- `none: true` for no paved shoulder or no sidewalk
- `visual_narrow_paved_shoulder_present: true` for paved shoulder when zoomed road-edge review shows a very narrow paved strip that geometry measured as zero or missed
- `zoom_artifact`: path to the zoomed crop used for paved shoulder validation
- sidewalk-specific fields:
  - `passenger_crop_reviewed`: must be `true` for evidence-derived sidewalk coding
  - `semantic_inference_source`: `vlm`, `segmentation`, `vlm_segmentation`, or `manual_review`
  - `review_required`: unresolved cases must remain review items and must not be finalized
  - `passenger_context_crop`: path to the broad passenger-side crop
  - `passenger_focus_crop`: path to the passenger road-edge crop
  - `crop_xyxy`: original-image bounds for the primary crop
  - `continuous_segment_reviewed`: whether target and adjacent frames cover the coded segment
  - `facility_present`: whether a pedestrian facility is visibly present
  - `continuous_over_segment`: whether the facility is continuous over the coded segment
  - `purpose_built`: whether it is a formal purpose-built sidewalk
  - `all_weather_surface`: whether it offers a reliable sealed or unsealed walking surface
  - `pedestrian_flow_evidence`: evidence supporting an informal path
  - `partially_blocked`: whether a sidewalk is partly obstructed
  - `pedestrians_forced_onto_road`: whether pedestrians must enter the roadway
  - `barrier_present`
  - `barrier_restrains_vehicle`: whether the barrier can restrain a vehicle; a kerb alone is `false`
  - `curb_only`
  - `facility_type`: `sidewalk` or `informal_path`
  - `distance_from_road_m`
  - `distance_reference`: `nearest driving lane edge to near facility edge, including shoulder/parking`

## Optional Fields

- `side`
- `measurement_source`
- `image`, `image_id`, `frame_id`, `segment_id`
- `evidence`
- `confidence`
- `uncertainties`
- `rejected_alternatives`

For evidence-derived sidewalk coding, do not use `none: true` without `passenger_crop_reviewed: true` and `continuous_segment_reviewed: true`. Direct `code` or `label` inputs remain accepted as externally decided values.

Do not set `semantic_inference_source` to a color/texture/pixel-ratio heuristic. Those signals may identify candidate regions but cannot finalize facility presence, type, continuity, barrier sufficiency, or distance.

## Output Shape

Each result includes `attribute`, `col_id`, `cat_id`, `category`, `measured_meters`, `measurement_source`, `confidence`, `evidence`, and `trace.input`.
