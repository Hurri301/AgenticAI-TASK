# Zero-Shot iRAP 17-Attribute Visual Coding with Updated Skill Rules

You are performing a strictly zero-shot visual iRAP road-attribute coding task.

Use only visible evidence from the supplied road panorama image. Do not use ground truth, file names as labels, spreadsheets, previous predictions, comparison outputs, or any other label-bearing source. The image path is provided only for traceability:

`{image_path}`

Code all 17 iRAP attributes below. For every attribute, choose exactly one allowed Cat ID. Do not output `Unknown` or `review_required`; when the updated skill workflow requires evidence unavailable in this single panorama, choose the most defensible allowed visual category, lower confidence, and explain the limitation in `evidence_summary`.

Orientation convention:

- The road environment follows right-hand traffic unless the visible road scene clearly contradicts it.
- Passenger side is the left half of the panorama.
- Driver side is the right half of the panorama.
- Roadside severity distance and roadside severity object must be paired from the same selected side-specific hazard.

Allowed Cat IDs:

1. Area type: `1 Rural`, `2 Urban`
2. Street lighting: `1 Not present`, `2 Present`
3. Service road: `1 Not present`, `2 Present`
4. Delineation: `1 Adequate`, `2 Poor`
5. Number of lanes: `1 One`, `2 Two`, `3 Three`, `4 Four or more`, `5 Two and one`, `6 Three and two`
6. Median Type: `1 Safety barrier - metal`, `2 Safety barrier - concrete`, `3 Physical median width >=20m`, `4 Physical median width 10 to <20m`, `5 Physical median width 5 to <10m`, `6 Physical median width 1 to <5m`, `7 Physical median width 0 to <1m`, `8 Continuous central turning lane`, `9 Flexible posts`, `10 Central hatching >1m`, `11 Centre line`, `12 Safety barrier - motorcycle friendly`, `13 One way`, `14 Wide centre line 0.3m to 1m`, `15 Safety barrier - wire rope`
7. Lane width: `1 Wide >=3.25m`, `2 Medium 2.75m to <3.25m`, `3 Narrow 0m to <2.75m`
8. Paved shoulder - drivers side: `1 Wide >=2.4m`, `2 Medium 1m to <2.4m`, `3 Narrow 0m to <1m`, `4 None`
9. Paved shoulder - passenger side: `1 Wide >=2.4m`, `2 Medium 1m to <2.4m`, `3 Narrow 0m to <1m`, `4 None`
10. Sidewalk - passenger side: `1 Sidewalk with barrier`, `2 Sidewalk >=3m from road`, `3 Sidewalk 1m to <3m from road`, `4 Sidewalk 0m to <1m from road`, `5 None`, `6 Informal path >=1m`, `7 Informal path 0m to <1m`
11. Property access points: `1 Commercial access >=1`, `2 Residential access >=3`, `3 Residential access <3`, `4 None`
12. Curvature: `1 Straight or gently curving`, `2 Moderate`, `3 Sharp`, `4 Very sharp`
13. Sight distance: `1 Adequate`, `2 Poor`
14. Roadside severity - driver side distance: `1 0 to <1m`, `2 1 to <5m`, `3 5 to <10m`, `4 >=10m`
15. Roadside severity - driver side object: `10 Cliff`, `11 Tree >=10cm`, `12 Rigid sign, post or pole >=10cm`, `15 Unprotected safety barrier end`, `5 Aggressive vertical face`, `6 Upwards slope - roll over`, `8 Deep drainage ditch`, `9 Downwards slope`, `16 Low rigid object >=20cm high`, `13 Rigid structure or building`, `7 Upwards slope - no roll over`, `14 Semi-rigid structure or building`, `2 Safety barrier - concrete`, `1 Safety barrier - metal`, `4 Safety barrier - wire rope`, `3 Safety barrier - motorcycle friendly`, `17 No object`
16. Roadside severity - passenger side distance: `1 0 to <1m`, `2 1 to <5m`, `3 5 to <10m`, `4 >=10m`
17. Roadside severity - passenger side object: same Cat IDs as driver side object.

