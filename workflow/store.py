from __future__ import annotations
from typing import Optional
from .models import WorkflowTask


class InMemoryWorkflowTaskStore:
    def __init__(self) -> None:
        self.tasks: dict[str, WorkflowTask] = {}

    def save(self, task: WorkflowTask) -> WorkflowTask:
        task.validate()
        task.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        self.tasks[task.task_id] = task
        return task

    def get(self, tenant_id: str, task_id: str) -> Optional[WorkflowTask]:
        task = self.tasks.get(task_id)
        return task if task and task.tenant_id == tenant_id else None

    def list(self, tenant_id: str) -> list[WorkflowTask]:
        return [t for t in self.tasks.values() if t.tenant_id == tenant_id]

    def find_external(self, tenant_id: str, source: str, external_id: str) -> Optional[WorkflowTask]:
        for task in self.tasks.values():
            if task.tenant_id == tenant_id and task.source == source and task.external_id == external_id:
                return task
        return None
