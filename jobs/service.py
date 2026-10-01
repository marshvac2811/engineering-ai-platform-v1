"""Provider-neutral engineering job lifecycle service.

This V1 service is deliberately synchronous. A database-backed queue worker can
replace the in-memory store without changing the job contract.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from orchestrator.engine import execute, SKILLS
from orchestrator.executor import execute_engineering_plan
from orchestrator.result import build_workflow_result
from skills.common import SkillRequest
from validators.basic import require_positive
from validators.governance import validate_governance_context
from validators.registered_skill_inputs import validate_registered_skill_inputs
from ingestion.service import IngestionService
from reports.service import ReportService

from .models import Job, JobStatus
from .store import JobStore


Dispatcher = Callable[[Job], Dict[str, Any]]


class JobService:
    def __init__(self, store: JobStore, dispatcher: Optional[Dispatcher] = None, *, tenant_id: Optional[str] = None, ingestion_service: Optional[IngestionService] = None, report_service: Optional[ReportService] = None) -> None:
        self.store = store
        self.dispatcher = dispatcher or self._default_dispatcher
        self.tenant_id = tenant_id
        self.ingestion = ingestion_service or IngestionService()
        self.report_service = report_service

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


    def create_from_plan(self, plan, *, attachments: Optional[list[Dict[str, Any]]] = None, provider: Any = None) -> Job:
        """Create a job and, when supplied, turn uploaded files into project context before execution."""
        job = self.create_job(
            source="orchestrator",
            requested_skill_id=plan.selected_skill_id,
            inputs=plan.extracted_inputs,
            project_context=plan.project_context,
            standards_context=plan.standards_context,
            assumptions_context=plan.assumptions_context,
            orchestration=plan.to_dict(),
        )
        job.add_event("orchestration_plan", "Natural-language request classified by orchestrator.", plan=plan.to_dict())

        if attachments:
            import base64
            document_context = list((job.project_context or {}).get("documents") or [])
            for spec in attachments:
                if not isinstance(spec, dict):
                    raise ValueError("Each attachment must be an object")
                filename = str(spec.get("filename") or "attachment.bin").strip()
                raw = spec.get("content_base64")
                if not raw:
                    raise ValueError(f"content_base64 is required for {filename}")
                try:
                    data = base64.b64decode(raw, validate=True)
                except Exception as exc:
                    raise ValueError(f"Invalid base64 content for {filename}") from exc
                self.register_attachment(
                    job.job_id,
                    filename=filename,
                    mime_type=spec.get("mime_type"),
                    data=data,
                    metadata=spec.get("metadata") or {},
                )
                attachment = job.attachments[-1]
                extracted = self.extract_attachment(job.job_id, attachment["attachment_id"])
                document_context.append({
                    "attachment_id": attachment["attachment_id"],
                    "filename": attachment["filename"],
                    "mime_type": attachment["mime_type"],
                    "source_type": attachment["source_type"],
                    "sha256": attachment["sha256"],
                    "extraction_status": extracted.get("status"),
                    "metadata": extracted.get("metadata") or {},
                    "warnings": extracted.get("warnings") or [],
                    "text": extracted.get("text") or "",
                    "chunks": extracted.get("chunks") or [],
                })
            job.project_context = {**(job.project_context or {}), "documents": document_context}

            # Reinterpret the request with the actual project evidence now available.
            from orchestrator.intake import build_plan
            plan = build_plan(
                plan.normalized_request,
                requested_skill_id=plan.selected_skill_id,
                provided_inputs=job.inputs,
                project_context=job.project_context,
                standards_context=job.standards_context,
                assumptions_context=job.assumptions_context,
                provider=provider,
            )
            job.orchestration = plan.to_dict()
            job.add_event("project_context_enriched", "Uploaded project documents were extracted and added to AI engineering context.",
                          attachment_count=len(attachments))

        if plan.status == "awaiting_information":
            job.transition(JobStatus.AWAITING_INFORMATION, "Additional engineering inputs are required before execution.",
                           missing_inputs=plan.missing_inputs)
        elif plan.status in {"ambiguous", "unroutable"}:
            job.add_event("orchestration_needs_clarification", "Orchestrator could not select a unique executable skill.", status=plan.status)
        else:
            self.enqueue(job.job_id)
            job = self.process(job.job_id)
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

    def provide_missing_information(self, job_id: str, updates: Dict[str, Any] | None = None, message: str | None = None) -> Job:
        job = self._get(job_id)
        if job.status != JobStatus.AWAITING_INFORMATION:
            raise ValueError("Job is not awaiting information")
        updates = dict(updates or {})
        if message and str(message).strip():
            from orchestrator.intake import extract_facts
            # Accept a normal-language client reply. Structured inputs remain
            # supported, but the client never needs to know field names.
            extracted = extract_facts(str(message))
            updates = {**extracted, **updates}
        if not updates:
            raise ValueError("Provide information either as normal-language message or structured inputs.")
        # Dashboard form values arrive as strings. Normalize them against the
        # authoritative skill registry before re-planning/execution so numeric
        # engineering inputs are passed to validators/calculators as numbers.
        from skill_framework.registry import load_skill_registry
        registry_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml"
        try:
            definition = load_skill_registry(registry_path).get(job.requested_skill_id or "")
            numeric_types = {
                d.name: d.data_type for d in (
                    list(definition.required_inputs)
                    + list(definition.optional_inputs)
                    + list(definition.conditional_inputs)
                ) if d.data_type in {"number", "integer"}
            }
            normalized_updates = dict(updates)
            for name, data_type in numeric_types.items():
                if name in normalized_updates and isinstance(normalized_updates[name], str):
                    raw = normalized_updates[name].strip()
                    if raw:
                        normalized_updates[name] = int(float(raw)) if data_type == "integer" else float(raw)
            updates = normalized_updates
        except (KeyError, ValueError, TypeError):
            # Keep the original values so the normal validation path reports
            # the precise input error rather than hiding it here.
            pass
        job.inputs.update(updates)
        job.add_event("information_received", "Missing input information supplied.", fields=list(updates))
        from orchestrator.intake import build_plan
        plan = build_plan(
            job.orchestration.get("normalized_request", ""),
            requested_skill_id=job.requested_skill_id,
            provided_inputs=job.inputs,
            project_context=job.project_context,
            standards_context=job.standards_context,
            assumptions_context=job.assumptions_context,
        )
        job.orchestration = plan.to_dict()
        if plan.status == "ready_for_execution":
            job.transition(JobStatus.QUEUED, "All required inputs supplied; job returned to queue.")
            job = self.process(job.job_id)
        else:
            job.add_event("orchestration_replanned", "Additional required inputs remain missing.", missing_inputs=plan.missing_inputs)
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

        plan = dict(job.orchestration.get("engineering_plan") or {})
        if not plan.get("tasks"):
            if not job.requested_skill_id:
                job.transition(JobStatus.AWAITING_INFORMATION, "A specific engineering capability could not be established.")
                job.add_event("skill_selection_required", "No executable capability was established by orchestration.")
                self.store.save(job)
                return job
            plan = {
                "status": "ready_for_execution",
                "tasks": [{
                    "task_id": "task-1",
                    "objective": job.orchestration.get("request_understanding", {}).get("objective") or "Engineering analysis",
                    "capability_id": job.requested_skill_id,
                    "sequence": 1,
                    "depends_on": [],
                    "status": "ready",
                    "missing_inputs": [],
                    "requested_outputs": job.orchestration.get("request_understanding", {}).get("requested_outputs", []),
                    "methodology": job.orchestration.get("request_understanding", {}).get("methodology", {}),
                    "governance": job.standards_context,
                    "human_review_required": True,
                }],
                "execution_order": ["task-1"],
                "human_review_required": True,
            }

        job.skill_id = job.requested_skill_id
        job.transition(JobStatus.ENGINEERING_VALIDATION, "Executing universal engineering workflow.")
        workflow = execute_engineering_plan(
            plan=plan,
            inputs=job.inputs,
            project_context=job.project_context,
            standards_context=job.standards_context,
            assumptions_context=job.assumptions_context,
            request_id=job.job_id,
        )
        job.orchestration["engineering_plan"] = workflow["engineering_plan"]
        consolidated = build_workflow_result(
            workflow=workflow,
            request_understanding=dict(job.orchestration.get("request_understanding") or {}),
            governance=dict(job.orchestration.get("standards_context") or job.standards_context or {}),
            inputs=job.inputs,
            assumptions=job.assumptions_context,
        )
        job.result = {
            **consolidated,
            "engineering_result": {
                "task_results": workflow["engineering_results"],
                "results": workflow["engineering_results"],
                "blockers": workflow["blockers"],
            },
            "human_review_required": True,
        }

        if workflow["status"] == "completed" and workflow["engineering_results"]:
            job.errors = []
            job.transition(JobStatus.DRAFT_READY, "Universal engineering workflow produced a draft.", task_count=len(workflow["engineering_results"]))
            job.transition(JobStatus.HUMAN_REVIEW, "Draft routed to human engineering review.")
        elif workflow["status"] == "awaiting_information":
            job.errors.extend(workflow["blockers"])
            job.transition(JobStatus.AWAITING_INFORMATION, "Universal workflow requires additional engineering information.", blockers=workflow["blockers"])
        elif workflow["status"] in {"blocked", "failed"}:
            job.errors.extend(workflow["blockers"])
            job.transition(JobStatus.FAILED, "Universal engineering workflow could not complete.", blockers=workflow["blockers"])
        else:
            job.add_event("workflow_pending", "Universal workflow has pending dependency-gated tasks.")

        self.store.save(job)
        return job

    def approve(self, job_id: str, reviewer: str, comment: str = "") -> Job:
        job = self._get(job_id)
        if job.status != JobStatus.HUMAN_REVIEW:
            raise ValueError("Only jobs in human_review can be approved")

        # Approval is a hard lifecycle gate. A stale/inconsistent persisted job
        # must never become approved merely because its status says human_review.
        # Re-check the authoritative registry contract and deterministic skill
        # validator against the exact inputs that produced the result.
        result = job.result or {}
        result_status = str(result.get("status") or "")
        if result_status in {"input_validation_failed", "calculation_failed", "skill_not_registered"}:
            raise ValueError("Job cannot be approved because the engineering result is not valid")
        if not isinstance(result.get("engineering_result"), dict) or not result.get("engineering_result"):
            raise ValueError("Job cannot be approved because no engineering result is present")

        from skill_framework.registry import load_skill_registry
        from skill_framework.input_resolver import resolve_input_requirements

        registry_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml"
        registry = load_skill_registry(registry_path)
        plan_tasks = list(job.orchestration.get("engineering_plan", {}).get("tasks") or [])
        if not plan_tasks:
            plan_tasks = [{"task_id": "task-1", "capability_id": job.requested_skill_id or job.skill_id, "status": "completed"}]
        incomplete = [str(t.get("task_id")) for t in plan_tasks if t.get("status") != "completed"]
        if incomplete:
            raise ValueError("Job cannot be approved because workflow tasks are incomplete: " + ", ".join(incomplete))

        for task in plan_tasks:
            capability_id = task.get("capability_id")
            if not capability_id or capability_id not in registry:
                raise ValueError("Job cannot be approved because workflow capability is not registered: " + str(capability_id))
            definition = registry.get(capability_id)
            task_inputs = dict(job.inputs)
            for target, source in dict(task.get("input_bindings") or {}).items():
                source_task, sep, output_name = str(source).partition(".")
                persisted = dict(job.orchestration.get("engineering_plan", {}).get("task_outputs", {}).get(source_task, {}).get("engineering_result") or {})
                if not sep or output_name not in persisted:
                    raise ValueError("Job cannot be approved because bound output is missing: " + str(source))
                task_inputs[str(target)] = persisted[output_name]
            resolution = resolve_input_requirements(definition, task_inputs)
            if resolution.missing_inputs:
                raise ValueError("Job cannot be approved because " + capability_id + " still has required inputs: " + ", ".join(resolution.missing_inputs))
            if resolution.invalid_inputs:
                raise ValueError("Job cannot be approved because " + capability_id + " has invalid inputs: " + "; ".join(resolution.invalid_inputs))
            skill = SKILLS.get(capability_id)
            if skill is not None and hasattr(skill, "validate"):
                validation_errors = list(skill.validate(SkillRequest(
                    skill_id=capability_id,
                    inputs=job.inputs,
                    project_context=job.project_context,
                    standards_context=job.standards_context,
                    assumptions_context=job.assumptions_context,
                    request_id=job.job_id,
                )))
                if validation_errors:
                    raise ValueError("Job cannot be approved because " + capability_id + " validation failed: " + "; ".join(validation_errors))

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
    def _update_orchestration_for_validation_errors(job: Job, errors: list[str]) -> None:
        """Expose actionable skill-validation gaps to the dashboard.

        Some deterministic skills report conditional/semantic requirements only
        during execution (for example, pump_head requires roughness_mm or a
        valid material). The execution error must therefore be reflected back
        into the orchestration plan so the UI can render the exact field(s)
        needed for continuation.
        """
        from skill_framework.registry import load_skill_registry

        registry_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml"
        try:
            definition = load_skill_registry(registry_path).get(job.requested_skill_id or "")
        except (KeyError, ValueError, TypeError):
            return

        definitions = (
            list(definition.required_inputs)
            + list(definition.optional_inputs)
            + list(definition.conditional_inputs)
        )
        fields_by_name = {d.name: d for d in definitions}
        missing = list(job.orchestration.get("missing_inputs") or [])
        questions = list(job.orchestration.get("questions") or [])

        for error in errors:
            text = str(error)
            # Prefer an explicitly named field in "Provide <field> ..." rules.
            match = __import__("re").search(r"Provide\s+([A-Za-z_][A-Za-z0-9_]*)", text)
            if match and match.group(1) in fields_by_name:
                names = [match.group(1)]
            else:
                names = [name for name in fields_by_name if name in text]

            for name in names:
                if name not in missing:
                    missing.append(name)
                definition_for_field = fields_by_name[name]
                question = getattr(definition_for_field, "question", None)
                if question and question not in questions:
                    questions.append(question)

        job.orchestration["missing_inputs"] = missing
        job.orchestration["questions"] = questions

    @staticmethod
    def _is_missing_information_case(errors: list[str]) -> bool:
        markers = ("Missing required", "Provide ", "must be supplied")
        return any(error.startswith(markers) for error in errors)

