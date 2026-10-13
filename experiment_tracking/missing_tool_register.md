# Missing Tool Register

Created: 2026-04-28  
Updated: 2026-04-30

Step 2 update: 2026-05-06

Step 3 pilot update: 2026-05-13

## Immediate Setup Blockers

| Missing capability / issue | Affected workflows | Priority | Evidence | Proposed solution | Status |
| --- | --- | --- | --- | --- | --- |
| `pytest` missing in `.venv`. | Normal test-suite execution and repeatable validation. | High | Previously failed with `No module named pytest`. On 2026-04-30, `pytest==9.0.3` is installed and `python -m pytest tests -q` passed: `3 passed`. | No further setup needed unless new tests require extra plugins. | Closed |
| `torchvision` missing. | Skill-based GroundingDINO detector: `.agents/skills/irap-roadside-groundingdino/scripts/irap_groundingdino_bbox.py`. | High | Previously missing. On 2026-05-04, `torchvision 0.26.0+cpu` imports successfully with `torch 2.11.0+cpu`. | No further package setup needed. | Closed |
| `groundingdino` Python package missing. | Skill-based GroundingDINO detector and end-to-end roadside severity coding. | High | Previously missing. On 2026-05-04, editable package imports from `<repository-root>\GroundingDINO\groundingdino\__init__.py`; `pip show groundingdino` reports version `0.1.0`. | No further package setup needed. | Closed |
| GroundingDINO repository/config/checkpoint missing or unconfirmed. | Skill-based GroundingDINO image detection. | High | On 2026-05-04, repo and config exist, and `GroundingDINO\weights\groundingdino_swint_ogc.pth` exists with size 693,997,677 bytes. | No further checkpoint setup needed. | Closed |
| `bert-base-uncased` Hugging Face model weights missing/incomplete in local cache. | Skill-based GroundingDINO image detection. | High | Previously missing/incomplete. On 2026-05-04, local-only `AutoTokenizer`/`AutoModel` verification printed `BERT OK`, and GroundingDINO passenger smoke test completed successfully. | No further BERT setup needed. | Closed |
| Point-cloud workflow scripts missing. | Point-cloud segmentation, clustering, object-to-road distance, and end-to-end RS_D/RS_O coding. | High | Previously missing. On 2026-05-04, scripts exist and help commands work: `segment_road_cloud.py`, `pointcloud/cluster_euclidean.py`, `pointcloud/min_cluster_distance.py`, `visualize_segmented_cloud.py`. Router segment, distance, cluster, and roadside-distance validation runs completed. | No further script-presence setup needed. Continue quality validation of segmentation/distance behavior. | Closed |
| `laspy` missing. | Point-cloud processing and LAS write/read helpers likely needed by missing point-cloud scripts. | Medium | Previously missing. On 2026-04-30, `laspy==2.7.0` imports successfully. | No further package setup needed. | Closed |
| `scipy` missing. | Likely euclidean clustering, KD-tree nearest-neighbor distance, and point-cloud metrics. | Medium | Previously missing. On 2026-04-30, `scipy==1.17.1` imports successfully. | No further package setup needed. | Closed |
| `scikit-learn` missing. | Possible DBSCAN/euclidean clustering implementation. | Medium | Previously missing. On 2026-04-30, `scikit-learn==1.8.0` imports successfully via `sklearn`. | No further package setup needed. | Closed |
| `open3d` missing. | Optional point-cloud visualization and possibly clustering. | Medium | Previously missing. On 2026-04-30, `open3d==0.19.0` imports successfully. | No further package setup needed. | Closed |
| `images-labeling-coding.xlsx` missing. | Representativeness/codebook analysis script. | Medium | `scripts/analyze_code_representativeness.py --help` actually executed the script and failed with `FileNotFoundError` for `<repository-root>\images-labeling-coding.xlsx`. | Place the workbook at repo root or update the script to point to the correct workbook path. | Open |
| Hugging Face model assets not cached. | Legacy `detect_roadside_severity.py` route using `IDEA-Research/grounding-dino-base` and `facebook/sam-vit-base`. | Medium | Script imports are present and packages exist, but cache search found no local model assets. First real run will need internet or pre-downloaded model cache. | Download/cache the two Hugging Face models, or avoid this legacy route and use the skill-based GroundingDINO path. | Open |

## Attribute Workflow Gaps

