---
name: irap-visual-context-coder
description: Code iRAP visual/context road attributes from panorama images, scene descriptions, or manual visual evidence. Use when a task involves Area type, Street lighting, Service road, or Delineation coding for iRAP road attribute workflows, excluding roadside severity object and distance workflows.
---

# iRAP Visual Context Coder

Code four visual/context iRAP attributes:

1. `Area type`
2. `Street lighting`
3. `Service road`
4. `Delineation`

Use this skill when these attributes can be decided from panorama evidence, scene descriptions, adjacent-frame context, or manual review notes.

Read [input contract](references/input_contract.md) before running.

## Dependency Skills

Use these repository skills when raw panorama interpretation is needed:

1. `$panoramic-road-safety-describer`

This skill then applies iRAP Cat ID mappings from [cat_ids.json](references/cat_ids.json).

Read [tool selection](references/tool_selection.md) before choosing whether to use image interpretation, provided scene text, or manual evidence.
Read [intermediate outputs](references/intermediate_outputs.md) to know what evidence must be produced for validation before final coding.

## Workflow

1. Resolve coded road section, travel direction, and available image/description evidence.
2. Describe the scene context and visible features relevant to the inspected carriageway. For Street lighting, inspect the complete visible roadway corridor in three ranges: near, medium and far distance. Small or distant lamps may count when their lamp head/luminaire is visibly attached to a roadway-relevant pole, or when repeated aligned luminaires provide consistent evidence. Do not impose an arbitrary short-distance cutoff.
3. Select the lightest sufficient tool path using [tool selection](references/tool_selection.md).
4. Produce attribute-level intermediate evidence using [intermediate outputs](references/intermediate_outputs.md).
5. Apply attribute gates:
- Area type: built-up urban frontage/context vs rural context.
- Street lighting: visible roadway-relevant lamp heads or luminaires.
- Service road: separate parallel frontage/service road, not a shoulder/ramp/driveway.
- Delineation: adequate visual guidance from lines, kerbs, signs, posts, reflectors, or road-edge contrast.
6. Emit Cat ID codes from [cat_ids.json](references/cat_ids.json).
7. Save traceable evidence and uncertainties per attribute.

## Optional streetlight-detector route

For Street lighting, the repository includes an experimental adapter for the
`cpnlab/YOLOR-Streetlights` checkpoint (`scripts/run_yolov11_streetlight_experiment.py`).
The checkpoint is a YOLOv11x detector with a custom `streetlight` class. Use it
as an evidence generator, not as the final iRAP coder.

1. Run inference on the full panorama and overlapping horizontal tiles to reduce
   missed small luminaires in equirectangular images.
2. Keep only the custom `streetlight` class and suppress duplicate boxes across
   overlapping tiles.
3. Apply the roadway-luminaire gate: accept a detection only when a lamp head or
   luminaire is visible and it is relevant to the coded carriageway. Reject bare
   utility poles, wires, house lights and unrelated lamps.
4. Use adjacent-frame persistence as supporting evidence, not as an automatic
   replacement for frame-level evidence.
5. Convert the verified evidence to the binary iRAP code: `1 = Not present`,
   `2 = Present`, with confidence and detection trace retained.
   For distance-aware review, consider a lamp visible at near, medium or far
   range, but code `Present` only when the evidence supports illumination of
   the coded road corridor and is not merely a utility pole, wire, house light
   or unrelated background lamp.
6. Tune thresholds on a development subset only. Report the untouched evaluation
   result separately and compare it with the existing visual-context baseline.

The checkpoint was trained on campus streetlight imagery, so Portuguese road
panoramas, rural scenes, equirectangular distortion and small distant lamps are
domain-shift risks. Do not promote this route to the primary workflow unless its
precision and recall are verified on representative local examples.

## Command

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-visual-context-coder\scripts\visual_context_router.py `
  --input-json ".\.agents\skills\irap-visual-context-coder\references\example_input.json" `
  --out-json "artifacts\irap_visual_context\coded_results.json"
```

## Output Rules

1. Use exact Cat ID mappings from `references/cat_ids.json`.
2. Keep one result per requested attribute.
3. Preserve evidence and original item payload under `trace.input`.
4. Mark low confidence when image evidence is ambiguous or inferred from text only.
5. Do not code roadside severity object or distance attributes here.
6. Include the relevant intermediate output block from `references/intermediate_outputs.md` for every coded attribute when doing a full workflow.

## Notes

1. Reject poles/wires for Street lighting unless a lamp head/luminaire is visible.
2. Reject shoulders, driveways, ramps, slip lanes, side roads, and opposing carriageways for Service road.
3. For Delineation, judge the coded travel path, not unrelated markings outside the inspected carriageway.
