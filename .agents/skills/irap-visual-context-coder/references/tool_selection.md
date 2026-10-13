# Tool Selection

Use the lightest tool path that can produce traceable evidence.

## Decision Rules

| Situation | Select | Reason |
| --- | --- | --- |
| User provides exact `code` or `label` plus evidence | Router only | The coding decision is already made; router normalizes Cat ID and trace. |
| User provides structured scene text or manual notes | Router + text reasoning | These attributes are semantic/visual and can be validated from explicit notes. |
| User provides panorama image but no scene description | `$panoramic-road-safety-describer` | The model needs a road-scene summary before applying code rules. |
| Image is ambiguous or contains transitions | Adjacent-frame review | Area type, service road, and delineation often need context beyond one frame. |
| Street lighting poles are visible but lamps are unclear | Image review before coding | Utility poles are common false positives; require lamp/luminaire evidence. |

## Attribute-Specific Tool Choice

- `Area type`: prefer scene description or adjacent frames; use aerial/context notes if urban/rural boundary is uncertain.
- `Street lighting`: use image interpretation focused on lamp heads/luminaires; no 3D tool is needed.
- `Service road`: use adjacent-frame layout review; no pointcloud is needed unless the task asks for separation geometry.
- `Delineation`: use panorama interpretation; object detection is optional only if guideposts/signs/markers need counting.

## What Not To Select

- Do not use `$projection-dataflow-router` or `$pointcloud-multistep-processor` unless the user asks for geometric verification.
- Do not use roadside severity skills for these attributes.
