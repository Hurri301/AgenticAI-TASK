# Experiment Log

## 2026-04-28 - Step 1 validation start

| What I did | How I did it | Result / evidence | Next action |
| --- | --- | --- | --- |
| Read the structured work planner. | Extracted text from the `.docx` file and identified the 28 Apr - 1 May task: close Step 1 by validating tools, skills, models, and execution environment. | Planner says this week must produce a validated tool inventory and reproducible example runs. | Use this log as the running record for Step 1. |
| Inspected the repository structure. | Listed top-level files/folders, then narrowed to `scripts`, `src`, `tests`, `data`, `Dataset`, `.agents/skills`, and `artifacts`. | Found projection source API, CLI scripts, tests, demo data, full dataset, existing artifacts, and five local skills. | Continue keeping the inventory small and action-oriented. |
| Checked fast search availability. | Tried `rg --files`. | Failed with `Access is denied`. | Use PowerShell listing for now; record `rg` as an environment issue if it keeps happening. |
| Validated projection API tests manually. | Ran the three test functions directly with `.venv\Scripts\python.exe -c "..."` because `pytest` is missing. | Passed: `manual test calls passed`. | Install or enable `pytest` later so normal test commands work. |
| Tried normal pytest suite. | Ran `.venv\Scripts\python.exe -m pytest tests -q`. | Failed: `No module named pytest`. | Add `pytest` to the dev environment or project extras. |
| Validated projection skill: bbox to points. | Ran `.agents\skills\projection-dataflow-router\scripts\projection_router.py` with `example_bbox_input.json`. | Passed. Wrote `artifacts/validation_2026-04-28/projection_bbox_to_points.json`. Two bboxes returned 4 and 6 selected indices. | Keep this as a reproducible command for 2D-to-3D validation. |
| Validated projection skill: points to bbox. | Ran `.agents\skills\projection-dataflow-router\scripts\projection_router.py` with `example_indices_input.json`. | Passed. Wrote `artifacts/validation_2026-04-28/projection_points_to_bbox.json`. Indices `[1,2,3,4]` mapped to bbox `[1106,436,1109,440]`. | Keep this as a reproducible command for 3D-to-2D validation. |
| Tested direct `points_to_bbox.py` CLI. | Ran `scripts\points_to_bbox.py` with indices `1,2,3,4` and `--out-json artifacts\validation_2026-04-28\cli_points_to_bbox.json`. | Passed. Output bbox was `[1064,529,1065,530]` for `cloud_test_markings.las`. | Note that LAS choice affects bbox result. |
| Tested direct `bbox_to_points.py` CLI. | First tried it with `--max-points 10`, then reran without that unsupported flag. | The unsupported flag failed as expected. Without it, the selected bbox returned `0` indices from 19,009 projected candidates. | Use a known-positive bbox for future CLI smoke tests. |
| Confirmed direct `bbox_to_points.py` with a known-positive bbox. | Reused the router example bbox with `cloud_test.las`: `--bbox 1106,436,1109,440`. | Passed. Returned indices `[1,2,3,4]` with 404,685 candidates/projected and 4 selected points. | Use this as the direct CLI smoke test going forward. |
| Ran a controlled multi-image projection demo. | Ran `scripts\multi_image_projection_demo.py --scene image_1_baseline --max-points 1000 --no-show-preview --outdir artifacts\validation_2026-04-28\multi_image_projection_demo`. | Passed. Summary JSON, preview PNG, overlay PNG, and pose CSV were written. Bbox 2 selected 179 points. | Next time, test one LUT-based scene too. |
| Validated iRAP description-to-GroundingDINO prompt mapping. | Ran `irap_descriptions_to_hints.py` with the skill template JSON for passenger side. | Passed. Wrote `irap_description_mapping.json` and `irap_description_hints.json`; prompt was `pole . tree . signpost`. | This supports text-to-detection prompt preparation. |
| Checked GroundingDINO image detector readiness. | Ran `irap_groundingdino_bbox.py --help`; import happens before help text. | Blocked: `ModuleNotFoundError: No module named 'torchvision'`. | Install/repair GroundingDINO dependencies and confirm model files. |
| Checked point-cloud workflow readiness. | Ran point-cloud skill router with `example_segment_input.json`. | Blocked: router could not locate expected point-cloud scripts in the repo. | Decide whether to implement missing scripts or update the router to current repo structure. |
| Checked Python dependency snapshot. | Imported core packages from `.venv`. | Python 3.11.0, Pillow 12.2.0, numpy 2.4.4, torch 2.11.0+cpu. `laspy` missing. | `laspy` may be needed for point-cloud workflows even if current projection reader works without it. |
| Checked git state. | Ran `git status --short`. | Blocked by Git dubious ownership / safe.directory. | Add this repo as a safe Git directory if we need clean version tracking and commits. |

