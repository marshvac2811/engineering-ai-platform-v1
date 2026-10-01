"""Project applicability gate for governing sources."""
from __future__ import annotations

from typing import Any, Dict, List

from knowledge.standards_catalog import candidate_sources


def infer_domains(*, skill_id: str | None, disciplines: List[str] | None = None,
                  objective: str = "") -> List[str]:
    text = " ".join([str(skill_id or ""), *(disciplines or []), objective]).lower()
    mapping = {
        "hvac": "hvac", "duct": "hvac", "pump": "plumbing", "fire": "fire",
        "life safety": "life_safety", "bms": "electrical", "energy": "energy",
        "decarbon": "sustainability", "solar": "renewable_energy", "bess": "renewable_energy",
        "structur": "structural", "civil": "civil", "plumb": "plumbing",
        "interior": "interiors", "partition": "interiors", "envelope": "building_envelope",
        "lighting": "lighting", "electrical": "electrical",
    }
    result: List[str] = []
    for needle, domain in mapping.items():
        if needle in text and domain not in result:
            result.append(domain)
    return result


def build_applicability_context(*, jurisdiction: str | None, skill_id: str | None,
                                 disciplines: List[str] | None = None,
                                 objective: str = "",
                                 supplied: Dict[str, Any] | None = None) -> Dict[str, Any]:
    supplied = dict(supplied or {})
    domains = infer_domains(skill_id=skill_id, disciplines=disciplines, objective=objective)
    candidates = candidate_sources(jurisdiction=jurisdiction, domains=domains)
    verified = [
        x for x in supplied.get("verified_sources", [])
        if isinstance(x, dict) and x.get("verified") is True
    ]
    return {
        "domains": domains,
        "candidate_sources": candidates,
        "verified_sources": verified,
        "status": "verified_source_available" if verified else ("candidates_available" if candidates else "source_required"),
        "legal_applicability_established": bool(supplied.get("legal_applicability_established", False)),
        "compliance_claim_allowed": bool(
            supplied.get("legal_applicability_established", False) and verified
        ),
        "limitations": [
            "Candidate source discovery does not establish legal or contractual applicability.",
            "A compliance claim requires a verified source and established project applicability.",
        ],
    }
