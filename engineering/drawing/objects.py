"""Engineering drawing objects shared by HVAC, fire and plumbing."""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class EngineeringObject:
    object_id: str
    discipline: str
    kind: str
    x_mm: float
    y_mm: float
    floor_id: str
    size: Optional[str]=None
    source_calculation: Optional[str]=None
    confidence: Optional[float]=None
    attributes: Dict[str,Any]=field(default_factory=dict)

    def __post_init__(self):
        if self.confidence is not None and not 0 <= self.confidence <= 1: raise ValueError("confidence must be 0..1")

@dataclass(frozen=True)
class DrawingAnnotation:
    text: str
    x_mm: float
    y_mm: float
    kind: str="NOTE"

@dataclass
class DisciplineDrawing:
    drawing_id: str
    title: str
    discipline: str
    floor_id: str
    objects: list[EngineeringObject]=field(default_factory=list)
    annotations: list[DrawingAnnotation]=field(default_factory=list)
    revision: str="A"
    status: str="preliminary"
    metadata: Dict[str,Any]=field(default_factory=dict)

    def validate(self):
        errors=[]
        if not self.drawing_id: errors.append("drawing_id is required")
        if not self.floor_id: errors.append("floor_id is required")
        if self.status not in {"preliminary","review","approved","superseded"}: errors.append("invalid drawing status")
        if any(o.discipline.upper()!=self.discipline.upper() for o in self.objects): errors.append("object discipline mismatch")
        return errors
