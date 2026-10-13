# iRAP Visual Context Coding Rules

Source: iRAP Coding Manual Drive on Right, quick coding guide pages 95 and 98, plus the project workflow test document.

## Attributes

### Area type

Code rural/urban context from full-scene land use, frontage, buildings, kerbs, commercial/residential density, and village/town street context.

| Code | Label |
| --- | --- |
| 1 | Rural |
| 2 | Urban |

### Street lighting

Code present only when roadway-relevant lighting is visible. Require a luminaire/lamp head on roadside, median, overhead, or pedestrian-space lighting. Reject poles or wires with no visible lamps.

| Code | Label |
| --- | --- |
| 1 | Not present |
| 2 | Present |

### Service road

Code present only for a separate parallel frontage/service road serving local/property access. Reject shoulders, driveways, ramps, side streets, slip lanes, and opposing carriageways.

| Code | Label |
| --- | --- |
| 1 | Not present |
| 2 | Present |

### Delineation

Code whether the travel path is clearly guided by centre/lane/edge lines, kerbs, guideposts, reflectors, signs, road-edge contrast, or similar guidance features.

| Code | Label |
| --- | --- |
| 1 | Adequate |
| 2 | Poor |

## Output

Return concise traceable results:

```json
{
  "attribute": "Street lighting",
  "code": 2,
  "label": "Present",
  "confidence": "medium",
  "evidence": ["visible lamp heads on right side of carriageway"],
  "uncertainties": []
}
```
