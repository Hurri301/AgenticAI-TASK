# Output And Evaluation Contract

Use this reference when specifying the files, tables, and evaluation outputs for the whole multiagent experiment.

## Segment Packet

Each segment-level run should start from a normalized packet:

```json
{
  "segment_id": "segment_001",
  "segment_length_m": 100,
  "coded_direction": "forward",
  "side_convention": {
    "right_hand_traffic": true,
    "passenger_side_image_region": "left",
    "driver_side_image_region": "right"
  },
  "images": [{"image_id": "pano_001", "path": "data/images/...png"}],
  "adjacent_frames": [],
  "point_cloud": {"las": "data/point_cloud/cloud_test.las", "clip_id": null},
  "calibration": {"extrinsics": "data/Calibration/calib1.xml", "poses": "data/Trajectories/01_N3.CSV"},
  "ground_truth": {},
  "metadata": {}
}
```

## Attribute Result Record

Every final attribute result should preserve the intermediate evidence that justified the code:

```json
{
  "segment_id": "segment_001",
  "method": "heuristic_pipeline",
  "attribute": "Lane width",
  "cat_id": 2,
  "category": "Medium 2.75m to <3.25m",
  "confidence": 0.78,
  "route": "fusion",
  "evidence_summary": "Lane boundaries identified visually and measured from projected points.",
  "intermediate": {},
  "artifacts": [],
  "fallbacks_used": [],
  "trace": {
    "input": {},
    "skills": [],
    "source_files": [],
    "notes": []
  }
}
```

## Segment Attribute Table

Use a wide table for final method comparison and a long table for error analysis.

Minimum wide-table columns:

- `segment_id`
- `method`
- one column per selected iRAP attribute Cat ID
- one column per selected iRAP attribute confidence
- `run_id`
- `workflow_version`
- `notes`

Minimum long-table columns:

- `segment_id`
- `method`
- `attribute`
- `ground_truth_cat_id`
- `predicted_cat_id`
- `correct`
- `confidence`
- `route`
- `primary_evidence`
- `failure_category`
- `planned_fix`
- `artifact_paths`

## Tracking Files

Maintain these living files for reproducibility:

| Tracking item | Purpose | Minimum contents |
|---|---|---|
| Tool inventory | Know what the agent can already execute. | Tool or skill name, command/invocation, required inputs, output files, tested status, known limitations. |
| Attribute workflow matrix | Connect each attribute to a reproducible method. | Attribute, data source, tool sequence, intermediate outputs, final code/value, validation rule, fallback option. |
| Missing-tool register | Avoid late blockers. | Missing capability, affected attributes, priority, proposed solution, implementation status. |
| Experiment log | Make each run auditable. | Date, dataset subset, command or prompt, code version, parameters, output path, metric summary, notes. |
| Results and error-analysis table | Support iteration and paper writing. | Ground truth, prediction, correctness, confidence/evidence, failure category, planned fix. |

## Evaluation Metrics

Report at least:

- Attribute-level accuracy against ground truth.
- Segment-level completeness: percent of requested attributes with final codes.
- Confidence-stratified accuracy: high/medium/low confidence buckets.
- Failure category counts: missing input, alignment failure, detection failure, projection failure, measurement failure, ambiguous visual evidence, coding-rule conflict.
- Method comparison: heuristic pipeline vs 2D-only baseline vs 3D-only baseline.
- Efficiency: runtime, number of tool calls, manual review count, and reusable intermediates saved.

## Quality Gates

- Do not mark a dataset-wide run complete until every selected attribute has a documented workflow and output field.
- Do not compare to ground truth until prediction outputs are frozen for that run.
- Do not collapse both roadside severity fields independently; RS_D and RS_O must remain a paired candidate.
- Do not hide low-confidence results in the final table; include confidence and reason.
- Do not report a final method as paper-ready until error analysis explains the dominant failure modes.

## Paper-Ready Outputs

The final system output should support:

- Methodology diagram or flowchart.
- Attribute workflow matrix.
- Dataset-wide prediction table.
- Comparison table against ground truth and prior methods.
- Accuracy and efficiency metrics.
- Error-analysis table with representative examples.
- Limitations and reproducibility notes tied to actual artifacts.
