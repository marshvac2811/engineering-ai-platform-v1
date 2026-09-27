"""Phase 16 structured engineering drawing model.

The model is intentionally CAD-neutral. Geometry is explicit, deterministic and
validated before a downstream DXF/PDF renderer is invoked.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Line:
    start: Point
    end: Point
    layer: str = "DEFAULT"


@dataclass(frozen=True)
class Dimension:
    start: Point
    end: Point
    value: float
    unit: str = "mm"
    label: str = ""


@dataclass
class DrawingModel:
    drawing_id: str
    title: str
    units: str = "mm"
    lines: List[Line] = field(default_factory=list)
    dimensions: List[Dimension] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors = []
        if not self.drawing_id:
            errors.append("drawing_id is required")
        if not self.title:
            errors.append("title is required")
        for i, line in enumerate(self.lines):
            if line.start == line.end:
                errors.append(f"line[{i}] has zero length")
        for i, dim in enumerate(self.dimensions):
            if dim.value <= 0:
                errors.append(f"dimension[{i}] must be positive")
        return errors


def facade_elevation(width_mm: float, height_mm: float,
                     drawing_id: str = "facade-elevation") -> DrawingModel:
    """Create a minimal parametric facade elevation from explicit inputs."""
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("width_mm and height_mm must be positive")
    p1, p2 = Point(0, 0), Point(width_mm, 0)
    p3, p4 = Point(width_mm, height_mm), Point(0, height_mm)
    model = DrawingModel(
        drawing_id=drawing_id,
        title="Facade Elevation",
        metadata={"width_mm": width_mm, "height_mm": height_mm,
                  "generation": "parametric"},
    )
    model.lines.extend([
        Line(p1, p2, "FACADE"),
        Line(p2, p3, "FACADE"),
        Line(p3, p4, "FACADE"),
        Line(p4, p1, "FACADE"),
    ])
    model.dimensions.extend([
        Dimension(p1, p2, width_mm, label="Overall Width"),
        Dimension(p2, p3, height_mm, label="Overall Height"),
    ])
    return model
