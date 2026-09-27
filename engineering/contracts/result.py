from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class EngineeringResult:
    skill_id: str
    status: str
    engineering_result: Dict[str, Any] = field(default_factory=dict)
    compliance_checks: List[Dict[str, Any]] = field(default_factory=list)
    report_metadata: Dict[str, Any] = field(default_factory=dict)
