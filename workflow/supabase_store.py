from __future__ import annotations
import os
from typing import Any, Optional
from .models import WorkflowTask
from .store import InMemoryWorkflowTaskStore


class SupabaseWorkflowTaskStore(InMemoryWorkflowTaskStore):
    def __init__(self, client: Any, *, table: str = "workflow_tasks") -> None:
        super().__init__()
        self.client = client
        self.table = table

    def save(self, task: WorkflowTask) -> WorkflowTask:
        task.validate()
        self.client.table(self.table).upsert(task.to_dict(), on_conflict="task_id").execute()
        return task

    def get(self, tenant_id: str, task_id: str) -> Optional[WorkflowTask]:
        response = self.client.table(self.table).select("*").eq("tenant_id", tenant_id).eq("task_id", task_id).limit(1).execute()
        rows = getattr(response, "data", None) or []
        return self._hydrate(rows[0]) if rows else None

    def list(self, tenant_id: str) -> list[WorkflowTask]:
        response = self.client.table(self.table).select("*").eq("tenant_id", tenant_id).order("created_at", desc=False).execute()
        return [self._hydrate(row) for row in (getattr(response, "data", None) or [])]

    def find_external(self, tenant_id: str, source: str, external_id: str) -> Optional[WorkflowTask]:
        response = (self.client.table(self.table).select("*").eq("tenant_id", tenant_id)
                    .eq("source", source).eq("external_id", external_id).limit(1).execute())
        rows = getattr(response, "data", None) or []
        return self._hydrate(rows[0]) if rows else None

    @staticmethod
    def _hydrate(row: dict[str, Any]) -> WorkflowTask:
        return WorkflowTask(
            tenant_id=str(row["tenant_id"]), source=row["source"], title=row["title"],
            requirement=row.get("requirement", ""), client_name=row.get("client_name", ""),
            client_contact=row.get("client_contact", ""), company=row.get("company", ""),
            skill_id=row.get("skill_id"), priority=row.get("priority", "NORMAL"),
            deadline=row.get("deadline"), status=row.get("status", "NEW"), external_id=row.get("external_id"),
            engineering_job_id=str(row["engineering_job_id"]) if row.get("engineering_job_id") else None,
            deliverable=row.get("deliverable"), follow_up_at=row.get("follow_up_at"), notes=row.get("notes", ""),
            task_id=str(row["task_id"]), created_at=row.get("created_at", ""), updated_at=row.get("updated_at", ""),
        )


def build_supabase_workflow_task_store_from_env() -> Optional[SupabaseWorkflowTaskStore]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("Supabase environment is configured but supabase-py is not installed") from exc
    return SupabaseWorkflowTaskStore(create_client(url, key))
