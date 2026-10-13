# Step 1 Validation Refresh

Date: 2026-05-13

Deadline: 28 April - 1 May 2026

Decision gate:

> Can the agent execute the main building blocks without manual intervention?

Answer:

> Yes for controlled repository examples, using the active Anaconda Python environment. The checked-in `.venv` is broken and should be recreated before treating the workspace as fully portable.

## What Was Done

1. Confirmed the repository structure, local `.agents` skills, demo data, GroundingDINO checkout, and checkpoint.
2. Confirmed `mm-link` imports from the local repository and `pytest` passes.
3. Ran reproducible examples for 2D-to-3D projection, 3D-to-2D projection, iRAP prompt preparation, GroundingDINO detection, point-cloud distance, point-cloud segmentation, point-cloud clustering, roadside object-to-road distance, and the full roadside severity router.
4. Saved the refresh outputs under `artifacts/validation_2026-05-13`.

## Environment Notes

| Item | Status | Evidence |
| --- | --- | --- |
| Repository package | Passed | `python -c "import mm_link"` resolves to `src/mm_link`. |
| Test suite | Passed | `python -m pytest tests -q` returned `3 passed`. |
| Checked-in virtual environment | Failed | `.venv\pyvenv.cfg` points to missing `<python-installation>`. |
| Active fallback environment | Passed | `<python-executable>`, Python 3.12.7. |
| GroundingDINO checkpoint | Present | `GroundingDINO\weights\groundingdino_swint_ogc.pth`. |
| GroundingDINO dependencies | Repaired | Installed missing `addict` and `supervision>=0.22.0` into Anaconda. |
| BERT text encoder cache | Repaired | First detector run required network/cache access for `bert-base-uncased`; subsequent runs should use the local Hugging Face cache. |

## Reproduced Outputs

| Building block | Output artifact | Result |
| --- | --- | --- |
| Bbox to point indices | `artifacts/validation_2026-05-13/projection_bbox_to_points.json` | 2 bbox records processed; selected 4 and 6 points. |
| Point indices to bbox | `artifacts/validation_2026-05-13/projection_points_to_bbox.json` | 4 input points projected to bbox `[1106, 436, 1109, 440]`. |
| iRAP description to hints | `artifacts/validation_2026-05-13/irap_description_mapping.json` | Passenger-side prompt/category mapping generated. |
| GroundingDINO image detection | `artifacts/validation_2026-05-13/groundingdino_passenger_test.json` | Passenger-side detector ran on the demo panorama. |
| Point-cloud distance | `artifacts/validation_2026-05-13/pointcloud_distance_results.json` | Minimum distance example returned `28.7510 m`. |
| Point-cloud segmentation | `artifacts/validation_2026-05-13/pointcloud_segment_results.json` | 404,685 points processed; road 144,494, ground 144,535, not-ground 260,150. |
| Point-cloud clustering | `artifacts/validation_2026-05-13/pointcloud_cluster_results.json` | 260,150 candidate points clustered into 29 clusters, 205 noise points. |
| Roadside distance to road | `artifacts/validation_2026-05-13/pointcloud_roadside_distance_results.json` | Road and ground self-check distances returned `0.0 m` as expected. |
| Full roadside severity router | `artifacts/validation_2026-05-13/roadside_severity_coded_results.json` | 1 image, both sides, 32 projection items, 30 distance objects, 30 candidates. |

## Full Router Result

For `data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png`:

| Side | RS_D | RS_O | Selected distance |
| --- | --- | --- | --- |
| Driver | `0 to <1m` | `Cliff` | `0.0 m` |
| Passenger | `0 to <1m` | `Tree >=10cm` | `0.0 m` |

Warnings:

- Two driver-side detections projected to zero LAS indices and were skipped in the distance step.
- GroundingDINO is running in CPU mode because custom C++ ops are not built.
- Segmentation is still a heuristic and needs quality validation before paper-scale results.

## Conclusion

The first deadline is satisfied as a technical execution gate: the agent can run the main repository building blocks and the end-to-end roadside severity workflow on controlled demo data. Before claiming dataset-wide readiness, recreate the local virtual environment and run a small representative pilot batch against ground truth.
