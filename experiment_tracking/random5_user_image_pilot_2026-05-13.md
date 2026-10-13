# Random 5-Image Roadside Object Pilot

Date: 2026-05-13

Purpose: test the current roadside-object detector on five user-provided images from different dataset folders and compare top-confidence predictions with `GroundTruth.csv`.

## Inputs

| Folder | Image |
| --- | --- |
| `02_A23_DESCENDENTE` | `Panoramic_002_4780.jpg` |
| `05_N365 NORTE` | `Panoramic-3_002_441.jpg` |
| `06_RAMAL N118` | `Panoramic_000_StreamFile_25.jpg` |
| `07_N118` | `Portugal_000_StreamFile_1121.jpg` |
| `08_N114` | `Panoramic-8_002_461.jpg` |

All five images matched exact ground-truth rows after normalizing the `02_A23_DESCENDENTE` folder name to the `GroundTruth.csv` spelling `02_A23 DESCENDENTE`.

## Artifacts

- Manifest: `artifacts/random5_user_images_2026-05-13/manifest.csv`
- Detector output: `artifacts/random5_user_images_2026-05-13/groundingdino_roadside_both_sides.json`
- Comparison table: `artifacts/random5_user_images_2026-05-13/roadside_object_comparison.csv`
- Summary: `artifacts/random5_user_images_2026-05-13/summary.json`

## Result Summary

Side-specific predictions: 10

Correct top-confidence roadside-object predictions: 2

Top-confidence accuracy: 20%

## Interpretation

The detector runs successfully on GPU and produces iRAP-mapped roadside object detections. However, taking the top-confidence detection as the final iRAP roadside object is not reliable enough. The next improvement must rank candidates using the iRAP risk hierarchy, side context, object plausibility, and distance evidence rather than confidence alone.

## Needed Improvement

1. Calibrate prompts for each roadside object class.
2. Use side-specific candidate filtering.
3. Use the risk hierarchy to select the final object.
4. Add projection/distance evidence before deciding the final RS_O/RS_D pair.
5. Add manual/visual review labels for ambiguous pilot failures.
