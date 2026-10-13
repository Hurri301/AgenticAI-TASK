---
name: irap-alignment-visibility-coder
description: Code iRAP alignment and visibility attributes from panorama images, adjacent frames, GPS/trajectory geometry, and scene descriptions. Use when the task involves Curvature or Sight distance coding for iRAP road attribute workflows.
---

# iRAP Alignment Visibility Coder

Code two alignment/visibility iRAP attributes:

1. `Curvature`
2. `Sight distance`

Use this skill when the coded attribute depends on horizontal road alignment, forward visibility, trajectory geometry, or adjacent-frame road context.

Read [input contract](references/input_contract.md) before running.

## Dependency Skills

Use these repository skills when supporting evidence is needed:

1. `$panoramic-road-safety-describer`
2. `$projection-dataflow-router` only if line-of-sight or geometric evidence is being routed through projected points

This skill then applies iRAP Cat ID mappings from [cat_ids.json](references/cat_ids.json).

Read [tool selection](references/tool_selection.md) before choosing between trajectory geometry, visual alignment review, adjacent-frame review, or projected line-of-sight evidence.
Read [intermediate outputs](references/intermediate_outputs.md) to know what geometry and visibility evidence must be emitted for validation.

## Workflow

1. Resolve image frame, coded segment, direction of travel, and available trajectory/GPS points.
2. Select tools using [tool selection](references/tool_selection.md).
3. Produce geometry/visibility intermediate evidence using [intermediate outputs](references/intermediate_outputs.md).
4. For Curvature, use trajectory/GPS heading change, fitted curve radius, or a visual alignment class.
5. Define the visual alignment region as the forward roadway in the left side crop first, using the left road edge and lane boundary to detect small persistent bends. Use the right side crop and adjacent-frame left crops as corroboration. Treat the central/lower panorama as rear/vehicle context only, and exclude the bonnet, roof/rear reflection, camera housing, and vehicle body from curvature evidence.
6. Fit the local trajectory/road centreline over a spatial window and report radius in metres; do not classify curvature from a single frame's apparent perspective distortion.
7. Reconcile the geometry and visual classes. A visual bend at a junction, roundabout, merge, or exit is not a mid-block curve unless the trajectory and adjacent frames confirm persistent road alignment.
8. Ignore roundabout/intersection-related bends when they do not represent mid-block road alignment.
9. For Sight distance, inspect the forward travel path and persistent visibility restrictions from curve, crest, vegetation, structures, or geometry.
10. Emit Cat ID codes from [cat_ids.json](references/cat_ids.json).
11. Save geometry metrics, visual evidence, and uncertainties.

## Command

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-alignment-visibility-coder\scripts\alignment_visibility_router.py `
  --input-json ".\.agents\skills\irap-alignment-visibility-coder\references\example_input.json" `
  --out-json "artifacts\irap_alignment_visibility\coded_results.json"
```

## Output Rules

1. Use exact Cat ID mappings from `references/cat_ids.json`.
2. Prefer trajectory/GPS geometry for Curvature when available.
3. Treat Sight distance as lower confidence unless evidence clearly shows adequate or poor forward visibility.
4. Preserve original item payload under `trace.input`.
5. If a project heuristic is used for curvature radius thresholds, mark `rule_source` as `project_heuristic`.
6. `visual_alignment_class` must describe the forward side-road evidence (`straight_or_gentle`, `moderate_bend`, `sharp_bend`, `very_sharp_bend`, or `junction_or_uncertain`) and must state that the rear/vehicle region was excluded. A small but persistent bend in the left crop is sufficient for Cat 2 when supported by adjacent frames or trajectory. Code Cat 1 only when the forward road remains straight/gentle in the primary left crop; do not let the central/rear view override it.
6. Include the relevant intermediate output block from `references/intermediate_outputs.md` for every coded attribute when doing a full workflow.

## Notes

1. Temporary vehicles alone should normally reduce confidence rather than decide Sight distance.
2. The project GroundTruth currently shows Curvature codes 1-3, but iRAP manual code 4 `Very sharp` is valid.
3. Do not use the back of the inspection vehicle or the lower central panorama as a road-edge detection region. Use the forward left crop as the primary road-alignment region, with the right crop and adjacent frames for corroboration. The central panorama may only provide scene continuity and cannot override a small bend visible on the left.
