# Point-Cloud Projection Random Test

Date: 2026-05-14

Purpose:
- Verify that the 3D point-cloud layer can be involved before coding measurement-required iRAP attributes.
- Project LAS points into a panorama image and inspect whether the 3D evidence aligns with visible road/roadside objects.

Random test image:
- `Dataset/01_N3/from-01/Panoramic_000_481.jpg`

Resolved inputs:
- Lookup row: `01_N3`, frame `481`
- Point cloud reference: `01_N3/pointClouds/L003-1-M01-S1-C1_s_RGB_REDNAP_AJ.rar`
- Resolved LAS: `Dataset/01_N3/L003-1-M01-S1-C1_s_RGB_REDNAP_AJ/L003-1-M01-S1-C1_s_RGB_REDNAP_AJ.las`
- Calibration: `data/Calibration/calib1.xml`

Projection result:
- Local radius: 60 m
- Local candidate LAS points: 2,487,848
- Projected input points after downsampling: 207,321
- Valid projected points: 207,321

Artifacts:
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/Panoramic_000_481_las_projection_overlay.jpg`
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/Panoramic_000_481_las_projection_side_crops.jpg`
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/projection_summary.json`
- `artifacts/pointcloud_projection_random_test_2026-05-14/direct_projection_01_N3_481/routing_plan.csv`

Interpretation:
- The projection layer is usable for this random frame: points land on visible road surface, roadside walls, buildings, slopes, and nearby vehicles.
- This validates the evidence layer needed for lane width, paved shoulder width, and roadside distance workflows.

Important caveat:
- This run only proves 3D-to-image alignment. Final iRAP measurement still needs explicit road-edge/object-edge selection, then width or distance computation.
