"""Supabase/PostgREST-backed job store and queue primitives.

The store deliberately depends only on the small interface exposed by the
Supabase Python client (`table`, `select`, `insert`, `update`, `upsert`,
`eq`, `order`, `limit`, `execute`, plus `rpc` for the queue claim function).
This keeps the application layer independent of the exact SDK version.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .models import Job, JobEvent, JobStatus
from .store import JobStore


class SupabaseJobStore(JobStore):
    def __init__(self, client: Any, *, jobs_table: str = "automation_jobs", events_table: str = "automation_job_events") -> None:
        self.client = client
        self.jobs_table = jobs_table
        self.events_table = events_table

    def save(self, job: Job) -> Job:
        payload = job.to_dict()
        row = {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "source": job.source,
            "requested_skill_id": job.requested_skill_id,
            "inputs": job.inputs,
            "project_context": job.project_context,
            "standards_context": job.standards_context,
            "assumptions_context": job.assumptions_context,
            "status": job.status.value,
            "skill_id": job.skill_id,
            "result": job.result,
            "dispatch_result": job.dispatch_result,
            "errors": job.errors,
            "warnings": job.warnings,
            "attachments": job.attachments,
            "attempt": job.attempt,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
        self.client.table(self.jobs_table).upsert(row, on_conflict="job_id").execute()

        event_rows = []
        for index, event in enumerate(job.events):
            event_rows.append({
                "job_id": job.job_id,
                "event_key": f"{job.job_id}:{index}",
                "event_type": event.event_type,
                "status": event.status,
                "message": event.message,
                "metadata": event.metadata,
                "created_at": event.created_at,
            })
        if event_rows:
            self.client.table(self.events_table).upsert(
                event_rows,
                on_conflict="event_key",
            ).execute()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        response = (
            self.client.table(self.jobs_table)
            .select("*")
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if not rows:
            return None
        return self._hydrate(rows[0])

    def list(self, *, tenant_id: Optional[str] = None) -> Iterable[Job]:
        query = self.client.table(self.jobs_table).select("*")
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.order("created_at", desc=False).execute()
        return tuple(self._hydrate(row) for row in (getattr(response, "data", None) or []))

    def list_summaries(self, *, tenant_id: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        columns = "job_id,tenant_id,source,requested_skill_id,status,skill_id,attempt,created_at,updated_at"
        query = self.client.table(self.jobs_table).select(columns)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.order("created_at", desc=False).execute()
        return tuple(getattr(response, "data", None) or [])

    def claim_next(self, worker_id: str, *, tenant_id: Optional[str] = None, lock_seconds: int = 300) -> Optional[Job]:
        """Claim the next queued job through the Postgres SKIP LOCKED RPC."""
        response = self.client.rpc(
            "claim_next_automation_job",
            {"p_worker_id": worker_id, "p_tenant_id": tenant_id, "p_lock_seconds": lock_seconds},
        ).execute()
        rows = getattr(response, "data", None) or []
        if not rows:
            return None
        return self._hydrate(rows[0])

    def release_claim(self, job_id: str, worker_id: str) -> None:
        self.client.rpc(
            "release_automation_job_claim",
            {"p_job_id": job_id, "p_worker_id": worker_id},
        ).execute()

    def heartbeat(self, job_id: str, worker_id: str) -> None:
        self.client.rpc(
            "heartbeat_automation_job_claim",
            {"p_job_id": job_id, "p_worker_id": worker_id},
        ).execute()

    def _hydrate(self, row: Dict[str, Any]) -> Job:
        job = Job(
            job_id=row["job_id"],
            tenant_id=row["tenant_id"],
            source=row["source"],
            requested_skill_id=row.get("requested_skill_id"),
            inputs=row.get("inputs") or {},
            project_context=row.get("project_context") or {},
            standards_context=row.get("standards_context") or {},
            assumptions_context=row.get("assumptions_context") or {},
            status=JobStatus(row.get("status", JobStatus.RECEIVED.value)),
            skill_id=row.get("skill_id"),
            result=row.get("result"),
            dispatch_result=row.get("dispatch_result"),
            errors=row.get("errors") or [],
            warnings=row.get("warnings") or [],
            attachments=row.get("attachments") or [],
            attempt=int(row.get("attempt") or 0),
            created_at=row.get("created_at") or "",
            updated_at=row.get("updated_at") or "",
        )

        response = (
            self.client.table(self.events_table)
            .select("event_type,status,message,metadata,created_at,event_key")
            .eq("job_id", job.job_id)
            .order("created_at", desc=False)
            .execute()
        )
        events = getattr(response, "data", None) or []
        job.events = [
            JobEvent(
                event_type=e["event_type"],
                status=e["status"],
                message=e["message"],
                metadata=e.get("metadata") or {},
                created_at=e.get("created_at") or "",
            )
            for e in events
        ]
        return job
def build_supabase_job_store_from_env() -> Optional[SupabaseJobStore]:
    import os

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, "
            "but supabase-py is not installed"
        ) from exc

    client = create_client(url, key)
    return SupabaseJobStore(client)

