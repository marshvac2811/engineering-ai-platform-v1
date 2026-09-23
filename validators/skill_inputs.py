from __future__ import annotations

from numbers import Real
from typing import Any, Dict, List


def _type_matches(value: Any, data_type: str) -> bool:
    if data_type == "string":
        return isinstance(value, str)
    if data_type == "number":
        return isinstance(value, Real) and not isinstance(value, bool)
    if data_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if data_type == "boolean":
        return isinstance(value, bool)
    if data_type == "object":
        return isinstance(value, dict)
    if data_type == "array":
        return isinstance(value, list)
    return True


def _condition_matches(inputs: Dict[str, Any], condition: Any) -> bool:
    if not condition:
        return True
    if not isinstance(condition, dict):
        return False
    return all(inputs.get(name) == expected for name, expected in condition.items())


def _validate_definition_input(
    inputs: Dict[str, Any],
    definition: Any,
    *,
    required: bool,
    conditional: bool = False,
) -> List[str]:
    errors: List[str] = []
    name = definition.name
    present = name in inputs and inputs[name] is not None

    if required and not present:
        errors.append(f"Missing required input: {name}")
        return errors

    if not present:
        return errors

    value = inputs[name]
    data_type = definition.data_type

    if not _type_matches(value, data_type):
        errors.append(
            f"Input has invalid type: {name}; expected {data_type}"
        )
        return errors

    allowed_values = getattr(definition, "allowed_values", None)
    if allowed_values and value not in allowed_values:
        errors.append(
            f"Input has invalid value: {name}; "
            f"allowed values are {', '.join(map(str, allowed_values))}"
        )

    minimum = getattr(definition, "minimum", None)
    maximum = getattr(definition, "maximum", None)

    if minimum is not None and isinstance(value, Real) and not isinstance(value, bool):
        if value < minimum:
            errors.append(f"Input below minimum: {name} >= {minimum}")

    if maximum is not None and isinstance(value, Real) and not isinstance(value, bool):
        if value > maximum:
            errors.append(f"Input above maximum: {name} <= {maximum}")

    return errors


def validate_skill_inputs(inputs: Any, skill_definition: Any) -> List[str]:
    """Validate job inputs against the selected registry SkillDefinition."""
    if not isinstance(inputs, dict):
        return ["inputs must be an object/dict"]

    errors: List[str] = []

    for definition in skill_definition.required_inputs:
        errors.extend(
            _validate_definition_input(
                inputs,
                definition,
                required=True,
            )
        )

    for definition in skill_definition.optional_inputs:
        errors.extend(
            _validate_definition_input(
                inputs,
                definition,
                required=False,
            )
        )

    for definition in skill_definition.conditional_inputs:
        condition = getattr(definition, "conditional_on", None)
        if not _condition_matches(inputs, condition):
            continue

        required = bool(getattr(definition, "required", False))
        errors.extend(
            _validate_definition_input(
                inputs,
                definition,
                required=required,
                conditional=True,
            )
        )

    return errors
