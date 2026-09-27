from __future__ import annotations
from dataclasses import dataclass
from workflow.service import WorkflowTaskService
from workflow.store import InMemoryWorkflowTaskStore

@dataclass(frozen=True)
class TrialResult:
    passed: bool
    task_id: str
    engineering_job_id: str
    status: str
    assertions: tuple[str, ...]


def run_controlled_intake_trial(*, tenant_id: str = "trial-tenant") -> TrialResult:
    store = InMemoryWorkflowTaskStore()
    svc = WorkflowTaskService(store, tenant_id=tenant_id)
    task, created = svc.create_from_event(
        source="upwork", external_id="trial-upwork-001",
        payload={"subject": "Preliminary HVAC load", "body_text": "Calculate cooling load for an office."},
    )
    assert created and task.status == "NEW"
    svc.transition(task.task_id, "TRIAGE")
    svc.transition(task.task_id, "READY_FOR_ENGINEERING")
    svc.link_job(task.task_id, "trial-job-001")
    task = svc.get(task.task_id)
    assertions = (
        "external intake created exactly one workflow task",
        "task reached READY_FOR_ENGINEERING",
        "engineering job linkage moved task to ENGINEERING",
        "tenant-scoped task retrieval returned the same task",
    )
    return TrialResult(True, task.task_id, task.engineering_job_id or "", task.status, assertions)
