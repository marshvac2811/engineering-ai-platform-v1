import pytest
from jobs.models import JobStatus
from jobs.service import JobService
from jobs.store import InMemoryJobStore


class _Store(InMemoryJobStore):
    fail = True

    def create_dispatch_artifacts(self, job):
        if self.fail:
            raise RuntimeError("storage timeout")
        return {"pdf": "x.pdf"}


def _approved(svc):
    job = svc.create_job(source="api", requested_skill_id="duct_sizing", inputs={}, project_context={})
    job.status = JobStatus.APPROVED
    svc.store.save(job)
    return job


def test_failed_dispatch_can_be_retried():
    store = _Store()
    svc = JobService(store, tenant_id="t1", dispatcher=lambda j: {"sent": True})
    job = _approved(svc)
    assert svc.dispatch(job.job_id).status == JobStatus.FAILED
    store.fail = False
    done = svc.retry_dispatch(job.job_id)
    assert done.status == JobStatus.COMPLETED
    assert done.dispatch_result["artifacts"] == {"pdf": "x.pdf"}


def test_retry_refused_for_other_failures_and_other_states():
    store = _Store()
    svc = JobService(store, tenant_id="t1", dispatcher=lambda j: {})
    job = svc.create_job(source="api", requested_skill_id="duct_sizing", inputs={}, project_context={})
    with pytest.raises(ValueError):
        svc.retry_dispatch(job.job_id)          # not failed
    job.status = JobStatus.FAILED
    store.save(job)
    with pytest.raises(ValueError):
        svc.retry_dispatch(job.job_id)          # failed earlier than dispatch
