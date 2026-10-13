# Tool Selection

Property access points are sequence-sensitive. Select tools that preserve candidate-level evidence.

## Decision Rules

| Situation | Select | Reason |
| --- | --- | --- |
| User provides exact `code` or `label` | Router only | Normalizes Cat ID and trace. |
| User provides `commercial_present` and `residential_count` | Router only | Priority logic can be applied directly. |
| User provides candidate list | Router only, with candidate validation | Candidate type and rejection reasons are already inspectable. |
| Single panorama is available | `$panoramic-road-safety-describer`, then mark limited context | A single frame may miss accesses outside the view. |
| Adjacent frames are available | Adjacent-frame visual review | This is preferred because access points are segment-level. |
| Public road vs private access is unclear | Manual/visual review of layout context | Misclassifying public side roads is the main failure mode. |
| Residential access is weak in a single frame | Adjacent-frame candidate aggregation | Repeated driveway/frontage candidates across a local sequence are stronger than any one panorama. |

## What To Select For Evidence

- Use candidate tables rather than only a final count.
- Record rejected features whenever they resemble accesses.
- Use commercial/residential priority after candidates are classified.
- For automated batch runs, preserve the sequence-window candidate count used to recover residential access classes.

## What Not To Select

- Do not use projection or pointcloud by default; access coding is layout/semantic, not distance measurement.
- Do not count service roads themselves as property access points.
