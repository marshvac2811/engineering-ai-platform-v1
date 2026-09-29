from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from .decision import report_profile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EngineeringReport:
    report_id: str
    tenant_id: str
    job_id: str
    report: Dict[str, Any]
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReportService:
    def __init__(self, store, *, tenant_id: Optional[str] = None) -> None:
        self.store = store
        self.tenant_id = tenant_id

    def _assert_tenant(self, report: EngineeringReport) -> None:
        if self.tenant_id is not None and report.tenant_id != self.tenant_id:
            raise PermissionError("Report does not belong to the configured tenant")

    def build(self, job, work_items: list[Dict[str, Any]]) -> EngineeringReport:
        valid = [item for item in work_items if item.get("result") and item.get("result", {}).get("engineering_result") is not None]
        if not valid:
            raise ValueError("Cannot generate engineering report without a valid engineering result")

        profiles = [report_profile(item["skill_id"]) for item in valid]
        first = profiles[0]
        standards = []
        for item, profile in zip(valid, profiles):
            result = item["result"]
            checks = []
            for check_id in profile.verified_check_ids:
                checks.append({"check_id": check_id, "status": "not_assessed", "reason": "Applicability evidence was not supplied by the workflow context."})
            for standard in result.get("standards", []):
                checks.append({"source": "skill_result", "assessment": standard})
            standards.append({"skill_id": item["skill_id"], "checks": checks, "not_assessed": not bool(profile.verified_check_ids)})

        report_work_items = []
        for item in valid:
            report_item = dict(item)
            result = item.get("result") or {}
            engineering = result.get("engineering_result") or {}
            trace = result.get("calculation_trace") or engineering.get("calculation_trace") or []
            if trace:
                report_item["calculation_trace"] = trace
            report_work_items.append(report_item)

        payload = {
            "report_type": first.report_type if len(valid) == 1 else "engineering_workflow_report",
            "title": first.title if len(valid) == 1 else "Engineering Workflow Report",
            "scope": {
                "requested_skill_id": job.requested_skill_id,
                "normalized_request": job.orchestration.get("normalized_request"),
                "work_item_count": len(valid),
            },
            "work_items": report_work_items,
            "standards_assessment": standards,
            "unsupported_scope": job.orchestration.get("unsupported_scope", []),
            "human_review": {
                "required": True,
                "status": "pending",
                "reason": "Deterministic engineering outputs require human engineering review before approval or dispatch.",
            },
        }
        report = EngineeringReport(str(uuid4()), job.tenant_id, job.job_id, payload)
        self._assert_tenant(report)
        self.store.save(report)
        return report

    def get(self, report_id: str, *, include_content: bool = False):
        report = self.store.get(report_id)
        if report is None:
            raise KeyError(f"Unknown report: {report_id}")
        self._assert_tenant(report)
        return report
