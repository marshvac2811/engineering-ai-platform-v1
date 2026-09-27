"""Phase 15 — deterministic client-ready engineering deliverable contract.

The renderer consumes structured engineering results and preserves provenance.
It does not invent calculations, standards, clauses, evidence or conclusions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import hashlib
import json


@dataclass
class DeliverableSection:
    title: str
    content: Any


@dataclass
class EngineeringDeliverable:
    title: str
    client_request: str
    status: str
    sections: List[DeliverableSection] = field(default_factory=list)
    standards: List[Dict[str, Any]] = field(default_factory=list)
    compliance: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "client_request": self.client_request,
            "status": self.status,
            "sections": [{"title": s.title, "content": s.content} for s in self.sections],
            "standards": self.standards,
            "compliance": self.compliance,
            "evidence": self.evidence,
            "assumptions": self.assumptions,
            "limitations": self.limitations,
            "deliverables": self.deliverables,
        }

    def sha256(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(raw).hexdigest()


def build_deliverable(*, title: str, client_request: str, result: Dict[str, Any],
                      standards: Optional[List[Dict[str, Any]]] = None,
                      compliance: Optional[List[Dict[str, Any]]] = None,
                      evidence: Optional[List[Dict[str, Any]]] = None,
                      assumptions: Optional[List[str]] = None,
                      limitations: Optional[List[str]] = None,
                      deliverables: Optional[List[str]] = None) -> EngineeringDeliverable:
    """Build only from supplied structured data."""
    sections = [
        DeliverableSection("Engineering Result", result),
    ]
    return EngineeringDeliverable(
        title=title,
        client_request=client_request,
        status=str(result.get("status", "UNKNOWN")),
        sections=sections,
        standards=standards or [],
        compliance=compliance or [],
        evidence=evidence or [],
        assumptions=assumptions or [],
        limitations=limitations or [],
        deliverables=deliverables or [],
    )


def render_markdown(d: EngineeringDeliverable) -> str:
    lines = [f"# {d.title}", "", "## Client Request", d.client_request, "",
             "## Engineering Result", "```json",
             json.dumps(d.sections[0].content, indent=2, default=str), "```", ""]
    lines += ["## Standards / References"]
    if d.standards:
        for s in d.standards:
            lines.append(f"- {s}")
    else:
        lines.append("- None supplied.")
    lines += ["", "## Compliance"]
    if d.compliance:
        for c in d.compliance:
            lines.append(f"- {c}")
    else:
        lines.append("- No governed compliance result supplied.")
    lines += ["", "## Evidence"]
    if d.evidence:
        for e in d.evidence:
            lines.append(f"- {e}")
    else:
        lines.append("- No evidence supplied.")
    lines += ["", "## Assumptions"]
    lines.extend([f"- {x}" for x in d.assumptions] or ["- None supplied."])
    lines += ["", "## Limitations"]
    lines.extend([f"- {x}" for x in d.limitations] or ["- None supplied."])
    lines += ["", "## Deliverables"]
    lines.extend([f"- {x}" for x in d.deliverables] or ["- None supplied."])
    lines += ["", f"**Artifact SHA-256:** `{d.sha256()}`"]
    return "\n".join(lines) + "\n"
