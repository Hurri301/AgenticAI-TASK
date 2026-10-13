---
name: irap-roadside-severity-coder
description: Compute iRAP Roadside severity coding for driver side, passenger side, or both sides by orchestrating GroundingDINO object detection, 2D-to-3D projection, and pointcloud distance workflows. Use when a task needs paired RS_D (distance) and RS_O (object) codes with highest-risk selection from the provided hierarchy.
---

# iRAP Roadside Severity Coder

Code the two linked iRAP attributes:

1. `Roadside severity - side distance` (RS_D)
2. `Roadside severity - side object` (RS_O)

Use this skill when both attributes must be computed together and kept consistent as one selected object-distance pair, for one side (`driver` or `passenger`) or both sides.

Read [input contract](references/input_contract.md) before running.
For passenger-side object work, read `$irap-roadside-groundingdino/references/passenger_side_object_workflow.md` before detection.

## Dependency Skills

Use these repository skills in this order:

1. `$irap-roadside-groundingdino`
2. `$projection-dataflow-router`
3. `$pointcloud-multistep-processor`

Optional supplementary detector:

4. Open Images YOLO (`artifacts/streetlight_model_pilot_2026-10-08/yolov8x-oiv7.pt`)

This skill wraps that sequence in one script and then applies iRAP coding IDs and risk-priority selection.

## Workflow

1. Detect potential roadside objects per side from panorama image(s).
2. Optionally use the Open Images YOLO detector as a supplementary candidate generator for `Tree`, `Building`, `Traffic sign`, and `Street light` detections. Keep this evidence separate from GroundingDINO until side assignment, confidence and visual relevance have been checked.
3. Project each object bbox to LAS point indices.
4. Compute object-to-reference distance (reference is road by default. Road must be segmented to get this reference).
5. Convert numeric distance to category (`0 to <1m`, `1 to <5m`, `5 to <10m`, `>=10m`).
6. Select highest risk pair using [risk hierarchy](references/risk_hierarchy.csv).
7. Emit paired codes:
- RS_D distance Cat ID from [cat_ids.json](references/cat_ids.json)
- RS_O object Cat ID from [cat_ids.json](references/cat_ids.json)
8. Save bounding-box visualization image(s) with labels from GroundingDINO and any supplementary detector evidence.
9. Save an explainability JSON with concise natural-language summaries for detection, projection, distance, and final selection.

### Passenger-only mode

When the requested attribute is `Roadside severity - passenger side object`, process only the passenger-side left forward crop for this dataset. Confirm travel direction and carriageway layout first, then exclude the center/vehicle region, right roadside, median, and opposite carriageway. Keep each passenger-side object's bbox, projected points, distance, and selected iRAP code as one linked candidate; never combine an object from one candidate with the distance of another.

Validate panorama horizontal orientation per dataset folder before projection. The current pilot indicates `flip_pano_u=true` for `01_N3` and `07_N118`, and `flip_pano_u=false` for `05_N365 NORTE` and `16_N243`. Treat these as folder-level calibration results, not a universal rule; folders without valid lookup/LAS coverage remain unresolved.

## Command

```powershell
& .\.venv\Scripts\python.exe .\.agents\skills\irap-roadside-severity-coder\scripts\roadside_severity_router.py `
  --input-json ".\.agents\skills\irap-roadside-severity-coder\references\example_input.json" `
  --out-json "artifacts\irap_roadside_severity\coded_results.json"
```

## Output Rules

