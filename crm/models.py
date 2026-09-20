from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

PIPELINE_STAGES = [
    ("budgetary", "Budgetary"),
    ("tendering", "Tendering"),
    ("quotation", "Quotation"),
    ("followup", "Follow-Up"),
    ("negotiation", "Negotiation"),
    ("won", "Closed — Won"),
    ("lost", "Closed — Lost"),
]
STAGE_KEYS = {k for k, _ in PIPELINE_STAGES}
CATEGORY_KEYS = {"Project Sales", "Retrofit Jobs", "Energy Optimization"}
STAKEHOLDERS = {"Consultant", "Builder", "Developer", "Contractor", "End Client", "Other"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CRMDeal:
    tenant_id: str
    name: str
    category: str = "Project Sales"
    stakeholder: str = "Other"
    contact: str = ""
    company: str = ""
    value: float = 0.0
    stage: str = "budgetary"
    next_follow_up: Optional[str] = None
    notes: str = ""
    engineering_job_id: Optional[str] = None
    hubspot_object_id: Optional[str] = None
    deal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def validate(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.name.strip():
            raise ValueError("deal name is required")
        if self.category not in CATEGORY_KEYS:
            raise ValueError(f"Unsupported deal category: {self.category}")
        if self.stakeholder not in STAKEHOLDERS:
            raise ValueError(f"Unsupported stakeholder: {self.stakeholder}")
        if self.stage not in STAGE_KEYS:
            raise ValueError(f"Unsupported pipeline stage: {self.stage}")
        if self.value < 0:
            raise ValueError("deal value cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
