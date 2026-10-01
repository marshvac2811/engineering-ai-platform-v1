"""Authoritative-source catalog.

The catalog contains source metadata, not copyrighted standard text. Entries are
candidate sources only; applicability must be established from project
jurisdiction, discipline, contract/specification, and the tenant's verified
source material.
"""
from __future__ import annotations

from typing import Any, Dict, List

SOURCES: List[Dict[str, Any]] = [
    {
        "source_id": "bis_nbc_2016",
        "authority": "BIS",
        "title": "National Building Code of India 2016",
        "edition": "2016",
        "jurisdictions": ["IN"],
        "domains": ["building", "civil", "structural", "fire", "plumbing", "hvac", "electrical", "interiors", "sustainability"],
        "source_type": "official_public_reference",
        "official_url": "https://www.bis.gov.in/standards/national-building-code/?lang=en",
    },
    {
        "source_id": "bee_ecbc",
        "authority": "BEE",
        "title": "Energy Conservation Building Code",
        "edition": "2017",
        "jurisdictions": ["IN"],
        "domains": ["energy", "hvac", "building_envelope", "electrical", "lighting", "renewable_energy", "sustainability"],
        "source_type": "official_public_reference",
        "official_url": "https://beeindia.gov.in/view_content.php?lang=1&lid=615",
    },
    {
        "source_id": "ashrae_standards",
        "authority": "ASHRAE",
        "title": "ASHRAE Standards and Guidelines",
        "edition": "",
        "jurisdictions": ["GLOBAL"],
        "domains": ["hvac", "refrigeration", "thermal_comfort", "iaq", "energy"],
        "source_type": "official_public_reference",
        "official_url": "https://www.ashrae.org/i-want-to-view/standards",
    },
    {
        "source_id": "ishrae_standards",
        "authority": "ISHRAE",
        "title": "ISHRAE Standards and Guidelines",
        "edition": "",
        "jurisdictions": ["IN"],
        "domains": ["hvac", "refrigeration", "thermal_comfort", "iaq"],
        "source_type": "official_public_reference",
        "official_url": "https://www.ishrae.in/standards-position-published",
    },
    {
        "source_id": "nfpa_codes",
        "authority": "NFPA",
        "title": "NFPA Codes and Standards",
        "edition": "",
        "jurisdictions": ["GLOBAL"],
        "domains": ["fire", "life_safety", "electrical"],
        "source_type": "official_public_reference",
        "official_url": "https://www.nfpa.org/",
    },
]


def candidate_sources(*, jurisdiction: str | None, domains: List[str] | None) -> List[Dict[str, Any]]:
    """Return source candidates without declaring them legally applicable."""
    requested = {str(x).strip().lower() for x in (domains or []) if str(x).strip()}
    jur = str(jurisdiction or "").strip().upper()
    rows = []
    for source in SOURCES:
        source_jur = set(source["jurisdictions"])
        domain_match = bool(requested) and bool(requested & set(source["domains"]))
        jurisdiction_match = not jur or jur in source_jur or "GLOBAL" in source_jur
        if domain_match and jurisdiction_match:
            rows.append({
                **source,
                "applicability_status": "candidate",
                "verification_required": True,
            })
    return rows
