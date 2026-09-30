from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .skill_definition import InputDefinition, SkillDefinition


@dataclass(frozen=True)
class InputResolution:
    missing_inputs: List[str]
    invalid_inputs: List[str]
    questions: List[str]
    source: str


def _is_present(inputs: Dict[str, Any], name: str) -> bool:
    if name not in inputs:
        return False
    value = inputs[name]
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _condition_matches(
    definition: InputDefinition,
    inputs: Dict[str, Any],
) -> bool:
    if not definition.conditional_on:
        return True

    for field, expected in definition.conditional_on.items():
        if not _is_present(inputs, field):
            return False

        actual = inputs[field]

        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False

    return True


def _type_matches(value: Any, data_type: str) -> bool:
    if data_type == "string":
        return isinstance(value, str)

    if data_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)

    if data_type == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )

    if data_type == "boolean":
        return isinstance(value, bool)

    if data_type == "object":
        return isinstance(value, dict)

    if data_type == "array":
        return isinstance(value, list)

    return False


def _validate_definition_input(
    definition: InputDefinition,
    inputs: Dict[str, Any],
) -> List[str]:
    if not _is_present(inputs, definition.name):
        return []

    value = inputs[definition.name]
    errors: List[str] = []

    if not _type_matches(value, definition.data_type):
        errors.append(
            f"Invalid input type for {definition.name}: "
            f"expected {definition.data_type}"
        )
        return errors

    if definition.allowed_values and value not in definition.allowed_values:
        errors.append(
            f"Invalid value for {definition.name}: {value}. "
            f"Allowed values: {definition.allowed_values}"
        )

    if (
        definition.minimum is not None
        and isinstance(value, (int, float))
        and value < definition.minimum
    ):
        errors.append(
            f"Input {definition.name} must be >= {definition.minimum}"
        )

    if (
        definition.maximum is not None
        and isinstance(value, (int, float))
        and value > definition.maximum
    ):
        errors.append(
            f"Input {definition.name} must be <= {definition.maximum}"
        )

    return errors


def resolve_input_requirements(
    definition: SkillDefinition,
    inputs: Dict[str, Any],
) -> InputResolution:
    """
    Resolve registry-defined input requirements.

    This resolver performs orchestration-level contract validation only.
    It does not perform engineering calculations and does not replace the
    deterministic engineering skill validator.
    """
    if not isinstance(inputs, dict):
        return InputResolution(
            missing_inputs=[],
            invalid_inputs=["inputs must be an object/dict"],
            questions=[],
            source="registry",
        )

    missing: List[str] = []
    invalid: List[str] = []
    questions: List[str] = []

    definitions = (
        list(definition.required_inputs)
        + list(definition.conditional_inputs)
    )

    # Some skills have an either/or engineering requirement expressed as a
    # validation rule rather than a required input (for example pump_head:
    # roughness_mm OR material). Surface that requirement during intake so the
    # user receives the complete input form in one pass instead of discovering
    # the second field only after execution.
    optional_by_name = {item.name: item for item in definition.optional_inputs}
    for rule in getattr(definition, "validation_rules", []) or []:
        text = str(rule)
        match = __import__("re").search(
            r"Provide\s+([A-Za-z_][A-Za-z0-9_]*)\s+or\s+(?:a\s+valid\s+)?(?:pipe\s+)?(?:material|[A-Za-z_][A-Za-z0-9_]*)",
            text,
            __import__("re").IGNORECASE,
        )
        if match:
            first = match.group(1)
            # Prefer the named alternative if it is present in the rule.
            second_match = __import__("re").search(
                r"or\s+(?:a\s+valid\s+)?(?:pipe\s+)?(material|[A-Za-z_][A-Za-z0-9_]*)",
                text,
                __import__("re").IGNORECASE,
            )
            second = second_match.group(1) if second_match else None
            alternatives = [name for name in (first, second) if name in optional_by_name]
            if alternatives and not any(_is_present(inputs, name) for name in alternatives):
                for name in alternatives:
                    if name not in missing:
                        missing.append(name)
                    item = optional_by_name[name]
                    questions.append(
                        item.question
                        or item.description
                        or f"Please provide the engineering input: {name}."
                    )

    seen = set()

    for item in definitions:
        if item.name in seen:
            continue
        seen.add(item.name)

        if item.conditional_on and not _condition_matches(item, inputs):
            continue

        if item.required and not _is_present(inputs, item.name):
            missing.append(item.name)
            questions.append(
                item.question
                or item.description
                or f"Please provide the engineering input: {item.name}."
            )
            continue

        invalid.extend(_validate_definition_input(item, inputs))

    return InputResolution(
        missing_inputs=list(dict.fromkeys(missing)),
        invalid_inputs=list(dict.fromkeys(invalid)),
        questions=list(dict.fromkeys(questions)),
        source="registry",
    )
