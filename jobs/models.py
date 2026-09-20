"""Provider-neutral job and lifecycle models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class JobStatus(str, Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    INPUT_VALIDATION = "input_validation"
    AWAITING_INFORMATION = "awaiting_information"
    ENGINEERING_VALIDATION = "engineering_validation"
    DRAFT_READY = "draft_ready"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.CANCELLED,
}

ALLOWED_TRANSITIONS = {
    JobStatus.RECEIVED: {JobStatus.QUEUED, JobStatus.AWAITING_INFORMATION, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.CANCELLED},
    JobStatus.PROCESSING: {
        JobStatus.INPUT_VALIDATION,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.INPUT_VALIDATION: {
        JobStatus.AWAITING_INFORMATION,
        JobStatus.ENGINEERING_VALIDATION,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.AWAITING_INFORMATION: {
        JobStatus.QUEUED,
        JobStatus.CANCELLED,
    },
    JobStatus.ENGINEERING_VALIDATION: {
        JobStatus.AWAITING_INFORMATION,
        JobStatus.DRAFT_READY,
        JobStatus.FAILED,
        JobStatus.RETRY,
    },
    JobStatus.DRAFT_READY: {
        JobStatus.HUMAN_REVIEW,
        JobStatus.FAILED,
    },
    JobStatus.HUMAN_REVIEW: {
        JobStatus.APPROVED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.APPROVED: {
        JobStatus.DISPATCHING,
        JobStatus.CANCELLED,
    },
    JobStatus.DISPATCHING: {
        JobStatus.DISPATCHED,
        JobStatus.FAILED,
        JobStatus.RETRY,
    },
    JobStatus.DISPATCHED: {
        JobStatus.COMPLETED,
    },
    JobStatus.FAILED: {
        JobStatus.RETRY,
        JobStatus.CANCELLED,
    },
    JobStatus.RETRY: {
        JobStatus.QUEUED,
        JobStatus.CANCELLED,
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobEvent:
    event_type: str
    status: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Job:
    job_id: str
    tenant_id: str
    source: str
    requested_skill_id: Optional[str]
    inputs: Dict[str, Any]
    project_context: Dict[str, Any] = field(default_factory=dict)
    standards_context: Dict[str, Any] = field(default_factory=dict)
    assumptions_context: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.RECEIVED
    skill_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    dispatch_result: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    events: List[JobEvent] = field(default_factory=list)
    attempt: int = 0
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        source: str,
        inputs: Dict[str, Any],
        requested_skill_id: Optional[str] = None,
        project_context: Optional[Dict[str, Any]] = None,
        standards_context: Optional[Dict[str, Any]] = None,
        assumptions_context: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> "Job":
        if not tenant_id:
            raise ValueError("tenant_id is required")
        return cls(
            job_id=job_id or str(uuid4()),
            tenant_id=tenant_id,
            source=source,
            requested_skill_id=requested_skill_id,
            inputs=inputs,
            project_context=project_context or {},
            standards_context=standards_context or {},
            assumptions_context=assumptions_context or {},
        )

    def transition(self, new_status: JobStatus, message: str, **metadata: Any) -> None:
        if new_status == self.status:
            return
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid job transition: {self.status.value} -> {new_status.value}")
        self.status = new_status
        self.updated_at = now_iso()
        self.events.append(JobEvent("status_change", new_status.value, message, metadata))

    def add_attachment(self, attachment: Dict[str, Any]) -> None:
        self.attachments.append(attachment)
        self.updated_at = now_iso()
        self.events.append(JobEvent("attachment_registered", self.status.value, "Attachment registered for ingestion.", {"attachment_id": attachment.get("attachment_id"), "filename": attachment.get("filename"), "source_type": attachment.get("source_type")}))

    def add_event(self, event_type: str, message: str, **metadata: Any) -> None:
        self.updated_at = now_iso()
        self.events.append(JobEvent(event_type, self.status.value, message, metadata))

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["events"] = [asdict(event) for event in self.events]
        return value
