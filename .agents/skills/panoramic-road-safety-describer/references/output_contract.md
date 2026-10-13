# Output Contract

Return a single JSON object with this structure.

## Required Fields

- `trace.skill`: Always `panoramic-road-safety-describer`.
- `trace.image.path`: Input image path as provided.
- `trace.image.id`: Input image identifier when available, else `null`.
- `trace.methodology`: Always `iRAP`.
- `trace.orientation`: Keep assumptions used for side interpretation.
- `trace.request`: Scope requested by user (`full`, `driver`, `passenger`, `both`, or `custom`).
- `results`: Array with one item per processed patch.

Each `results[]` item must include:

- `patch_id`: Stable patch label (for example `full`, `driver`, `passenger`, `custom_1`).
- `side`: `driver`, `passenger`, `full`, or `custom`.
- `crop_xyxy`: Patch bounds in original-image coordinates.
- `description`: Concise safety-focused natural-language description.
- `confidence`: Number from `0.0` to `1.0`.
- `notes`: Short caveats (occlusion, blur, low light). Use empty string when none.

Optional:

- `trace.irap_lookup`: Include focused manual lookup metadata when performed (`queries`, `hits_used`).

## Example

```json
{
  "trace": {
    "skill": "panoramic-road-safety-describer",
    "image": {
      "path": "data/images/example_panorama.png",
      "id": "example_panorama_001"
    },
    "methodology": "iRAP",
    "orientation": {
      "center_points": "backward",
      "passenger_side": "left",
      "driver_side": "right",
      "traffic_rule": "right-hand"
    },
    "request": {
      "scope": "both"
    }
  },
  "results": [
    {
      "patch_id": "passenger",
      "side": "passenger",
      "crop_xyxy": [0, 0, 1023, 1023],
      "description": "A rigid barrier is present with several fixed poles near the shoulder, indicating high roadside severity if run-off occurs.",
      "confidence": 0.83,
      "notes": ""
    },
    {
      "patch_id": "driver",
      "side": "driver",
      "crop_xyxy": [1024, 0, 2047, 1023],
      "description": "Roadside is relatively clear with a wider shoulder and no obvious fixed-object cluster close to the carriageway.",
      "confidence": 0.79,
      "notes": ""
    }
  ]
}
```
