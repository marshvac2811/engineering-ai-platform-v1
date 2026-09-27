"""Deterministic drawing serialization for downstream renderers."""
import json
from .model import DrawingModel


def to_dict(model: DrawingModel):
    return {
        "drawing_id": model.drawing_id,
        "title": model.title,
        "units": model.units,
        "lines": [
            {"start": {"x": x.start.x, "y": x.start.y},
             "end": {"x": x.end.x, "y": x.end.y},
             "layer": x.layer}
            for x in model.lines
        ],
        "dimensions": [
            {"start": {"x": x.start.x, "y": x.start.y},
             "end": {"x": x.end.x, "y": x.end.y},
             "value": x.value, "unit": x.unit, "label": x.label}
            for x in model.dimensions
        ],
        "metadata": model.metadata,
    }


def to_json(model: DrawingModel) -> str:
    return json.dumps(to_dict(model), sort_keys=True, indent=2)
