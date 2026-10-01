"""Standards/governance contract for AI-driven engineering work.

This layer records which governing authorities/methodologies apply to a job.
It deliberately does not invent standard clauses or reproduce copyrighted
standards. Verified references may come from the registry, tenant-provided
documents, or a trusted knowledge provider.
"""
from __future__ import annotations
from typing import Any, Dict, Iterable

def build_governance_context(*, skill_id: str | None, project_context: Dict[str, Any] | None = None,
                             standards_context: Dict[str, Any] | None = None,
                             methodology: Dict[str, Any] | None = None) -> Dict[str, Any]:
    project_context = dict(project_context or {})
    supplied = dict(standards_context or {})
    return {
        "status": "governance_required",
        "jurisdiction": project_context.get("jurisdiction") or supplied.get("jurisdiction"),
        "governing_bodies": list(supplied.get("governing_bodies") or []),
        "standards": list(supplied.get("standards") or []),
        "methodology": dict(methodology or supplied.get("methodology") or {}),
        "references": list(supplied.get("references") or []),
        "applicability": supplied.get("applicability") or {},
        "evidence": list(supplied.get("evidence") or []),
        "limitations": [
            "A standard is not treated as authoritative merely because an LLM names it.",
            "Compliance claims require a verified governing source and established project applicability.",
        ],
        "skill_id": skill_id,
    }

def merge_governance(base: Dict[str, Any], extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result = dict(base or {})
    extra = extra or {}
    for key in ("governing_bodies", "standards", "references", "evidence"):
        result[key] = list(result.get(key) or []) + [x for x in list(extra.get(key) or []) if x not in list(result.get(key) or [])]
    for key in ("jurisdiction", "methodology", "applicability"):
        if extra.get(key):
            result[key] = extra[key]
    if extra.get("status"):
        result["status"] = extra["status"]
    return result
