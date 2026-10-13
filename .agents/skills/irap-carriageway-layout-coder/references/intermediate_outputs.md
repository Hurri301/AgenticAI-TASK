# Intermediate Outputs To Validate

Produce these blocks before the final Cat ID when doing a full workflow.

## Number of lanes

```json
{
  "attribute": "Number of lanes",
  "lane_evidence": {
    "coded_direction": "forward",
    "through_lanes_counted": 2,
    "lane_pattern": null,
    "excluded_features": ["short turn lane", "shoulder"],
    "adjacent_frames_checked": true,
    "geometry_cross_check": {
      "used": false,
      "road_width_m": null,
      "note": null
    }
  },
  "candidate_codes": [
    {"cat_id": 2, "category": "Two", "support": ["two through lanes"]}
  ],
  "validation_checks": ["turn lanes excluded", "short changes under 400m excluded", "coded direction clear"]
}
```

## Median Type

```json
{
  "attribute": "Median Type",
  "median_evidence": {
    "opposing_flow_present": true,
    "separator_type": "centre line",
    "barrier_type": null,
    "physical_width_m": null,
    "painted_hatching_width_m": null,
    "one_way_evidence": false
  },
  "candidate_codes": [
    {"cat_id": 11, "category": "Centre line", "support": ["single centre line separates directions"]}
  ],
  "validation_checks": ["separator between opposing flows identified", "physical vs painted separator resolved"]
}
```
