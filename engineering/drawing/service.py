"""Governed drawing package service helpers.

Drawing packages are linked to an engineering job but remain preliminary until
the normal human-review/approval lifecycle authorizes issue.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from .package import build_drawing_package


def build_job_drawing_package(job: Any, drawings: Iterable[Any], *, source_hashes: Dict[str, str] | None = None, conflicts=None) -> Dict[str, Any]:
    if job is None or not getattr(job, "job_id", None):
        raise ValueError("job with job_id is required")
    drawings = list(drawings)
    if not drawings:
        raise ValueError("at least one drawing is required")
    manifest = build_drawing_package(drawings, source_hashes=source_hashes, conflicts=conflicts)
    manifest["job_id"] = str(job.job_id)
    manifest["tenant_id"] = str(getattr(job, "tenant_id", "") or "")
    manifest["report_id"] = getattr(job, "report_id", None)
    manifest["report_revision"] = int((getattr(job, "result", {}) or {}).get("report_revision") or 1)
    manifest["issue_status"] = "not_approved"
    manifest["dispatch_allowed"] = False
    return manifest


def authorize_drawing_package_issue(manifest: Dict[str, Any], job: Any) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("drawing package manifest must be an object")
    if getattr(job, "status", None).value != "approved":
        raise ValueError("drawing package issue requires an approved engineering job")
    if manifest.get("job_id") != str(job.job_id):
        raise ValueError("drawing package does not belong to this job")
    if manifest.get("manifest_sha256") is None:
        raise ValueError("drawing package manifest hash is required")
    updated = dict(manifest)
    updated["issue_status"] = "approved_for_controlled_dispatch"
    updated["dispatch_allowed"] = True
    updated["approval_job_status"] = "approved"
    return updated
