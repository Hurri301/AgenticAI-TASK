---
name: irap-roadside-groundingdino
description: Detect iRAP roadside-severity object categories from panoramic road images or from natural-language roadside description JSON, and return traceable JSON with iRAP category mappings plus GroundingDINO-ready labels/prompts. Use when a user asks for driver-side, passenger-side, or both-side roadside object coding aligned to iRAP "roadside severity - object", including text-to-prompt preparation before GroundingDINO inference.
---

# iRAP Roadside GroundingDINO

## Overview

Use this skill in one of two input modes:

1. `image` mode
- Inspect panorama side(s), select relevant roadside objects, run GroundingDINO, and return bounding boxes.

2. `description_json` mode
- Read natural-language roadside descriptions, map text evidence to iRAP categories, and generate a GroundingDINO prompt in `label . label . label` format (1-2 word labels).

Read [iRAP categories and prompt mapping](references/irap_categories.md) before running either mode.
For passenger-side object coding, also read [passenger-side object workflow](references/passenger_side_object_workflow.md).

## Workflow

1. Resolve input mode.
- If user provides image path(s), run `image` mode.
- If user provides JSON natural-language description(s), run `description_json` mode.

2. Resolve target side.
If the user does not explicitly request `driver` or `passenger`, process `both`.

3. Generate candidate objects for GroundingDINO.

For `image` mode:
- Inspect panorama(s) for each requested side and draft object hints as 2-4 word descriptions, each mapped to an iRAP category (for example: `tree trunk`, `metal guardrail`, `retaining wall`).

For `description_json` mode:
- Run `scripts/irap_descriptions_to_hints.py`.
- Map explicitly mentioned roadside elements to iRAP categories.
- Build GroundingDINO prompt labels in 1-2 words, separated with `.` (for example: `pole . tree . signpost`).

You must describe objects as simply as possible. Use only one word if possible (e.g. tree, guardrail, wall, pole).
Different objects can be mapped to the same iRAP category (for example: 'sign', 'pole' may be detected individually but will map to the same iRAP category later). 
For this dataset, passenger-side object detection is the left forward crop (`[1, 260, 600, 920]`): the roadside beyond the left road edge in the vehicle's travel direction. Do not include the center/bonnet, right-side roadside, median, or opposite carriageway. Driver-side detection uses the right crop (`[1481, 260, 2048, 920]`) and is out of scope when the task requests passenger side only.

4. Save hints JSON (recommended).
Use `references/trace_template.json` as template and write only the categories/descriptions that make sense for the scene for traceability.

5. Run detector script for `image` mode.
Use `scripts/irap_groundingdino_bbox.py` with one or many images. The script crops side-specific regions before inference:
- Passenger crop: `[1, 260, 600, 920]`
- Driver crop: `[1481, 260, 2048, 920]`
The prompt for groundingdino should have the object descriptions generated in step 2, separated with `.`. (e.g. ` tree . guardrail . pole `).
For passenger-only runs, generate hints and detections only for the passenger crop and preserve the left-side crop coordinates in the trace.
Save groundingdino visualization of bounding boxes in the output folder for traceability.

6. Return result JSON.
- `description_json` mode: return side-specific iRAP elements and `groundingdino_prompt`.
- `image` mode: return image name, side, iRAP category, simple description, and `bbox_xyxy` in original image coordinates.

## Batch Reliability Guidance

1. For roadside object coding, output all plausible barrier, rigid-object, tree/pole, and terrain candidates with confidence and bbox coordinates; do not collapse competing objects inside the detector step.
2. Terrain prompts such as `steep slope`, `earth embankment`, and `drainage ditch` often fire on the same pixels as barriers, walls, and vegetation. Mark them as candidates, but let the severity coder decide with projection, distance, bbox shape, and risk hierarchy.
3. Guardrail detections should be long, low, road-edge ribbons. Be cautious with barrier labels on vehicle bodywork, retaining walls, building facades, or very low panorama artifacts.
4. When `Safety barrier - metal` and `Safety barrier - concrete` overlap with similar confidence, keep both candidates. The downstream coder may prefer metal for guardrail-like bboxes when the confidence gap is small.
5. In urban/commercial frames, keep separate `tree`, `pole`, `signpost`, `wall`, and `building` candidates even when a barrier prompt also fires. These discrete candidates are important for the severity coder because close rigid objects can outrank a nearby barrier in the iRAP risk hierarchy.
6. Treat motorcycle-friendly barrier detections as broad barrier hypotheses, not final labels. Keep them in the JSON, but preserve competing true-barrier and discrete-object candidates so the downstream coder can resolve false positives.
7. Treat `barrier end` as a candidate that needs downstream confirmation, not a final high-risk answer. In batch runs, ordinary guardrail ends, vegetation edges, or crop borders may trigger this prompt; preserve competing tree, pole, wall, and slope detections in the same side crop.

## Commands

Description JSON to iRAP categories and GroundingDINO prompt:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-groundingdino\scripts\irap_descriptions_to_hints.py `
  --input-json ".\.agents\skills\irap-roadside-groundingdino\references\description_input_template.json" `
  --side passenger `
  --out-json "artifacts\irap_description_mapping.json" `
  --out-hints-json "artifacts\irap_description_hints.json"
```

Single image, both sides, default prompts:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-groundingdino\scripts\irap_groundingdino_bbox.py `
  --images "data/images/example_panorama.png" `
  --side both `
  --out-json "artifacts\irap_detection.json"
```

Single image, passenger side, custom hints:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-groundingdino\scripts\irap_groundingdino_bbox.py `
  --images "data/images/example_panorama.png" `
  --side passenger `
  --hints-json ".\.agents\skills\irap-roadside-groundingdino\references\trace_template.json" `
  --out-json "artifacts\irap_detection_passenger.json"
```

Single image, prompts derived from description JSON:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-groundingdino\scripts\irap_groundingdino_bbox.py `
  --images "data/images/example_panorama.png" `
  --side passenger `
  --hints-json "artifacts\irap_description_hints.json" `
  --out-json "artifacts\irap_detection_from_description_hints.json"
```

Many images:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-groundingdino\scripts\irap_groundingdino_bbox.py `
  --images "data/images/panorama_001.png" "data/images/panorama_002.png" `
  --side driver `
  --out-json "artifacts\irap_detection_driver_batch.json"
```

## Output Rules

1. Keep iRAP category names exactly as defined in `references/irap_categories.md`.
2. Keep object descriptions short (2-4 words) and concrete.
3. For generated GroundingDINO labels, use 1-2 words and join prompts with ` . `.
4. Preserve `bbox_xyxy` on original image coordinates in `image` mode.
5. If no eligible object is found on a side, return `No object` for that side.

## Notes

1. Use conservative interpretation for slope/ditch/cliff classes because monocular images can be ambiguous.
2. In `description_json` mode, treat negated statements (for example `no visible barrier`) as absence evidence, not object presence.
