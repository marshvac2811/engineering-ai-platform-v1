"""Build a bounded AI reasoning context from governed evidence.

This is a context adapter, not an engineering calculator or standards interpreter.
It exposes evidence with provenance and explicit claim limits.
"""
from __future__ import annotations
from typing import Any, Dict, List

def build_reasoning_context(governed_knowledge: Dict[str, Any] | None = None, *, max_evidence: int = 12) -> Dict[str, Any]:
    governed = dict(governed_knowledge or {})
    evidence = list(governed.get("verified_evidence") or [])[:max_evidence]
    applicability = dict(governed.get("applicability") or {})
    claim_gate = dict(governed.get("claim_gate") or {})
    project_evidence: List[Dict[str, Any]] = []
    governance_evidence: List[Dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        compact = {
            "evidence_id": item.get("evidence_id"), "source_type": item.get("source_type"),
            "authority": item.get("authority"), "title": item.get("title"),
            "reference": item.get("reference"), "edition": item.get("edition"),
            "jurisdiction": item.get("jurisdiction"), "location": item.get("location"),
            "clause": item.get("clause"), "excerpt": item.get("excerpt"),
            "content_hash": item.get("content_hash"), "verified": bool(item.get("verified")),
            "applicability": item.get("applicability"),
        }
        if compact["source_type"] == "project_document": project_evidence.append(compact)
        else: governance_evidence.append(compact)
    return {
        "purpose": "bounded engineering reasoning over supplied evidence; not a calculation engine",
        "project_evidence": project_evidence, "governance_evidence": governance_evidence,
        "candidate_sources": list(governed.get("candidate_sources") or []),
        "applicability": applicability, "claim_gate": claim_gate,
        "instructions": [
            "Use project evidence only as evidence of supplied project facts; do not assume missing values.",
            "Use governance evidence only when verification and applicability metadata support the claim.",
            "A candidate source is not verified evidence.",
            "Do not invent standard clauses, limits, editions, calculations, or compliance conclusions.",
            "Preserve evidence_id when making a statement that depends on retrieved evidence.",
            "If required evidence is absent, identify the evidence needed rather than filling the gap from memory.",
        ],
    }

__all__ = ["build_reasoning_context"]