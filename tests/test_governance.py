from skills.common import SkillRequest
from skills.hvac.duct_sizing.adapter import DuctSizingSkill
from skills.hvac.pump_head.adapter import PumpHeadSkill
from validators.governance import load_assumption_registry, load_standard_registry


def test_registries_load_without_invented_standard_values():
    assumptions = load_assumption_registry()
    standards = load_standard_registry()
    assert assumptions["assumptions"]
    assert standards["standards"] == []


def test_assumption_and_standard_context_are_carried_into_result():
    request = SkillRequest(
        skill_id="pump_head",
        inputs={
            "flow_m3hr": 20,
            "diameter_mm": 80,
            "roughness_mm": 0.0015,
            "straight_length_m": 10,
            "static_head_m": 0,
            "margin_pct": 0,
        },
        assumptions_context={"pump.gravity.source_default": 9.81},
        standards_context={"standards": [{"standard": "PROJECT_SPEC", "edition": "2026", "status": "supplied_by_user"}]},
    )
    result = PumpHeadSkill().run(request)
    assert result.status == "draft_ready"
    assert result.assumptions[1]["source"] == "project_override"
    assert result.standards[0]["standard"] == "PROJECT_SPEC"


def test_duct_assumption_override_changes_pressure_loss():
    base = SkillRequest(
        skill_id="duct_sizing",
        inputs={"airflow": 8000, "method": "velocity", "duct_type": "round", "target_velocity_ms": 7, "material": "gss"},
    )
    override = SkillRequest(
        skill_id="duct_sizing",
        inputs={"airflow": 8000, "method": "velocity", "duct_type": "round", "target_velocity_ms": 7, "material": "gss"},
        assumptions_context={"duct.air_density.source_default": 1.0},
    )
    a = DuctSizingSkill().run(base)
    b = DuctSizingSkill().run(override)
    assert a.status == b.status == "draft_ready"
    assert a.engineering_result["actual_friction_pa_per_m"] != b.engineering_result["actual_friction_pa_per_m"]
