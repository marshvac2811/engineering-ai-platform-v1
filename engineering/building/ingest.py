"""Safe ingestion of already-structured layout facts.

PDF/CAD/BIM parsers can be plugged in later. This adapter deliberately accepts
only normalized dictionaries and marks inferred/low-confidence facts explicitly.
"""
from typing import Any, Dict
from .model import BuildingModel, Floor, Room, SourceReference, Confidence

def ingest_structured_layout(payload: Dict[str,Any]) -> BuildingModel:
    if not isinstance(payload,dict): raise ValueError("layout payload must be an object")
    bid=str(payload.get("building_id") or "")
    name=str(payload.get("name") or "")
    if not bid or not name: raise ValueError("building_id and name are required")
    sources=[SourceReference(str(s.get("source_id")),s.get("page"),str(s.get("location") or "")) for s in payload.get("sources",[]) if s.get("source_id")]
    floors=[]
    for f in payload.get("floors",[]):
        rooms=[]
        for r in f.get("rooms",[]):
            conf=r.get("confidence")
            confidence=Confidence(float(conf.get("score",0)),str(conf.get("method","extraction")),bool(conf.get("review_required",False))) if conf else None
            src=SourceReference(str(r["source_id"]),r.get("page"),str(r.get("location") or "")) if r.get("source_id") else None
            rooms.append(Room(str(r.get("room_id") or ""),str(r.get("name") or ""),r.get("area_m2"),r.get("x_mm"),r.get("y_mm"),r.get("width_mm"),r.get("height_mm"),r.get("occupancy"),src,confidence,dict(r.get("attributes") or {})))
        floors.append(Floor(str(f.get("floor_id") or ""),str(f.get("name") or ""),f.get("elevation_m"),rooms,source=SourceReference(str(f["source_id"]),f.get("page")) if f.get("source_id") else None))
    model=BuildingModel(bid,name,str(payload.get("units") or "mm"),floors,sources,dict(payload.get("metadata") or {}))
    errors=model.validate()
    if any(e.startswith("duplicate") or "required" in e for e in errors): raise ValueError("; ".join(errors))
    return model
