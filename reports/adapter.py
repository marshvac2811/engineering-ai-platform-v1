"""Provider-neutral adapter from SkillResult payloads to report envelopes."""
from __future__ import annotations

from typing import Any, Dict

from .profiles import report_profile
from code_engine.coverage import build_standards_applicability
from code_engine.scope import scope_references_for_skill


def build_report_envelope(*, skill_id: str, result: Dict[str, Any], inputs: Dict[str, Any], project_context: Dict[str, Any], standards_context: Dict[str, Any] | None = None, assumptions_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a traceable report payload without changing calculation results."""
    profile = report_profile(skill_id)
    engineering = dict(result.get("engineering_result") or {})
    compliance = list(engineering.get("compliance") or result.get("compliance") or [])
    standards = list(result.get("standards") or engineering.get("standards") or [])
    assumptions = list(result.get("assumptions") or engineering.get("assumptions") or [])
    warnings = list(result.get("warnings") or [])
    trace = list(result.get("calculation_trace") or engineering.get("calculation_trace") or [])

    return {
        "report_type": profile.report_type,
        "title": profile.title,
        "skill_id": skill_id,
        "classification": result.get("classification"),
        "status": result.get("status"),
        "deliverables": list(profile.deliverables),
        "inputs": inputs,
        "project_context": project_context,
        "standards_context": standards_context or {},
        "standards_applicability": build_standards_applicability(skill_id, project_context),
        "standards_scope_references": scope_references_for_skill(skill_id),
        "compliance_gate": {
            "status": "REQUIREMENTS_CHECKED" if compliance else "NO_GOVERNED_REQUIREMENT_CHECK_PERFORMED",
            "note": "Standards references do not constitute compliance. A requirement must exist in the governed standards registry and project applicability must be established before PASS/FAIL is reported.",
        },
        "assumptions_context": assumptions_context or {},
        "engineering_result": engineering,
        "calculation_trace": trace,
        "assumptions": assumptions,
        "warnings": warnings,
        "standards": standards,
        "compliance_checks": compliance,
        "human_review": {
            "required": bool(result.get("human_review_required", True)),
            "status": "required" if result.get("human_review_required", True) else "not_required",
        },
        "limitations": {
            "source_revision": result.get("source_revision"),
            "note": "This envelope reports the registered skill result. It does not imply certification, code compliance, or unsupported deliverables.",
        },
    }
