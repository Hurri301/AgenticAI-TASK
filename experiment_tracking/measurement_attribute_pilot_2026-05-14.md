# Measurement Attribute Pilot

Date: 2026-05-14

Purpose:
- Move beyond point-cloud projection and compute first numeric estimates for measurement-required iRAP attributes.

Image:
- `Dataset/01_N3/from-01/Panoramic_000_481.jpg`

Point cloud:
- `Dataset/01_N3/L003-1-M01-S1-C1_s_RGB_REDNAP_AJ/L003-1-M01-S1-C1_s_RGB_REDNAP_AJ.las`

Implemented script:
- `scripts/measure_frame_geometry.py`

Method:
- Resolve image folder/frame from the panorama filename.
- Use `lookup_dataset_filtered_corrected.csv` to resolve pose and LAS.
- Build a local road-aligned frame from Applanix heading.
- Use a 60 m local LAS subset and an 18 m longitudinal measurement window.
- Infer a near-ground/road interval from local height and roughness bins.
- Estimate:
  - road width,
  - lane width,
  - paved shoulder width on both sides,
  - nearest vertical roadside candidate distance on both sides.

Pilot result:

| Measurement attribute | Numeric estimate | iRAP code estimate |
| --- | ---: | --- |
| Lane width | 2.625 m | `3 Narrow` |
| Paved shoulder - passenger side | 0.0 m | `4 None` |
| Paved shoulder - driver side | 0.0 m | `4 None` |
| Roadside severity - passenger side distance | 0.355 m | `1 0 to <1m` |
| Roadside severity - driver side distance | 0.036 m | `1 0 to <1m` |

Artifacts:
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/measurements/Panoramic_000_481_measurement_results.json`
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/measurements/Panoramic_000_481_measurement_plan_view.png`
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/Panoramic_000_481_projection_with_measurements.jpg`

Limitations:
- The road/object boundaries are still inferred geometrically, not semantically selected.
- Shoulder width can confuse road edge, sidewalk, parking area, and paved apron without image segmentation.
- Roadside distance currently uses nearest vertical LAS candidate; the next refinement should tie this to a GroundingDINO-selected iRAP object bbox.
