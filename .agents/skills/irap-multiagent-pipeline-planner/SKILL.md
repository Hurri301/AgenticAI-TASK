---
name: irap-multiagent-pipeline-planner
description: Plan, document, and visualize the complete iRAP multiagent road-attribute coding pipeline from 2D panoramas, 3D LiDAR point clouds, calibration/trajectory data, segment indexes, toolbox modules, attribute agents, method-comparison baselines, evidence tables, and evaluation outputs. Use when the task asks for the whole multiagent system architecture, flowchart, end-to-end pipeline, global workflow, attribute-to-tool matrix, experiment methodology, or paper-ready diagram covering all selected iRAP attribute workflows.
---

# iRAP Multiagent Pipeline Planner

## Overview

Use this skill to turn the repository's iRAP attribute coders and shared 2D/3D tools into one coherent multiagent system plan. The output should usually be a flowchart, workflow specification, attribute-to-tool matrix, or experiment methodology that is traceable from data input to segment-level attributes and evaluation.

Load these references as needed:

- [Attribute workflow map](references/attribute-workflow-map.md): all selected attributes, evidence needs, tool routes, category boundaries, and validation checks.
- [System pipeline blueprint](references/system-pipeline-blueprint.md): whole-system architecture, method-comparison branches, and Mermaid flowchart templates.
- [Output and evaluation contract](references/output-and-evaluation-contract.md): expected artifacts, segment tables, logs, confidence handling, and metrics.

## Core Workflow

1. Define the processing unit.
- Prefer segment-level processing, usually 100 m road segments unless the user or dataset specifies otherwise.
- Treat each segment as a packet containing panorama frame IDs, LAS/point-cloud clip or indices, calibration/extrinsics, trajectory/GPS evidence, coded direction, driver/passenger side convention, and optional ground truth.

2. Build and validate shared data products.
- Create the segment index: panos, image patches, point-cloud clips, trajectory window, and metadata.
- Validate 2D-to-3D alignment before any measurement-heavy workflow.
- Cache reusable intermediates: scene descriptions, side crops, detections, projected indices, road/ground segmentation, and geometry measurements.

3. Select the method branch.
- `human_ground_truth`: use only for comparison labels, not as agent input during prediction.
- `heuristic_pipeline`: use the full hybrid agent workflow with coded rules, thresholds, and confidence checks.
- `2d_only_baseline`: use panorama descriptions, visual detections, and adjacent-frame review; skip LAS-derived measurements.
- `3d_only_baseline`: use point-cloud/trajectory geometry where possible; skip VLM-only interpretation except for trace labels if explicitly allowed.

4. Route each attribute to the lightest sufficient toolchain.
- Use 2D tools for visual context, visible lane/median evidence, lighting, service road, delineation, access points, and visual sanity checks.
- Use 3D tools for lane/shoulder widths, offsets, roadside distances, trajectory curvature, and any point-cloud distance or segmentation task.
- Use fusion when the final code depends on both semantic identity and metric distance, especially roadside severity and side-facility measurements.

5. Loop through attributes.
- Read [Attribute workflow map](references/attribute-workflow-map.md) before preparing a matrix, flowchart, or global workflow.
- Invoke the existing attribute skills rather than restating their full rules when actual coding is requested.
- Preserve one traceable intermediate-output block per attribute before writing the final Cat ID.

6. Apply confidence and fallback gates.
- If confidence is low, request/inspect adjacent frames, alternate crops, measurement evidence, or manual review notes.
- Keep the predicted value, confidence, evidence source, competing categories, and fallback reason together.
- Never silently overwrite a low-confidence result with a cleaner-looking final table.

7. Produce evaluation outputs.
- Build the segment attribute table for every method branch.
- Compare predictions to ground truth where available.
- Report accuracy, completeness, confidence calibration, runtime/effort, failure categories, and reproducibility notes.

## Existing Agent Roles

- `$panoramic-road-safety-describer`: Convert full panoramas or side crops into concise, iRAP-grounded safety descriptions.
- `$irap-roadside-groundingdino`: Detect or prompt-map roadside severity objects by side and produce bbox evidence.
- `$projection-dataflow-router`: Route bbox-to-points and points-to-bbox projection using calibration, trajectory, image, and LAS data.
- `$pointcloud-multistep-processor`: Segment road/ground, cluster candidate points, measure distances, and generate point-cloud artifacts.
- `$irap-roadside-severity-coder`: Code paired roadside severity distance/object attributes.
- `$irap-width-facility-coder`: Code lane width, paved shoulders, and passenger-side sidewalk/path.
- `$irap-carriageway-layout-coder`: Code number of lanes and median type.
- `$irap-visual-context-coder`: Code area type, street lighting, service road, and delineation.
- `$irap-access-points-coder`: Code segment-level property access points.
- `$irap-alignment-visibility-coder`: Code curvature and sight distance.

## Flowchart Rules

When creating a whole-system flowchart:

1. Show data input first: 3D LiDAR point cloud, 2D panoramic images, calibration/extrinsics, and trajectory/GPS.
2. Show shared preprocessing before attribute agents: road segmentation, segment index, pano/point-cloud clips, and alignment validation.
3. Separate toolbox modules into 2D tools, 3D tools, and fusion tools.
4. Show the AI agent orchestrator as an attribute loop with a decision point: `2D`, `3D`, or `Fusion`.
5. Show method-comparison branches: human coding ground truth, heuristic pipeline, 2D-only baseline, and 3D-only baseline.
6. Show confidence loops before finalizing an attribute.
7. End with segment attribute tables, comparison metrics, error analysis, quality/efficiency report, and paper-ready outputs.

Use [System pipeline blueprint](references/system-pipeline-blueprint.md) for Mermaid templates and layout guidance.

## Output Style

For planning outputs, prefer:

- A compact architecture narrative.
- A Mermaid flowchart or diagram-ready block.
- An attribute-to-tool matrix.
- A reusable data/artifact contract.
- A short list of open blockers and missing tools.
- A validation plan tied to ground truth and paper outputs.
