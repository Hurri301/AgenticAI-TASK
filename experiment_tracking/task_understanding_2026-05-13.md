# Experiment Understanding Refresh

Date: 2026-05-13

Sources read:

- `artifacts/Experiments planning - structured work plan.docx`
- `artifacts/experiments_planning_structured_work_plan_clean.txt`
- `GroundTruth.csv`
- `experiment_tracking/attribute_workflow_matrix.md`
- `experiment_tracking/groundtruth_focused_attribute_values.md`

## Correct Understanding

This project is not a single object-detection task. It is an agent-assisted iRAP attribute-coding experiment from road panoramas and point clouds.

The final goal before the end of June 2026 is to produce dataset-wide iRAP attribute predictions, compare them with the available ground truth, analyse errors, and use the final workflow and results in the paper.

The phrase `passenger side` in this repository means the roadside on the passenger side of the vehicle. It does not mean detecting passengers/people.

## Ground Truth

Ground-truth file:

`<repository-root>\GroundTruth.csv`

Rows: 469

Columns: 23

Core identity/linking columns:

- `Folder_name`
- `cloud_name`
- `Event File Matching`
- `traj_index_start`
- `traj_index_end`
- `Image number`

Focused iRAP attributes:

- `Area type`
- `Number of lanes`
- `Lane width`
- `Street lighting`
- `Service road`
- `Sight distance`
- `Median Type`
- `Delineation`
- `Roadside severity - driver side object`
- `Roadside severity - passenger side object`
- `Roadside severity - drivers side distance`
- `Roadside severity - passenger side distance`
- `Paved shoulder - drivers side`
- `Paved shoulder - passenger side`
- `Property access points`
- `Curvature`
- `Sidewalk - passenger side`

## Work Package Interpretation

The document defines five work packages:

1. Tool and skill validation.
2. Attribute-to-tool mapping.
3. Global agent workflow.
4. Results and iteration.
5. Paper writing.

Step 1 is a short validation and handover task, not an open-ended exploration phase. Step 2 maps every selected iRAP attribute to a plausible toolchain. The next active window is to resolve missing tools and run attribute-level pilots.

## Practical Workflow Direction

The global workflow should be hybrid:

- Shared preprocessing: resolve image row, panorama path, trajectory interval, LAS/cloud path, and side orientation.
- Image-based attributes: use panorama/vision reasoning and targeted object prompts.
- Geometry attributes: use trajectory, projection, and LAS processing.
- Roadside severity: use object detection, projection, road segmentation, distance measurement, and risk-ranking.
- Evaluation: always output numeric codes compatible with `GroundTruth.csv`, plus evidence.

## Immediate Correction To Current Work

The previous GPU GroundingDINO test was only a technical smoke test for roadside-object detection. It should not be treated as the main experiment.

Next work should start from `GroundTruth.csv` rows and produce per-row predictions for the selected iRAP attributes. Roadside severity is only one subset of the larger experiment.

## Next Required Artifacts

1. A selected-row pilot input table: 3-5 rows from `GroundTruth.csv` with resolved image and LAS paths.
2. A codebook table mapping every numeric GT code to its iRAP meaning.
3. An output schema for predictions:
   - row id
   - image path
   - attribute name
   - ground truth code
   - predicted code
   - confidence
   - evidence
   - workflow used
   - artifact paths
4. A pilot results table comparing predicted values with ground truth.

## Decision-Gate Alignment

For 11-15 May, the question is:

> Which attributes still need fallback strategies or reduced scope?

The next run should therefore be an attribute-level pilot, not another isolated detector demo.
