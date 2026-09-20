"""Queue worker for the provider-neutral engineering job lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .models import Job, JobStatus
from .service import JobService


class ClaimableStore(Protocol):
    def claim_next(self, worker_id: str, *, tenant_id: Optional[str] = None, lock_seconds: int = 300) -> Optional[Job]: ...
    def release_claim(self, job_id: str, worker_id: str) -> None: ...
    def heartbeat(self, job_id: str, worker_id: str) -> None: ...


@dataclass
class WorkerOutcome:
    worker_id: str
    job_id: Optional[str]
    status: Optional[str]
    processed: bool
    error: Optional[str] = None


class JobWorker:
    """Claims one queued job, delegates execution to JobService, then releases the lock.

    The worker is intended for trusted server-side execution. Browser clients should
    never receive database service-role credentials or call worker claim RPCs.
    """

    def __init__(
        self,
        store: ClaimableStore,
        service: JobService,
        *,
        worker_id: str,
        tenant_id: Optional[str] = None,
        lock_seconds: int = 300,
    ) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        self.store = store
        self.service = service
        self.worker_id = worker_id
        self.tenant_id = tenant_id
        self.lock_seconds = lock_seconds

    def run_once(self) -> WorkerOutcome:
        job = self.store.claim_next(
            self.worker_id,
            tenant_id=self.tenant_id,
            lock_seconds=self.lock_seconds,
        )
        if job is None:
            return WorkerOutcome(self.worker_id, None, None, False)

        try:
            # Service tenant scoping is defense-in-depth on top of database RLS.
            if self.tenant_id is not None and job.tenant_id != self.tenant_id:
                raise PermissionError("Claimed job belongs to a different tenant")
            processed = self.service.process(job.job_id)
            return WorkerOutcome(
                self.worker_id,
                processed.job_id,
                processed.status.value,
                True,
            )
        except Exception as exc:
            # Recover the lifecycle from unexpected calculation/provider errors.
            current = self.service.store.get(job.job_id)
            if current is not None:
                current.errors.append(str(exc))
                if current.status in {
                    JobStatus.PROCESSING,
                    JobStatus.INPUT_VALIDATION,
                    JobStatus.ENGINEERING_VALIDATION,
                }:
                    current.transition(JobStatus.FAILED, "Worker caught an unexpected processing error.", error=str(exc))
                self.service.store.save(current)
            return WorkerOutcome(
                self.worker_id,
                job.job_id,
                current.status.value if current is not None else None,
                False,
                str(exc),
            )
        finally:
            self.store.release_claim(job.job_id, self.worker_id)

    def heartbeat(self, job_id: str) -> None:
        self.store.heartbeat(job_id, self.worker_id)
