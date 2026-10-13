You are coding iRAP Curvature from a target panoramic road image and adjacent frames.

Use the forward roadway only. The LEFT side crop is the primary curvature
region: carefully follow its road edge, lane boundary, and road path extending
away from the camera. Look for small persistent bends, not only obvious sharp
curves. Use the right side crop and the left side of adjacent frames as
corroboration. The central/lower part of the panorama is rear/vehicle context,
not the coding region: ignore the bonnet, roof/rear reflection, camera housing,
vehicle body, and apparent bends caused only by panorama stitching.

If the left forward crop shows a small persistent bend and adjacent frames or
trajectory support it, code Cat 2 (moderate curve), even if the central
panorama appears straight or distorted. Code Cat 1 only when the left forward
road remains straight or gently curving. Do not infer curvature from the
vehicle/rear region.

Use the supplied trajectory context as a geometric cross-check. A persistent
mid-block bend supported by both trajectory and adjacent frames is Curvature.
A roundabout, junction, merge, exit, or temporary lane shift is not a
curvature code unless the curve continues as the road's natural alignment.

iRAP categories: 1 = straight/gentle (radius >=800 m); 2 = moderate
(400-800 m); 3 = sharp (200-400 m); 4 = very sharp (<200 m).

Return exactly one JSON object with:
cat_id (1-4), confidence (0-1), visual_alignment_class
(straight_or_gentle|moderate_bend|sharp_bend|very_sharp_bend|junction_or_uncertain),
radius_m, heading_change_deg, forward_side_regions_used, rear_vehicle_region_excluded,
midblock_alignment, evidence, and uncertainties.

Do not use the rear/vehicle area as a road-edge or curvature detection point.
Do not infer a bend from the center of the equirectangular panorama, and do
not dismiss a small bend visible in the left forward crop because the center
looks straight.
If visual alignment and trajectory disagree, choose the conservative class,
lower confidence, and explain the disagreement.
