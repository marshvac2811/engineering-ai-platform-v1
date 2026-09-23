from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_framework.skill_definition import (
    SkillDefinition,
    definition_from_dict,
    validate_definition_dict,
)


def test_valid_skill_definition_contract():
    data = {
        "skill_id": "example_skill",
        "name": "Example Engineering Skill",
        "domain": "HVAC",
        "purpose": "Framework contract test",
        "version": "1.0.0",
        "executable": True,
        "execution_type": "deterministic_python",
        "required_inputs": [
            {
                "name": "airflow_cfm",
                "data_type": "number",
                "unit": "CFM",
                "required": True,
                "minimum": 0,
                "question": "What is the airflow?",
            }
        ],
        "optional_inputs": [
            {
                "name": "method",
                "data_type": "string",
                "allowed_values": ["velocity", "equal_friction"],
            }
        ],
        "conditional_inputs": [],
        "standards": [],
        "assumptions": [],
        "validation_rules": ["airflow_cfm must be positive"],
        "warning_rules": [],
        "perfection_filter_rules": ["check_input_completeness"],
        "review": {
            "required": True,
            "roles": ["review"],
            "conditions": ["engineering_result_ready"],
        },
        "output_fields": ["engineering_result", "warnings"],
        "audit_fields": ["job_id", "request_id"],
    }

    assert validate_definition_dict(data) == []

    definition = definition_from_dict(data)

    assert isinstance(definition, SkillDefinition)
    assert definition.skill_id == "example_skill"
    assert definition.required_inputs[0].unit == "CFM"
    assert definition.review.required is True


def test_invalid_definition_reports_missing_identity():
    errors = validate_definition_dict(
        {
            "skill_id": "",
            "name": "",
            "domain": "HVAC",
        }
    )

    assert "Missing required SkillDefinition field: skill_id" in errors
    assert "Missing required SkillDefinition field: name" in errors
    assert "Missing required SkillDefinition field: purpose" in errors


def test_invalid_input_type_is_rejected():
    errors = validate_definition_dict(
        {
            "skill_id": "test",
            "name": "Test",
            "domain": "HVAC",
            "purpose": "Test",
            "required_inputs": [
                {
                    "name": "x",
                    "data_type": "invalid_type",
                }
            ],
        }
    )

    assert any("unsupported data_type" in error for error in errors)


def test_framework_contract_supports_conditional_inputs():
    data = {
        "skill_id": "cooling_tower",
        "name": "Cooling Tower",
        "domain": "HVAC",
        "purpose": "Framework conditional-input test",
        "conditional_inputs": [
            {
                "name": "chiller_tr",
                "data_type": "number",
                "conditional_on": {"load_method": "chiller"},
            },
            {
                "name": "direct_load_kw",
                "data_type": "number",
                "conditional_on": {"load_method": "direct"},
            },
        ],
    }

    definition = definition_from_dict(data)

    assert len(definition.conditional_inputs) == 2
    assert definition.conditional_inputs[0].conditional_on["load_method"] == "chiller"
    assert definition.conditional_inputs[1].conditional_on["load_method"] == "direct"
