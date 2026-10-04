from pathlib import Path

from skill_framework.registry import load_skill_registry
from validators.skill_inputs import validate_skill_inputs


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill_registry" / "registry.yaml"


def test_preliminary_load_required_inputs_validate():
    registry = load_skill_registry(REGISTRY_PATH)
    definition = registry.get("preliminary_load_estimation")

    errors = validate_skill_inputs(
        {
            "building_type": "office",
            "area_sqft": 10000,
            "climate_zone": "Delhi",
        },
        definition,
    )

    assert errors == []


def test_required_input_is_reported():
    registry = load_skill_registry(REGISTRY_PATH)
    definition = registry.get("preliminary_load_estimation")

    errors = validate_skill_inputs(
        {
            "building_type": "office",
            "area_sqft": 10000,
        },
        definition,
    )

    assert "Missing required input: climate_zone" in errors


def test_allowed_value_is_reported():
    registry = load_skill_registry(REGISTRY_PATH)
    definition = registry.get("duct_sizing")

    errors = validate_skill_inputs(
        {
            "airflow": 5000,
            "method": "invalid_method",
            "duct_type": "round",
        },
        definition,
    )

    assert any("invalid value: method" in error for error in errors)


def test_rectangular_sizing_does_not_require_dimensions():
    registry = load_skill_registry(REGISTRY_PATH)
    definition = registry.get("duct_sizing")

    errors = validate_skill_inputs(
        {
            "airflow": 5000,
            "method": "velocity",
            "duct_type": "rectangular",
            "target_velocity_ms": 7,
        },
        definition,
    )

    assert errors == []


def test_conditional_round_inputs_are_not_required_for_rectangular():
    registry = load_skill_registry(REGISTRY_PATH)
    definition = registry.get("duct_sizing")

    errors = validate_skill_inputs(
        {
            "airflow": 5000,
            "method": "velocity",
            "duct_type": "rectangular",
            "width_mm": 500,
            "height_mm": 300,
        },
        definition,
    )

    assert errors == []


def test_wrong_data_type_is_reported():
    registry = load_skill_registry(REGISTRY_PATH)
    definition = registry.get("preliminary_load_estimation")

    errors = validate_skill_inputs(
        {
            "building_type": "office",
            "area_sqft": "10000",
            "climate_zone": "Delhi",
        },
        definition,
    )

    assert any("invalid type: area_sqft" in error for error in errors)
