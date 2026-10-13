# Intermediate Outputs To Validate

Produce these blocks before the final Cat ID when doing a full workflow.

## Lane width

```json
{
  "attribute": "Lane width",
  "boundary_evidence": {
    "lane_selected": "representative through lane",
    "left_boundary": "centre/lane marking",
    "right_boundary": "edge/lane marking",
    "excluded_surfaces": ["shoulder", "parking", "slip lane"]
  },
  "measurement": {
    "width_m": 3.1,
    "source": "projected boundary points",
    "projection_artifacts": []
  },
  "candidate_codes": [
    {"cat_id": 2, "category": "Medium 2.75m to <3.25m", "support": ["width_m=3.1"]}
  ],
  "validation_checks": ["traffic lane only", "shoulder excluded", "boundary source documented"]
}
```

## Paved Shoulder - Driver Side

```json
{
  "attribute": "Paved shoulder - drivers side",
  "side_resolution": {"side": "driver", "direction_verified": true},
  "boundary_evidence": {
    "lane_edge": "driver-side edge line",
    "outer_shoulder_edge": "pavement edge",
    "zoom_check": {
      "performed": true,
      "zoom_artifact": "path/to/driver_side_zoom.png",
      "very_narrow_paved_strip_visible": true
    },
    "excluded_surfaces": ["travel lane", "sidewalk", "parking bay", "gravel verge"]
  },
  "measurement": {"width_m": 1.4, "source": "visual estimate or LAS"},
  "candidate_codes": [
    {"cat_id": 2, "category": "Medium 1m to <2.4m", "support": ["width_m=1.4"]}
  ],
  "validation_checks": ["side verified", "paved strip outside lane edge verified"]
}
```

## Paved Shoulder - Passenger Side

```json
{
  "attribute": "Paved shoulder - passenger side",
  "side_resolution": {"side": "passenger", "direction_verified": true},
  "boundary_evidence": {
    "lane_edge": "passenger-side edge line",
    "outer_shoulder_edge": "pavement edge",
    "zoom_check": {
      "performed": true,
      "zoom_artifact": "path/to/passenger_side_zoom.png",
      "very_narrow_paved_strip_visible": true
    },
    "excluded_surfaces": ["travel lane", "sidewalk", "parking bay", "gravel verge"]
  },
  "measurement": {"width_m": 0.8, "source": "visual estimate or LAS"},
  "candidate_codes": [
    {"cat_id": 3, "category": "Narrow 0m to <1m", "support": ["width_m=0.8"]}
  ],
  "validation_checks": ["side verified", "zoomed road-edge check performed", "sidewalk/shoulder distinction documented"]
}
```

## Sidewalk - Passenger Side

```json
{
  "attribute": "Sidewalk - passenger side",
  "side_resolution": {
    "side": "passenger",
    "direction_verified": true,
    "panorama_region": "left",
    "passenger_context_crop": "path/to/passenger_context.png",
    "passenger_focus_crop": "path/to/passenger_focus.png",
    "crop_xyxy": [0, 0, 346, 576]
  },
  "segment_review": {
    "target_frame_checked": true,
    "adjacent_frames_checked": true,
    "continuous_over_segment": true
  },
  "facility_evidence": {
    "facility_present": true,
    "facility_type": "sidewalk",
    "purpose_built": true,
    "all_weather_surface": true,
    "continuous_usable": true,
    "barrier_present": false,
    "barrier_restrains_vehicle": false,
    "curb_only": true,
    "pedestrian_flow_evidence": false,
    "pedestrians_forced_onto_road": false,
    "distinguished_from_shoulder": true,
    "rejected_alternatives": ["paved shoulder", "driveway apron", "grass verge"]
  },
  "measurement": {
    "distance_from_road_m": 1.6,
    "source": "visual estimate or LAS",
    "reference": "nearest driving lane edge to near sidewalk edge, including shoulder/parking"
  },
  "candidate_codes": [
    {"cat_id": 3, "category": "Sidewalk 1m to <3m from road", "support": ["distance=1.6m"]}
  ],
  "validation_checks": [
    "passenger side verified",
    "passenger crops inspected",
    "segment continuity checked",
    "formal sidewalk vs informal path resolved",
    "shoulder/driveway/cycle-only alternatives rejected",
    "vehicle-restraining barrier checked",
    "distance reference documented"
  ]
}
```
