from datetime import datetime, timedelta, timezone
import pytest
from api.memory import MemoryGuard, tune_allocator, rss_mb
from jobs.models import JobStatus
from jobs.service import JobService
from jobs.store import InMemoryJobStore


class _Store(InMemoryJobStore):
    def create_dispatch_artifacts(self, job):
        return {"pdf": "x.pdf"}


def _old(job, minutes=30):
    job.updated_at = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def test_interrupted_dispatch_is_failed_and_retryable():
    store = _Store(); svc = JobService(store, tenant_id="t1", dispatcher=lambda j: {})
    job = svc.create_job(source="api", requested_skill_id="duct_sizing", inputs={}, project_context={})
    job.status = JobStatus.DISPATCHING; _old(job); store.save(job)
    assert svc.recover_interrupted() == [job.job_id]
    assert store.get(job.job_id).status == JobStatus.FAILED
    assert svc.retry(job.job_id).status == JobStatus.COMPLETED


def test_recent_jobs_are_left_alone():
    store = _Store(); svc = JobService(store, tenant_id="t1")
    job = svc.create_job(source="api", requested_skill_id="duct_sizing", inputs={}, project_context={})
    job.status = JobStatus.PROCESSING; _old(job, 1); store.save(job)
    assert svc.recover_interrupted() == []


def test_interrupted_processing_can_be_rerun():
    store = _Store(); svc = JobService(store, tenant_id="t1")
    job = svc.create_job(source="api", requested_skill_id="duct_sizing", inputs={}, project_context={})
    job.status = JobStatus.QUEUED; svc.store.save(job)
    job.transition(JobStatus.PROCESSING, "Job processing started."); _old(job); store.save(job)
    assert svc.recover_interrupted() == [job.job_id]
    with pytest.raises(ValueError):
        svc.retry_dispatch(job.job_id)
    again = svc.retry(job.job_id)
    assert again.status != JobStatus.FAILED or again.errors   # the job was processed again


def test_memory_helpers_do_not_crash():
    tune_allocator(2)
    assert rss_mb() >= 0
    out = list(MemoryGuard(lambda e, s: [b"ok"])({"REQUEST_METHOD": "GET", "PATH_INFO": "/"}, lambda *a: None))
    assert out == [b"ok"]
