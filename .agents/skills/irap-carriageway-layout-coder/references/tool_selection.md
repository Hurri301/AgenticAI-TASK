# Tool Selection

Use the lightest reliable path for lane and median layout evidence.

## Decision Rules

| Situation | Select | Reason |
| --- | --- | --- |
| User provides exact `code` or `label` | Router only | Normalizes Cat ID and preserves trace. |
| User provides `lane_count`, `lane_pattern`, `median_type`, or `median_width_m` | Router only | Inputs are already structured enough for code mapping. |
| Single panorama clearly shows lanes/median | `$panoramic-road-safety-describer` or direct visual review | Layout is visible and does not require 3D. |
| Lane markings are occluded or ambiguous | Adjacent-frame review | Through lanes and short turn lanes are easier to distinguish over a sequence. |
| Lane count conflicts with visible road width | `$projection-dataflow-router` optional geometry cross-check | Geometry can support a plausibility check but should not replace lane-function reasoning. |
| Median type depends on physical width | Visual review plus optional measurement | Physical median width classes may need measured or estimated width. |

## Attribute-Specific Tool Choice

- `Number of lanes`: prefer visual/sequence review. Use geometry only to cross-check, not as primary evidence.
- `Median Type`: prefer visual separator classification. Use geometry only for physical median width categories.

## What Not To Select

- Do not use pointcloud segmentation for routine lane counting.
- Do not use width-facility skill for lane count; use it only for lane width/shoulder/sidewalk measurements.
