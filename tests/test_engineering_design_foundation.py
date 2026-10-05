import json
import pytest
from engineering.building import ingest_structured_layout
from engineering.building.serialization import to_json
from engineering.design import plan_discipline_layout
from engineering.drawing import drawing_to_svg
from engineering.coordination import find_coordinate_conflicts

def building():
    return ingest_structured_layout({"building_id":"B1","name":"Demo","sources":[{"source_id":"A-101","page":1}],"floors":[{"floor_id":"L1","name":"Ground","rooms":[{"room_id":"R1","name":"Office","area_m2":20,"x_mm":100,"y_mm":100,"confidence":{"score":0.98,"method":"explicit"}},{"room_id":"R2","name":"Toilet","area_m2":6,"x_mm":150,"y_mm":120,"confidence":{"score":0.95,"method":"explicit"}}]})

def test_building_model_is_source_traceable_and_deterministic():
    b=building(); data=json.loads(to_json(b)); assert data["sources"][0]["source_id"]=="A-101"; assert data["floors"][0]["rooms"][0]["room_id"]=="R1"

def test_low_confidence_requires_confirmation():
    b=ingest_structured_layout({"building_id":"B1","name":"Demo","floors":[{"floor_id":"L1","name":"Ground","rooms":[{"room_id":"R1","name":"Office","area_m2":20,"x_mm":1,"y_mm":1,"confidence":{"score":0.4,"method":"ocr"}}]}]})
    assert b.review_required()

def test_hvac_planner_requires_explicit_airflow_and_is_traceable():
    b=building(); d=plan_discipline_layout(b,"HVAC","L1",{"R1":{"airflow_m3h":500,"source_calculation":"load-job-1"}}); assert d.objects[0].attributes["airflow_m3h"]==500; assert d.objects[0].source_calculation=="load-job-1"; assert "preliminary" in d.metadata["design_boundary"]

def test_fire_and_plumbing_require_explicit_engineering_inputs():
    b=building()
    with pytest.raises(ValueError): plan_discipline_layout(b,"FIRE","L1",{"R1":{}})
    with pytest.raises(ValueError): plan_discipline_layout(b,"PLUMBING","L1",{"R2":{}})

def test_drawing_svg_is_deterministic_and_validated():
    b=building(); d=plan_discipline_layout(b,"HVAC","L1",{"R1":{"airflow_m3h":500}}); svg=drawing_to_svg(d); assert svg.startswith("<svg"); assert "AT-R1" in svg

def test_coordination_detects_cross_discipline_clearance_conflict():
    b=building(); h=plan_discipline_layout(b,"HVAC","L1",{"R1":{"airflow_m3h":500}}); p=plan_discipline_layout(b,"PLUMBING","L1",{"R1":{"fixture_type":"WC"}}); c=find_coordinate_conflicts(h.objects+p.objects,clearance_mm=100); assert c and c[0].review_required

def test_no_geometry_is_invented_when_coordinates_missing():
    b=ingest_structured_layout({"building_id":"B1","name":"Demo","floors":[{"floor_id":"L1","name":"Ground","rooms":[{"room_id":"R1","name":"Office","area_m2":20}]}]})
    with pytest.raises(ValueError,match="no coordinates"): plan_discipline_layout(b,"HVAC","L1",{"R1":{"airflow_m3h":500}})
