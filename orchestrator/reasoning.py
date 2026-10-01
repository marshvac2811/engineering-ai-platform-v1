"""Validate and package AI engineering reasoning without performing calculations."""
from __future__ import annotations
from typing import Any, Dict

def _delegated_calculations(plan: Dict[str, Any]) -> list[Dict[str, Any]]:
    return [{"task_id": t.get("task_id"), "capability_id": t.get("capability_id"), "objective": t.get("objective", ""), "status": t.get("status", "pending"), "depends_on": list(t.get("depends_on") or []), "requested_outputs": list(t.get("requested_outputs") or [])} for t in (plan.get("tasks") or []) if isinstance(t, dict)]

def build_decision_package(request_understanding: Dict[str, Any] | None, governance: Dict[str, Any] | None, engineering_plan: Dict[str, Any] | None = None) -> Dict[str, Any]:
    understanding, governance, plan = dict(request_understanding or {}), dict(governance or {}), dict(engineering_plan or {})
    governed = dict(governance.get("governed_knowledge") or {})
    gate = dict(governed.get("claim_gate") or {})
    evidence_ids = {str(x.get("evidence_id")) for x in governed.get("verified_evidence", []) if isinstance(x, dict) and x.get("evidence_id")}
    usage_ids = [str(x.get("evidence_id") if isinstance(x, dict) else x) for x in (understanding.get("evidence_usage") or [])]
    valid_usage = [x for x in usage_ids if x in evidence_ids]
    missing = [str(x) for x in understanding.get("missing_evidence") or []]
    claims = list(understanding.get("compliance_claims") or []) if gate.get("compliance_claim_allowed", False) else []
    return {"objective": understanding.get("objective", ""), "reasoning": dict(understanding.get("reasoning") or {}), "constraints": list(understanding.get("constraints") or []), "evidence_used": valid_usage, "unresolved_evidence": missing, "compliance_claims": claims, "claim_gate": gate, "delegated_calculations": _delegated_calculations(plan), "status": "evidence_bounded" if not missing else "evidence_incomplete", "calculation_authority": "registered_engineering_capability", "human_review_required": True, "guardrails": ["AI reasoning does not replace deterministic engineering calculation.", "Every numerical/design calculation must be delegated to a registered engineering capability.", "Unsupported or unverified evidence cannot establish compliance.", "Human engineering review remains mandatory."]}

__all__ = ["build_decision_package"]