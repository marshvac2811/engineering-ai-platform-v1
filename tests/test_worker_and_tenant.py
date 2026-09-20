from jobs.models import Job, JobStatus
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from jobs.worker import JobWorker
from jobs.tenant import TenantContext


class ClaimStore(InMemoryJobStore):
    def __init__(self):
        super().__init__()
        self.released = []
        self.heartbeats = []
        self.locked = set()

    def claim_next(self, worker_id, *, tenant_id=None, lock_seconds=300):
        for job in self._jobs.values():
            if job.status == JobStatus.QUEUED and (tenant_id is None or job.tenant_id == tenant_id) and job.job_id not in self.locked:
                self.locked.add(job.job_id)
                return job
        return None

    def release_claim(self, job_id, worker_id):
        self.locked.discard(job_id)
        self.released.append((job_id, worker_id))

    def heartbeat(self, job_id, worker_id):
        self.heartbeats.append((job_id, worker_id))


def test_worker_processes_only_requested_tenant():
    store = ClaimStore()
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"
    for tenant in (tenant_a, tenant_b):
        job = Job.create(
            tenant_id=tenant,
            source="test",
            inputs={"airflow": 1000, "target_velocity_ms": 5, "method": "velocity", "duct_type": "round", "material": "gss"},
            requested_skill_id="duct_sizing",
        )
        job.transition(JobStatus.QUEUED, "queued")
        store.save(job)

    service = JobService(store, tenant_id=tenant_a)
    worker = JobWorker(store, service, worker_id="worker-a", tenant_id=tenant_a)
    outcome = worker.run_once()

    assert outcome.processed is True
    assert outcome.status == JobStatus.HUMAN_REVIEW.value
    assert store.released
    remaining = [j for j in store.list() if j.status == JobStatus.QUEUED]
    assert len(remaining) == 1
    assert remaining[0].tenant_id == tenant_b


def test_service_rejects_cross_tenant_access():
    store = InMemoryJobStore()
    job = Job.create(tenant_id="tenant-b", source="test", inputs={}, requested_skill_id="duct_sizing")
    store.save(job)
    service = JobService(store, tenant_id="tenant-a")

    try:
        service.enqueue(job.job_id)
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_tenant_context_review_and_dispatch_roles():
    assert TenantContext("t1", "u1", "reviewer").can_review()
    assert not TenantContext("t1", "u1", "member").can_review()
    assert TenantContext("t1", "u1", "admin").can_dispatch()
