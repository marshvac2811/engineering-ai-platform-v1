"""Shared input validation helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def require_positive(inputs: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    errors: List[str] = []
    for field in fields:
        value = inputs.get(field)
        if value is None:
            errors.append(f"Missing required input: {field}")
            continue
        try:
            if float(value) <= 0:
                errors.append(f"Input must be > 0: {field}")
        except (TypeError, ValueError):
            errors.append(f"Input must be numeric: {field}")
    return errors


def require_non_negative(inputs: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    errors: List[str] = []
    for field in fields:
        value = inputs.get(field)
        if value is None:
            errors.append(f"Missing required input: {field}")
            continue
        try:
            if float(value) < 0:
                errors.append(f"Input must be >= 0: {field}")
        except (TypeError, ValueError):
            errors.append(f"Input must be numeric: {field}")
    return errors


def require_enum(inputs: Dict[str, Any], field: str, allowed: Iterable[str]) -> List[str]:
    value = inputs.get(field)
    allowed_list = list(allowed)
    if value is None:
        return [f"Missing required input: {field}"]
    if value not in set(allowed_list):
        return [f"Invalid value for {field}: {value}. Allowed: {', '.join(allowed_list)}"]
    return []
