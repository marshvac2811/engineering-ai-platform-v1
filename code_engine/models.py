from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

class RequirementType(str, Enum):
    MANDATORY_REGULATORY = "MANDATORY_REGULATORY"
    CONTRACTUAL = "CONTRACTUAL"
    CERTIFICATION = "CERTIFICATION"
    CLIENT_REQUIREMENT = "CLIENT_REQUIREMENT"
    ENGINEERING_REFERENCE = "ENGINEERING_REFERENCE"

class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"

@dataclass(frozen=True)
class CodeDocument:
    authority: str
    code_name: str
    edition: str
    category: str
    jurisdiction: str = ""
    status: str = "active"
    source_url: str = ""
    effective_from: str = ""
    notes: str = ""

@dataclass(frozen=True)
class CodeRequirement:
    requirement_id: str
    document: CodeDocument
    clause: str
    title: str
    discipline: str
    parameter: str
    operator: str
    required_value: float
    unit: str
    requirement_type: RequirementType
    applicability: Dict[str, Any] = field(default_factory=dict)
    verification_method: str = "calculation"

@dataclass(frozen=True)
class ComplianceCheck:
    requirement_id: str
    status: ComplianceStatus
    input_value: Optional[float]
    required_value: Optional[float]
    unit: str
    calculation: str
    clause_reference: str
    authority: str
    code_name: str
    edition: str
    requirement_type: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "requirement_id": self.requirement_id,
            "status": self.status.value,
            "input_value": self.input_value,
            "required_value": self.required_value,
            "unit": self.unit,
            "calculation": self.calculation,
            "clause_reference": self.clause_reference,
            "authority": self.authority,
            "code_name": self.code_name,
            "edition": self.edition,
            "requirement_type": self.requirement_type,
            "evidence": self.evidence,
        }
