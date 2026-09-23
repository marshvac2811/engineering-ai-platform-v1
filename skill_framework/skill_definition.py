from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class InputDefinition:
    name: str
    data_type: str
    description: str = ""
    unit: Optional[str] = None
    required: bool = False
    question: Optional[str] = None
    allowed_values: List[Any] = field(default_factory=list)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    conditional_on: Dict[str, Any] = field(default_factory=dict)
    source_types: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class StandardReference:
    standard_id: str
    title: str = ""
    edition: Optional[str] = None
    source: Optional[str] = None
    status: str = "source_pending"


@dataclass(frozen=True)
class AssumptionReference:
    assumption_id: str
    unit: Optional[str] = None
    override_allowed: bool = True


@dataclass(frozen=True)
class ReviewDefinition:
    required: bool = False
    roles: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    domain: str
    purpose: str
    version: str = "1.0.0"
    classification: str = ""
    integration_status: str = ""
    executable: bool = False
    execution_type: str = ""
    implementation_binding: Optional[str] = None
    required_inputs: List[InputDefinition] = field(default_factory=list)
    optional_inputs: List[InputDefinition] = field(default_factory=list)
    conditional_inputs: List[InputDefinition] = field(default_factory=list)
    standards: List[StandardReference] = field(default_factory=list)
    assumptions: List[AssumptionReference] = field(default_factory=list)
    validation_rules: List[str] = field(default_factory=list)
    warning_rules: List[str] = field(default_factory=list)
    perfection_filter_rules: List[str] = field(default_factory=list)
    review: ReviewDefinition = field(default_factory=ReviewDefinition)
    output_fields: List[str] = field(default_factory=list)
    audit_fields: List[str] = field(default_factory=list)
    source_revision: Optional[str] = None


REQUIRED_FIELDS = (
    "skill_id",
    "name",
    "domain",
    "purpose",
)

VALID_INPUT_TYPES = {
    "string",
    "integer",
    "number",
    "boolean",
    "object",
    "array",
}


def validate_definition_dict(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not isinstance(data, dict):
        return ["SkillDefinition must be an object"]

    for field_name in REQUIRED_FIELDS:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Missing required SkillDefinition field: {field_name}")

    for section_name in (
        "required_inputs",
        "optional_inputs",
        "conditional_inputs",
        "standards",
        "assumptions",
        "validation_rules",
        "warning_rules",
        "perfection_filter_rules",
        "output_fields",
        "audit_fields",
    ):
        if section_name in data and not isinstance(data[section_name], list):
            errors.append(f"{section_name} must be a list")

    inputs = (
        list(data.get("required_inputs", []))
        + list(data.get("optional_inputs", []))
        + list(data.get("conditional_inputs", []))
    )

    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            errors.append(f"input[{index}] must be an object")
            continue

        if not isinstance(item.get("name"), str) or not item["name"].strip():
            errors.append(f"input[{index}] missing name")

        data_type = item.get("data_type")
        if data_type not in VALID_INPUT_TYPES:
            errors.append(
                f"input[{index}] has unsupported data_type: {data_type}"
            )

        allowed_values = item.get("allowed_values", [])
        if allowed_values is not None and not isinstance(allowed_values, list):
            errors.append(f"input[{index}].allowed_values must be a list")

    review = data.get("review", {})
    if review is not None and not isinstance(review, dict):
        errors.append("review must be an object")

    return errors


def definition_from_dict(data: Dict[str, Any]) -> SkillDefinition:
    errors = validate_definition_dict(data)
    if errors:
        raise ValueError("; ".join(errors))

    def inputs(section: str) -> List[InputDefinition]:
        return [
            InputDefinition(
                name=item["name"],
                data_type=item["data_type"],
                description=item.get("description", ""),
                unit=item.get("unit"),
                required=bool(item.get("required", section == "required_inputs")),
                question=item.get("question"),
                allowed_values=list(item.get("allowed_values", [])),
                minimum=item.get("minimum"),
                maximum=item.get("maximum"),
                conditional_on=dict(item.get("conditional_on", {})),
                source_types=list(item.get("source_types", [])),
            )
            for item in data.get(section, [])
        ]

    standards = [
        StandardReference(
            standard_id=item["standard_id"],
            title=item.get("title", ""),
            edition=item.get("edition"),
            source=item.get("source"),
            status=item.get("status", "source_pending"),
        )
        for item in data.get("standards", [])
    ]

    assumptions = [
        AssumptionReference(
            assumption_id=item["assumption_id"],
            unit=item.get("unit"),
            override_allowed=bool(item.get("override_allowed", True)),
        )
        for item in data.get("assumptions", [])
    ]

    review_data = data.get("review", {}) or {}
    review = ReviewDefinition(
        required=bool(review_data.get("required", False)),
        roles=list(review_data.get("roles", [])),
        conditions=list(review_data.get("conditions", [])),
    )

    return SkillDefinition(
        skill_id=data["skill_id"],
        name=data["name"],
        domain=data["domain"],
        purpose=data["purpose"],
        version=data.get("version", "1.0.0"),
        classification=data.get("classification", ""),
        integration_status=data.get("integration_status", ""),
        executable=bool(data.get("executable", False)),
        execution_type=data.get("execution_type", ""),
        implementation_binding=data.get("implementation_binding"),
        required_inputs=inputs("required_inputs"),
        optional_inputs=inputs("optional_inputs"),
        conditional_inputs=inputs("conditional_inputs"),
        standards=standards,
        assumptions=assumptions,
        validation_rules=list(data.get("validation_rules", [])),
        warning_rules=list(data.get("warning_rules", [])),
        perfection_filter_rules=list(data.get("perfection_filter_rules", [])),
        review=review,
        output_fields=list(data.get("output_fields", [])),
        audit_fields=list(data.get("audit_fields", [])),
        source_revision=data.get("source_revision"),
    )