| Missing capability / issue | Affected workflows | Priority | Evidence | Proposed solution | Status |
| --- | --- | --- | --- | --- | --- |
| Manual codebook table not yet extracted for focused attributes. | All Step 2 attribute workflows. | High | `attribute_workflow_matrix.md` maps attributes to tools, but exact code options from the iRAP manual still need to be copied into a clean table. | Extract coding options/pages for the 16 focused attributes and create `attribute_codebook.md`. | Open |
| GroundTruth unique-value audit not yet completed. | Output formatting for all attributes. | High | `GroundTruth.csv` contains matching columns, but unique labels/codes have not yet been summarized side-by-side with the manual. | Generate unique values per focused column and compare to manual codebook. | Open |
| Lane-count detector/workflow not yet implemented. | `Number of lanes`. | High | Current tools can inspect panoramas, but there is no repeatable lane-count pipeline. No 5-row pilot prediction exists yet. | Start with vision/manual prompt workflow, then test lane marking or segmentation approach. | Open |
| Lane-width measurement workflow not yet implemented. | `Lane width`. | High | Projection and LAS tools exist, but lane/road boundary detection is not yet connected to a measurement script. | Detect lane/road boundaries, project to 3D, measure lateral width, and compare to GT labels. | Open |
| Curvature-from-trajectory workflow needs improvement. | `Curvature`. | Medium | On 2026-05-13, `scripts/pilot_curvature_from_lookup.py` ran on 5 rows but reached only 20% top-code accuracy; one row lacked lookup samples. | Replace heading-window heuristic with a radius/arc-length method and repair lookup matching for `08_N114`. | Open |
| Sight-distance visibility workflow not yet implemented. | `Sight distance`. | High | Manual criterion depends on visibility distance and speed context; current tools do not estimate visible road distance. | Treat as pilot: combine forward image reasoning, trajectory geometry, and occlusion checks. | Open |
| Visual prompt/rule templates not yet written. | Area type, street lighting, service road, median type, delineation, paved shoulder, property access points, sidewalk passenger side. | Medium | Attributes are mapped to visual workflows, but prompts and output schemas are not standardized. The 5-row pilot manifest exists, but visual predictions have not been generated yet. | Create one JSON schema and short prompt template per attribute group. | Open |

## Environment / Reproducibility Issues

| Missing capability / issue | Affected workflows | Priority | Evidence | Proposed solution | Status |
| --- | --- | --- | --- | --- | --- |
| Git refuses repo status due to dubious ownership. | Version tracking, experiment reproducibility, commits. | Medium | `git status --short` failed and suggested `git config --global --add safe.directory E:/Agent-LLM-task/2D_3D_projection`. | Add this repo as a safe Git directory when ready to use Git metadata. | Open |
| `rg` cannot run in this workspace. | Fast inventory/search workflow. | Medium | `rg --files` failed with `Access is denied`. | Fix executable permission/path issue; PowerShell listing is the fallback for now. | Open |
| GroundingDINO custom CUDA ops are not compiled. | Detector speed/performance and optimized GPU inference. | Medium | On 2026-05-13, detector ran under `irap-gpu` with `device: cuda`, but custom `_C` ops were unavailable. A local fallback patch allows PyTorch deformable attention to run without crashing. | For production speed, install a full CUDA toolkit with `nvcc` and build GroundingDINO in the GPU env. For pilots, keep the PyTorch fallback. | Partially mitigated |
| Possible leftover Python processes from interrupted model/detection runs. | Machine performance and clean validation. | Medium | On 2026-05-04, several Python processes were still present after interruption, including repo venv Python processes. | Close the terminal or stop only the leftover Python processes related to this run before retrying. | Open |
| `detect_roadside_severity.py --help` is slow under current environment. | Legacy detector usability. | Low | The command printed help but exceeded the 30-second timeout, likely due heavy `transformers`/`torch` imports. | Treat as usable but slow; prefer lighter skill scripts for setup checks. | Open |

## Workflow Design / Code Gaps

| Missing capability / issue | Affected workflows | Priority | Evidence | Proposed solution | Status |
| --- | --- | --- | --- | --- | --- |
| Direct `bbox_to_points.py` CLI has no `--max-points` flag. | Small bounded CLI smoke tests. | Low | CLI rejected `--max-points 10`. | Use distance/intensity filters for CLI smoke tests, or add a CLI `--max-points` option if needed. | Open |
| Need a selected point-cloud segmentation method. | RS_D distance from roadside object to road. | High | On 2026-05-04, a simple low-Z/lateral road heuristic runs and produces `ground`, `road`, and `not-ground` index files. | Validate segmentation quality visually/numerically before using for paper results; improve method if needed. | Open |
| Need a selected object-distance method. | RS_D distance bucket assignment. | High | On 2026-05-04, `min_cluster_distance.py` and router distance mode run successfully with SciPy backend. | Validate distances against known cases and integrate with projected detections. | Open |
| Need a selected clustering method. | Grouping projected object points and non-ground candidates. | Medium | On 2026-05-04, `cluster_euclidean.py` and router cluster mode run successfully on inline candidate indices with SciPy backend. | Validate clustering parameters on representative object detections. | Open |
| Known-positive bbox for direct bbox CLI smoke test. | Reproducible bbox-to-points command outside router. | Low | Initial test bbox `3000,1500,3600,2200` selected 0 points. Follow-up bbox `1106,436,1109,440` returned indices `[1,2,3,4]`. | Use bbox `1106,436,1109,440` with `cloud_test.las` for future direct CLI smoke tests. | Closed |
