from pathlib import Path

import pytest

from mm_link.attribute_rules import (
    build_routing_plan,
    collect_data_availability,
    default_attribute_rules,
    route_attribute,
)


def test_las_measurement_attributes_are_not_image_final():
    rules = default_attribute_rules()

    for name in (
        "Lane width",
        "Roadside severity - drivers side distance",
        "Roadside severity - passenger side distance",
        "Paved shoulder - drivers side",
        "Paved shoulder - passenger side",
    ):
        rule = rules[name]
        assert rule.final_source == "las_measurement"
        assert rule.requires_measurement
        assert not rule.image_only_allowed


def test_street_lighting_gate_rejects_utility_poles_only():
    rule = default_attribute_rules()["Street lighting"]
    gates = " ".join(rule.evidence_gates).lower()

    assert "luminaire" in gates
    assert "utility poles" in gates
    assert "do not count" in gates


def test_urban_one_way_overfit_is_guarded():
    rules = default_attribute_rules()

    lane_gates = " ".join(rules["Number of lanes"].evidence_gates).lower()
    median_gates = " ".join(rules["Median Type"].evidence_gates).lower()

    assert "do not code one-way" in lane_gates
    assert "strong one-way evidence" in median_gates
    assert "prefer centre-line" in median_gates


def test_sidewalk_requires_passenger_crop_and_does_not_use_kerb_as_barrier():
    rule = default_attribute_rules()["Sidewalk - passenger side"]
    gates = " ".join(rule.evidence_gates).lower()

    assert "passenger context" in gates
    assert "full panorama alone" in gates
    assert "kerb alone is not a physical barrier" in gates
    assert "do not default missing distance" in gates
    assert "color/texture heuristics" in gates


def test_route_blocks_measurement_when_las_missing(tmp_path: Path):
    image = tmp_path / "Portugal-16_000_601.jpg"
    image.write_bytes(b"not a real image, only path existence matters")
    availability = collect_data_availability(image, tmp_path / "Dataset")
    routed = route_attribute(default_attribute_rules()["Lane width"], availability)

    assert routed.status == "blocked"
    assert "LAS point cloud" in routed.missing_inputs


def test_route_plan_finds_route_16_context():
    image = Path("Dataset/16_N243/from-16/Portugal-16_000_601.jpg")
    if not image.exists():
        pytest.skip("Full 468-observation dataset is not included in the public repository")
    plan = build_routing_plan(image, "Dataset")

    assert len(plan["attributes"]) == 17
    assert plan["data_availability"]["folder_name"] == "16_N243"
    assert plan["data_availability"]["frame_id"] == 601
    assert plan["data_availability"]["las_paths"]
    assert plan["data_availability"]["trajectory_paths"] or plan["data_availability"]["gps_info_paths"]
    assert plan["status_counts"]["ready_for_measurement"] >= 5
