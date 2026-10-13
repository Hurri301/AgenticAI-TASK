---
name: irap-width-facility-coder
description: Code iRAP width and side-facility attributes from panorama images, side-specific visual evidence, and optional 2D-to-3D/LAS measurement. Use for Lane width, Paved shoulder driver/passenger side, and Sidewalk passenger side workflows.
---

# iRAP Width Facility Coder

Code four width/side-facility iRAP attributes:

1. `Lane width`
2. `Paved shoulder - drivers side`
3. `Paved shoulder - passenger side`
4. `Sidewalk - passenger side`

Use this skill when the attribute depends on lane/road-edge boundaries, shoulder width, sidewalk/path type, or side-specific offset from the road.

Read [input contract](references/input_contract.md) before running.

## Dependency Skills

Use these repository skills when measurement evidence is needed:

1. `$panoramic-road-safety-describer`
2. `$projection-dataflow-router`
3. `$pointcloud-multistep-processor`

This skill can also code directly from pre-measured widths/offsets and then applies Cat IDs from [cat_ids.json](references/cat_ids.json).

Read [tool selection](references/tool_selection.md) before choosing between visual-only coding, 2D-to-3D projection, pointcloud measurement, or provided measurements.
Read [intermediate outputs](references/intermediate_outputs.md) to know what boundary, measurement, and side-specific evidence must be emitted for validation.
For `Sidewalk - passenger side`, read [sidewalk passenger workflow](references/sidewalk-passenger-workflow.md) before coding.
When prompting a vision model for this attribute, use [sidewalk passenger prompt](references/sidewalk-passenger-prompt.md).

## Workflow

1. Resolve coded direction and driver/passenger side convention.
2. Identify lane edge, road edge, shoulder edge, kerb, sidewalk/path edge, and any physical barrier.
3. Select tools using [tool selection](references/tool_selection.md).
4. Create or inspect the required side-specific crop:
- For paved shoulder attributes, use a zoomed road-edge crop for the requested side.
- For `Sidewalk - passenger side`, always use passenger-side context and road-edge focus crops. For this project's rear-facing panorama convention under right-hand traffic, passenger side is the left side of the image.
5. Produce boundary/measurement intermediate evidence using [intermediate outputs](references/intermediate_outputs.md).
6. Project boundary evidence to LAS and measure lateral width/offset when available.
7. For `Sidewalk - passenger side`, use a two-stage decision before assigning a Cat ID:
- Stage A: confirm a continuous passenger-side pedestrian facility and distinguish formal sidewalk, informal path, shoulder, verge, driveway, cycle-only facility, and no facility.
- Stage B: if present, check a vehicle-restraining physical barrier first; otherwise measure/estimate distance from the nearest driving-lane edge to the near edge of the facility, including shoulder or parking width.
- Set `semantic_inference_source` from a sidewalk-specific VLM, segmentation model, combined VLM/segmentation stage, or manual review. Do not use color ratios, texture ratios, generic pavement masks, or GroundingDINO boxes alone as final semantic evidence.
8. Convert measurements to iRAP width categories:
- Lane width: `>=3.25m`, `2.75m to <3.25m`, `0m to <2.75m`.
- Paved shoulder: `>=2.4m`, `1m to <2.4m`, `0m to <1m`, `None`.
- Sidewalk passenger side: barrier/formal sidewalk/informal path plus distance bucket.
9. If LAS gives `0.0m` but zoomed visual evidence shows a paved strip outside the lane edge, code paved shoulder as `Narrow 0m to <1m` and mark `rule_source` as visual zoom override.
10. Emit Cat ID codes from [cat_ids.json](references/cat_ids.json).
11. Save measurement source, evidence, crop artifacts, rejected alternatives, and uncertainties.

## Passenger-Side Sidewalk Crop

Generate a passenger context crop and a tighter road-edge crop when only a full panorama is available:

```powershell
python .\.agents\skills\irap-width-facility-coder\scripts\prepare_sidewalk_passenger_crops.py `
  --images "data\images\example_panorama.png" `
  --outdir "artifacts\sidewalk_passenger_crops"
```

Pass both crops to the visual agent. Use the context crop to verify the side and relation to the carriageway; use the focus crop to inspect surface, kerb, barrier, separation, and whether the candidate is actually a sidewalk/path. Use adjacent-frame crops to establish segment continuity.

## Command

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-width-facility-coder\scripts\width_facility_router.py `
  --input-json ".\.agents\skills\irap-width-facility-coder\references\example_input.json" `
  --out-json "artifacts\irap_width_facility\coded_results.json"
```

## Output Rules

1. Use exact Cat ID mappings from `references/cat_ids.json`.
2. Do not include shoulder, parking, slip-lane, or extra paved area in Lane width.
3. Do not treat sidewalks, parking bays, gravel/grass verges, or extra lanes as paved shoulders.
4. For Sidewalk passenger side, barrier category has priority when a physical barrier separates users from traffic.
5. Preserve original item payload under `trace.input`.
6. Include the relevant intermediate output block from `references/intermediate_outputs.md` for every coded attribute when doing a full workflow.
7. For paved shoulder attributes, do not accept a `None` code until a zoomed road-edge check has looked for very narrow paved strips.
8. Do not finalize `Sidewalk - passenger side` from the full panorama alone. Record passenger crop bounds and artifact paths.
9. Do not infer sidewalk/path from Area type. Require passenger-side pedestrian-facility evidence.
10. Accept `None` only after passenger crop and segment-continuity review reject both formal sidewalk and informal path.
11. Do not treat paved shoulder, road lane, parking bay, driveway apron, isolated crossing, grass/gravel verge without pedestrian-flow evidence, or cycle-only facility as sidewalk.
12. A kerb alone is not a physical barrier. Use Cat ID 1 only when the barrier can restrain a vehicle from entering the pedestrian facility.
13. Do not default missing distance to Cat ID 3 or 6. Estimate/measure it, lower confidence if visual-only, or route to review.
14. Evaluate with per-class precision, recall, F1, and Macro-F1. Accuracy alone is insufficient because Cat ID 5 is dominant.
15. Treat `review_required=true` as unresolved, not as a prediction. Do not force a Cat ID to complete a batch.
16. Do not promote a revised workflow when blind evaluation collapses Cat ID 5 recall or produces broad false-positive classes, even if minority detections increase.

## Notes

1. If a boundary is inferred visually rather than measured, return lower confidence.
2. Do not use this skill for roadside severity object or distance coding.
