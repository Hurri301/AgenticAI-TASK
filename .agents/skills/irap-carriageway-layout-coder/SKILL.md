---
name: irap-carriageway-layout-coder
description: Code iRAP carriageway layout attributes from panorama images, adjacent frames, scene descriptions, and optional road-width evidence. Use when the task involves Number of lanes or Median Type coding for iRAP road attribute workflows.
---

# iRAP Carriageway Layout Coder

Code two carriageway-layout iRAP attributes:

1. `Number of lanes`
2. `Median Type`

Use this skill when the coded attribute depends on through-lane count or opposing-flow separation.

Read [input contract](references/input_contract.md) before running.

## Dependency Skills

Use these repository skills when supporting evidence is needed:

1. `$panoramic-road-safety-describer`
2. `$projection-dataflow-router` only if optional geometry cross-checking is requested

This skill then applies iRAP Cat ID mappings from [cat_ids.json](references/cat_ids.json).

Read [tool selection](references/tool_selection.md) before choosing between visual counting, adjacent-frame review, or optional geometry cross-checking.
Read [intermediate outputs](references/intermediate_outputs.md) to know what lane/median evidence must be emitted for validation.
Read [median verifier](references/median-verifier.md) for the iRAP-manual decision order and exact Median Type distinctions.

## Workflow

1. Resolve the coded road section and travel direction before interpreting any median feature.
2. Identify the recording vehicle's carriageway and the opposing-flow boundary in the panorama/adjacent frames.
3. Identify the main through carriageway and count through lanes for the coded direction only.
4. Select tools using [tool selection](references/tool_selection.md).
5. Produce lane/median intermediate evidence using [intermediate outputs](references/intermediate_outputs.md).
6. Verify opposing-flow status and classify the separator using the median verifier.
7. Measure physical-median width with LAS/3D projection when a width category is required.
8. Emit Cat ID codes from [cat_ids.json](references/cat_ids.json).
9. Save travel direction, excluded features, evidence, and uncertainties.

## Command

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-carriageway-layout-coder\scripts\carriageway_layout_router.py `
  --input-json ".\.agents\skills\irap-carriageway-layout-coder\references\example_input.json" `
  --out-json "artifacts\irap_carriageway_layout\coded_results.json"
```

## Output Rules

1. Use exact Cat ID mappings from `references/cat_ids.json`.
2. Count through lanes only; exclude turn lanes, parking lanes, shoulders, slip lanes, and short changes under about 400 m.
3. Include bus/transit lanes only when they operate as part of the main carriageway.
4. Prefer physical/barrier median evidence over painted markings when both are present.
5. Preserve original item payload under `trace.input`.
6. Include the relevant intermediate output block from `references/intermediate_outputs.md` for every coded attribute when doing a full workflow.

## Notes

1. If lane markings are unclear, use adjacent frames, lane arrows, vehicle positions, and optional road-width evidence.
2. If a median category is visually uncertain, return the best code with low confidence and list the competing categories.
3. When LAS lane-count measurement is missing or implausible, broad divided/marked carriageway evidence from the panorama should not collapse to one lane. Code at least two through lanes for the coded direction when the image shows a wide paved carriageway, strong lane/edge markings, and divided-road context.
4. For physical median/barrier coding, broad divided-road visual evidence can support a physical median even when bbox-to-LAS projection is unavailable. Keep this separate from property-access or sidewalk decisions.
5. For median barrier subtype coding, do not map all physical separators to metal barrier. If the image evidence shows a bright rigid separator with divided-road markings and a concrete-like median/barrier face, recover `Safety barrier - concrete` and keep the competing metal-barrier evidence in the trace.
6. Do not use color/texture ratios as final Median Type evidence. They may propose a region, but semantic verification and manual rules must decide the class.
7. Do not use Cat 11 as the unconditional fallback when a physical median, hatching, turning lane, flexible posts, wide centre line, or one-way evidence is present.
8. Assign Cat 13 only when adjacent frames confirm a single direction of travel and no opposing-flow carriageway; a divided road with visible opposing traffic is not one-way.
9. Assign Cat 10 only when the image or adjacent frames visibly show a continuous central hatched/striped area wider than 1 m. Lane-edge gaps, merge chevrons, isolated diagonal markings, and ordinary centre lines are not Cat 10.
10. For Cat 10 and Cat 13, record the visual span and adjacent-frame evidence in the trace. If either is missing, retain the candidate as review-required instead of promoting it.
