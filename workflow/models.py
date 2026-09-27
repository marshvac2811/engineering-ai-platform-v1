from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

TASK_STATUSES = {
    "NEW", "TRIAGE", "AWAITING_CLIENT_INFO", "READY_FOR_ENGINEERING",
    "ENGINEERING", "AWAITING_REVIEW", "READY_FOR_DELIVERY", "DELIVERED",
    "FOLLOW_UP", "COMPLETED", "CANCELLED",
}
PRIORITIES = {"LOW", "NORMAL", "HIGH", "URGENT"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowTask:
    tenant_id: str
    source: str
    title: str
    requirement: str = ""
    client_name: str = ""
    client_contact: str = ""
    company: str = ""
    skill_id: Optional[str] = None
    priority: str = "NORMAL"
    deadline: Optional[str] = None
    status: str = "NEW"
    external_id: Optional[str] = None
    engineering_job_id: Optional[str] = None
    deliverable: Optional[str] = None
    follow_up_at: Optional[str] = None
    notes: str = ""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def validate(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.source:
            raise ValueError("source is required")
        if not self.title.strip():
            raise ValueError("task title is required")
        if self.status not in TASK_STATUSES:
            raise ValueError(f"Unsupported task status: {self.status}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"Unsupported task priority: {self.priority}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
