from skill_framework.input_resolver import resolve_input_requirements
from skill_framework.registry import load_skill_registry
from governance.assumption_policy import resolve_input_assumptions

def test_pump_head_minor_missing_inputs_are_auto_assumed():
    registry = load_skill_registry("skill_registry/registry.yaml")
    definition = registry.get("pump_head")
    inputs = {
        "flow_m3hr": 25,
        "diameter_mm": 100,
        "straight_length_m": 50,
        "static_head_m": 20,
    }
    resolved, assumptions, blockers = resolve_input_assumptions("pump_head", inputs)
    assert not blockers
    assert resolved["material"] == "ms_cs"
    assert resolved["margin_pct"] == 10
    assert len(assumptions) == 2
    resolution = resolve_input_requirements(definition, resolved)
    assert resolution.missing_inputs == []

def test_auto_assumption_is_explicitly_marked_for_client_disclosure():
    resolved, assumptions, blockers = resolve_input_assumptions(
        "pump_head",
        {"flow_m3hr": 25, "diameter_mm": 100, "straight_length_m": 50, "static_head_m": 20},
    )
    assert not blockers
    assert all(a["status"] == "ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE" for a in assumptions)
    assert all(a["client_confirmation"] == "recommended" for a in assumptions)
