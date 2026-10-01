"""Universal AI engineering orchestration contracts.

AI is responsible for understanding and decomposing the request. Registered
engineering capabilities are execution tools selected internally. Unknown
engineering work is never converted into a fabricated deterministic result.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

@dataclass
class EngineeringUnderstanding:
    objective: str = ""
    disciplines: List[str] = field(default_factory=list)
    requested_outputs: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    methodology: Dict[str, Any] = field(default_factory=dict)
    governance: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source: str = "ai"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def unsupported_engineering_plan(*, request: str, understanding: EngineeringUnderstanding,
                                 question: str) -> Dict[str, Any]:
    return {
        "status": "awaiting_information",
        "reason": "capability_or_governance_required",
        "request_understanding": understanding.to_dict(),
        "question": question,
        "safety": {
            "calculation_performed": False,
            "fabricated_result": False,
            "human_review_required": True,
        },
    }
