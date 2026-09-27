from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class EngineeringRequirement:
    request_text: str
    discipline: str
    task_type: str
    skill_id: str
    required_inputs: List[str] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    project_context: Dict[str, Any] = field(default_factory=dict)
