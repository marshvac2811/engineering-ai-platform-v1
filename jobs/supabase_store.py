"""Supabase/PostgREST-backed job store and queue primitives.

The store deliberately depends only on the small interface exposed by the
Supabase Python client (`table`, `select`, `insert`, `update`, `upsert`,
`eq`, `order`, `limit`, `execute`, plus `rpc` for the queue claim function).
This keeps the application layer independent of the exact SDK version.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
import hashlib
import json

from .models import Job, JobEvent, JobStatus
from .store import JobStore
from reports.artifacts import build_approved_pdf, build_evidence_xlsx, sha256_bytes


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
            "orchestration": job.orchestration,
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

        self._persist_engineering_artifacts(job)
        return job

    @staticmethod
    def _orchestration_from_events(job: Job) -> Dict[str, Any]:
        for event in reversed(job.events):
            if event.event_type == "orchestration_plan":
                return event.metadata.get("plan") or {}
        return {}

    def _persist_engineering_artifacts(self, job: Job) -> None:
        """Persist the versioned engineering report plus normalized compliance evidence."""
        result = job.result or {}
        engineering = result.get("engineering_result") or {}
        checks = list(engineering.get("compliance") or [])
        report = result.get("compliance_report")
        if not report and engineering:
            from reports.compliance_report import build_compliance_report
            report = build_compliance_report(skill_id=job.skill_id or job.requested_skill_id or "", engineering_result=engineering)
        if not report:
            return

        canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str)
        content_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        status = "approved" if job.status == JobStatus.APPROVED else "draft"
        title = f"Engineering Report — {job.skill_id or job.requested_skill_id or 'analysis'}"

        try:
            latest = (self.client.table("engineering_report_artifacts")
                      .select("report_id,version,content_sha256")
                      .eq("job_id", job.job_id)
                      .order("version", desc=True)
                      .limit(1)
                      .execute())
            latest_rows = getattr(latest, "data", None) or []
            if latest_rows and latest_rows[0].get("content_sha256") == content_sha256:
                report_id = latest_rows[0]["report_id"]
                version = int(latest_rows[0].get("version") or 1)
                self.client.table("engineering_report_artifacts").update({
                    "status": status,
                    "reviewer": next((e.metadata.get("reviewer") for e in reversed(job.events) if e.event_type == "status_change" and e.metadata.get("reviewer")), None),
                    "review_comment": next((e.metadata.get("comment", "") for e in reversed(job.events) if e.event_type == "status_change" and e.metadata.get("comment")), ""),
                    "approved_at": job.updated_at if status == "approved" else None,
                }).eq("report_id", report_id).execute()
            else:
                version = (int(latest_rows[0].get("version") or 0) + 1) if latest_rows else 1
                response = self.client.table("engineering_report_artifacts").insert({
                    "tenant_id": job.tenant_id,
                    "job_id": job.job_id,
                    "version": version,
                    "status": status,
                    "title": title,
                    "skill_id": job.skill_id or job.requested_skill_id,
                    "report": report,
                    "content_sha256": content_sha256,
                    "html_path": "",
                    "pdf_path": "",
                    "reviewer": next((e.metadata.get("reviewer") for e in reversed(job.events) if e.event_type == "status_change" and e.metadata.get("reviewer")), None),
                    "review_comment": next((e.metadata.get("comment", "") for e in reversed(job.events) if e.event_type == "status_change" and e.metadata.get("comment")), ""),
                    "approved_at": job.updated_at if status == "approved" else None,
                    "created_at": job.updated_at or job.created_at,
                }).execute()
                rows = getattr(response, "data", None) or []
                report_id = rows[0].get("report_id") if rows else None

            if report_id:
                job.report_id = report_id
                if job.result is not None:
                    job.result["report_id"] = report_id
                self.client.table(self.jobs_table).update({"report_id": report_id, "result": job.result}).eq("job_id", job.job_id).execute()

            for check in checks:
                row = {
                    "job_id": job.job_id,
                    "tenant_id": job.tenant_id,
                    "requirement_id": check.get("requirement_id", ""),
                    "status": check.get("status", "NOT_VERIFIABLE"),
                    "input_value": check.get("input_value"),
                    "required_value": check.get("required_value"),
                    "unit": check.get("unit", ""),
                    "calculation": check.get("calculation", ""),
                    "clause_reference": check.get("clause_reference", ""),
                    "authority": check.get("authority", ""),
                    "code_name": check.get("code_name", ""),
                    "edition": check.get("edition", ""),
                    "requirement_type": check.get("requirement_type", ""),
                    "evidence": check.get("evidence", {}),
                    "created_at": job.updated_at or job.created_at,
                }
                response = self.client.table("engineering_compliance_checks").upsert(row, on_conflict="job_id,requirement_id").execute()
                check_rows = getattr(response, "data", None) or []
                check_id = check_rows[0].get("check_id") if check_rows else None
                evidence = row["evidence"]
                if check_id and isinstance(evidence, dict):
                    source_type = evidence.get("source_type") or evidence.get("sourceType")
                    if source_type:
                        self.client.table("engineering_compliance_evidence").insert({
                            "check_id": check_id,
                            "job_id": job.job_id,
                            "tenant_id": job.tenant_id,
                            "source_type": str(source_type),
                            "source_reference": str(evidence.get("source_reference") or evidence.get("sourceReference") or ""),
                            "document_reference": str(evidence.get("document_reference") or evidence.get("documentReference") or ""),
                            "calculation_reference": str(evidence.get("calculation_reference") or evidence.get("calculationReference") or ""),
                            "metadata": evidence,
                            "created_at": job.updated_at or job.created_at,
                        }).execute()
        except Exception as exc:
            # Engineering evidence is part of the authoritative record. Never
            # silently discard persistence failures: surface them to the caller
            # so a job cannot appear successfully processed while its evidence
            # artifact/compliance record is missing.
            raise RuntimeError(
                f"Engineering artifact persistence failed for job {job.job_id}: {exc}"
            ) from exc

    def create_dispatch_artifacts(self, job: Job) -> Dict[str, Any]:
        """Create and persist the final watermarked PDF plus internal evidence workbook."""
        result = job.result or {}
        evidence_bundle = result.get("evidence_bundle")
        if not evidence_bundle:
            raise RuntimeError("Evidence bundle is missing; final dispatch is not permitted")

        response = (self.client.table("engineering_report_artifacts")
                    .select("*")
                    .eq("job_id", job.job_id)
                    .eq("tenant_id", job.tenant_id)
                    .order("version", desc=True)
                    .limit(1)
                    .execute())
        rows = getattr(response, "data", None) or []
        if not rows:
            raise RuntimeError("Engineering report artifact is missing; final dispatch is not permitted")
        artifact = rows[0]
        report_id = artifact.get("report_id")
        version = int(artifact.get("version") or 1)

        watermark = "ENGINEERING AI PLATFORM • APPROVED CONTROLLED DOCUMENT"
        pdf = build_approved_pdf(job=job, evidence_bundle=evidence_bundle, watermark=watermark)
        xlsx = build_evidence_xlsx(job=job, evidence_bundle=evidence_bundle)
        pdf_sha = sha256_bytes(pdf)
        xlsx_sha = sha256_bytes(xlsx)
        prefix = f"{job.tenant_id}/{job.job_id}/v{version}"
        pdf_path = f"{prefix}/engineering-report-{job.job_id}.pdf"
        xlsx_path = f"{prefix}/engineering-evidence-{job.job_id}.xlsx"
        bucket = "engineering-artifacts"

        self.client.storage.from_(bucket).upload(
            pdf_path, pdf,
            {"content-type": "application/pdf", "cache-control": "private, max-age=0", "upsert": "false"},
        )
        self.client.storage.from_(bucket).upload(
            xlsx_path, xlsx,
            {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "cache-control": "private, max-age=0", "upsert": "false"},
        )

        self.client.table("engineering_report_artifacts").update({
            "evidence_sha256": evidence_bundle.get("manifest", {}).get("bundle_sha256"),
            "pdf_sha256": pdf_sha,
            "pdf_storage_path": pdf_path,
            "pdf_filename": f"engineering-report-{job.job_id}.pdf",
            "xlsx_sha256": xlsx_sha,
            "xlsx_storage_path": xlsx_path,
            "xlsx_filename": f"engineering-evidence-{job.job_id}.xlsx",
            "watermark_text": watermark,
            "dispatched_at": None,
        }).eq("report_id", report_id).execute()

        signed = self.client.storage.from_(bucket).create_signed_url(pdf_path, 86400)
        signed_data = signed.get("data") if isinstance(signed, dict) else getattr(signed, "data", None)
        if signed_data is None and isinstance(signed, dict):
            signed_data = signed
        signed_url = (signed_data or {}).get("signedURL") or (signed_data or {}).get("signedUrl")
        return {
            "report_id": report_id,
            "version": version,
            "pdf": {
                "filename": f"engineering-report-{job.job_id}.pdf",
                "storage_path": pdf_path,
                "sha256": pdf_sha,
                "watermark": watermark,
                "signed_url": signed_url,
            },
            "evidence_workbook": {
                "filename": f"engineering-evidence-{job.job_id}.xlsx",
                "storage_path": xlsx_path,
                "sha256": xlsx_sha,
            },
            "evidence_sha256": evidence_bundle.get("manifest", {}).get("bundle_sha256"),
        }

    def mark_dispatch_complete(self, job: Job) -> None:
        report_id = job.report_id or (job.dispatch_result or {}).get("artifacts", {}).get("report_id")
        if not report_id:
            return
        self.client.table("engineering_report_artifacts").update({
            "dispatched_at": job.updated_at,
        }).eq("report_id", report_id).eq("job_id", job.job_id).execute()

    def get_report_artifact(self, job_id: str, *, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = self.client.table("engineering_report_artifacts").select("*").eq("job_id", job_id).order("version", desc=True).limit(1)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.execute()
        rows = getattr(response, "data", None) or []
        return rows[0] if rows else None

    def get_compliance_checks(self, job_id: str, *, tenant_id: Optional[str] = None) -> list[Dict[str, Any]]:
        query = self.client.table("engineering_compliance_checks").select("*").eq("job_id", job_id).order("created_at", desc=False)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.execute()
        return list(getattr(response, "data", None) or [])

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
        columns = "job_id,tenant_id,source,requested_skill_id,status,skill_id,report_id,attempt,created_at,updated_at"
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
            orchestration=row.get("orchestration") or {},
            report_id=row.get("report_id"),
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

    url = (os.getenv("SUPABASE_URL") or "").strip()
    if url and "://" not in url:
        url = f"https://{url}"
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    try:
        from supabase import create_client
        from supabase.lib.client_options import ClientOptions
    except ImportError as exc:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, "
            "but supabase-py is not installed"
        ) from exc

    # Production must fail fast rather than leaving a Render request hanging
    # when the Supabase Data API is unavailable. The browser has its own
    # request timeout, but the server-side client needs an explicit timeout too.
    timeout_seconds = float(os.getenv("SUPABASE_POSTGREST_TIMEOUT_SECONDS", "10"))
    if timeout_seconds <= 0:
        raise RuntimeError("SUPABASE_POSTGREST_TIMEOUT_SECONDS must be greater than zero")
    client = create_client(
        url,
        key,
        options=ClientOptions(
            postgrest_client_timeout=timeout_seconds,
            storage_client_timeout=timeout_seconds,
            auto_refresh_token=False,
            persist_session=False,
        ),
    )
    return SupabaseJobStore(client)