Updated carriageway and median verification rules:

- Resolve travel direction, coded carriageway, and opposing-flow boundary before interpreting the median.
- Count through lanes for the coded direction only; exclude shoulders, parking, slip lanes, turn lanes, and short lane changes.
- Do not use color or texture ratios as final Median Type evidence.
- Do not use Cat 11 as an unconditional fallback when physical median, hatching, turning-lane, flexible-post, wide-centre-line, or one-way evidence is visible.
- Cat 13 requires clear single-direction evidence and no opposing-flow carriageway; a ramp, merge, exit lane, or recording-vehicle direction alone is insufficient.
- Cat 10 requires a continuous central hatched/striped area visibly wider than 1 m; isolated diagonal markings, merge chevrons, lane tapers, and ordinary centre lines are not Cat 10.
- Safety-barrier categories require an impact-capable barrier. Do not promote kerbs, fences, vegetation, damaged barriers, or painted lines to safety barriers.
- Physical median width categories require visible width support. Do not infer width from apparent distance to trees or terrain.
- Adjacent frames and LAS are unavailable in this image-only run; where they would be required, choose the best visually supported valid category and lower confidence.

Updated width and passenger-side sidewalk rules:

- Lane width is the driving-lane width only; exclude shoulders, parking, slip lanes, sidewalks, and extra paved areas.
- For both paved shoulders, inspect the relevant road edge and do not select `None` if a visible narrow paved strip exists outside the lane edge.
- Passenger side is the left side of the panorama. Do not borrow sidewalk evidence from the driver/right side.
- For Sidewalk - passenger side, first decide whether a continuous pedestrian-use facility is visible, then distinguish formal sidewalk, informal path, shoulder, verge, driveway, parking bay, crossing, road lane, and cycle-only facility.
- A kerb alone is not a vehicle-restraint barrier. Cat 1 requires a barrier capable of restraining a vehicle from entering the pedestrian facility.
- For formal sidewalks, use the driving-lane edge to near sidewalk edge for the distance band. For informal paths, require visible pedestrian-use evidence; grass, dirt, verge, driveway, or open ground alone is not an informal path.
- Do not infer sidewalk categories from Area type, class prevalence, generic pavement appearance, color ratios, texture ratios, or object boxes alone.
- Full panorama only is available in this run; adjacent passenger crops and segment continuity cannot be checked. Lower confidence when those checks would be needed, but still emit one valid Cat ID.

Other visual coding rules:

- Street lighting requires roadway-relevant lamp heads or luminaires; utility poles and wires alone are not lighting.
- Service road means a separate parallel frontage/service road, not a shoulder, driveway, ramp, slip lane, side road, or opposing carriageway.
- Property access points require direct vehicle-entry evidence; reject public intersections, side roads, ramps, service roads, and weak single-frame impressions.
- For Curvature, ignore intersection or roundabout bends when they do not represent mid-block alignment. For Sight distance, do not mark Poor solely because of a temporary vehicle.
- If metric measurement is not directly visible, make the best visual estimate and set the relevant measurement note to `visual_estimate_no_lidar` or `visual_estimate_no_trajectory`.

Return exactly one valid JSON object with this structure:

```json
{
  "scene_summary": "brief visual summary of the road scene",
  "results": [
    {
      "attribute": "Area type",
      "cat_id": 1,
      "category": "Rural",
      "predicted_value": "Rural",
      "confidence": 0.0,
      "evidence_summary": "visible evidence supporting this code",
      "measurement_note": null
    }
  ]
}
```

Output requirements:

- Include exactly 17 `results` items, one for each attribute listed above.
- Use the exact attribute names and exact category strings from the allowed Cat IDs.
- `cat_id` must be a number or numeric string matching the selected category.
- `confidence` must be between 0 and 1.
- Keep evidence concise and visual.
- Do not include markdown fences or explanatory prose outside the JSON object.
