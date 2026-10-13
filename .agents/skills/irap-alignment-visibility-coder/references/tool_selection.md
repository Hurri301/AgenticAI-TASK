# Tool Selection

Curvature and sight distance need different evidence. Select tools by the attribute and available geometry.

## Decision Rules

| Situation | Select | Reason |
| --- | --- | --- |
| User provides exact `code` or `label` | Router only | Normalizes Cat ID and trace. |
| User provides `curvature_class`, `radius_m`, or `geometry_metrics` | Router only, plus note rule source | Structured geometry/class evidence can be mapped directly. |
| Trajectory/GPS points are available for Curvature | Trajectory geometry script or existing metrics | Curvature is better estimated from path geometry than panorama distortion. |
| Only panorama is available for Curvature | `$panoramic-road-safety-describer` visual class | Acceptable for pilot coding, but confidence should be lower. |
| Sight distance has forward image/adjacent frames | Visual forward-path review | Current repo has no mature line-of-sight engine. |
| Sight distance needs geometric proof | Optional `$projection-dataflow-router` with projected path/occluder evidence | Use only when the task explicitly needs geometric support. |

## Attribute-Specific Tool Choice

- `Curvature`: prefer trajectory/GPS heading change or fitted radius; use visual evidence to reject intersections/roundabouts.
- `Sight distance`: prefer forward-view and adjacent-frame evidence; use geometry only as support.

## What Not To Select

- Do not rely on pointcloud tools for routine Curvature unless a path geometry workflow is explicitly available.
- Do not mark Sight distance Poor from temporary vehicles alone.
