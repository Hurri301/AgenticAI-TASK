---
name: irap-access-points-coder
description: Code iRAP Property access points from panorama images, adjacent-frame road-segment evidence, scene descriptions, or manual review notes. Use when the task involves counting or categorizing commercial and residential vehicle accesses for iRAP road attribute coding.
---

# iRAP Access Points Coder

Code one iRAP attribute:

1. `Property access points`

Use this skill when the task needs segment-level counting/categorization of private, residential, or commercial vehicle accesses.

Read [input contract](references/input_contract.md) before running.

## Dependency Skills

Use this repository skill when raw visual interpretation is needed:

1. `$panoramic-road-safety-describer`

This skill then applies iRAP Cat ID mappings from [cat_ids.json](references/cat_ids.json).

Read [tool selection](references/tool_selection.md) before choosing between single-frame, adjacent-frame, scene-description, or manual candidate review.
Read [intermediate outputs](references/intermediate_outputs.md) to know what candidate counts and rejection evidence must be emitted for validation.

## Workflow

1. Resolve the coded segment and adjacent frames that cover it.
2. Inspect both sides of the coded road segment.
3. Select tools using [tool selection](references/tool_selection.md).
4. Produce candidate-level intermediate evidence using [intermediate outputs](references/intermediate_outputs.md).
5. Identify vehicle entry/exit points that are not public roads.
6. Classify candidates as commercial access, residential access, or rejected.
7. When adjacent frames are available, aggregate candidate evidence across the local segment before final coding. Repeated low-green paved frontage, driveway, gate, parking-lot, or property-entry evidence across neighboring frames should recover residential access classes instead of defaulting to `None`.
8. Apply priority:
- commercial access present => `Commercial access >=1`
- otherwise residential count >=3 => `Residential access >=3`
- otherwise residential count 1-2 => `Residential access <3`
- otherwise => `None`
9. Emit Cat ID code from [cat_ids.json](references/cat_ids.json).
10. Save counted candidates, rejected candidates, frames reviewed, and sequence-window evidence for traceability.

## Command

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-access-points-coder\scripts\access_points_router.py `
  --input-json ".\.agents\skills\irap-access-points-coder\references\example_input.json" `
  --out-json "artifacts\irap_access_points\coded_results.json"
```

## Output Rules

1. Use exact Cat ID mappings from `references/cat_ids.json`.
2. Commercial access takes priority over residential count.
3. Reject public intersections, side roads, ramps, slip lanes, and service roads themselves.
4. Preserve candidate evidence and original item payload under `trace.input`.
5. Include the intermediate output block from `references/intermediate_outputs.md` when doing a full workflow.
6. Do not infer property access points from Area type alone. Divided/engineered corridors with barriers, retaining walls, or separated frontage should remain `None` unless a direct vehicle access is visible.
7. When a built frontage has a low-green paved passenger-side access zone and clear commercial/urban frontage evidence, do not default to `None`; recover `Commercial access >=1` only when the evidence indicates a direct vehicle entry/exit rather than a public side road or service road.
8. Do not code residential access from a single weak frame. Use adjacent-frame repetition or explicit driveway/gate evidence; record the candidate count window when recovering `Residential access >=3` or `Residential access <3`.

## Notes

1. Use adjacent frames where possible; single panoramas often miss access points just outside the field of view.
2. Mark low confidence when candidate entrances are partly occluded or outside the coded segment boundary.
