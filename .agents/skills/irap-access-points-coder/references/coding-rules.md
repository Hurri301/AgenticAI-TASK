# iRAP Property Access Points Coding Rules

Source: iRAP Coding Manual Drive on Right, quick coding guide page 97, plus the project workflow test document.

## Property access points

Count or categorize private/commercial/residential vehicle access points for the coded road segment. Commercial access has priority over residential count.

| Code | Label |
| --- | --- |
| 1 | Commercial access >=1 |
| 2 | Residential access >=3 |
| 3 | Residential access <3 |
| 4 | None |

## Candidate Examples

Count as candidates:

- commercial driveway or business entrance
- fuel station or parking-lot entry
- residential driveway
- garage entry
- farm/property gate or private access track

Reject as candidates:

- public side road or intersection
- ramp or slip lane
- service road as a roadway, unless counting individual property accesses from it is explicitly required
- shoulder, parking space, or lay-by with no property connection
- uncertain gaps without vehicle-access evidence

## Output

Return concise traceable results:

```json
{
  "attribute": "Property access points",
  "code": 1,
  "label": "Commercial access >=1",
  "commercial_present": true,
  "residential_count": 2,
  "evidence_frames": ["frame 1201: fuel station entry", "frame 1221: driveway"],
  "confidence": "medium",
  "uncertainties": []
}
```
