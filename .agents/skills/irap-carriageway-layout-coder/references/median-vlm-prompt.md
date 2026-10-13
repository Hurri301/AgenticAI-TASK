Code only `Median Type` for the supplied road panorama.

## Required travel-direction stage

Before classifying the median, identify the coded travel direction and the
carriageway used by the recording vehicle. Use lane position, vehicle motion,
lane arrows, signs, road geometry, and adjacent frames. State whether the
recording vehicle is travelling on the left or right carriageway of a divided
road, and identify which side of the image contains the opposing-flow boundary.
Do not infer the median from the nearest road edge or from the passenger/driver
side alone. If direction is ambiguous, set `review_required=true`.

For an undivided road, identify the centre of the two-way carriageway and the
opposing traffic stream before deciding whether the marking is a centre line,
wide centre line, hatching, or turning lane. For a divided road, inspect the
separator between the coded carriageway and the opposing carriageway; do not
mistake a same-direction lane line, shoulder, service road, or property edge
for the median.

The median type is the infrastructure feature separating opposing traffic flows
for the coded segment. First decide whether opposing flows exist. A one-way
code requires clear evidence of one direction and no opposing flow.

Apply these iRAP categories exactly:
1 metal safety barrier; 2 concrete safety barrier; 3 physical median >=20 m;
4 physical median 10 to <20 m; 5 physical median 5 to <10 m; 6 physical
median 1 to <5 m; 7 physical median 0 to <1 m; 8 continuous central turning
lane; 9 flexible posts/median fence not designed to withstand vehicle impact;
10 central hatching >1 m; 11 ordinary centre line or marked central strip
<0.3 m; 12 motorcycle-friendly safety barrier; 13 one way; 14 wide centre line
0.3 to 1 m; 15 wire-rope safety barrier.

Do not code defective, damaged, sub-standard, or broken barriers as safety
barriers. Do not treat kerbs, property fences, vegetation, or ordinary median
fences as impact-capable safety barriers. Use adjacent frames to confirm the
coded segment. If a width or subtype cannot be supported, set review_required
true rather than guessing.

When a physical median is visible, also return normalized 2D boxes in the full
panorama coordinates as `[x1,y1,x2,y2]` with values from 0 to 1:
`coded_carriageway_bbox`, `opposing_carriageway_bbox`, and `median_bbox`. Leave
these fields null when the boundary cannot be identified reliably.

Return JSON only with: travel_direction, coded_carriageway, opposing_flow_side,
opposing_flows, separator_type, impact_capable,
median_width_m, width_source, adjacent_frame_consensus, cat_id, confidence,
review_required, evidence, excluded_features, uncertainties.
