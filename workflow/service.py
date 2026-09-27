from __future__ import annotations
from typing import Any, Optional
from .models import WorkflowTask, TASK_STATUSES

ALLOWED_TRANSITIONS = {
    "NEW": {"TRIAGE", "CANCELLED"},
    "TRIAGE": {"AWAITING_CLIENT_INFO", "READY_FOR_ENGINEERING", "CANCELLED"},
    "AWAITING_CLIENT_INFO": {"TRIAGE", "CANCELLED"},
    "READY_FOR_ENGINEERING": {"ENGINEERING", "AWAITING_CLIENT_INFO", "CANCELLED"},
    "ENGINEERING": {"AWAITING_REVIEW", "AWAITING_CLIENT_INFO", "CANCELLED"},
    "AWAITING_REVIEW": {"READY_FOR_DELIVERY", "ENGINEERING", "CANCELLED"},
    "READY_FOR_DELIVERY": {"DELIVERED", "CANCELLED"},
    "DELIVERED": {"FOLLOW_UP", "COMPLETED"},
    "FOLLOW_UP": {"COMPLETED", "DELIVERED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class WorkflowTaskService:
    def __init__(self, store, *, tenant_id: Optional[str] = None):
        self.store = store
        self.tenant_id = tenant_id

    def _tenant(self) -> str:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        return self.tenant_id

    def create(self, **kwargs: Any) -> WorkflowTask:
        task = WorkflowTask(tenant_id=self._tenant(), **kwargs)
        task.validate()
        return self.store.save(task)

    def get(self, task_id: str) -> WorkflowTask:
        task = self.store.get(self._tenant(), task_id)
        if not task:
            raise KeyError(f"Unknown workflow task: {task_id}")
        return task

    def list(self) -> list[WorkflowTask]:
        return self.store.list(self._tenant())

    def transition(self, task_id: str, status: str) -> WorkflowTask:
        task = self.get(task_id)
        status = status.upper()
        if status not in TASK_STATUSES:
            raise ValueError(f"Unsupported task status: {status}")
        if status != task.status and status not in ALLOWED_TRANSITIONS.get(task.status, set()):
            raise ValueError(f"Invalid task transition: {task.status} -> {status}")
        task.status = status
        return self.store.save(task)

    def link_job(self, task_id: str, job_id: str) -> WorkflowTask:
        task = self.get(task_id)
        task.engineering_job_id = job_id
        if task.status in {"NEW", "TRIAGE", "READY_FOR_ENGINEERING"}:
            task.status = "ENGINEERING"
        return self.store.save(task)

    def create_from_event(self, *, source: str, external_id: str, payload: dict[str, Any]) -> tuple[WorkflowTask, bool]:
        tenant = self._tenant()
        existing = self.store.find_external(tenant, source, external_id)
        if existing:
            return existing, False
        subject = str(payload.get("subject", "")).strip()
        message = str(payload.get("body_text", payload.get("message", payload.get("text", "")))).strip()
        title = subject or f"{source.title()} engineering request"
        client_name = str(payload.get("client_name", payload.get("from_name", "")))
        client_contact = str(payload.get("client_contact", payload.get("from", payload.get("email", ""))))
        company = str(payload.get("company", ""))
        task = self.create(
            source=source,
            external_id=external_id,
            title=title[:240],
            requirement=message,
            client_name=client_name,
            client_contact=client_contact,
            company=company,
            priority=str(payload.get("priority", "NORMAL")).upper(),
            notes=f"External event: {external_id}",
        )
        return task, True
