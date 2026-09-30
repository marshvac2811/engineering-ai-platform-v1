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
    assert job.status == JobStatus.HUMAN_REVIEW
    assert job.orchestration["status"] == "ready_for_execution"
    assert job.result["status"] == "draft_ready"


def test_answers_do_not_queue_when_inputs_remain_missing():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_from_plan(build_plan("Size a duct"))
    service.provide_missing_information(job.job_id, {"airflow": 8000})
    assert job.status == JobStatus.AWAITING_INFORMATION
    assert "method" in job.orchestration["missing_inputs"]




def test_pump_head_intake_surfaces_complete_input_contract():
    plan = build_plan("Calculate pump head")
    assert plan.status == "awaiting_information"
    assert {
        "flow_m3hr",
        "diameter_mm",
        "straight_length_m",
        "static_head_m",
        "margin_pct",
        "roughness_mm",
        "material",
    }.issubset(set(plan.missing_inputs))


def test_answers_automatically_continue_to_human_review_when_complete():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_from_plan(build_plan("Calculate pump head"))
    service.provide_missing_information(
        job.job_id,
        {
            "flow_m3hr": 20,
            "diameter_mm": 80,
            "straight_length_m": 60,
            "static_head_m": 8,
            "margin_pct": 10,
            "material": "gi",
        },
    )
    assert job.status == JobStatus.HUMAN_REVIEW
    assert job.result["status"] == "draft_ready"
    assert job.result["engineering_result"]["total_dynamic_head_m"] > 0
    assert job.errors == []


def test_approval_rejects_inconsistent_job_with_missing_inputs():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_job(
        source="test",
        requested_skill_id="pump_head",
        inputs={
            "flow_m3hr": 20,
            "straight_length_m": 60,
            "static_head_m": 8,
            "margin_pct": 10,
            "material": "gi",
        },
        project_context={},
    )
    job.skill_id = "pump_head"
    job.result = {
        "status": "draft_ready",
        "engineering_result": {"total_dynamic_head_m": 10.0},
    }
    job.transition(JobStatus.QUEUED, "test")
    job.transition(JobStatus.PROCESSING, "test")
    job.transition(JobStatus.INPUT_VALIDATION, "test")
    job.transition(JobStatus.ENGINEERING_VALIDATION, "test")
    job.transition(JobStatus.DRAFT_READY, "test")
    job.transition(JobStatus.HUMAN_REVIEW, "test")
    service.store.save(job)

    try:
        service.approve(job.job_id, "test-reviewer")
        assert False, "Approval should reject incomplete engineering inputs"
    except ValueError as exc:
        assert "missing" in str(exc).lower()
