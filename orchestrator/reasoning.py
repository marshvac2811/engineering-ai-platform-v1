"""Validate and package AI engineering reasoning without performing calculations."""
from __future__ import annotations
from typing import Any, Dict, List

def build_decision_package(request_understanding: Dict[str, Any] | None, governance: Dict[str, Any] | None) -> Dict[str, Any]:
    understanding = dict(request_understanding or {})
    governance = dict(governance or {})
    governed = dict(governance.get("governed_knowledge") or {})
    gate = dict(governed.get("claim_gate") or {})
    evidence_ids = {str(x.get("evidence_id")) for x in governed.get("verified_evidence", []) if isinstance(x, dict) and x.get("evidence_id")}
    usage = [str(x) for x in understanding.get("evidence_usage") or []]
    valid_usage = [x for x in usage if x in evidence_ids]
    missing = [str(x) for x in understanding.get("missing_evidence") or []]
    claims = [x for x in understanding.get("compliance_claims") or []]
    if not gate.get("compliance_claim_allowed", False): claims = []
    return {
        "objective": understanding.get("objective", ""),
        "reasoning": dict(understanding.get("reasoning") or {}),
        "constraints": list(understanding.get("constraints") or []),
        "evidence_used": valid_usage,
        "unresolved_evidence": missing,
        "compliance_claims": claims,
        "claim_gate": gate,
        "status": "evidence_bounded" if not missing else "evidence_incomplete",
        "calculation_authority": "registered_engineering_capability",
        "human_review_required": True,
        "guardrails": [
            "AI reasoning does not replace deterministic engineering calculation.",
            "Unsupported or unverified evidence cannot establish compliance.",
            "Human engineering review remains mandatory.",
        ],
    }

__all__ = ["build_decision_package"]