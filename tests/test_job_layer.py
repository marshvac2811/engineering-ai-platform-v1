from jobs import InMemoryJobStore, JobService, JobStatus


def sample_inputs():
    return {
        "flow_m3hr": 20,
        "diameter_mm": 80,
        "roughness_mm": 0.0015,
        "straight_length_m": 10,
        "static_head_m": 0,
        "margin_pct": 0,
    }


def test_provider_neutral_job_lifecycle():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_job(tenant_id="test-tenant", source="test", requested_skill_id="pump_head", inputs=sample_inputs())
    assert job.status == JobStatus.RECEIVED
    service.enqueue(job.job_id)
    job = service.process(job.job_id)
    assert job.status == JobStatus.HUMAN_REVIEW
    assert job.result["status"] == "draft_ready"
    service.approve(job.job_id, reviewer="engineer-1", comment="Reviewed")
    job = service.dispatch(job.job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.dispatch_result["mode"] == "manual"
    assert any(e.event_type == "status_change" for e in job.events)


def test_missing_skill_selection_waits_for_information():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_job(tenant_id="test-tenant", source="upwork", inputs=sample_inputs())
    service.enqueue(job.job_id)
    job = service.process(job.job_id)
    assert job.status == JobStatus.AWAITING_INFORMATION


def test_retry_path_after_human_rejection():
    service = JobService(InMemoryJobStore(), tenant_id="test-tenant")
    job = service.create_job(tenant_id="test-tenant", source="fiverr", requested_skill_id="pump_head", inputs=sample_inputs())
    service.enqueue(job.job_id)
    service.process(job.job_id)
    job = service.reject(job.job_id, reviewer="engineer-1", reason="Need revised pipe data", retry=True)
    assert job.status == JobStatus.RETRY
    service.enqueue(job.job_id)
    job = service.process(job.job_id)
    assert job.status == JobStatus.HUMAN_REVIEW