1. Keep RS_D and RS_O codes tied to the same selected candidate object.
2. Use exact Cat ID mappings from `references/cat_ids.json`.
3. Use risk ranking from `references/risk_hierarchy.csv`.
4. Keep per-side candidate evidence in `candidates_considered` for traceability.
5. If no valid candidate exists for a side, return `No object` + `>=10m`.
6. Return a bbox visualization artifact list and an explainability JSON artifact path.
7. Do not let adjacent-frame smoothing or late semantic overrides replace a projected object-distance pair unless the replacement has equal or stronger side-specific evidence. If a post-process changes RS_O, record the previous code and the reason.
8. Treat terrain classes (`Upwards slope`, `Downwards slope`, `Deep drainage ditch`) as low-reliability monocular detections when they overlap or compete with a clear road-edge safety barrier. A barrier may shield the underlying slope/ditch; use bbox shape, side crop position, projection support, and adjacent frames before promoting terrain over a barrier.
9. Do not promote the Open Images YOLO roadside route to the primary coder without local validation. Its broad classes do not directly represent barriers, slopes, cliffs or ditches, and the current 468-image experiment did not improve either side-object baseline. Use it only as corroborating evidence or for candidate review.
10. For metal-vs-concrete barrier ambiguity, prefer the visually consistent guardrail subtype only when the confidence gap is small and the bbox is a plausible road-edge barrier, not a wall, vehicle bodywork, or building facade.
11. In batch projection runs, keep the general object confidence threshold conservative. If lower thresholds are needed for driver-side guardrails, apply them only to driver-side barrier/rigid classes and require a projected guardrail-ribbon selection reason before accepting the low-confidence pair.
12. Apply adjacent-frame consistency to RS_D distance codes after frame-level measurement. Use a shorter driver-side window and a longer passenger-side window when processing regular 20m frame sequences; this reduces LAS edge jitter near the `0 to <1m` / `1 to <5m` boundary without changing object labels.
13. If LAS coverage or bbox-to-LAS projection is unavailable but side-specific image evidence/GroundingDINO finds a valid visible roadside object, do not default RS_D to `>=10m`. Use a low-confidence image-only fallback of `1 to <5m`, keep the RS_O object evidence attached, and mark the distance evidence as projection-unavailable.
14. In urban or commercial scenes, do not let noisy barrier detections suppress close discrete objects. Keep tree, pole/signpost, and rigid-structure candidates in the projected candidate set, then allow a guarded post-process to override a barrier label only when side-specific DINO confidence and local scene evidence support the discrete object.
15. Treat `Safety barrier - motorcycle friendly` as a weak generic barrier cue in batch mode. If it competes with slope/ditch, rigid structure, pole/signpost, or tree evidence, compare against stronger true-barrier classes (`metal`, `concrete`, `wire rope`) before accepting a barrier object code.
16. Treat `Unprotected safety barrier end`, `Safety barrier - motorcycle friendly`, and monocular slope classes as unstable batch labels. After normal projection/risk selection, run a guarded cleanup that can replace those labels only with stronger side-specific tree, pole/signpost, structure, or slope evidence; record the evidence string whenever this happens.
17. For driver-side object verification, allow a very high-confidence broad terrain candidate (`Upwards slope - roll over`, `Downwards slope`, or `Deep drainage ditch`) to override weak no-object, barrier, tree, pole, or structure selections only when the terrain bbox passes shape validation, confidence is at least `0.84`, and it exceeds the current selected class confidence by at least `0.12`. Record this as `high_confidence_driver_terrain`.

## Notes

1. The hierarchy includes one `Any` row for `Cliff`; it is applied to all distance buckets.
2. If a pair is missing in the hierarchy, use nearest available bucket rank for the same object and mark `rank_source` as fallback.
3. GroundingDINO terrain prompts are noisy on panoramic road edges. In batch mode, confidence-first candidate filtering followed by risk ranking has been more stable than pure risk-first selection unless projection confirms the object-distance pair.
4. Reliable projected driver-side pairs should be protected from later adjacent-frame smoothing and slope/discrete-object refinements; otherwise the projected object-distance pairing can be broken after selection.
5. Current batch default for RS_D smoothing is driver window `7`, passenger window `15`. Revisit only after evaluating several additional folders, not one folder at a time.
6. For mixed urban roadside scenes, lowering rigid/discrete object thresholds is acceptable when the output still records projected bbox-to-LAS support and downstream risk ranking. This helps prevent barriers, walls, and terrain masks from hiding true close poles, trees, and structures.
7. Barrier-end detections are high-risk in the iRAP hierarchy but can be false positives on ordinary guardrail or vegetation edges. Do not let a low-confidence barrier-end bbox dominate if tree/pole/structure evidence and side-crop vegetation/urban cues contradict it.
8. The promoted batch verifier is deliberately narrow: driver-side high-confidence terrain only. Broader barrier/discrete-object verifier rules were tested but not promoted because they reduced full-dataset roadside object accuracy.
