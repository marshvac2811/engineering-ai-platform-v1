import json
from .model import BuildingModel

def to_dict(model: BuildingModel):
    return {"building_id":model.building_id,"name":model.name,"units":model.units,"metadata":model.metadata,"sources":[{"source_id":s.source_id,"page":s.page,"location":s.location} for s in model.sources],"floors":[{"floor_id":f.floor_id,"name":f.name,"elevation_m":f.elevation_m,"rooms":[{"room_id":r.room_id,"name":r.name,"area_m2":r.area_m2,"x_mm":r.x_mm,"y_mm":r.y_mm,"width_mm":r.width_mm,"height_mm":r.height_mm,"occupancy":r.occupancy,"source":({"source_id":r.source.source_id,"page":r.source.page,"location":r.source.location} if r.source else None),"confidence":({"score":r.confidence.score,"method":r.confidence.method,"review_required":r.confidence.review_required} if r.confidence else None),"attributes":r.attributes} for r in f.rooms]} for f in model.floors]}

def to_json(model): return json.dumps(to_dict(model),sort_keys=True,indent=2)
