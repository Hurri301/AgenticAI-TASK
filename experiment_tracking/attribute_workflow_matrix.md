# Step 2 Attribute-to-Tool Workflow Matrix

Created: 2026-05-06  
Reviewed: 2026-05-13  
Planner window: 4-8 May  
Goal: map each selected iRAP road attribute to available tools, required inputs, expected outputs, and a candidate workflow.

## Simple Meaning of This Step

Your professor is asking you to prove that each selected iRAP attribute has a believable coding route. At this stage, we do not need perfect final accuracy for every attribute. We need a clear matrix that says:

- what the manual asks us to code,
- what data we need,
- which tool can help,
- what output we will produce,
- and whether the workflow is already runnable or still needs implementation.

The decision gate is: can every selected attribute be connected to at least one plausible workflow?

## Input Sources

| Source | Purpose |
| --- | --- |
| iRAP Coding Manual, Drive on Left | Defines the attribute meanings and coding criteria. |
| `GroundTruth.csv` | Contains existing labels/columns for the focused attributes. |
| Panorama images | Visual evidence for roadside objects, lighting, shoulders, markings, service roads, access points, and area context. |
| LAS point clouds | 3D distance/geometry evidence for roadside distance, lane/road width, and possible curvature support. |
| `lookup_dataset_filtered_corrected.csv` | Links panorama image frame numbers to LAS/trajectory position. |
| Existing projection scripts | Connect 2D image boxes to 3D point-cloud points. |
| GroundingDINO setup | Detects described roadside objects in images. |

## Attribute Matrix

| Attribute | Manual meaning in simple words | Existing GT column | Data needed | Available / candidate tool | Candidate workflow | Expected output | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Area type | Decide whether the road environment is urban, rural, or similar area context. | `Area type` | Panorama image, nearby scene context, maybe manual label examples. | Vision description skill + manual rules. | Describe scene context from panorama, check buildings/access/activity density, then map to iRAP area type. | Area type code + short evidence note. | Plausible; needs classifier/prompt validation. |
| Number of lanes | Count traffic lanes in the coded direction/road section. | `Number of lanes` | Panorama image, lane markings, road edges, possibly point cloud road width. | Vision/manual review now; future lane detector. | Detect lane markings/visible lanes, cross-check with road width when possible, then assign lane count. | Lane count code/value. | Needs implementation. |
| Lane width | Estimate/categorize width of traffic lanes. | `Lane width` | Road edges/lane boundaries from image or LAS, camera/LAS projection. | Projection + point cloud geometry; future lane-boundary detection. | Detect lane or road boundaries, project to 3D, measure lateral distance, divide by lane count if needed. | Lane width category/code. | Needs implementation. |
| Street lighting | Record if sufficient road lighting is present. | `Street lighting` | Panorama image. | GroundingDINO or vision descriptor. | Search image for streetlights/light poles; verify they are relevant to roadway, then code present/not present. | Present/not-present code + detected evidence. | Plausible; needs detector prompts. |
| Service road | Record if a parallel service/frontage road exists beside the main carriageway. | `Service road` | Panorama image, road layout context. | Vision descriptor + projection if distance/layout needed. | Look for parallel carriageway separated from main road; avoid coding the main carriageway itself as service road. | Present/not-present code. | Plausible; needs visual workflow test. |
| Sight distance | Judge whether forward visibility is adequate for the road/speed context. | `Sight distance` | Forward panorama view, road curvature/crest/occlusion, speed context if available. | Vision descriptor now; future geometry visibility estimator. | Identify whether the driver can see enough roadway ahead; mark poor when visibility is blocked by curve, crest, vegetation, structures, or geometry. | Poor/adequate code + reason. | High-risk; needs pilot definition. |
| Median Type | Identify the type of median or separation between opposing traffic streams. | `Median Type` | Panorama image, road layout. | Vision descriptor + object detection for barriers/markings. | Detect whether road is divided, painted median, physical median, barrier, or no median; map to manual code. | Median type code. | Plausible; needs prompt/code mapping. |
| Delineation | Judge whether road markings/signs/guideposts give adequate guidance. | `Delineation` | Panorama image. | Vision descriptor + possible line/sign detector. | Check lane/edge/center lines, guideposts, studs/markers, and signs; code adequate or poor. | Adequate/poor code + evidence. | Plausible; needs repeatable criteria. |
| Roadside severity - driver side object | Identify the most safety-critical roadside object on the driver side. | `Roadside severity - driver side object` | Driver-side image crop, object prompts, manual severity hierarchy. | `irap-roadside-groundingdino` skill. | Crop/select driver side, run GroundingDINO with iRAP roadside object prompts, map detected object to iRAP object category. | RS_O driver-side object code + bbox/confidence. | Ready; already smoke-tested. |
| Roadside severity - passenger side object | Identify the most safety-critical roadside object on the passenger side. | `Roadside severity - passenger side object` | Passenger-side image crop, object prompts, manual severity hierarchy. | `irap-roadside-groundingdino` skill. | Crop/select passenger side, run GroundingDINO with iRAP roadside object prompts, map detected object to iRAP object category. | RS_O passenger-side object code + bbox/confidence. | Ready; already smoke-tested. |
| Roadside severity - drivers side distance | Measure distance from road edge to driver-side roadside object. | `Roadside severity - drivers side distance` | Object bbox, projected LAS points, road/ground segmentation. | `projection-dataflow-router` + `pointcloud-multistep-processor`. | Detect object bbox, project bbox to LAS points, segment road cloud, compute minimum object-to-road distance, map distance bin to iRAP code. | RS_D driver-side distance code + meters. | Ready for demo; needs quality validation. |
| Roadside severity - passenger side distance | Measure distance from road edge to passenger-side roadside object. | `Roadside severity - passenger side distance` | Object bbox, projected LAS points, road/ground segmentation. | `projection-dataflow-router` + `pointcloud-multistep-processor`. | Detect object bbox, project bbox to LAS points, segment road cloud, compute minimum object-to-road distance, map distance bin to iRAP code. | RS_D passenger-side distance code + meters. | Ready for demo; needs quality validation. |
| Paved shoulder - drivers side | Record paved shoulder presence/width on driver side, usually within about 2 m of travel lane edge. | `Paved shoulder - drivers side` | Driver-side panorama, road edge/shoulder boundary, LAS if measuring width. | Vision descriptor + future shoulder width measurement. | Detect paved strip outside travel lane; if measurable, project boundaries to 3D and estimate width/category. | Driver-side shoulder code + evidence. | Plausible; needs measurement workflow. |
| Paved shoulder - passenger side | Record paved shoulder presence/width on passenger side, usually within about 2 m of travel lane edge. | `Paved shoulder - passenger side` | Passenger-side panorama, road edge/shoulder boundary, LAS if measuring width. | Vision descriptor + future shoulder width measurement. | Detect paved strip outside travel lane; if measurable, project boundaries to 3D and estimate width/category. | Passenger-side shoulder code + evidence. | Plausible; needs measurement workflow. |
| Property access points | Count or categorize driveways/access connections entering the road. | `Property access points` | Panorama image, side views, possible sequence of adjacent frames. | Vision descriptor + object/layout detection. | Detect driveways, gates, minor entrances, side roads, or accesses within the coded segment; count/category using manual rule. | Access point category/code. | Plausible; needs sequence-based test. |
| Curvature | Code horizontal road curvature/straightness over the road section. | `Curvature` | Trajectory/GPS path, panorama forward view. | Future trajectory geometry script. | Use consecutive trajectory points to estimate curve radius/change in heading, then map to iRAP curvature classes; use image as sanity check. | Curvature code + geometric evidence. | Strong candidate; needs script. |
| Sidewalk - passenger side | Record whether a pedestrian sidewalk/path facility is present on the passenger side and whether it is relevant to the coded road segment. | `Sidewalk - passenger side` | Passenger-side panorama crop, roadside layout context, possible adjacent frames. | Vision descriptor + object/layout prompts; optional projection if separating sidewalk from shoulder/road edge is ambiguous. | Inspect passenger-side crop for a raised kerb, paved pedestrian path, separated footway, or no pedestrian facility; map the observation to the iRAP sidewalk codebook. | Passenger-side sidewalk code + evidence note. | Plausible; needs prompt/code mapping and pilot validation. |

