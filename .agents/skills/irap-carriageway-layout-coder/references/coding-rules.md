# iRAP Carriageway Layout Coding Rules

Source: iRAP Coding Manual Drive on Right, quick coding guide pages 94 and 95, plus the project workflow test document.

## Number of lanes

Count through traffic lanes in the coded direction only. Exclude turning lanes, short changes under about 400 m, shoulders, parking lanes, slip lanes, and extra paved area. Include bus/transit lanes only when they are part of the main carriageway.

| Code | Label |
| --- | --- |
| 1 | One |
| 2 | Two |
| 3 | Three |
| 4 | Four or more |
| 5 | Two and one |
| 6 | Three and two |

## Median Type

Classify the separator between opposing traffic streams for the coded segment.

| Code | Label |
| --- | --- |
| 1 | Safety barrier - metal |
| 2 | Safety barrier - concrete |
| 3 | Physical median width >=20m |
| 4 | Physical median width 10 to <20m |
| 5 | Physical median width 5 to <10m |
| 6 | Physical median width 1 to <5m |
| 7 | Physical median width 0 to <1m |
| 8 | Continuous central turning lane |
| 9 | Flexible posts |
| 10 | Central hatching >1m |
| 11 | Centre line |
| 12 | Safety barrier - motorcycle friendly |
| 13 | One way |
| 14 | Wide centre line 0.3m to 1m |
| 15 | Safety barrier - wire rope |

## Output

Before assigning a code, verify opposing-flow status, separator type,
impact-capability, width evidence where applicable, and adjacent-frame
consensus. Do not use a damaged/sub-standard barrier as a safety barrier. Do
not use a property fence, kerb, vegetation, or ordinary median fence as an
impact-capable barrier. If the evidence is insufficient, return
`review_required=true` and preserve the competing categories.

Return concise traceable results:

```json
{
  "attribute": "Number of lanes",
  "code": 2,
  "label": "Two",
  "confidence": "high",
  "evidence": ["two continuous through lanes in coded direction"],
  "excluded_features": ["short right-turn lane"]
}
```
