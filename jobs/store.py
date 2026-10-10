"""Storage interface with an in-memory V1 implementation."""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from reports.artifacts import build_approved_pdf, build_evidence_xlsx, sha256_bytes

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
        self._artifacts: Dict[str, Dict[str, object]] = {}

    def save(self, job: Job) -> Job:
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self, *, tenant_id: Optional[str] = None) -> Iterable[Job]:
        return tuple(j for j in self._jobs.values() if tenant_id is None or j.tenant_id == tenant_id)

    def get_artifact_bytes(self, job_id: str, kind: str, *, tenant_id: Optional[str] = None) -> Optional[bytes]:
        if kind not in {"pdf", "xlsx"}:
            raise ValueError("kind must be 'pdf' or 'xlsx'")
        data = (self._artifacts.get(job_id) or {}).get(kind)
        return data if isinstance(data, (bytes, bytearray)) else None

    def create_dispatch_artifacts(self, job: Job) -> Dict[str, object]:
        evidence = (job.result or {}).get("evidence_bundle")
        if not evidence:
            raise RuntimeError("Evidence bundle is missing; final dispatch is not permitted")
        pdf = build_approved_pdf(job=job, evidence_bundle=evidence)
        xlsx = build_evidence_xlsx(job=job, evidence_bundle=evidence)
        payload = {
            "report_id": job.report_id,
            "pdf": {
                "filename": f"engineering-report-{job.job_id}.pdf",
                "sha256": sha256_bytes(pdf),
                "watermark": "ENGINEERING AI PLATFORM • APPROVED CONTROLLED DOCUMENT",
            },
            "evidence_workbook": {
                "filename": f"engineering-evidence-{job.job_id}.xlsx",
                "sha256": sha256_bytes(xlsx),
            },
        }
        self._artifacts[job.job_id] = {"metadata": payload, "pdf": pdf, "xlsx": xlsx}
        return payload