## Workflow Groups

| Group | Attributes | Main idea | Current confidence |
| --- | --- | --- | --- |
| Already executable roadside pipeline | Roadside severity objects and distances | GroundingDINO finds object boxes; projection links boxes to LAS points; point cloud measures distance. | High for demonstration, medium for final accuracy. |
| Image-based visual coding | Area type, street lighting, service road, median type, delineation, paved shoulder, property access points, sidewalk passenger side | Use panorama evidence and manual rules; add object prompts where useful. | Medium; needs repeatable prompt/rule templates. |
| Geometry-based coding | Lane width, curvature, roadside distances | Use trajectory, LAS, and projection to measure physical quantities. | Medium; roadside distance works, lane width/curvature need scripts. |
| Hard visibility coding | Sight distance | Needs road geometry, occlusion reasoning, and speed threshold context. | Low to medium; should be treated as a pilot attribute first. |

## Immediate Step-by-Step Plan

1. Lock the focused attribute list in this matrix.
2. For each attribute, copy the exact coding options from the iRAP manual into a codebook table.
3. Check `GroundTruth.csv` unique values for each attribute, so our outputs match the dataset labels.
4. Start with the already working roadside severity pipeline and create 3-5 reproducible examples.
5. Build simple visual prompt templates for street lighting, service road, median type, delineation, paved shoulder, area type, and property access points.
6. Build one small geometry script for curvature from trajectory points.
7. Build one lane/shoulder measurement pilot using image-to-point-cloud projection.
8. Treat sight distance as a separate pilot, because it is less direct than the others.

## Decision Gate Answer

Yes, every selected attribute has at least one plausible workflow. The strongest workflow today is roadside severity object/distance. The next strongest are visual attributes that can be coded from panoramas with manual rules. The attributes needing new implementation are lane width, curvature, and sight distance.
