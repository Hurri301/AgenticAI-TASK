# Focused Attribute Workflow Validation Plan

Created: 2026-05-12  
Purpose: move from "attribute-to-tool mapping" to "tested candidate workflows" for the 4-8 May planner task.

## What We Need To Prove

The professor's decision gate is:

> Do all selected attributes have at least one plausible workflow?

A stronger answer is:

> All selected attributes have a documented workflow, and each workflow has either a completed smoke test, a manual/visual pilot test, or a clearly defined implementation gap.

## Validation Levels

| Level | Meaning | Good enough for now? |
| --- | --- | --- |
| L1 - Designed | Inputs, outputs, and candidate tools are documented. | Yes for planning, not enough for final validation. |
| L2 - Manual pilot | One image/segment is reviewed manually using the workflow rules. | Good for visual attributes. |
| L3 - Script smoke test | A command runs and writes an output artifact. | Good for tool-based workflows. |
| L4 - Batch test | Multiple images/segments are tested and compared with ground truth. | Best answer for professor, next target. |

## Current Status By Attribute

| Attribute | Workflow type | Current test status | Existing evidence | Next test to run |
| --- | --- | --- | --- | --- |
| Area type | Panorama visual classification | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images; compare with `GroundTruth.csv`. |
| Number of lanes | Image/geometry lane counting | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images; later add lane detection/road-width support. |
| Lane width | 3D geometry measurement | L1 designed | `attribute_workflow_matrix.md` | Prototype road/lane boundary measurement using LAS/projection. |
| Street lighting | Object detection/visual classification | L1 designed | `attribute_workflow_matrix.md` | Run GroundingDINO/visual prompt for streetlight/pole evidence on 5 images. |
| Service road | Panorama visual layout | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images for parallel road presence. |
| Sight distance | Visibility/geometry reasoning | L1 designed | `attribute_workflow_matrix.md` | Treat as pilot only; manually label 5 forward views and define failure cases. |
| Median Type | Panorama visual classification | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images; compare with GT median codes. |
| Delineation | Road marking/sign visual classification | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images for lane/edge/center markings. |
| Roadside severity - driver side object | GroundingDINO detection | L3 smoke-tested | `artifacts/validation_2026-05-08/groundingdino_both_sides.json` and selected candidate file | Batch test on 3-5 images. |
| Roadside severity - passenger side object | GroundingDINO detection | L3 smoke-tested | `artifacts/validation_2026-05-08/groundingdino_both_sides.json` | Batch test on 3-5 images. |
| Roadside severity - drivers side distance | Bbox-to-LAS projection + distance | L3 partially smoke-tested | `selected_driver_projection_summary.json`; 241,913 projected points | Complete object-to-road distance calculation. |
| Roadside severity - passenger side distance | Bbox-to-LAS projection + distance | L2/L3 partial | passenger candidate identified, not yet projected in current validation folder | Project passenger bbox and calculate distance. |
| Paved shoulder - drivers side | Visual + possible 3D width | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images; mark visible paved shoulder and side. |
| Paved shoulder - passenger side | Visual + possible 3D width | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 images; mark visible paved shoulder and side. |
| Property access points | Visual counting over segment | L1 designed | `attribute_workflow_matrix.md` | Manual pilot on 5 adjacent frames; count driveways/accesses. |
| Curvature | Trajectory geometry | L1 designed | `attribute_workflow_matrix.md` | Implement small curvature-from-trajectory smoke test. |

## Minimum Test Set To Show Professor

Use the same 5 images/rows for every attribute where possible:

1. `Dataset/01_N3/from-01/Panoramic_000_481.jpg`
2. Add 4 more images from `GroundTruth.csv` with available panorama files and LAS/lookup rows.

For each image, create one JSON/CSV row:

| Field | Meaning |
| --- | --- |
| image_path | Panorama tested. |
| attribute | iRAP attribute name. |
| gt_code | Existing label from `GroundTruth.csv`. |
| predicted_or_observed_code | Workflow output or manual pilot code. |
| evidence | Bbox, measurement, or short visual reason. |
| workflow_status | manual_pilot, script_smoke_test, or needs_implementation. |

## Recommended Testing Order

1. Finish roadside severity distance for the already selected driver-side object.
2. Run the same roadside object workflow on 3-5 images.
3. Build a manual visual pilot sheet for all visual attributes on the same 5 images.
4. Add a curvature script using trajectory points.
5. Leave sight distance as a documented pilot unless we can define a reliable visibility metric.

## How To Answer Right Now

> We completed the attribute-to-tool matrix and began testing the workflows. The roadside severity workflow has been smoke-tested end-to-end through GroundingDINO object detection and 2D-to-3D projection. For one panorama, the selected driver-side wall/barrier bbox projected to 241,913 LAS points. The remaining attributes are mapped and now need a small validation batch: visual pilot tests for image-based attributes, geometry scripts for lane width/curvature, and a special pilot for sight distance.

## Better Answer After Validation Batch

> We tested each selected attribute with at least a pilot workflow. Roadside severity was tested with detection and projection outputs. Visual attributes were tested through manual/vision coding on a small image batch and compared with ground truth. Geometry attributes were tested with trajectory or point-cloud measurements where available. This gives evidence that every selected iRAP attribute has a practical workflow, while also showing which workflows require further automation.
