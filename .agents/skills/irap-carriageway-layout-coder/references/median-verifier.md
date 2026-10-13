# Median Type Verifier

This verifier follows the iRAP manual definition: record the infrastructure
feature separating opposing traffic flows for the coded segment. Do not code a
defective or damaged safety barrier as a safety barrier. A median fence used for
traffic or pedestrian control is coded as flexible posts unless it can
withstand vehicle impact.

## Required evidence stages

1. Determine travel direction and the coded carriageway. Use lane position,
   traffic flow, arrows, signs, and adjacent frames. Record whether the vehicle
   is on the left or right carriageway and where the opposing-flow boundary lies
   in the image. If this cannot be established, require review.
2. Determine whether opposing traffic flows exist in the coded segment. A
   one-way code requires clear single-direction evidence and no opposing flow.
3. Identify the separator: safety barrier, physical median, hatching, turning
   lane, flexible posts, wide centre line, ordinary centre line, or none.
4. Decide whether the separator is impact-capable. Property fences, kerbs,
   vegetation, and damaged or sub-standard barriers must not be promoted to a
   safety-barrier class.
5. If the separator is a physical median, measure its width from the relevant
   carriageway edges. Use LAS/3D measurement when available; otherwise mark the
   width band as uncertain rather than inventing a precise width.
6. Confirm the interpretation over adjacent frames. A carriageway label should
   not change for distances shorter than 400 m unless the coded segment itself
   changes.
7. Treat one-way as a high-specificity decision: require consistent travel
   direction across adjacent frames and no visible opposing-flow carriageway.
   Do not infer one-way from a ramp, merge, exit lane, or the direction of the
   recording vehicle alone.
8. Treat central hatching as a high-specificity decision: require visible,
   continuous diagonal hatch/stripe markings spanning a central strip greater
   than 1 m. Do not code Cat 10 from a single diagonal marking, lane taper,
   merge chevron, or a generic VLM phrase without image evidence.

## iRAP mapping

| Code | Required evidence |
| --- | --- |
| 1 | Impact-capable metal safety barrier on a divided road |
| 2 | Impact-capable concrete safety barrier meeting the standard |
| 3 | Physical median at least 20 m wide |
| 4 | Physical median 10 m to less than 20 m wide |
| 5 | Physical median 5 m to less than 10 m wide |
| 6 | Physical median 1 m to less than 5 m wide |
| 7 | Physical median 0 m to less than 1 m wide |
| 8 | Continuous central turning lane on an undivided two-way road |
| 9 | Flexible posts or median fencing that would not withstand vehicle impact |
| 10 | Central hatching greater than 1 m on an undivided two-way road |
| 11 | Ordinary single/double centre line or marked central strip less than 0.3 m |
| 12 | Impact-capable motorcycle-friendly safety barrier |
| 13 | One-way road with no opposing flow |
| 14 | Wide centre line or marked central strip 0.3 m to 1 m on an undivided two-way road |
| 15 | Impact-capable wire-rope safety barrier |

## Error-prevention checks

- If `opposing_flows=true`, Cat 13 is prohibited.
- If `separator_type` is not explicitly hatching and the image trace has no
  hatch evidence, Cat 10 is prohibited.
- Review at least one adjacent frame before accepting Cat 10 or Cat 13 when
  the separator is near a junction, ramp, merge, or carriageway split.

## Structured verifier output

```json
{
  "attribute": "Median Type",
  "opposing_flows": true,
  "separator_type": "physical_median|metal_barrier|concrete_barrier|wire_rope|motorcycle_barrier|flexible_posts|hatching|turning_lane|wide_centre_line|centre_line|none|uncertain",
  "impact_capable": true,
  "median_width_m": null,
  "width_source": "projection_las|visual_estimate|not_applicable|unknown",
  "adjacent_frame_consensus": "strong|weak|none",
  "cat_id": 11,
  "confidence": 0.0,
  "review_required": false,
  "evidence": [],
  "excluded_features": [],
  "uncertainties": []
}
```

The final router must assign a Cat ID only after these fields are populated.
