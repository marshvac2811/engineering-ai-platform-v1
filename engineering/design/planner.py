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
        if spec is None: continue
        if room.x_mm is None or room.y_mm is None: raise ValueError(f"room {room.room_id} has no coordinates; drawing placement cannot be inferred")
        if discipline=="HVAC":
            airflow=spec.get("airflow_m3h")
            if airflow is None: raise ValueError(f"HVAC room {room.room_id} requires explicit airflow_m3h")
            objects.append(EngineeringObject(f"AT-{room.room_id}","HVAC","air_terminal",room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0,attributes={"airflow_m3h":airflow}))
        elif discipline=="FIRE":
            kind=spec.get("protection_type")
            storage_m3=spec.get("total_storage_m3")
            if kind:
                objects.append(EngineeringObject(f"FP-{room.room_id}","FIRE",str(kind).lower(),room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0))
            elif storage_m3 is not None:
                objects.append(EngineeringObject(f"FT-{room.room_id}","FIRE","fire_tank",room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0,attributes={"storage_m3":storage_m3}))
            else:
                raise ValueError(f"FIRE room {room.room_id} requires explicit protection_type or total_storage_m3")
        else:
            fixture=spec.get("fixture_type")
            demand=spec.get("design_demand_lpm")
            if fixture:
                objects.append(EngineeringObject(f"PL-{room.room_id}","PLUMBING","fixture",room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0,attributes={"fixture_type":fixture}))
            elif demand is not None:
                objects.append(EngineeringObject(f"PD-{room.room_id}","PLUMBING","water_demand",room.x_mm,room.y_mm,floor_id,source_calculation=str(spec.get("source_calculation") or ""),confidence=room.confidence.score if room.confidence else 1.0,attributes={"design_demand_lpm":demand}))
            else:
                raise ValueError(f"PLUMBING room {room.room_id} requires explicit fixture_type or design_demand_lpm")
    return DisciplineDrawing(f"{discipline}-{building.building_id}-{floor_id}-R{revision}",f"{discipline} Preliminary Layout - {floor.name}",discipline,floor_id,objects,revision=revision,status="preliminary",metadata={"building_id":building.building_id,"human_review_required":True,"design_boundary":"preliminary engineering layout; discipline calculations and project/code review required"})
