# Step 2 Attribute-To-Tool Mapping

Date: 2026-05-13

Deadline: 4-8 May 2026

Decision gate:

> Do all selected attributes have at least one plausible workflow?

Answer:

> Yes. All 17 selected ground-truth attributes now have at least one candidate workflow. Some are already executable, while others need pilot validation, prompt templates, or small geometry scripts before dataset-wide execution.

## Sources Checked

- `GroundTruth.csv`
- `experiment_tracking/attribute_workflow_matrix.md`
- `experiment_tracking/attribute_workflow_matrix_detailed_2026-05-13.md`
- `experiment_tracking/groundtruth_focused_attribute_values.md`
- `artifacts/experiments_planning_structured_work_plan_clean.txt`

Ground-truth coverage:

- Rows: 469
- Selected attributes: 17
- Identity/linking fields: `Folder_name`, `cloud_name`, `traj_index_start`, `traj_index_end`, `Image number`

## Attribute Coverage

| Attribute | Main workflow | Current readiness | Fallback strategy |
| --- | --- | --- | --- |
| `Area type` | Panorama scene classification using iRAP visual criteria. | Plausible; needs prompt validation. | Manual/vision-assisted coding on pilot rows. |
| `Number of lanes` | Count visible lanes from panorama, cross-check with road width where possible. | Needs implementation. | Manual/vision count for pilot; later lane-boundary detector. |
| `Lane width` | Detect/project road or lane boundaries to LAS and measure width. | Needs implementation. | Use road-width estimate divided by lane count where lane boundaries are unclear. |
| `Street lighting` | Detect streetlights/light poles and judge road relevance. | Plausible. | Vision descriptor if GroundingDINO prompt is unreliable. |
| `Service road` | Visual layout detection for parallel frontage/service road. | Plausible. | Manual/vision-assisted pilot with adjacent frames. |
| `Sight distance` | Forward visibility reasoning from panorama plus trajectory context. | High-risk pilot. | Reduced-scope manual/vision pilot; report as limited if unreliable. |
| `Median Type` | Panorama classification of separation/median/barrier type. | Plausible. | Manual/vision rule template with codebook mapping. |
| `Delineation` | Check road markings, guideposts, signs, and lane/edge visibility. | Plausible. | Manual/vision rubric for pilot rows. |
| `Roadside severity - driver side object` | Driver-side crop + GroundingDINO + iRAP object mapping. | Executable. | Vision/manual review if detection is ambiguous. |
| `Roadside severity - passenger side object` | Passenger-side crop + GroundingDINO + iRAP object mapping. | Executable. | Vision/manual review if detection is ambiguous. |
| `Roadside severity - drivers side distance` | Object bbox to LAS projection + road segmentation + object-to-road distance. | Executable for demo; needs quality validation. | Manual distance bucket if projection fails. |
| `Roadside severity - passenger side distance` | Object bbox to LAS projection + road segmentation + object-to-road distance. | Executable for demo; needs quality validation. | Manual distance bucket if projection fails. |
| `Paved shoulder - drivers side` | Driver-side visual shoulder detection; optional 3D width measurement. | Plausible; needs pilot. | Visual coding without measurement for first pilot. |
| `Paved shoulder - passenger side` | Passenger-side visual shoulder detection; optional 3D width measurement. | Plausible; needs pilot. | Visual coding without measurement for first pilot. |
| `Property access points` | Detect/count driveways, gates, minor roads, and access connections over a short frame sequence. | Plausible; needs sequence pilot. | Manual/vision count over adjacent frames. |
| `Curvature` | Trajectory geometry from consecutive GPS/pose points; image sanity check. | Strong candidate; needs script. | Manual/vision curve class for pilot rows. |
| `Sidewalk - passenger side` | Passenger-side visual detection of footway/sidewalk/kerb-separated pedestrian path. | Plausible; added to matrix on 2026-05-13. | Manual/vision rule template with codebook mapping. |

## Workflow Groups

| Group | Attributes | Shared method |
| --- | --- | --- |
| Roadside severity pipeline | Roadside object and distance fields for both sides. | GroundingDINO, bbox-to-points projection, point-cloud segmentation, distance measurement, risk ranking. |
| Visual panorama coding | Area type, street lighting, service road, median, delineation, shoulder, sidewalk, access points. | Side-aware panorama crops, iRAP codebook prompts, evidence notes, optional object prompts. |
| Geometry coding | Lane width, curvature, roadside distance. | Trajectory and LAS processing, projection, road/edge measurement. |
| Hard/uncertain pilot | Sight distance. | Treat first as a controlled pilot because reliable visibility distance needs stronger assumptions. |

## Geometry / 3D Clarification

The detailed matrix separates attributes by required evidence source:

| Evidence type | Attributes |
| --- | --- |
| Required 2D-to-3D / LAS geometry | `Lane width`, `Roadside severity - drivers side distance`, `Roadside severity - passenger side distance` |
| Recommended 3D measurement after visual pilot | `Paved shoulder - drivers side`, `Paved shoulder - passenger side`, median-width-related `Median Type` classes, sidewalk separation-width classes |
| Trajectory geometry | `Curvature`, plus supporting evidence for `Sight distance` |
| Mostly visual / object detection | `Area type`, `Number of lanes`, `Street lighting`, `Service road`, `Delineation`, roadside object classes, `Property access points` |

## Missing Pieces For Next Deadline

These do not block the Step 2 decision gate, but they are the work for 11-15 May:

1. Extract or build the numeric codebook for every selected attribute so predictions match `GroundTruth.csv`.
2. Resolve 3-5 representative ground-truth rows to actual panorama paths and LAS/cloud paths.
3. Create a pilot output schema with `gt_code`, `predicted_code`, `evidence`, `confidence`, `workflow`, and `artifact_paths`.
4. Implement or script the smallest missing geometry pieces: curvature first, then lane/shoulder width.
5. Run a controlled pilot batch and identify which attributes need fallback or reduced scope.

## Conclusion

The 4-8 May deadline is satisfied as a planning gate: every selected attribute in `GroundTruth.csv` has a plausible workflow and expected output. The next deadline should shift from mapping to pilot execution and gap reduction.
