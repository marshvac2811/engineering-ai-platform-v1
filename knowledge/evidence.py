"""Governed evidence normalization for engineering workflows.

This module is source-agnostic. It does not scrape or invent standards content.
Evidence can come from licensed standards, official public sources, or client
documents supplied to the platform. Every record carries provenance and
verification state.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Dict, Iterable, List


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _hash_content(value: Any) -> str:
    if value is None:
        return ""
    return sha256(str(value).encode("utf-8")).hexdigest()


def normalize_evidence(items: Any, *, default_source_type: str = "unspecified") -> List[Dict[str, Any]]:
    """Normalize evidence records without fabricating missing provenance."""
    normalized: List[Dict[str, Any]] = []
    for raw in _as_list(items):
        if isinstance(raw, str):
            raw = {"reference": raw}
        if not isinstance(raw, dict):
            continue
        content = raw.get("content")
        normalized.append({
            "source_type": str(raw.get("source_type") or default_source_type),
            "authority": str(raw.get("authority") or ""),
            "title": str(raw.get("title") or ""),
            "reference": str(raw.get("reference") or raw.get("source_reference") or ""),
            "edition": str(raw.get("edition") or ""),
            "jurisdiction": str(raw.get("jurisdiction") or ""),
            "location": str(raw.get("location") or raw.get("document_reference") or ""),
            "clause": str(raw.get("clause") or raw.get("clause_reference") or ""),
            "content_hash": str(raw.get("content_hash") or _hash_content(content)),
            "retrieved_at": raw.get("retrieved_at"),
            "verified": bool(raw.get("verified", False)),
            "applicability": raw.get("applicability") or "unassessed",
            "claim_type": str(raw.get("claim_type") or "reference"),
            "metadata": dict(raw.get("metadata") or {}),
        })
    return normalized


def build_evidence_bundle(*, governance: Dict[str, Any] | None = None,
                          project_context: Dict[str, Any] | None = None,
                          result_evidence: Any = None) -> Dict[str, Any]:
    """Build a provenance-aware evidence bundle for a workflow result."""
    governance = governance or {}
    project_context = project_context or {}
    records: List[Dict[str, Any]] = []

    for key in ("evidence", "sources", "references"):
        records.extend(normalize_evidence(governance.get(key), default_source_type="governance_context"))
    for key in ("evidence", "documents", "attachments"):
        records.extend(normalize_evidence(project_context.get(key), default_source_type="project_document"))
    records.extend(normalize_evidence(result_evidence, default_source_type="capability_result"))

    verified = [r for r in records if r["verified"]]
    applicable_verified = [r for r in verified if r["applicability"] in {"applicable", "confirmed"}]
    return {
        "records": records,
        "counts": {
            "total": len(records),
            "verified": len(verified),
            "verified_applicable": len(applicable_verified),
            "unverified": len(records) - len(verified),
        },
        "claim_gate": {
            "status": "evidence_required" if not applicable_verified else "evidence_available",
            "verified_applicable_evidence_required": True,
            "note": "A standards reference alone is not evidence of applicability.",
        },
    }


__all__ = ["normalize_evidence", "build_evidence_bundle"]
