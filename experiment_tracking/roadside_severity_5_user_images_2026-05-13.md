# Roadside Severity Sample Test On 5 User Images

Date: 2026-05-13

Scope: only the four roadside severity attributes:

- `Roadside severity - driver side object`
- `Roadside severity - passenger side object`
- `Roadside severity - drivers side distance`
- `Roadside severity - passenger side distance`

## Context

The overview document confirms the intended system is a multi-agent iRAP coding workflow:

1. Scene understanding.
2. Object detection.
3. 2D-to-3D projection.
4. Geometry / measurement.
5. iRAP attribute reasoning.
6. Final synthesis and comparison with ground truth.

## Input Images

| Folder | Image |
| --- | --- |
| `02_A23_DESCENDENTE` | `Panoramic_002_4780.jpg` |
| `05_N365 NORTE` | `Panoramic-3_002_441.jpg` |
| `06_RAMAL N118` | `Panoramic_000_StreamFile_25.jpg` |
| `07_N118` | `Portugal_000_StreamFile_1121.jpg` |
| `08_N114` | `Panoramic-8_002_461.jpg` |

All five images were matched to exact `GroundTruth.csv` rows. Four images have exact lookup poses; `08_N114` used nearest lookup frame 401 for input frame 461.

## Artifacts

- Input manifest: `artifacts/roadside_severity_5_user_images_2026-05-13/manifest.csv`
- Router input: `artifacts/roadside_severity_5_user_images_2026-05-13/roadside_severity_input.json`
- Detector output: `artifacts/roadside_severity_5_user_images_2026-05-13/work/detections.json`
- Selected top-confidence candidates: `artifacts/roadside_severity_5_user_images_2026-05-13/selected_candidates.csv`
- Four-attribute comparison: `artifacts/roadside_severity_5_user_images_2026-05-13/roadside_severity_four_attribute_comparison.csv`
- Candidate recall: `artifacts/roadside_severity_5_user_images_2026-05-13/roadside_object_candidate_recall.csv`

## What Worked

- GroundingDINO ran on GPU with `device: cuda`.
- Bbox visualizations were generated for all five images.
- Detector candidate recall was strong: the ground-truth roadside object category appeared somewhere in the candidate list for all 10 side-specific cases.

## What Did Not Work Yet

- The full router timed out after detection because it generated 144 candidate bboxes for projection and distance.
- A reduced 10-bbox projection attempt also exceeded 600 seconds.
- Therefore RS_D distance predictions were not completed for this sample.
- A naive top-confidence object selection gave 0/10 correct RS_O final object codes for this run.

## Interpretation

This sample confirms the object detector can surface the correct iRAP object category, but the final decision agent is not ready. The next improvement should focus on candidate selection and fast projection:

1. Select candidates using iRAP risk hierarchy, not confidence alone.
2. Limit candidates before projection by side, class plausibility, bbox size, and location.
3. Optimize bbox-to-point projection for large LAS files by caching projected cloud pixels per image/LAS.
4. Run distance only for a small ranked candidate set.
5. Then synthesize RS_O and RS_D as a linked pair.
