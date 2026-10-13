# Step 1 Validation Brief

Period: 28 April - 1 May 2026  
Project: AI agent-assisted iRAP attribute coding from road imagery and point clouds

## Purpose

The goal of Step 1 was to confirm that the repository, local agent skills, models, scripts, and execution environment can run the main building blocks needed for the experiment.

Decision gate:

> Can the agent execute the main building blocks without manual intervention?

Current answer:

> Yes, for controlled validation examples. The main building blocks now run end to end as individual components. The next phase should validate quality and integrate them into a controlled pilot workflow.

## What Was Completed

| Building block | What was validated | Evidence |
| --- | --- | --- |
| Repository and Python environment | Core package imports, dependency installation, and test execution. | `pytest` passed: 3 tests passed. |
| 2D-to-3D projection | Image bounding boxes can be mapped to LAS point indices. | `projection_bbox_to_points.json` and direct CLI validation. |
| 3D-to-2D projection | LAS point indices can be mapped back to image bounding boxes. | `projection_points_to_bbox.json` and direct CLI validation. |
| Multi-image projection demo | One baseline image scene ran and produced preview/overlay artifacts. | `multi_image_projection_demo/projection_demo_summary.json`. |
| iRAP object prompt preparation | Roadside descriptions can be converted to iRAP object hints and GroundingDINO prompts. | `irap_description_mapping.json`, prompt: `pole . tree . signpost`. |
| GroundingDINO setup | GroundingDINO, checkpoint, BERT text encoder, and image detection run successfully on the demo panorama. | `groundingdino_passenger_test.json`. |
| Point-cloud segmentation | LAS cloud can be segmented into `ground`, `road`, and `not-ground` index sets. | `pointcloud_segment_results.json`. |
| Point-cloud distance | Minimum 3D distance between two point-index sets can be computed. | `pointcloud_distance_results.json`. |
| Point-cloud clustering | Euclidean clustering can group candidate point indices. | `pointcloud_cluster_inline_results.json`. |
| Roadside object-to-road distance | A projected object point set can be measured against the segmented road reference. | `pointcloud_roadside_inline_results.json`. |

## Key Outputs

Validation folder:

```text
artifacts/validation_2026-04-28
artifacts/validation_2026-05-04
```

Tracking files:

```text
experiment_tracking/tool_inventory.md
experiment_tracking/experiment_log.md
experiment_tracking/missing_tool_register.md
experiment_tracking/setup_installation_needs.md
```

Important validation outputs:

```text
artifacts/validation_2026-04-28/projection_bbox_to_points.json
artifacts/validation_2026-04-28/projection_points_to_bbox.json
artifacts/validation_2026-04-28/irap_description_mapping.json
artifacts/validation_2026-05-04/groundingdino_passenger_test.json
artifacts/validation_2026-05-04/pointcloud_segment_results.json
artifacts/validation_2026-05-04/pointcloud_distance_results.json
artifacts/validation_2026-05-04/pointcloud_cluster_inline_results.json
artifacts/validation_2026-05-04/pointcloud_roadside_inline_results.json
```

## Example Results From Validation

GroundingDINO passenger-side detection on the demo panorama produced:

| Detected object | iRAP category | Confidence |
| --- | --- | --- |
| signpost | Rigid sign, post or pole >=10cm | 0.61 |
| tree | Tree >=10cm | 0.54 |
| pole | Rigid sign, post or pole >=10cm | 0.41 |

Point-cloud roadside distance validation:

```text
Example object point set: [1, 2, 3, 4]
Reference class: road
Minimum distance: 47.96 m
Backend: scipy
```

Segmentation validation:

```text
Total points processed: 404,685
Ground points: 144,535
Road points: 144,494
Not-ground points: 260,150
```

## Remaining Caveats

These are no longer basic setup blockers, but they must be addressed before final paper-scale results:

1. GroundingDINO currently runs in CPU-only mode, so detection is slow.
2. The point-cloud road segmentation is currently a simple geometric heuristic and must be validated against representative scenes.
3. The next phase must connect all components into one controlled pilot run and compare outputs against ground truth.
4. The file `images-labeling-coding.xlsx` is still needed for representativeness/codebook analysis, unless the script is updated to use another source.

## Suggested Explanation To Professor

During Step 1, I validated the local experimental environment and confirmed that the main computational building blocks can run: image-to-point-cloud projection, point-cloud-to-image projection, GroundingDINO object detection, iRAP object hint generation, point-cloud segmentation, clustering, and object-to-road distance measurement.

The validation produced traceable JSON outputs and logs for each component. The environment is now ready for Step 2: mapping each selected iRAP attribute to a reproducible toolchain and then running controlled pilot cases.

The main remaining work is not setup, but methodological validation: checking the quality of the road segmentation and running end-to-end pilot cases against ground truth.

