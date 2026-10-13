# Tool Selection

Select tools based on whether the task needs defensible measurement or only visual categorization.

## Decision Rules

| Situation | Select | Reason |
| --- | --- | --- |
| User provides exact `code` or `label` | Router only | Normalizes Cat ID and trace. |
| User provides `width_m`, `distance_from_road_m`, or `barrier_present` | Router only | Measurement/category evidence is already structured. |
| Boundary is visible but no measurement exists | `$panoramic-road-safety-describer` plus visual estimate | Useful for pilot coding, but mark confidence lower. |
| Lane/shoulder/sidewalk boundary must be measured | `$projection-dataflow-router` then geometry helper or `$pointcloud-multistep-processor` | 2D boundary evidence must be tied to 3D/LAS to compute width or offset. |
| Paved shoulder may be very narrow | Zoomed road-edge crop plus visual review | Full panorama and LAS bins can miss thin paved strips beside the edge line. |
| Side is unclear | Adjacent-frame or direction-resolution review | Driver/passenger side errors change the attribute being coded. |
| Sidewalk vs shoulder is ambiguous | Visual review focused on kerb, pedestrian path, continuity, and separation | Geometry alone cannot classify facility function. |
| Full panorama is the only sidewalk evidence | Generate passenger context and road-edge focus crops | Sidewalk/path pixels occupy too little of a panorama and minority classes are easily collapsed to `None`. |
| Sidewalk continuity is unclear | Inspect adjacent passenger-side crops from the coded segment | iRAP requires continuity over the full coding segment. |
| Sidewalk type is confirmed but distance bucket is unclear | Use projection/LAS measurement or a documented visual estimate | Distance classes must not be guessed from class frequency. |

## Attribute-Specific Tool Choice

- `Lane width`: use projection/geometry when available; otherwise visual estimate from seeded lane boundaries.
- `Paved shoulder - drivers side`: use side-specific visual boundary detection; always inspect a zoomed driver-side road-edge crop before accepting `None`; measure width if road edge and shoulder edge can be projected.
- `Paved shoulder - passenger side`: same as driver side, but first verify passenger side; always inspect a zoomed passenger-side road-edge crop before accepting `None`.
- `Sidewalk - passenger side`: always inspect passenger-side context and focus crops first. Use visual evidence for presence/type/barrier; use geometry only after presence is confirmed, to assign the distance/offset bucket. Inspect adjacent frames for segment continuity.

## What Not To Select

- Do not include roadside severity tools; this skill measures road/facility boundaries, not hazard-object distance.
- Do not use pointcloud measurement if the visual boundary is not identified; geometry needs a semantic boundary target.
- Do not treat a LAS `0.0m` shoulder estimate as final `None` when a zoomed crop shows a thin paved strip outside the lane edge.
- Do not use the full panorama alone to finalize passenger-side sidewalk.
- Do not use area type as a proxy for sidewalk presence.
- Do not use a kerb as evidence for Cat ID 1.
- Do not force a distance class when the facility edge or nearest driving-lane edge cannot be identified.