### Reproducible commands confirmed today

```powershell
.\.venv\Scripts\python.exe -c "import tests.test_projection_sanity as t; t.test_projection_wraparound_and_flip(); import tests.test_bbox_to_points as b; b.test_bbox_to_point_indices_in_range_and_pixels_inside_bbox(); import tests.test_points_to_bbox as p; p.test_point_indices_to_bbox_encloses_projected_pixels(); print('manual test calls passed')"
```

```powershell
.\.venv\Scripts\python.exe .\.agents\skills\projection-dataflow-router\scripts\projection_router.py --input-json .\.agents\skills\projection-dataflow-router\references\example_bbox_input.json --out-json artifacts\validation_2026-04-28\projection_bbox_to_points.json
```

```powershell
.\.venv\Scripts\python.exe .\.agents\skills\projection-dataflow-router\scripts\projection_router.py --input-json .\.agents\skills\projection-dataflow-router\references\example_indices_input.json --out-json artifacts\validation_2026-04-28\projection_points_to_bbox.json
```

```powershell
.\.venv\Scripts\python.exe scripts\points_to_bbox.py --poses data\Trajectories\01_N3.CSV --extrinsics data\Calibration\calib1.xml --las data\point_cloud\cloud_test_markings.las --image data\images\ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png --image-id ladybug_panoramic_000108.jpg --indices 1,2,3,4 --out-json artifacts\validation_2026-04-28\cli_points_to_bbox.json
```

```powershell
.\.venv\Scripts\python.exe scripts\bbox_to_points.py --poses data\Trajectories\01_N3.CSV --extrinsics data\Calibration\calib1.xml --las data\point_cloud\cloud_test.las --image data\images\ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png --image-id ladybug_panoramic_000108.jpg --bbox 1106,436,1109,440
```

```powershell
.\.venv\Scripts\python.exe scripts\multi_image_projection_demo.py --scene image_1_baseline --max-points 1000 --no-show-preview --outdir artifacts\validation_2026-04-28\multi_image_projection_demo
```

```powershell
.\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-groundingdino\scripts\irap_descriptions_to_hints.py --input-json .\.agents\skills\irap-roadside-groundingdino\references\description_input_template.json --side passenger --out-json artifacts\validation_2026-04-28\irap_description_mapping.json --out-hints-json artifacts\validation_2026-04-28\irap_description_hints.json
```

### Output folder

`artifacts/validation_2026-04-28`

## 2026-04-30 - Missing-tool registration pass

