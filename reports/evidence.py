"""Immutable-style engineering evidence bundle construction.

The bundle is stored inside the authoritative job result so every engineering
task has a reproducible record of what was supplied, calculated, evidenced,
reviewed, and delivered. Hashes are over canonical JSON representations.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_evidence_bundle(*, job, workflow: Dict[str, Any], consolidated: Dict[str, Any]) -> Dict[str, Any]:
    results = list(workflow.get("engineering_results") or [])
    task_outputs = []
    for item in results:
        engineering = item.get("engineering_result") or {}
        task_outputs.append({
            "task_id": item.get("task_id"),
            "capability_id": item.get("capability_id"),
            "status": item.get("status"),
            "objective": item.get("objective"),
            "inputs": item.get("inputs") or {},
            "input_bindings": item.get("input_bindings") or {},
            "engineering_result": engineering,
            "calculation_trace": item.get("calculation_trace") or engineering.get("calculation_trace") or [],
            "assumptions": item.get("assumptions") or engineering.get("assumptions") or [],
            "warnings": item.get("warnings") or engineering.get("warnings") or [],
            "compliance": item.get("compliance") or engineering.get("compliance") or [],
        })

    evidence_sources = []
    for attachment in list(job.attachments or []):
        evidence_sources.append({
            "type": "project_attachment",
            "attachment_id": attachment.get("attachment_id"),
            "filename": attachment.get("filename"),
            "mime_type": attachment.get("mime_type"),
            "sha256": attachment.get("sha256"),
            "extraction_status": attachment.get("extraction_status"),
            "extraction_warnings": attachment.get("extraction_warnings") or [],
        })

    manifest = {
        "schema_version": "engineering-evidence-v1",
        "job_id": job.job_id,
        "tenant_id": job.tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status_at_capture": job.status.value,
        "requested_skill_id": job.requested_skill_id,
        "executed_capabilities": [x.get("capability_id") for x in task_outputs if x.get("capability_id")],
        "source_evidence": evidence_sources,
        "input_hash": sha256(job.inputs or {}),
        "project_context_hash": sha256(job.project_context or {}),
        "standards_context_hash": sha256(job.standards_context or {}),
        "assumptions_context_hash": sha256(job.assumptions_context or {}),
        "task_count": len(task_outputs),
    }

    bundle = {
        "manifest": manifest,
        "request": {
            "source": job.source,
            "requested_skill_id": job.requested_skill_id,
            "inputs": job.inputs,
            "project_context": job.project_context,
            "standards_context": job.standards_context,
            "assumptions_context": job.assumptions_context,
            "orchestration": job.orchestration,
        },
        "tasks": task_outputs,
        "workflow": {
            "status": workflow.get("status"),
            "blockers": workflow.get("blockers") or [],
            "engineering_plan": workflow.get("engineering_plan") or {},
        },
        "result": consolidated,
        "qa": consolidated.get("qa") or {},
        "governance": consolidated.get("governance") or {},
        "delivery": getattr(job, "dispatch_result", None) or {},
        "review": {
            "required": True,
            "status": "approved" if job.status.value in {"approved", "dispatching", "dispatched", "completed"} else "pending",
            "events": [e.to_dict() if hasattr(e, "to_dict") else {
                "event_type": e.event_type, "status": e.status,
                "message": e.message, "metadata": e.metadata, "created_at": e.created_at
            } for e in job.events],
        },
    }

    # Hash the complete evidence content separately from the manifest.
    bundle["manifest"]["bundle_sha256"] = sha256(bundle)
    return bundle


def refresh_evidence_bundle(*, job) -> Dict[str, Any]:
    """Rebuild the evidence bundle from the persisted job after lifecycle changes."""
    result = dict(job.result or {})
    result.pop("evidence_bundle", None)
    engineering = dict(result.get("engineering_result") or {})
    workflow = {
        "status": result.get("status") or job.status.value,
        "blockers": engineering.get("blockers") or [],
        "engineering_plan": job.orchestration.get("engineering_plan") or {},
        "engineering_results": engineering.get("task_results") or engineering.get("results") or [],
    }
    return build_evidence_bundle(job=job, workflow=workflow, consolidated=result)
