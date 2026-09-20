from skills.common import SkillRequest
from skills.hvac.duct_sizing.adapter import DuctSizingSkill


def test_velocity_method_executes_source_engine():
    skill = DuctSizingSkill()
    request = SkillRequest(
        skill_id="duct_sizing",
        inputs={
            "airflow": 8000,
            "method": "velocity",
            "duct_type": "round",
            "target_velocity_ms": 7,
            "material": "gss",
        },
    )
    result = skill.run(request)
    assert result.status == "draft_ready"
    assert result.engineering_result["recommended_diameter_mm"] == 900
    assert result.source_revision == "1410b71e16a4fe4b1c6b04f023291d7b0f458d68"
    assert result.human_review_required is True
    assert result.validation_errors == []


def test_rectangular_method_executes_source_engine():
    skill = DuctSizingSkill()
    request = SkillRequest(
        skill_id="duct_sizing",
        inputs={
            "airflow": 8000,
            "method": "velocity",
            "duct_type": "rectangular",
            "width_mm": 1000,
            "height_mm": 600,
            "material": "gss",
        },
    )
    result = skill.run(request)
    assert result.status == "draft_ready"
    assert "equivalent_diameter_mm" in result.engineering_result
