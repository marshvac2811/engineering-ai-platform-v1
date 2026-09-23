"""Provider-neutral engineering job lifecycle service.

This V1 service is deliberately synchronous. A database-backed queue worker can
replace the in-memory store without changing the job contract.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from orchestrator.engine import execute
from skills.common import SkillRequest
from validators.basic import require_positive
from validators.governance import validate_governance_context
from validators.registered_skill_inputs import validate_registered_skill_inputs
from ingestion.service import IngestionService

from .models import Job, JobStatus
from .store import JobStore


Dispatcher = Callable[[Job], Dict[str, Any]]


class JobService:
    def __init__(self, store: JobStore, dispatcher: Optional[Dispatcher] = None, *, tenant_id: Optional[str] = None, ingestion_service: Optional[IngestionService] = None) -> None:
        self.store = store
        self.dispatcher = dispatcher or self._default_dispatcher
        self.tenant_id = tenant_id
        self.ingestion = ingestion_service or IngestionService()

    def _assert_tenant(self, job: Job) -> None:
        if self.tenant_id is not None and job.tenant_id != self.tenant_id:
            raise PermissionError("Job does not belong to the configured tenant")

    @staticmethod
    def _default_dispatcher(job: Job) -> Dict[str, Any]:
        return {
            "mode": "manual",
            "message": "No external provider configured; dispatch artifact is ready for manual delivery.",
            "job_id": job.job_id,
        }

    def create_job(self, **kwargs: Any) -> Job:
        tenant_id = kwargs.pop("tenant_id", None) or self.tenant_id
        if not tenant_id:
            raise ValueError("tenant_id is required for job creation")
        job = Job.create(tenant_id=tenant_id, **kwargs)
        self._assert_tenant(job)
        job.add_event("job_created", "Job received.", source=job.source, tenant_id=tenant_id)
        self.store.save(job)
        return job


    def create_from_plan(self, plan) -> Job:
        """Create a job directly from an orchestration plan."""
        job = self.create_job(
            source="orchestrator",
            requested_skill_id=plan.selected_skill_id,
            inputs=plan.extracted_inputs,
            project_context=plan.project_context,
            standards_context=plan.standards_context,
            assumptions_context=plan.assumptions_context,
        )
        job.add_event("orchestration_plan", "Natural-language request classified by orchestrator.", plan=plan.to_dict())
        if plan.status == "awaiting_information":
            job.transition(
                JobStatus.AWAITING_INFORMATION,
                "Additional engineering inputs are required before execution.",
                missing_inputs=plan.missing_inputs,
            )
        elif plan.status in {"ambiguous", "unroutable"}:
            job.add_event("orchestration_needs_clarification", "Orchestrator could not select a unique executable skill.", status=plan.status)
        self.store.save(job)
        return job


    def register_attachment(self, job_id: str, *, filename: str, data: bytes, mime_type: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Job:
        job = self._get(job_id)
        attachment = self.ingestion.register(tenant_id=job.tenant_id, job_id=job.job_id, filename=filename, data=data, mime_type=mime_type, metadata=metadata)
        job.add_attachment(attachment.to_dict())
        self.store.save(job)
        return job

    def extract_attachment(self, job_id: str, attachment_id: str) -> Dict[str, Any]:
        job = self._get(job_id)
        match = next((a for a in job.attachments if a.get("attachment_id") == attachment_id), None)
        if not match:
            raise KeyError(f"Unknown attachment: {attachment_id}")
        from ingestion.models import Attachment
        attachment = Attachment(**match)
        result = self.ingestion.extract(attachment)
        for a in job.attachments:
            if a.get("attachment_id") == attachment_id:
                a["extraction_status"] = result.status
                a["extraction_metadata"] = result.metadata
                a["extraction_warnings"] = result.warnings
                a["extraction_errors"] = result.errors
                a["chunk_count"] = len(result.chunks)
        job.add_event("attachment_extracted", "Attachment content extracted.", attachment_id=attachment_id, status=result.status, chunk_count=len(result.chunks))
        self.store.save(job)
        return result.to_dict()

    def enqueue(self, job_id: str) -> Job:
        job = self._get(job_id)
        job.transition(JobStatus.QUEUED, "Job queued for processing.")
        self.store.save(job)
        return job

    def provide_missing_information(self, job_id: str, updates: Dict[str, Any]) -> Job:
        job = self._get(job_id)
        if job.status != JobStatus.AWAITING_INFORMATION:
            raise ValueError("Job is not awaiting information")
        job.inputs.update(updates)
        job.add_event("information_received", "Missing input information supplied.", fields=list(updates))
        job.transition(JobStatus.QUEUED, "Job returned to queue after input update.")
        self.store.save(job)
        return job

    def process(self, job_id: str) -> Job:
        job = self._get(job_id)
        if job.status not in {JobStatus.QUEUED, JobStatus.RETRY}:
            raise ValueError(f"Job cannot be processed from status {job.status.value}")

        job.attempt += 1
        job.transition(JobStatus.PROCESSING, "Job processing started.", attempt=job.attempt)
        self.store.save(job)

        job.transition(JobStatus.INPUT_VALIDATION, "Validating job inputs and governance context.")
        errors = self._validate_job(job)
        if errors:
            job.errors.extend(errors)
            if self._is_missing_information_case(errors):
                job.transition(JobStatus.AWAITING_INFORMATION, "Additional inputs are required.", errors=errors)
            else:
                job.transition(JobStatus.FAILED, "Input validation failed.", errors=errors)
            self.store.save(job)
            return job

        if not job.requested_skill_id:
            job.transition(JobStatus.AWAITING_INFORMATION, "A specific engineering skill has not been selected.")
            job.add_event("skill_selection_required", "Provider-neutral V1 requires explicit skill selection; no LLM provider is assumed.")
            self.store.save(job)
            return job

        job.skill_id = job.requested_skill_id
        job.transition(JobStatus.ENGINEERING_VALIDATION, "Executing registered deterministic engineering skill.", skill_id=job.skill_id)
        request = SkillRequest(
            skill_id=job.skill_id,
            inputs=job.inputs,
            project_context=job.project_context,
            standards_context=job.standards_context,
            assumptions_context=job.assumptions_context,
            request_id=job.job_id,
        )
        result = execute(request)
        job.result = result.to_dict()
        job.warnings.extend(result.warnings)

        if result.status == "input_validation_failed":
            job.errors.extend(result.validation_errors)
            job.transition(JobStatus.AWAITING_INFORMATION, "Engineering skill reported missing or invalid inputs.", errors=result.validation_errors)
        elif result.status in {"calculation_failed", "skill_not_registered"}:
            job.errors.extend(result.validation_errors)
            job.transition(JobStatus.FAILED, "Engineering execution failed.", errors=result.validation_errors)
        else:
            job.transition(JobStatus.DRAFT_READY, "Engineering draft produced.", skill_status=result.status)
            job.transition(JobStatus.HUMAN_REVIEW, "Draft routed to human engineering review.")
        self.store.save(job)
        return job

    def approve(self, job_id: str, reviewer: str, comment: str = "") -> Job:
        job = self._get(job_id)
        if job.status != JobStatus.HUMAN_REVIEW:
            raise ValueError("Only jobs in human_review can be approved")
        job.transition(JobStatus.APPROVED, "Engineering draft approved by human reviewer.", reviewer=reviewer, comment=comment)
        self.store.save(job)
        return job

    def reject(self, job_id: str, reviewer: str, reason: str, retry: bool = False) -> Job:
        job = self._get(job_id)
        if job.status != JobStatus.HUMAN_REVIEW:
            raise ValueError("Only jobs in human_review can be rejected")
        job.errors.append(reason)
        if retry:
            job.transition(JobStatus.FAILED, "Human review rejected the draft; retry requested.", reviewer=reviewer, reason=reason)
            job.transition(JobStatus.RETRY, "Job marked for retry after human rejection.")
        else:
            job.transition(JobStatus.FAILED, "Human review rejected the draft.", reviewer=reviewer, reason=reason)
        self.store.save(job)
        return job

    def dispatch(self, job_id: str) -> Job:
        job = self._get(job_id)
        if job.status != JobStatus.APPROVED:
            raise ValueError("Only approved jobs can be dispatched")
        job.transition(JobStatus.DISPATCHING, "Dispatch started.")
        self.store.save(job)
        try:
            result = self.dispatcher(job)
        except Exception as exc:  # external providers should not crash the lifecycle
            job.errors.append(str(exc))
            job.transition(JobStatus.FAILED, "Dispatch failed.", error=str(exc))
            self.store.save(job)
            return job
        job.dispatch_result = result
        job.transition(JobStatus.DISPATCHED, "Dispatch completed.")
        job.transition(JobStatus.COMPLETED, "Job completed after dispatch.")
        self.store.save(job)
        return job

    def list_jobs(self) -> list[Job]:
        return list(self.store.list(tenant_id=self.tenant_id))

    def _get(self, job_id: str) -> Job:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        self._assert_tenant(job)
        return job

    @staticmethod
    def _validate_job(job: Job) -> list[str]:
        errors = []
        if not isinstance(job.inputs, dict):
            errors.append("inputs must be an object/dict")
        if not isinstance(job.project_context, dict):
            errors.append("project_context must be an object/dict")
        errors.extend(validate_governance_context(
            SkillRequest(
                skill_id=job.requested_skill_id or "",
                inputs=job.inputs,
                project_context=job.project_context,
                standards_context=job.standards_context,
                assumptions_context=job.assumptions_context,
            )
        ))
        if not job.source:
            errors.append("source is required")
        return errors

    @staticmethod
    def _is_missing_information_case(errors: list[str]) -> bool:
        markers = ("Missing required", "Provide ", "must be supplied")
        return any(error.startswith(markers) for error in errors)

