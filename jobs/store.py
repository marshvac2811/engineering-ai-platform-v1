"""Storage interface with an in-memory V1 implementation."""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from .models import Job


class JobStore:
    def save(self, job: Job) -> Job:  # pragma: no cover - interface
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[Job]:  # pragma: no cover - interface
        raise NotImplementedError

    def list(self, *, tenant_id: Optional[str] = None) -> Iterable[Job]:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def save(self, job: Job) -> Job:
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self, *, tenant_id: Optional[str] = None) -> Iterable[Job]:
        return tuple(j for j in self._jobs.values() if tenant_id is None or j.tenant_id == tenant_id)
