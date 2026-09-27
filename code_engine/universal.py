"""Registry-driven universal compliance planning and execution.

Skills provide engineering values; the standards registry provides governed
requirements. This module joins the two without embedding code rules inside
individual calculators.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .compliance import ComplianceEngine
from .models import CodeRequirement, ComplianceStatus
from .registry import CodeRegistry


def _matches(expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    if isinstance(expected, (list, tuple, set)):
        return actual in expected
    return str(actual).strip().lower() == str(expected).strip().lower()


def requirement_applicable(requirement: CodeRequirement, context: Dict[str, Any]) -> bool:
    """Evaluate the registry's simple, auditable applicability predicates."""
    return all(_matches(expected, context.get(field)) for field, expected in requirement.applicability.items())


def find_applicable_requirements(
    registry: CodeRegistry,
    *,
    discipline: str,
    parameter: str,
    context: Dict[str, Any] | None = None,
) -> List[CodeRequirement]:
    context = context or {}
    return [
        req for req in registry.requirements.values()
        if req.discipline == discipline
        and req.parameter == parameter
        and requirement_applicable(req, context)
    ]


def evaluate_registered_requirements(
    registry: CodeRegistry,
    *,
    discipline: str,
    parameter: str,
    input_value: Any,
    context: Dict[str, Any] | None = None,
    evidence: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Evaluate only governed requirements whose applicability is established.

    No registered requirement means no PASS/FAIL conclusion. Missing values are
    represented by NOT_VERIFIABLE rather than an invented engineering result.
    """
    context = context or {}
    evidence = evidence or {}
    engine = ComplianceEngine()
    rows = []
    for req in find_applicable_requirements(
        registry, discipline=discipline, parameter=parameter, context=context
    ):
        check = engine.evaluate(req, input_value, applicable=True, evidence=evidence)
        rows.append(check.to_dict())
    return rows


def compliance_gate(checks: Iterable[Dict[str, Any]]) -> str:
    checks = list(checks)
    if not checks:
        return "NO_GOVERNED_REQUIREMENT"
    statuses = {str(c.get("status")) for c in checks}
    if "FAIL" in statuses:
        return "NON_COMPLIANT"
    if "NOT_VERIFIABLE" in statuses:
        return "NOT_VERIFIABLE"
    if statuses <= {"NOT_APPLICABLE"}:
        return "NOT_APPLICABLE"
    if "PASS" in statuses:
        return "COMPLIANT"
    return "REVIEW_REQUIRED"
