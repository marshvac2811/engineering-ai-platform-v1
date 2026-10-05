"""Deterministic, source-traceable building model.

This is deliberately CAD/BIM neutral. It stores facts extracted or supplied by a
source; it never invents geometry. Uncertain facts carry confidence and source.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class SourceReference:
    source_id: str
    page: Optional[int]=None
    location: str=""

@dataclass(frozen=True)
class Confidence:
    score: float
    method: str="explicit"
    review_required: bool=False
    def __post_init__(self):
        if not 0 <= self.score <= 1: raise ValueError("confidence score must be between 0 and 1")

@dataclass
class Opening:
    opening_id: str
    kind: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    source: Optional[SourceReference]=None
    confidence: Optional[Confidence]=None

@dataclass
class Room:
    room_id: str
    name: str
    area_m2: Optional[float]=None
    x_mm: Optional[float]=None
    y_mm: Optional[float]=None
    width_mm: Optional[float]=None
    height_mm: Optional[float]=None
    occupancy: Optional[float]=None
    source: Optional[SourceReference]=None
    confidence: Optional[Confidence]=None
    attributes: Dict[str,Any]=field(default_factory=dict)

@dataclass
class ServiceZone:
    zone_id: str
    name: str
    kind: str
    source: Optional[SourceReference]=None
    confidence: Optional[Confidence]=None

@dataclass
class Floor:
    floor_id: str
    name: str
    elevation_m: Optional[float]=None
    rooms: List[Room]=field(default_factory=list)
    openings: List[Opening]=field(default_factory=list)
    service_zones: List[ServiceZone]=field(default_factory=list)
    source: Optional[SourceReference]=None

@dataclass
class BuildingModel:
    building_id: str
    name: str
    units: str="mm"
    floors: List[Floor]=field(default_factory=list)
    sources: List[SourceReference]=field(default_factory=list)
    metadata: Dict[str,Any]=field(default_factory=dict)

    def validate(self)->List[str]:
        errors=[]
        if not self.building_id: errors.append("building_id is required")
        if not self.name: errors.append("name is required")
        seen=set()
        for floor in self.floors:
            if floor.floor_id in seen: errors.append(f"duplicate floor_id: {floor.floor_id}")
            seen.add(floor.floor_id)
            room_ids=set()
            for room in floor.rooms:
                if room.room_id in room_ids: errors.append(f"duplicate room_id on {floor.floor_id}: {room.room_id}")
                room_ids.add(room.room_id)
                if room.area_m2 is not None and room.area_m2 <= 0: errors.append(f"room {room.room_id} area must be positive")
                if room.confidence and room.confidence.score < 0.7: errors.append(f"room {room.room_id} requires confirmation: low confidence")
        return errors

    def review_required(self)->bool:
        return bool(self.validate()) or any((r.confidence and r.confidence.review_required) for f in self.floors for r in f.rooms)
