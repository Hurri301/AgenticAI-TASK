# Frozen Common Prompt v1: Zero-Shot iRAP 17-Attribute Visual Coding

You are performing a strictly zero-shot visual iRAP road-attribute coding task.

Use only visible evidence from the supplied road panorama image. Do not use ground truth, file names as labels, spreadsheets, previous predictions, comparison outputs, or any other label-bearing source. The image path is provided only for traceability:

`{image_path}`

Code all 17 iRAP attributes below. For every attribute, choose exactly one allowed Cat ID. Do not output `Unknown`. If metric measurement is not directly visible, make the best visual estimate from the image, lower the confidence, and set the relevant measurement note to `visual_estimate_no_lidar` or `visual_estimate_no_trajectory`.

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

Median Type decision protocol:

- First identify the recording vehicle's travel direction and the coded carriageway.
- Confirm whether an opposing-flow carriageway is visible. A road is Cat 13 (One way) only when no opposing flow is visible and adjacent scene context supports one-way travel. A ramp, merge, exit lane, or vehicle direction alone is not sufficient.
- Code Cat 1, 2, 12, or 15 only when a continuous impact-capable barrier subtype is visibly supported. Do not confuse a painted line, kerb, fence, or vegetation with a safety barrier.
- Code Cats 3-7 only when two separate carriageways and a physical median are visibly present. Use the width band only when the relevant median width is visually supported; do not infer width from the apparent distance to trees or terrain.
- Code Cat 10 only when continuous diagonal/ladder hatching visibly occupies a central strip wider than 1 m on an undivided two-way road. A single diagonal marking, merge chevron, lane taper, or bright road edge is not hatching.
- Code Cat 11 for an ordinary single/double centre line or marked central strip below 0.3 m. Code Cat 14 only when a visibly wide centre line/strip is 0.3-1 m. Code Cat 8 only for a continuous central turning lane. Code Cat 9 only for flexible posts or non-impact-capable median fencing.
- Inspect adjacent frames mentally from the visible road segment: retain a separator class only when it is consistent across the segment. If the frame is ambiguous, choose the conservative visually supported class, lower confidence, and explain the competing class in evidence_summary.

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
