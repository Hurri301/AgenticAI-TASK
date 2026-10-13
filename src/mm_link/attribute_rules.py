from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SELECTED_ATTRIBUTES = [
    "Area type",
    "Number of lanes",
    "Lane width",
    "Street lighting",
    "Service road",
    "Sight distance",
    "Median Type",
    "Delineation",
    "Roadside severity - driver side object",
    "Roadside severity - passenger side object",
    "Roadside severity - drivers side distance",
    "Roadside severity - passenger side distance",
    "Paved shoulder - drivers side",
    "Paved shoulder - passenger side",
    "Property access points",
    "Curvature",
    "Sidewalk - passenger side",
]


@dataclass(frozen=True)
class AttributeRule:
    attribute: str
    primary_source: str
    allowed_sources: tuple[str, ...]
    final_source: str
    tools: tuple[str, ...]
    output_codes: dict[int, str]
    evidence_gates: tuple[str, ...]
    fallback_policy: str
    image_only_allowed: bool
    requires_measurement: bool = False
    notes: str = ""


@dataclass(frozen=True)
class DataAvailability:
    image_path: str
    image_exists: bool
    folder_name: str | None = None
    frame_id: int | None = None
    dataset_dir: str | None = None
    las_paths: tuple[str, ...] = ()
    trajectory_paths: tuple[str, ...] = ()
    gps_info_paths: tuple[str, ...] = ()

    @property
    def has_las(self) -> bool:
        return bool(self.las_paths)

    @property
    def has_trajectory(self) -> bool:
        return bool(self.trajectory_paths or self.gps_info_paths)


@dataclass(frozen=True)
class RoutedAttribute:
    attribute: str
    status: str
    primary_source: str
    final_source: str
    tools: tuple[str, ...]
    evidence_gates: tuple[str, ...]
    fallback_policy: str
    image_only_allowed: bool
    requires_measurement: bool
    missing_inputs: tuple[str, ...] = ()
    output_codes: dict[int, str] = field(default_factory=dict)
    notes: str = ""


