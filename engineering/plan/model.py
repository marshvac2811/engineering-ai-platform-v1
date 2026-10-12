"""Normalised plan model. All geometry is in METRES. Nothing here is invented: every room carries its source and a confidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Pt = Tuple[float, float]


@dataclass
class PlanRoom:
    room_id: str
    name: str
    polygon: List[Pt]                      # empty when the source has no geometry (schedule only)
    area_m2: float
    centroid: Optional[Pt] = None
    bounds: Optional[Tuple[float, float, float, float]] = None   # minx, miny, maxx, maxy
    occupancy: Optional[int] = None
    name_source: str = "generated"          # label | layer | schedule | generated
    confidence: str = "medium"              # high | medium | low


@dataclass
class PlanModel:
    source_file: str
    file_type: str
    rooms: List[PlanRoom] = field(default_factory=list)
    walls: List[Tuple[Pt, Pt]] = field(default_factory=list)      # wall centre/lines, metres
    bounds: Optional[Tuple[float, float, float, float]] = None
    units_note: str = ""
    scale_note: str = ""
    method: str = ""                        # how rooms were obtained
    warnings: List[str] = field(default_factory=list)
    has_geometry: bool = True
    needs_confirmation: bool = True         # a person must confirm rooms/scale before drawings are issued

    def summary(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file, "file_type": self.file_type, "room_count": len(self.rooms),
            "total_area_m2": round(sum(r.area_m2 for r in self.rooms), 2), "has_geometry": self.has_geometry,
            "units": self.units_note, "scale": self.scale_note, "method": self.method,
            "needs_confirmation": self.needs_confirmation, "warnings": list(self.warnings),
        }


@dataclass
class PlanReadResult:
    status: str                              # ok | partial | unsupported | failed
    model: Optional[PlanModel] = None
    messages: List[str] = field(default_factory=list)
