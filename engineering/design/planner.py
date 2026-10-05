"""Preliminary drawing planner.

It converts explicit engineering inputs into traceable drawing objects. It does
not calculate loads, hydraulic demand or code compliance and never invents those
values. Real calculators remain authoritative skills in the existing registry.
"""
from typing import Dict, List
from engineering.building.model import BuildingModel
from engineering.drawing.objects import DisciplineDrawing, EngineeringObject

SUPPORTED={"HVAC":{"air_terminal","equipment","duct"},"FIRE":{"sprinkler","hydrant","fire_pipe"},"PLUMBING":{"fixture","water_pipe","drain"}}

def plan_discipline_layout(building:BuildingModel, discipline:str, floor_id:str, room_inputs:Dict[str,Dict], revision="A") -> DisciplineDrawing:
    discipline=discipline.upper()
    if discipline not in SUPPORTED: raise ValueError("discipline must be HVAC, FIRE or PLUMBING")
    floor=next((f for f in building.floors if f.floor_id==floor_id),None)
    if floor is None: raise ValueError(f"unknown floor_id: {floor_id}")
    objects=[]
    for room in floor.rooms:
        spec=room_inputs.get(room.room_id)
        if not spec: continue
        if room.x_mm is None or room.y_mm is None: raise ValueError(f"room {room.room_id} has no coordinates; drawing placement cannot be inferred")
        if discipline=="HVAC":
            airflow=spec.get("airflow_m3h")
            if airflow is None: raise ValueError(f"HVAC room {room.room_id} requires explicit airflow_m3h")
            objects.append(EngineeringObject(f"AT-{room.room_id}","HVAC","air_terminal",room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0,attributes={"airflow_m3h":airflow}))
        elif discipline=="FIRE":
            kind=spec.get("protection_type")
            if not kind: raise ValueError(f"FIRE room {room.room_id} requires explicit protection_type")
            objects.append(EngineeringObject(f"FP-{room.room_id}","FIRE",str(kind).lower(),room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0))
        else:
            fixture=spec.get("fixture_type")
            if not fixture: raise ValueError(f"PLUMBING room {room.room_id} requires explicit fixture_type")
            objects.append(EngineeringObject(f"PL-{room.room_id}","PLUMBING","fixture",room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0,attributes={"fixture_type":fixture}))
    return DisciplineDrawing(f"{discipline}-{building.building_id}-{floor_id}-R{revision}",f"{discipline} Preliminary Layout - {floor.name}",discipline,floor_id,objects,revision=revision,status="preliminary",metadata={"building_id":building.building_id,"human_review_required":True,"design_boundary":"preliminary engineering layout; discipline calculations and project/code review required"})