def default_attribute_rules() -> dict[str, AttributeRule]:
    roadside_object_codes = {
        1: "Safety barrier - metal",
        2: "Safety barrier - concrete",
        3: "Safety barrier - motorcycle friendly",
        4: "Safety barrier - wire rope",
        5: "Aggressive vertical face",
        6: "Upwards slope",
        7: "Upwards slope >=75 degrees",
        8: "Deep drainage ditch",
        9: "Downwards slope",
        10: "Cliff",
        11: "Tree >=10cm",
        12: "Non-frangible sign/post/pole >=10cm",
        13: "Rigid structure / bridge / building",
        14: "Semi-rigid structure / building",
        15: "Unprotected safety barrier end",
        16: "Large boulders >=20cm high",
        17: "No object",
    }
    roadside_distance_codes = {1: "0 to <1m", 2: "1 to <5m", 3: "5 to <10m", 4: ">=10m"}
    shoulder_codes = {
        1: "Wide (>=2.4m)",
        2: "Medium (>=1.0m to <2.4m)",
        3: "Narrow (>=0m to <1.0m)",
        4: "None",
    }

    rules = [
        AttributeRule(
            "Area type",
            "visual_scene",
            ("visual_scene", "segment_context"),
            "visual_scene",
            ("panoramic-road-safety-describer",),
            {1: "Rural", 2: "Urban"},
            (
                "Use full-panorama land use and nearby-frame context.",
                "Class urban only when built-up frontage, kerbs, commercial/residential density, or village street context dominates.",
            ),
            "If peri-urban evidence is mixed, mark low confidence and use adjacent frames before final coding.",
            True,
        ),
        AttributeRule(
            "Number of lanes",
            "segment_context",
            ("visual_scene", "segment_context", "las_measurement"),
            "segment_context",
            ("panoramic-road-safety-describer", "road/lane marking detector", "optional LAS road-width cross-check"),
            {1: "One", 2: "Two", 3: "Three", 4: "Four or more"},
            (
                "Count usable travel lanes/directions, not only visible painted lane markings.",
                "Do not code one-way unless signs, lane arrows, road topology, or sequence context strongly support it.",
                "Use nearby frames when panorama distortion hides the opposing lane.",
            ),
            "If lane count is uncertain, keep a provisional segment-context result and route lane width to LAS.",
            True,
        ),
        AttributeRule(
            "Lane width",
            "las_measurement",
            ("visual_scene", "las_measurement"),
            "las_measurement",
            ("projection-dataflow-router", "pointcloud-multistep-processor"),
            {1: "Wide (>=3.25m)", 2: "Medium (>=2.75m to <3.25m)", 3: "Narrow (>=0m to <2.75m)"},
            (
                "Final code requires measured lateral width from road/lane boundaries.",
                "Image-only estimates are provisional and must be flagged low confidence.",
            ),
            "If LAS boundary extraction fails, estimate from segmented road width divided by lane count and mark provisional.",
            False,
            True,
        ),
        AttributeRule(
            "Street lighting",
            "visual_detection",
            ("visual_detection", "segment_context"),
            "visual_detection",
            ("GroundingDINO or visual detector", "panoramic-road-safety-describer"),
            {1: "Not present", 2: "Present"},
            (
                "Require visible luminaire/light head or roadway lighting fixture.",
                "Do not count utility poles, overhead wires, traffic signs, or building-mounted non-road fixtures by themselves.",
                "Use adjacent frames if a pole is occluded or cropped.",
            ),
            "When only poles/wires are visible, code not present unless a lamp head is confirmed.",
            True,
        ),
        AttributeRule(
            "Service road",
            "visual_scene",
            ("visual_scene", "segment_context"),
            "visual_scene",
            ("panoramic-road-safety-describer",),
            {1: "Not present", 2: "Present"},
            (
                "Look for a parallel frontage/service road separated from the main carriageway.",
                "Do not count side streets, driveways, or parking bays as service roads.",
            ),
            "Use adjacent frames for complex junctions.",
            True,
        ),
        AttributeRule(
            "Sight distance",
            "trajectory_context",
            ("visual_scene", "trajectory_context"),
            "trajectory_context",
            ("panoramic-road-safety-describer", "trajectory curvature/visibility script"),
            {1: "Adequate", 2: "Poor"},
            (
                "Use visual obstruction plus heading/crest/curve context.",
                "Code poor only when road ahead is materially hidden by curve, crest, vegetation, structures, or parked vehicles.",
            ),
            "If trajectory is unavailable, produce visual provisional result.",
            True,
        ),
        AttributeRule(
            "Median Type",
            "visual_scene",
            ("visual_scene", "visual_detection", "segment_context"),
            "visual_scene",
            ("panoramic-road-safety-describer", "barrier/median detector"),
            {1: "Safety barrier - metal", 2: "Safety barrier - concrete", 11: "Centre line", 13: "One way"},
            (
                "Detect physical median/barrier first.",
                "For undivided roads without strong one-way evidence, prefer centre-line/undivided class over one-way fallback.",
                "Only use one-way when road signs, lane arrows, topology, or sequence context support it.",
            ),
            "When no physical median is visible, use undivided/centre-line unless one-way evidence is strong.",
            True,
        ),
        AttributeRule(
            "Delineation",
            "visual_scene",
            ("visual_scene", "visual_detection"),
            "visual_scene",
            ("panoramic-road-safety-describer", "marking/sign detector"),
            {1: "Adequate", 2: "Poor"},
            (
                "Accept centre line, edge line, kerb guidance, guideposts, signs, and road-edge contrast as delineation evidence.",
                "Do not require delineator posts if markings/kerbs provide adequate guidance.",
            ),
            "If markings are occluded, inspect adjacent frames.",
            True,
        ),
        AttributeRule(
            "Roadside severity - driver side object",
            "visual_detection",
            ("visual_detection", "segment_context", "las_measurement"),
            "visual_detection",
            ("irap-roadside-groundingdino", "irap-roadside-severity-coder"),
            roadside_object_codes,
            (
                "Use driver-side/right-half candidates under the project orientation model.",
                "Select the closest/highest-risk fixed roadside object; buildings/walls can be valid rigid structures.",
                "Ignore movable vehicles unless they obscure a fixed object.",
            ),
            "If detector misses objects, use side-aware visual description and mark manual-review candidate.",
            True,
        ),
        AttributeRule(
            "Roadside severity - passenger side object",
            "visual_detection",
            ("visual_detection", "segment_context", "las_measurement"),
            "visual_detection",
            ("irap-roadside-groundingdino", "irap-roadside-severity-coder"),
            roadside_object_codes,
            (
                "Use passenger-side/left-half candidates under the project orientation model.",
                "Select the closest/highest-risk fixed roadside object; buildings/walls can be valid rigid structures.",
                "Trees >=10cm, poles, walls, buildings, barriers, and ditches must be ranked by risk hierarchy.",
            ),
            "If detector misses objects, use side-aware visual description and mark manual-review candidate.",
            True,
        ),
        AttributeRule(
            "Roadside severity - drivers side distance",
            "las_measurement",
            ("visual_detection", "las_measurement"),
            "las_measurement",
            ("projection-dataflow-router", "pointcloud-multistep-processor", "irap-roadside-severity-coder"),
            roadside_distance_codes,
            (
                "Distance must be tied to the selected driver-side roadside object.",
                "Final code requires object bbox projection and object-to-road distance in LAS.",
                "Urban building frontage close to kerb should be checked for 0-<1m, not defaulted to 1-<5m.",
            ),
            "If projection fails, image-distance bucket is provisional and must be flagged.",
            False,
            True,
        ),
        AttributeRule(
            "Roadside severity - passenger side distance",
            "las_measurement",
            ("visual_detection", "las_measurement"),
            "las_measurement",
            ("projection-dataflow-router", "pointcloud-multistep-processor", "irap-roadside-severity-coder"),
            roadside_distance_codes,
            (
                "Distance must be tied to the selected passenger-side roadside object.",
                "Final code requires object bbox projection and object-to-road distance in LAS.",
                "Urban walls/frontage close to kerb should be checked for 0-<1m, not defaulted to 1-<5m.",
            ),
            "If projection fails, image-distance bucket is provisional and must be flagged.",
            False,
            True,
        ),
        AttributeRule(
            "Paved shoulder - drivers side",
            "las_measurement",
            ("visual_scene", "las_measurement"),
            "las_measurement",
            ("panoramic-road-safety-describer", "projection-dataflow-router", "pointcloud-multistep-processor"),
            shoulder_codes,
            (
                "Separate paved shoulder from sidewalk, parking bay, and travel lane.",
                "Narrow paved edge/strip may code as narrow; do not collapse all urban kerb edges to none.",
                "Final code should use side-specific width measurement where possible.",
            ),
            "Visual-only shoulder class is provisional unless width class is obvious.",
            False,
            True,
        ),
        AttributeRule(
            "Paved shoulder - passenger side",
            "las_measurement",
            ("visual_scene", "las_measurement"),
            "las_measurement",
            ("panoramic-road-safety-describer", "projection-dataflow-router", "pointcloud-multistep-processor"),
            shoulder_codes,
            (
                "Separate paved shoulder from sidewalk, parking bay, and travel lane.",
                "Narrow paved edge/strip may code as narrow; do not collapse all urban kerb edges to none.",
                "Final code should use side-specific width measurement where possible.",
            ),
            "Visual-only shoulder class is provisional unless width class is obvious.",
            False,
            True,
        ),
        AttributeRule(
            "Property access points",
            "segment_context",
            ("visual_scene", "segment_context"),
            "segment_context",
            ("panoramic-road-safety-describer", "access/driveway detector"),
            {1: "Commercial Access >=1", 2: "Residential Access >=3", 3: "Residential Access <3", 4: "None"},
            (
                "Count driveways/gates/entrances across the coded segment, not only the target frame.",
                "Classify dominant/valid access type from the segment; do not let one shop sign override residential-access density.",
            ),
            "Use target frame plus at least one neighboring frame on each side before final coding.",
            True,
        ),
        AttributeRule(
            "Curvature",
            "trajectory_context",
            ("visual_scene", "trajectory_context"),
            "trajectory_context",
            ("trajectory curvature script", "pilot_curvature_from_lookup.py"),
            {1: "Straight or gently curving", 2: "Moderate", 3: "Sharp", 4: "Very sharp"},
            (
                "Compute heading change/radius over the coded segment from trajectory data.",
                "Use panorama only as a sanity check, not the final source when trajectory exists.",
            ),
            "If trajectory cannot be matched, produce visual provisional result.",
            True,
        ),
        AttributeRule(
            "Sidewalk - passenger side",
            "visual_scene",
            ("visual_scene", "segment_context", "las_measurement"),
            "visual_scene",
            ("panoramic-road-safety-describer", "optional projection-dataflow-router"),
            {
                1: "Physical barrier",
                2: "Non-physical separation >=3.0m",
                3: "Non-physical separation 1.0m to <3.0m",
                4: "Non-physical separation 0m to <1.0m",
                5: "None",
                6: "Informal path >=1.0m",
                7: "Informal path 0m to <1.0m",
            },
            (
                "For the project rear-facing panorama convention, inspect the left-side passenger context and road-edge focus crops; do not finalize from the full panorama alone.",
                "Require a continuous, walkable pedestrian facility on the passenger side and inspect adjacent frames when segment continuity is unclear.",
                "Distinguish formal sidewalk, informal path, paved shoulder, parking, driveway apron, verge, crossing, and cycle-only facility before coding.",
                "Populate facility presence, type, continuity, and barrier semantics with a sidewalk-specific VLM, segmentation model, or manual review; color/texture heuristics and detector boxes alone are insufficient.",
                "A kerb alone is not a physical barrier; Cat ID 1 requires a separator capable of restraining a vehicle.",
                "Use 3D/separation measurement only after presence and facility type are confirmed; measure from nearest driving-lane edge and include shoulder/parking width.",
                "Do not default missing distance to Cat ID 3 or 6 and do not use area type as a proxy for sidewalk presence.",
            ),
            "If crop, continuity, facility type, barrier, or distance evidence remains unresolved, route to review rather than forcing the dominant class.",
            True,
        ),
    ]
    return {rule.attribute: rule for rule in rules}


