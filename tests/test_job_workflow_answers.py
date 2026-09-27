import io, json
from jobs import InMemoryJobStore, JobService, JobStatus
from orchestrator.intake import build_plan


def test_plan_is_persisted_on_job_and_answers_replan_until_ready():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    plan = build_plan("Size a duct")
    job = service.create_from_plan(plan)
    assert job.orchestration["normalized_request"] == "Size a duct"
    assert job.status == JobStatus.AWAITING_INFORMATION
    service.provide_missing_information(job.job_id, {"airflow": 8000, "method": "velocity", "duct_type": "round"})
    assert job.status == JobStatus.AWAITING_INFORMATION
    service.provide_missing_information(job.job_id, {"target_velocity_ms": 7, "material": "gss"})
    assert job.status == JobStatus.QUEUED
    assert job.orchestration["status"] == "ready_for_execution"


def test_answers_do_not_queue_when_inputs_remain_missing():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_from_plan(build_plan("Size a duct"))
    service.provide_missing_information(job.job_id, {"airflow": 8000})
    assert job.status == JobStatus.AWAITING_INFORMATION
    assert "method" in job.orchestration["missing_inputs"]


