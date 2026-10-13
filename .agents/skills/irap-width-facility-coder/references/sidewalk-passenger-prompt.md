# Passenger-Side Sidewalk Vision Prompt

Provide the full panorama for orientation, the passenger context crop, the passenger focus crop, and adjacent passenger crops when available.

```text
Code only "Sidewalk - passenger side" from the supplied visual evidence.

Orientation:
- Right-hand traffic and the project rear-facing panorama convention apply unless the scene proves otherwise.
- Passenger side is the left side of the panorama.
- Use only that passenger-side road edge for the decision.

First decide presence/type:
1. Is there a pedestrian-use corridor on the passenger side?
2. Is it continuous over the coded segment? Use adjacent crops when provided.
3. Is it a formal purpose-built, all-weather sidewalk; an informal path with pedestrian-flow evidence; or no usable pedestrian facility?
4. Explicitly reject paved shoulder, parking bay, driveway apron, isolated crossing, verge without pedestrian-flow evidence, road lane, and cycle-only facility.

Then decide separation:
1. A kerb alone is not a physical barrier.
2. Cat ID 1 requires a barrier capable of restraining a vehicle from entering the pedestrian facility.
3. Otherwise estimate/measure from the nearest driving-lane edge to the near facility edge, including shoulder and parking width.

Class-specific verification before selecting `cat_id`:
- Cat 1: use only a formal sidewalk plus a clear vehicle-restraint barrier between
  the road and the sidewalk. A kerb, painted line, hedge, fence on a property
  boundary, or shallow drainage edge is not enough.
- Cats 2-4: require a formal, purpose-built pedestrian sidewalk. Classify the
  lateral gap from the driving-lane edge to the near sidewalk edge as >=3 m,
  1 m to <3 m, or 0 m to <1 m. Do not use the road shoulder as sidewalk width.
- Cats 6-7: require a visibly used pedestrian path that is not a formal sidewalk
  (for example a worn or compacted footpath). Classify its separation using the
  same distance bands. Dirt, grass, verge, driveway, or an untracked open area
  is not an informal path without pedestrian-flow evidence such as a continuous
  worn corridor, foot traffic alignment, or connecting destinations.
- Cat 5: use only when the passenger side has no usable pedestrian facility after
  checking the focus and adjacent crops. Do not use Cat 5 as a fallback for
  uncertainty, missing distance, or an API/vision failure; use review_required.

Required reasoning checks:
1. State the facility type and the visual evidence that distinguishes it from a
   paved shoulder, parking bay, driveway, or verge.
2. State the road-edge reference and the estimated separation band.
3. If a rare class (1, 2, 3, 6, or 7) is selected, include at least two concrete
   supporting observations and explain why Cat 5 is rejected.
4. If those checks cannot be completed from the supplied images, return
   review_required=true rather than inventing a class.

Adjacent-frame consensus challenge:
- Compare the target passenger crop with both adjacent passenger crops before
  finalizing the code. Look for the same facility continuing through the segment,
  not just a one-frame texture or shadow.
- If the target appears to be Cat 5, explicitly test whether a continuous
  informal path (Cat 6 or 7) or a formal sidewalk (Cat 2, 3, or 4) is visible in
  either adjacent crop. Keep Cat 5 only when the adjacent evidence also lacks a
  usable pedestrian facility.
- If adjacent frames disagree, prefer the facility interpretation supported by
  at least two frames and record the disagreement in `uncertainties`.
- Do not copy an adjacent-frame class blindly: the final code must still match
  the target frame's visible road-edge separation.

Allowed codes:
- 1 Sidewalk with barrier
- 2 Sidewalk >=3m from road
- 3 Sidewalk 1m to <3m from road
- 4 Sidewalk 0m to <1m from road
- 5 None
- 6 Informal path >=1m
- 7 Informal path 0m to <1m

Do not choose None merely because the full panorama is ambiguous. Do not guess class 3 or 6 when distance is missing. Return review_required=true when the crop, continuity, type, barrier, or distance evidence cannot support one class.

Return JSON only:
{
  "attribute": "Sidewalk - passenger side",
  "side": "passenger",
  "passenger_region": "left",
  "semantic_inference_source": "vlm",
  "facility_present": true,
  "facility_type": "sidewalk|informal_path|none",
  "continuous_over_segment": true,
  "barrier_present": false,
  "barrier_restrains_vehicle": false,
  "curb_only": true,
  "distance_from_road_m": 0.6,
  "distance_source": "visual_estimate|projection_las|not_applicable",
  "cat_id": 4,
  "category": "Sidewalk 0m to <1m from road",
  "confidence": 0.0,
  "review_required": false,
  "evidence": [],
  "rejected_alternatives": [],
  "uncertainties": []
}
```

Do not provide ground-truth labels, class frequencies, or prior predictions to the prediction model.