def frame_id_from_image_name(name: str) -> int | None:
    match = re.search(r"_(\d+)\.(?:png|jpg|jpeg)$", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def infer_folder_name(image_path: Path, dataset_dir: Path) -> str | None:
    try:
        relative = image_path.resolve().relative_to(dataset_dir.resolve())
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def collect_data_availability(image_path: str | Path, dataset_dir: str | Path = "Dataset") -> DataAvailability:
    image = Path(image_path)
    dataset = Path(dataset_dir)
    folder = infer_folder_name(image, dataset)

    las_paths: list[str] = []
    gps_paths: list[str] = []
    trajectory_paths: list[str] = []
    if folder:
        folder_dir = dataset / folder
        las_paths = [str(path) for path in sorted(folder_dir.rglob("*.las")) if "elipsoidal" not in path.name.lower()]
        gps_paths = [str(path) for path in sorted(folder_dir.rglob("*frame_gps_info*.txt"))]
        trajectory_root = dataset / "Trajectories"
        if trajectory_root.is_dir():
            event_match = re.search(r"(\d+)_", folder)
            event_id = event_match.group(1).lstrip("0") if event_match else folder
            trajectory_paths = [
                str(path)
                for path in sorted(trajectory_root.glob("*.txt"))
                if event_id and re.search(rf"(?:event[_ ]?{re.escape(event_id)}|_{re.escape(event_id)}\.)", path.name, re.IGNORECASE)
            ]
    return DataAvailability(
        image_path=str(image),
        image_exists=image.is_file(),
        folder_name=folder,
        frame_id=frame_id_from_image_name(image.name),
        dataset_dir=str(dataset),
        las_paths=tuple(las_paths),
        trajectory_paths=tuple(trajectory_paths),
        gps_info_paths=tuple(gps_paths),
    )


def route_attribute(rule: AttributeRule, availability: DataAvailability) -> RoutedAttribute:
    missing: list[str] = []
    if rule.final_source == "las_measurement" and not availability.has_las:
        missing.append("LAS point cloud")
    if rule.final_source == "trajectory_context" and not availability.has_trajectory:
        missing.append("trajectory/GPS context")
    if not availability.image_exists:
        missing.append("panorama image")

    if missing:
        status = "blocked" if not rule.image_only_allowed else "provisional"
    elif rule.requires_measurement:
        status = "ready_for_measurement"
    else:
        status = "ready"

    return RoutedAttribute(
        attribute=rule.attribute,
        status=status,
        primary_source=rule.primary_source,
        final_source=rule.final_source,
        tools=rule.tools,
        evidence_gates=rule.evidence_gates,
        fallback_policy=rule.fallback_policy,
        image_only_allowed=rule.image_only_allowed,
        requires_measurement=rule.requires_measurement,
        missing_inputs=tuple(missing),
        output_codes=rule.output_codes,
        notes=rule.notes,
    )


def build_routing_plan(image_path: str | Path, dataset_dir: str | Path = "Dataset") -> dict[str, Any]:
    availability = collect_data_availability(image_path, dataset_dir)
    rules = default_attribute_rules()
    routed = [route_attribute(rules[name], availability) for name in SELECTED_ATTRIBUTES]
    status_counts: dict[str, int] = {}
    for item in routed:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1

    return {
        "image_path": str(image_path),
        "dataset_dir": str(dataset_dir),
        "data_availability": asdict(availability),
        "status_counts": status_counts,
        "attributes": [asdict(item) for item in routed],
    }


def write_routing_plan(plan: dict[str, Any], out_json: Path, out_csv: Path | None = None) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    if not out_csv:
        return
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "attribute",
            "status",
            "primary_source",
            "final_source",
            "tools",
            "requires_measurement",
            "image_only_allowed",
            "missing_inputs",
            "fallback_policy",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in plan["attributes"]:
            row = dict(item)
            row["tools"] = " | ".join(row["tools"])
            row["missing_inputs"] = " | ".join(row["missing_inputs"])
            writer.writerow({key: row.get(key) for key in fieldnames})
