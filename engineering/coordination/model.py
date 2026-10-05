"""Deterministic first-pass coordination checks for point/clearance conflicts."""
from dataclasses import dataclass
from math import hypot
from typing import Iterable, List
from engineering.drawing.objects import EngineeringObject

@dataclass(frozen=True)
class CoordinationConflict:
    conflict_id: str
    discipline_a: str
    object_a: str
    discipline_b: str
    object_b: str
    floor_id: str
    severity: str
    description: str
    suggested_resolution: str
    status: str="open"
    review_required: bool=True

def find_coordinate_conflicts(objects: Iterable[EngineeringObject], clearance_mm: float=100.0)->List[CoordinationConflict]:
    if clearance_mm < 0: raise ValueError("clearance_mm must not be negative")
    items=list(objects); conflicts=[]
    for i,a in enumerate(items):
        for b in items[i+1:]:
            if a.floor_id != b.floor_id or a.discipline == b.discipline: continue
            if hypot(a.x_mm-b.x_mm,a.y_mm-b.y_mm) <= clearance_mm:
                cid=f"CLASH-{a.object_id}-{b.object_id}"
                conflicts.append(CoordinationConflict(cid,a.discipline,a.object_id,b.discipline,b.object_id,a.floor_id,"high" if clearance_mm else "medium",f"Objects are within {clearance_mm:g} mm coordination clearance.","Review routing/elevation and resolve with the responsible engineer."))
    return conflicts
