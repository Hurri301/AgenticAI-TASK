# Strengthened Workflow Pilot - 16_N243 Frame 601

Image: `Dataset/16_N243/from-16/Portugal-16_000_601.jpg`

Prediction discipline:
- Predictions were saved before reading `GroundTruth.csv`.
- Ground truth was used only after the prediction artifact was written.

Result:
- Matched attributes: 6 / 17
- Prediction file: `artifacts/single_image_all_attributes_16_N243_601_2026-05-13/predictions_before_groundtruth.csv`
- Comparison file: `artifacts/single_image_all_attributes_16_N243_601_2026-05-13/prediction_vs_groundtruth.csv`

What improved:
- Area type matched after using full scene context.
- Roadside object class matched on both sides after treating buildings/walls as roadside fixed objects.
- Curvature matched after using nearby-frame context.

What still failed and how to strengthen it:

| Attribute | Failure | Required workflow change |
| --- | --- | --- |
| Number of lanes | One-way visual rule overfitted; GT coded two lanes. | Detect both travel directions/usable carriageway, not only visible lane markings. Add road-width + lane-direction reasoning from neighboring frames. |
| Lane width | Visual estimate overcalled wide; GT coded narrow. | Must use LAS road-edge or lane-boundary measurement. No final coding from image-only evidence. |
| Street lighting | Utility/street hardware was mistaken for lighting; GT says not present. | Require visible luminaire/light head, not just pole or overhead wire. |
| Median Type | One-way fallback overcalled; GT uses centre line. | Default undivided non-physical separation to centre-line class unless there is strong one-way evidence. |
| Delineation | Kerb/markings were underweighted; GT says adequate. | Include kerb/edge line/centre line as valid delineation evidence; don't require delineator posts. |
| Roadside distances | Both sides were under-risked as 1-5m; GT says 0-1m. | Need bbox-to-LAS or calibrated image-distance rule for urban building frontage close to kerb. |
| Paved shoulders | Urban edge was called none; GT says narrow. | Separate "paved shoulder" from full sidewalk; narrow paved edge/parking strip may count as narrow. Needs width estimate. |
| Property access | Commercial sign caused commercial access code; GT says residential >=3. | Count access points across the segment and classify dominant access, not one visible shop sign. |
| Sidewalk passenger side | Kerb/side path was overcalled; GT says none. | Require continuous, walkable sidewalk on passenger side; do not infer sidewalk from isolated kerb/wall edge. |

Decision:
- The stronger visual workflow is not sufficient for bulk coding yet.
- Next implementation step should add a rule engine with attribute-specific evidence gates:
  1. visual-only gates for area/service road/lighting/delineation,
  2. segment-context gates for property access/lanes/median,
  3. trajectory gates for curvature/sight distance,
  4. LAS measurement gates for lane width, paved shoulder width, and roadside distances.
