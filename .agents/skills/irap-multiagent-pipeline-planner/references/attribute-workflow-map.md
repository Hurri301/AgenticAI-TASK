# Attribute Workflow Map

Use this reference when building the global workflow, attribute-to-tool matrix, or flowchart. Invoke the listed skill for actual coding because each attribute skill owns its full input contract, Cat ID mapping, and intermediate-output details.

## Shared Evidence Vocabulary

- `2D evidence`: panorama, side crop, zoom crop, adjacent frames, VLM scene description, object bbox.
- `3D evidence`: LAS point cloud, road/ground segmentation, cluster indices, distance measurement, width/offset measurement, trajectory/GPS geometry.
- `Fusion evidence`: semantic object or boundary from 2D plus metric support from projection/point-cloud measurement.
- `Trace`: segment ID, image IDs, coded direction, side, input payload, tool route, artifact paths, confidence, and failure/fallback notes.

## Attribute Summary Table

| Attribute group | Attributes | Best route | Primary skills | Crux of workflow | Critical validation |
|---|---|---|---|---|---|
| Visual/context | Area type, Street lighting, Service road, Delineation | 2D | `$panoramic-road-safety-describer`, `$irap-visual-context-coder` | Inspect the coded carriageway context and visible safety features; apply direct visual gates. | Reject false positives: poles without luminaires, shoulders/driveways as service roads, unrelated markings outside the coded path. |
| Carriageway layout | Number of lanes, Median Type | 2D with optional geometry | `$panoramic-road-safety-describer`, `$irap-carriageway-layout-coder`, optional `$projection-dataflow-router` | Count through lanes in coded direction and classify opposing-flow separation. | Exclude turn lanes, shoulders, parking lanes, slip lanes, and short changes under about 400 m. Prefer physical/barrier evidence over paint when both exist. |
| Width/facility | Lane width, Paved shoulder driver side, Paved shoulder passenger side, Sidewalk passenger side | Fusion | `$panoramic-road-safety-describer`, `$projection-dataflow-router`, `$pointcloud-multistep-processor`, `$irap-width-facility-coder` | Identify boundaries/facilities visually, project or measure when possible, convert width/offset to iRAP buckets. | Do not include shoulders/parking/slip lanes in lane width. Perform zoomed shoulder check before coding paved shoulder as `None`. Barrier sidewalk has priority. |
| Access points | Property access points | 2D segment review | `$panoramic-road-safety-describer`, `$irap-access-points-coder` | Inspect both sides across the coded segment and adjacent frames; classify private/commercial/residential vehicle accesses. | Reject public intersections, side roads, ramps, slip lanes, and service roads themselves. Commercial access has priority over residential count. |
| Alignment/visibility | Curvature, Sight distance | 3D/trajectory plus 2D sanity check | `$panoramic-road-safety-describer`, `$projection-dataflow-router`, `$irap-alignment-visibility-coder` | Use GPS/trajectory geometry for curvature when available; inspect forward travel path for persistent visibility restrictions. | Ignore intersection/roundabout bends when not mid-block alignment. Temporary vehicles reduce confidence rather than deciding sight distance. |
| Roadside severity | Roadside severity - side distance, Roadside severity - side object | Fusion | `$irap-roadside-groundingdino`, `$projection-dataflow-router`, `$pointcloud-multistep-processor`, `$irap-roadside-severity-coder` | Detect side-specific roadside objects, project bbox to LAS indices, measure distance to road/ground reference, select highest-risk object-distance pair. | Keep RS_D and RS_O tied to the same object. If no valid candidate exists, return `No object` plus `>=10m`. Use hierarchy ranking. |

## Category Crux By Attribute

Use exact Cat IDs from each attribute skill's `references/cat_ids.json` when producing final tables.

### Visual/context

- `Area type`: Rural vs Urban; decide from built-up frontage, urban street features, and land-use density.
- `Street lighting`: Not present vs Present; require visible lamp head/luminaire relevant to roadway.
- `Service road`: Not present vs Present; require a separate parallel frontage/service road.
- `Delineation`: Adequate vs Poor; judge visual guidance for the coded travel path from lines, kerbs, signs, posts, reflectors, or edge contrast.

### Carriageway layout

- `Number of lanes`: One, Two, Three, Four or more, Two and one, Three and two.
- `Median Type`: safety barrier variants, physical median width buckets, continuous turning lane, flexible posts, central hatching, centre line, one way, wide centre line.

### Width/facility

- `Lane width`: Wide `>=3.25m`, Medium `2.75m to <3.25m`, Narrow `0m to <2.75m`.
- `Paved shoulder - drivers/passenger side`: Wide `>=2.4m`, Medium `1m to <2.4m`, Narrow `0m to <1m`, None.
- `Sidewalk - passenger side`: sidewalk with barrier, sidewalk distance buckets `>=3m`, `1m to <3m`, `0m to <1m`, None, informal path `>=1m`, informal path `0m to <1m`.

### Access points

- `Property access points`: Commercial access `>=1`, Residential access `>=3`, Residential access `<3`, None.

### Alignment/visibility

- `Curvature`: Straight or gently curving, Moderate, Sharp, Very sharp.
- `Sight distance`: Adequate vs Poor; confidence should stay low unless evidence clearly supports the selected class.

### Roadside severity

- `Roadside severity - side distance`: `0 to <1m`, `1 to <5m`, `5 to <10m`, `>=10m`.
- `Roadside severity - side object`: Cliff; Tree `>=10cm`; Rigid sign/post/pole `>=10cm`; Unprotected safety barrier end; Aggressive vertical face; Upwards slope roll-over; Deep drainage ditch; Downwards slope; Low rigid object `>=20cm high`; Rigid structure/building; Upwards slope no roll-over; Semi-rigid structure/building; safety barrier variants; No object.

## Attribute Routing Decision

Use this decision order for each segment and requested attribute:

1. If the attribute can be decided from stable visible context, route to 2D.
2. If the attribute requires numeric width, offset, distance, trajectory, or line-of-sight geometry, route to 3D or fusion.
3. If semantic identity comes from the image and metric value comes from LAS, route to fusion.
4. If confidence is below the project threshold, run the fallback evidence path before finalizing.
5. If the fallback still fails, emit the best available code with low confidence and an explicit unresolved reason.

## Reusable Intermediate Products

Produce once per segment when possible and reuse across attributes:

- Scene description JSON for full panorama and side crops.
- Passenger and driver side crop metadata.
- Segment-level adjacent-frame review notes.
- Road/ground segmentation metadata.
- 2D-to-3D projection artifacts for bboxes and boundary points.
- Lane/road-edge boundaries.
- Object detection bboxes and labels.
- Trajectory/heading/radius metrics.
- Measurement artifacts for widths, offsets, and distances.
