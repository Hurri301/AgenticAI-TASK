# iRAP Alignment And Visibility Coding Rules

Source: iRAP Coding Manual Drive on Right, quick coding guide pages 94 and 95, plus the project workflow test document.

## Curvature

Code horizontal road curvature for the coded segment. Prefer trajectory/GPS geometry over panorama-only judgement when available. The current project GroundTruth examples may only contain codes 1 to 3, but code 4 is valid in the manual.

| Code | Label |
| --- | --- |
| 1 | Straight or gently curving |
| 2 | Moderate |
| 3 | Sharp |
| 4 | Very sharp |

## Sight distance

Code whether the driver has adequate forward visibility for the road alignment and context. Poor cases include persistent restrictions from curve, crest, vegetation, structures, roadside features, or other non-temporary occlusions.

| Code | Label |
| --- | --- |
| 1 | Adequate |
| 2 | Poor |

## Output

Return concise traceable results:

```json
{
  "attribute": "Curvature",
  "code": 2,
  "label": "Moderate",
  "geometry_metrics": {
    "heading_change_degrees": 18.4,
    "trajectory_window_m": 100
  },
  "visual_evidence": ["visible bend continues across adjacent frames"],
  "confidence": "medium",
  "uncertainties": ["exact radius threshold not measured"]
}
```
