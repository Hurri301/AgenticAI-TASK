# Intermediate Outputs To Validate

Produce this block before the final Cat ID when doing a full workflow.

## Property Access Points

```json
{
  "attribute": "Property access points",
  "segment_review": {
    "segment_id": "optional",
    "frames_reviewed": ["frame_001", "frame_002"],
    "both_sides_checked": true
  },
  "candidate_accesses": [
    {
      "candidate_id": "access_001",
      "type": "residential",
      "frame_id": "frame_001",
      "side": "passenger",
      "evidence": "driveway connected to house",
      "counted": true
    }
  ],
  "rejected_candidates": [
    {
      "candidate_id": "reject_001",
      "type": "side_road",
      "reason": "public road intersection, not property access"
    }
  ],
  "counts": {
    "commercial_present": false,
    "residential_count": 1
  },
  "sequence_window": {
    "used": true,
    "candidate_count_window": 2,
    "window_reason": "neighboring frames show repeated direct paved property-entry candidates"
  },
  "candidate_codes": [
    {"cat_id": 3, "category": "Residential access <3", "support": ["one residential access"]}
  ],
  "validation_checks": ["public roads rejected", "commercial priority checked", "residential count traceable"]
}
```
