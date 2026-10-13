# Intermediate Outputs To Validate

Produce these blocks before the final Cat ID when doing a full workflow.

## Curvature

```json
{
  "attribute": "Curvature",
  "trajectory_evidence": {
    "trajectory_points_used": 25,
    "window_m": 100,
    "heading_change_degrees": 18.4,
    "radius_m": 520,
    "visual_alignment_class": "moderate_bend",
    "forward_side_regions": ["left_road_edge", "right_road_edge"],
    "rear_vehicle_region_excluded": true,
    "geometry_source": "GPS trajectory"
  },
  "visual_sanity_check": {
    "visible_alignment": "moderate bend",
    "intersection_or_roundabout_bend": false,
    "trajectory_image_match": true
  },
  "candidate_codes": [
    {"cat_id": 2, "category": "Moderate", "support": ["radius/heading evidence", "visual bend"]}
  ],
  "validation_checks": ["mid-block alignment only", "trajectory/image match checked", "rule source stated"]
}
```

## Sight Distance

```json
{
  "attribute": "Sight distance",
  "forward_visibility_evidence": {
    "forward_path_identified": true,
    "visible_distance_estimate_m": 120,
    "persistent_restrictions": ["curve"],
    "temporary_occlusions": [],
    "crest_or_vertical_obstruction": false,
    "vegetation_or_structure_obstruction": false
  },
  "candidate_codes": [
    {"cat_id": 1, "category": "Adequate", "support": ["road visible beyond curve"]}
  ],
  "validation_checks": ["forward path visible", "temporary occlusions separated", "poor-code reason explicit if used"]
}
```
