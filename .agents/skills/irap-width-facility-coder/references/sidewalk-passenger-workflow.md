# Passenger-Side Sidewalk Workflow

Use this workflow specifically for `Sidewalk - passenger side`. It addresses the demonstrated failure mode where high overall accuracy hides near-zero recall for minority sidewalk/path classes.

## Resolve Orientation

- Confirm direction of travel and traffic convention.
- For this project's rear-facing panoramas under right-hand traffic, passenger side is the left side of the panorama.
- Do not borrow evidence from the driver/right side.

## Prepare Visual Evidence

Create two crops from every target panorama:

1. `passenger_context`: left 50%, full height, for side and carriageway context.
2. `passenger_focus`: outer-left 30%, full height, for surface, kerb, barrier, path, and separation details.

Run `scripts/prepare_sidewalk_passenger_crops.py`. Override `--passenger-side` when camera orientation differs.

Inspect the target frame plus adjacent passenger crops covering the coded segment. A single image may establish presence but not continuity.

## Semantic Inference Requirement

Populate `facility_present`, `facility_type`, `continuous_over_segment`, `barrier_restrains_vehicle`, and the facility-edge evidence with one of:

- sidewalk-specific VLM inference over the full panorama plus passenger crops;
- sidewalk/pedestrian-facility segmentation followed by semantic validation;
- combined VLM and segmentation evidence;
- manual review.

Color ratios, texture ratios, generic pavement masks, and GroundingDINO detections may propose regions but must not finalize these fields. Overlapping sidewalk/barrier detections are not proof of a vehicle-restraining barrier.

If the semantic stage cannot support a class, set `review_required=true` and do not emit a final Cat ID.

## Stage A: Presence And Facility Type

Ask in order:

1. Is a pedestrian-use corridor visible on the passenger side?
2. Is it continuous over the coded segment?
3. Is it purpose-built with a reliable all-weather walking surface?
4. If not purpose-built, is there pedestrian-flow evidence forming an informal path?
5. If partly blocked, can pedestrians remain off the roadway?
6. Is the candidate actually a shoulder, parking bay, driveway apron, crossing island, verge, road lane, or cycle-only facility?

Decision:

- Formal, continuous, all-weather pedestrian facility -> `sidewalk`.
- Non-purpose-built route with pedestrian-flow evidence, or partly blocked sidewalk that keeps pedestrians off-road -> `informal_path`.
- No continuous usable pedestrian facility -> Cat ID 5 `None`.

Do not use urban/rural area type to answer this stage.

## Stage B: Barrier And Distance

For a confirmed sidewalk/path:

1. Check for a physical barrier capable of restraining a vehicle. A kerb alone does not qualify.
2. Qualifying barrier -> Cat ID 1.
3. Otherwise measure from the nearest driving-lane edge to the near edge of the facility, including shoulder and parking width.
4. Formal sidewalk: `>=3m` -> 2; `1m to <3m` -> 3; `0m to <1m` -> 4.
5. Informal path: `>=1m` -> 6; `0m to <1m` -> 7.

Never infer a bucket from class prevalence. If distance cannot be measured, document a visual estimate with lower confidence or route to review.

## Negative Evidence Required For None

Before Cat ID 5, record:

- passenger crop reviewed;
- segment continuity reviewed;
- no formal sidewalk confirmed;
- no informal path confirmed;
- shoulder, verge, driveway, crossing, parking, and cycle-only alternatives checked;
- occlusion or image-quality limitations.

## Class-Aware Quality Control

After freezing predictions, report confusion matrix and precision/recall/F1 for Cat IDs 1-7. Inspect every class with zero recall. Prioritize false negatives from classes 1, 4, 6, and 7 before tuning overall accuracy. Classes 2 and 3 have very low support, so report raw counts alongside F1.

Promotion gate: do not promote when blind evaluation shows majority-class recall collapse, broad false-positive facility detection, or a Macro-F1 regression. The failed 468-image run demonstrates that recovering minority candidates is not sufficient when facility-presence precision is poor.

Do not expose ground-truth labels to the prediction agent. Use ground truth only after predictions are frozen.
