import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "irap-width-facility-coder"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


router = load_module("width_facility_router_updated", SKILL / "scripts" / "width_facility_router.py")
crops = load_module("sidewalk_passenger_crops", SKILL / "scripts" / "prepare_sidewalk_passenger_crops.py")


def reviewed(**overrides):
    item = {
        "side": "passenger",
        "semantic_inference_source": "vlm",
        "passenger_crop_reviewed": True,
        "continuous_segment_reviewed": True,
        "facility_present": True,
        "continuous_over_segment": True,
        "facility_type": "sidewalk",
        "purpose_built": True,
        "all_weather_surface": True,
        "barrier_present": False,
    }
    item.update(overrides)
    return item


def test_left_passenger_focus_crop_uses_outer_left_region():
    assert crops.crop_bounds(1236, 576, "left", 0.30) == (0, 0, 371, 576)


def test_curb_is_not_vehicle_restraining_barrier():
    warnings = []
    code, source, measured = router.sidewalk_code(
        reviewed(
            barrier_present=True,
            barrier_restrains_vehicle=False,
            curb_only=True,
            distance_from_road_m=0.4,
        ),
        warnings,
    )
    assert (code, source, measured) == (4, "distance_from_road_m", 0.4)
    assert warnings


def test_qualifying_barrier_has_priority_for_formal_sidewalk():
    code, source, _ = router.sidewalk_code(
        reviewed(barrier_present=True, barrier_restrains_vehicle=True, curb_only=False),
        [],
    )
    assert (code, source) == (1, "vehicle_restraining_barrier")


def test_missing_distance_does_not_default_to_class_three():
    with pytest.raises(ValueError, match="requires distance_from_road_m"):
        router.sidewalk_code(reviewed(), [])


@pytest.mark.parametrize(("distance", "expected"), [(1.2, 6), (0.6, 7)])
def test_informal_path_requires_evidence_and_uses_distance(distance, expected):
    code, _, _ = router.sidewalk_code(
        reviewed(
            facility_type="informal_path",
            purpose_built=False,
            pedestrian_flow_evidence=True,
            distance_from_road_m=distance,
        ),
        [],
    )
    assert code == expected


def test_none_requires_crop_and_segment_review():
    with pytest.raises(ValueError, match="passenger_crop_reviewed"):
        router.sidewalk_code(
            {"side": "passenger", "semantic_inference_source": "vlm", "none": True}, []
        )

    code, source, measured = router.sidewalk_code(
        {
            "side": "passenger",
            "semantic_inference_source": "vlm",
            "passenger_crop_reviewed": True,
            "continuous_segment_reviewed": True,
            "none": True,
        },
        [],
    )
    assert (code, source, measured) == (5, "passenger_crop_no_continuous_facility", None)


@pytest.mark.parametrize("source", [None, "color_texture_heuristic", "pixel_ratio"])
def test_nonsemantic_heuristics_cannot_finalize_sidewalk(source):
    item = reviewed(distance_from_road_m=0.4)
    item["semantic_inference_source"] = source
    with pytest.raises(ValueError, match="semantic_inference_source"):
        router.sidewalk_code(item, [])


def test_review_required_is_not_forced_to_a_class():
    with pytest.raises(ValueError, match="do not force"):
        router.sidewalk_code(reviewed(review_required=True, distance_from_road_m=0.4), [])
