---
name: panoramic-road-safety-describer
description: Describe vehicle-mounted panoramic road images with concise safety-focused natural language grounded in iRAP methodology, and return traceable JSON per image or image patch. Use when a task asks for road-scene safety description, iRAP-aligned interpretation, or separate driver/passenger-side assessment with side-aware cropping.
---

# Panoramic Road Safety Describer

Use this skill to produce concise, iRAP-aligned safety descriptions for full panoramas or selected patches, then return JSON with image and patch traceability.
Read [output contract](references/output_contract.md) before returning results.
Use [iRAP Coding Manual](references/iRAP_Coding_Manual_Drive_on_Right.pdf) as the normative reference when coding decisions need confirmation.

## iRAP Grounding

1. Treat the uploaded manual as the source of truth for iRAP terminology and coding boundaries.
2. Query the manual only for the attributes needed by the current request (do not load broad unrelated sections).
3. Use `scripts/irap_pdf_lookup.py` to retrieve snippets from the PDF whenever iRAP interpretation is requested or uncertain.

Example lookup:

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\panoramic-road-safety-describer\scripts\irap_pdf_lookup.py `
  --query "roadside severity driver side object" `
  --query "distance roadside object" `
  --max-hits 3
```

## Orientation Model

Apply these assumptions unless the user explicitly overrides them:
1. The camera is mounted on a vehicle and the center of the panorama points backward.
2. Passenger side (right-hand traffic) is on the left side of the image.
3. Driver side is on the right side of the image.

## Workflow

1. Resolve scope.
- Detect whether the request targets `full`, `driver`, `passenger`, `both`, or custom patches.
- If scope is not stated, default to `full`.

2. Ground in iRAP context when needed.
- If the request mentions iRAP coding, roadside severity, coding disputes, or policy interpretation, run a focused PDF lookup first.
- Carry key manual terms into the description (for example `roadside object`, `distance`, `barrier`, `aggressive vertical face`) when they apply.

3. Resolve patches.
- If user-provided `crop_xyxy` is present, use it as-is.
- If `passenger` is requested without coordinates, use left half: `[0, 0, floor(width/2)-1, height-1]`.
- If `driver` is requested without coordinates, use right half: `[floor(width/2), 0, width-1, height-1]`.
- If `both` is requested, create two independent patch entries (`passenger` and `driver`).

4. Describe each patch for safety.
- Focus on crash-relevant elements only: fixed objects near the carriageway, barriers, slopes/ditches, shoulder quality, lane separation, intersections/access points, parked vehicles, vulnerable road users, work zones, and visibility constraints.
- Keep each description concise (1 to 3 sentences).
- Avoid unrelated details that do not change safety interpretation.
- Prefer iRAP-compatible wording over generic prose when relevant.

5. Return JSON only.
- Keep one result item per requested patch.
- Preserve traceability for image and patch source fields.
- If certainty is limited (blur, occlusion, low light), record this in `notes` and reduce `confidence`.

## Output Rules

1. Return valid JSON only (no surrounding prose).
2. Keep descriptions concise and safety-specific.
3. Keep passenger and driver descriptions independent unless the user requests aggregation.
4. Keep `crop_xyxy` in original-image coordinates for every patch.
5. Keep orientation assumptions explicit under `trace.orientation`.
6. If no meaningful safety cue is visible, state that clearly instead of inventing hazards.
7. Set `trace.methodology` to `iRAP`.