| What I did | How I did it | Result / evidence | Next action |
| --- | --- | --- | --- |
| Checked installed Python packages. | Ran `.venv\Scripts\python.exe -m pip list --format=freeze` and import checks for key packages. | Present: `torch`, `transformers`, `opencv-python`, `pandas`, `matplotlib`, `pyproj`, `pypdf`, `Pillow`, `numpy`. Missing: `pytest`, `torchvision`, `groundingdino`, `laspy`, `open3d`, `scipy`, `sklearn`. | Install only the packages needed for the selected workflow path. |
| Checked for GroundingDINO repo/model assets. | Searched top-level/project folders and model file extensions outside `.venv` and `Dataset`. | No top-level `GroundingDINO` directory or model checkpoint files found. | Choose skill-native GroundingDINO install versus Hugging Face detector route. |
| Inspected root detector script. | Read imports and model loading calls in `detect_roadside_severity.py`. | It uses Hugging Face `IDEA-Research/grounding-dino-base` and `facebook/sam-vit-base`; model assets are not locally cached. | Decide whether this legacy route should be kept or replaced by the skill detector. |
| Checked representativeness script readiness. | Ran `scripts/analyze_code_representativeness.py --help`. | Script does not expose help cleanly; it tried to run and failed because `images-labeling-coding.xlsx` is missing. | Provide workbook or update script path. |
| Checked evaluation script readiness. | Ran `scripts/evaluate_roadside_severity.py --help`. | Help printed successfully. | Test after a predicted output exists. |
| Updated missing-tool register. | Rewrote `experiment_tracking/missing_tool_register.md` into setup blockers, environment issues, and code gaps. | Added concrete install/provide/code items and priorities. | Use `setup_installation_needs.md` to decide what to install first. |
| Verified user-installed core packages. | Ran import checks for `pytest`, `laspy`, `scipy`, `sklearn`, and `open3d`; listed installed versions. | Imports passed. Versions: `pytest==9.0.3`, `laspy==2.7.0`, `scipy==1.17.1`, `scikit-learn==1.8.0`, `open3d==0.19.0`. | Mark these setup blockers closed. |
| Reran the repository test suite. | Ran `.venv\Scripts\python.exe -m pytest tests -q`. | Passed: `3 passed in 1.33s`. | Use pytest normally from now on. |
| Checked GroundingDINO installation. | Imported `torch`, `torchvision`, and `groundingdino`; checked repo/config/checkpoint paths; ran `irap_groundingdino_bbox.py --help`. | `torch 2.11.0+cpu`, `torchvision 0.26.0+cpu`, editable `groundingdino 0.1.0` import correctly. Repo and config exist. Checkpoint path `GroundingDINO\weights\groundingdino_swint_ogc.pth` is missing. Help printed but imports are slow and CPU-only warning appeared. | Download/place the checkpoint, then run one tiny image detection test. |
| Verified GroundingDINO checkpoint and attempted smoke test. | Checked `GroundingDINO\weights\groundingdino_swint_ogc.pth`, then ran `irap_groundingdino_bbox.py` on the demo panorama with passenger-side hints. | Checkpoint exists, size 693,997,677 bytes. Smoke test failed at text encoder resolution because `bert-base-uncased` is not fully cached locally; missing `pytorch_model.bin` or `model.safetensors`. | Download/cache `bert-base-uncased`, then rerun the same smoke test. |
| Fixed GroundingDINO/Transformers API mismatch. | Installed `transformers==4.41.2`, which restores `BertModel.get_head_mask`. | Verified `transformers 4.41.2`, `huggingface_hub 0.36.2`, `tokenizers 0.19.1`, and `has get_head_mask True`. | Keep `transformers` pinned to 4.x for GroundingDINO. |
| Rechecked after interrupted smoke test. | Checked versions, checkpoint, partial workspace Hugging Face cache, and running Python processes. | GroundingDINO packages and checkpoint are OK. Workspace BERT cache is partial/incomplete. Several Python processes remain after interruption. | Stop leftover processes if needed, finish BERT cache separately, then run one smoke test only after cache verification. |
| Completed GroundingDINO passenger smoke test. | Ran `irap_groundingdino_bbox.py` on the demo panorama, passenger side, using `irap_description_hints.json`, CPU mode, and `max_detections_per_hint=1`. | Passed. Wrote `artifacts/validation_2026-05-04/groundingdino_passenger_test.json`. Detected signpost, tree, and pole with confidences 0.61, 0.54, and 0.41. | Mark BERT/GroundingDINO setup as validated; next blocker is point-cloud workflow scripts. |
| Validated newly added point-cloud scripts. | Checked script presence and ran `--help` for segmentation, clustering, distance, and visualization CLIs. Added `src/mm_link/pointcloud.py` APIs expected by the scripts. | Help commands passed and existing pytest suite still passed: `3 passed`. | Run router examples. |
| Ran point-cloud router validations. | Ran `pointcloud_workflow_router.py` for segment, distance, cluster inline, and roadside-distance inline inputs. | Segment passed with 404,685 points processed. Distance passed with min distance 28.75 m for test sets. Cluster inline passed with 2 clusters and 3 noise points. Roadside inline passed with object-to-road distance 47.96 m. | Point-cloud workflow is now executable; next validate quality and integrate with GroundingDINO/projection outputs. |
