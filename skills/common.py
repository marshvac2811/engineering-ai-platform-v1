"""Common request/result contracts for deterministic engineering skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class SkillRequest:
    skill_id: str
    inputs: Dict[str, Any]
    project_context: Dict[str, Any] = field(default_factory=dict)
    standards_context: Dict[str, Any] = field(default_factory=dict)
    assumptions_context: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None


@dataclass
class SkillResult:
    skill_id: str
    status: str
    engineering_result: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[Dict[str, Any]] = field(default_factory=list)
    standards: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    calculation_trace: List[Dict[str, Any]] = field(default_factory=list)
    human_review_required: bool = True
    source_revision: Optional[str] = None
    skill_version: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "status": self.status,
            "engineering_result": self.engineering_result,
            "assumptions": self.assumptions,
            "standards": self.standards,
            "skill_version": self.skill_version,
            "warnings": self.warnings,
            "validation_errors": self.validation_errors,
            "calculation_trace": self.calculation_trace,
            "human_review_required": self.human_review_required,
            "source_revision": self.source_revision,
            "created_at": self.created_at,
        }
