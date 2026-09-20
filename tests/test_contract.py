from skills.common import SkillRequest
from skills.hvac.duct_sizing.adapter import DuctSizingSkill


def test_duct_validation():
    skill = DuctSizingSkill()
    request = SkillRequest(
        skill_id="duct_sizing",
        inputs={
            "airflow": 8000,
            "method": "velocity",
            "duct_type": "round",
            "target_velocity_ms": 7,
        },
    )
    assert skill.validate(request) == []


def test_duct_rejects_zero_airflow():
    skill = DuctSizingSkill()
    request = SkillRequest(
        skill_id="duct_sizing",
        inputs={
            "airflow": 0,
            "method": "velocity",
            "duct_type": "round",
            "target_velocity_ms": 7,
        },
    )
    assert skill.validate(request)
