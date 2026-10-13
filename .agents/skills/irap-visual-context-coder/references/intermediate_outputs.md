# Intermediate Outputs To Validate

Produce these blocks before the final Cat ID when doing a full workflow.

## Area type

```json
{
  "attribute": "Area type",
  "scene_context": {
    "built_up_frontage": false,
    "kerbs_or_urban_street_features": false,
    "residential_or_commercial_density": "low",
    "land_use_summary": "open rural frontage"
  },
  "candidate_codes": [
    {"cat_id": 1, "category": "Rural", "support": ["open land", "low development"]},
    {"cat_id": 2, "category": "Urban", "support": []}
  ],
  "validation_checks": ["coded segment context reviewed", "transition/edge case noted"]
}
```

## Street lighting

```json
{
  "attribute": "Street lighting",
  "lighting_evidence": {
    "lamp_heads_visible": true,
    "pole_only_false_positive": false,
    "roadway_relevance": "roadside lamps face carriageway"
  },
  "candidate_codes": [
    {"cat_id": 2, "category": "Present", "support": ["visible luminaires"]}
  ],
  "validation_checks": ["lamp/luminaire visible", "not only utility poles or wires"]
}
```

## Service road

```json
{
  "attribute": "Service road",
  "layout_evidence": {
    "parallel_separate_road": false,
    "serves_local_or_property_access": false,
    "rejected_features": ["shoulder", "driveway", "side road"]
  },
  "candidate_codes": [
    {"cat_id": 1, "category": "Not present", "support": ["no separate frontage road"]}
  ],
  "validation_checks": ["parallel road test applied", "reject list documented"]
}
```

## Delineation

```json
{
  "attribute": "Delineation",
  "guidance_evidence": {
    "centre_line": true,
    "edge_lines": true,
    "kerbs_or_edge_contrast": false,
    "guideposts_reflectors_signs": false,
    "travel_path_clear": true
  },
  "candidate_codes": [
    {"cat_id": 1, "category": "Adequate", "support": ["clear centre and edge lines"]}
  ],
  "validation_checks": ["coded carriageway inspected", "guidance features listed"]
}
```
