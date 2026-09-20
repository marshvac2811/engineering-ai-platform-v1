from skills.common import SkillRequest
from skills.hvac.pump_head.adapter import PumpHeadSkill
from orchestrator.engine import execute


def test_pump_head_source_equation_example():
    req = SkillRequest(
        skill_id="pump_head",
        inputs={
            "flow_m3hr": 20,
            "diameter_mm": 80,
            "material": "upvc_pvc",
            "straight_length_m": 60,
            "fittings":[{"name":"90° standard elbow","ld_ratio":30,"quantity":2}],
            "static_head_m": 8,
            "equipment_losses_m":[{"name":"AHU/FCU coil","loss_m":2}],
            "margin_pct": 10,
        },
    )
    result = PumpHeadSkill().run(req)
    assert result.status == "draft_ready"
    assert result.engineering_result["velocity_ms"] > 0
    assert result.engineering_result["total_dynamic_head_m"] > 10


def test_orchestrator_dispatches_pump_head():
    req = SkillRequest(
        skill_id="pump_head",
        inputs={
            "flow_m3hr": 20,
            "diameter_mm": 80,
            "roughness_mm": 0.0015,
            "straight_length_m": 10,
            "static_head_m": 0,
            "margin_pct": 0,
        },
    )
    result = execute(req)
    assert result.status == "draft_ready"
    assert result.skill_id == "pump_head"
