from __future__ import annotations

from typing import Dict, Iterable, Optional


class InMemoryReportStore:
    def __init__(self) -> None:
        self._reports: Dict[str, object] = {}

    def save(self, report):
        self._reports[report.report_id] = report
        return report

    def get(self, report_id: str):
        return self._reports.get(report_id)

    def list(self, *, tenant_id: Optional[str] = None) -> Iterable[object]:
        values = self._reports.values()
        if tenant_id is None:
            return list(values)
        return [r for r in values if r.tenant_id == tenant_id]
