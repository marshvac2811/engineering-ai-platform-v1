from pathlib import Path

from code_engine.registry import CodeRegistry
from code_engine.compliance import ComplianceEngine
from code_engine.models import ComplianceStatus
from skills.common import SkillRequest
from skills.hvac.facade_u_factor.adapter import FacadeUFactorSkill
from orchestrator.intake import build_plan

ROOT = Path(__file__).resolve().parents[1]

def test_facade_skill_calculates_and_applies_ecbc_for_commercial_vertical_fenestration():
    result = FacadeUFactorSkill().run(SkillRequest(
        skill_id="facade_u_factor",
        inputs={"components": [
            {"name": "glass", "area_m2": 80, "u_factor": 2.4},
            {"name": "frame", "area_m2": 20, "u_factor": 4.0},
        ]},
        project_context={"building_type": "commercial", "component": "vertical_fenestration"},
    ))
    assert result.status == "completed"
    assert round(result.engineering_result["overall_u_factor_w_m2k"], 3) == 2.72
    assert result.engineering_result["compliance"][0]["status"] == "PASS"
    assert "4.3.3 / Table 4-10" in result.engineering_result["compliance"][0]["clause_reference"]
    from reports.compliance_report import build_compliance_report
    report = build_compliance_report(skill_id="facade_u_factor", engineering_result=result.engineering_result)
    assert report["compliance_checks"][0]["clause"] == result.engineering_result["compliance"][0]["clause_reference"]

def test_facade_code_check_is_not_applicable_without_established_context():
    result = FacadeUFactorSkill().run(SkillRequest(
        skill_id="facade_u_factor",
        inputs={"components": [{"name": "glass", "area_m2": 10, "u_factor": 2.5}]},
        project_context={},
    ))
    assert result.engineering_result["compliance"][0]["status"] == "NOT_APPLICABLE"

def test_intake_routes_facade_u_factor():
    plan = build_plan(
        "Give me the U value of this facade with specified glass",
        provided_inputs={"components": [{"name": "glass", "area_m2": 10, "u_factor": 2.5}]},
        project_context={"building_type": "commercial", "component": "vertical_fenestration"},
    )
    assert plan.selected_skill_id == "facade_u_factor"
    assert plan.status == "ready_for_execution"

def test_code_registry_contains_governed_sources():
    registry = CodeRegistry.from_yaml(ROOT / "standards" / "registry.yaml")
    assert registry.get_requirement("ecbc2017_vertical_fenestration_u_factor").required_value == 3.0
    assert registry.get_requirement("ecbc2017_vertical_fenestration_u_factor").clause == "4.3.3 / Table 4-10"
