# iRAP Width And Side-Facility Coding Rules

Source: iRAP Coding Manual Drive on Right, quick coding guide pages 94, 97, and 99, plus the project workflow test document.

## Lane width

Measure or estimate the traffic lane width. Do not include shoulders, parking, slip lanes, or extra paved area.

| Code | Label |
| --- | --- |
| 1 | Wide >=3.25m |
| 2 | Medium 2.75m to <3.25m |
| 3 | Narrow 0m to <2.75m |

## Paved shoulder - drivers side

Code the paved shoulder outside the driver-side lane edge.
Before accepting `None`, inspect a zoomed driver-side road-edge crop for very narrow paved strips. If a paved strip is visible but too narrow or missed by geometry, code `Narrow 0m to <1m`.

| Code | Label |
| --- | --- |
| 1 | Wide >=2.4m |
| 2 | Medium 1m to <2.4m |
| 3 | Narrow 0m to <1m |
| 4 | None |

## Paved shoulder - passenger side

Code the paved shoulder outside the passenger-side lane edge.
Before accepting `None`, inspect a zoomed passenger-side road-edge crop for very narrow paved strips. If a paved strip is visible but too narrow or missed by geometry, code `Narrow 0m to <1m`.

| Code | Label |
| --- | --- |
| 1 | Wide >=2.4m |
| 2 | Medium 1m to <2.4m |
| 3 | Narrow 0m to <1m |
| 4 | None |

## Sidewalk - passenger side

Code only the pedestrian facility on the passenger side. For this project's rear-facing panorama convention under right-hand traffic, passenger side is the left side of the panorama. Inspect a passenger-side context crop and a tighter road-edge crop before deciding.

### Presence gate

1. Confirm the candidate is continuous over the coded segment. Use adjacent frames when one image cannot establish continuity.
2. A formal sidewalk is purpose-built for pedestrians, has an all-weather surface (sealed or unsealed), and provides reliable walkable space.
3. An informal path requires visible pedestrian-flow evidence where no purpose-built sidewalk exists. A partly blocked sidewalk can be coded as an informal path when pedestrians are not forced into the roadway.
4. Code `None` when no continuous formal sidewalk or informal path is confirmed, pedestrian access is impossible/restricted, the facility is insufficient for demand, or pedestrians must use the roadway, shoulder, motorcycle facility, or on-road cycle facility.
5. Do not count an isolated pedestrian crossing or a facility that is not continuous over the segment.

### Type and distance gate

1. Distinguish the candidate from paved shoulder, parking bay, driveway apron, road lane, verge, cycle-only facility, and unrelated paved frontage.
2. If a vehicle-restraining physical barrier separates the pedestrian facility from the nearest driving lane, use Cat ID 1. A kerb alone is not a physical barrier.
3. Otherwise measure from the edge line of the nearest driving lane to the near edge of the sidewalk/path. Include any paved shoulder and vehicle-parking width in this separation.
4. For a shared off-road bicycle/pedestrian path, record it as sidewalk as well as bicycle facility when applicable.

| Code | Label |
| --- | --- |
| 1 | Sidewalk with barrier |
| 2 | Sidewalk >=3m from road |
| 3 | Sidewalk 1m to <3m from road |
| 4 | Sidewalk 0m to <1m from road |
| 5 | None |
| 6 | Informal path >=1m |
| 7 | Informal path 0m to <1m |

Never assign Cat ID 3 or 6 as a fallback when distance is missing. Obtain a visual estimate, use 2D-to-3D measurement, or mark the item for review.

## Output

Return concise traceable results:

```json
{
  "attribute": "Paved shoulder - passenger side",
  "side": "passenger",
  "code": 3,
  "label": "Narrow 0m to <1m",
  "measured_meters": 0.8,
  "confidence": "medium",
  "evidence": ["paved strip outside lane edge is visible"],
  "uncertainties": ["outer shoulder boundary partially occluded"]
}
```
