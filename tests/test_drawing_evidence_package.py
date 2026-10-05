from engineering.building import ingest_structured_layout
from engineering.design import plan_discipline_layout
from engineering.drawing import build_drawing_package

def test_drawing_package_has_hashes_revision_and_source_trace():
    b=ingest_structured_layout({"building_id":"B1","name":"Demo","sources":[{"source_id":"A-101","page":1}],"floors":[{"floor_id":"L1","name":"Ground","rooms":[{"room_id":"R1","name":"Office","x_mm":100,"y_mm":100,"area_m2":20}]}]})
    d=plan_discipline_layout(b,"HVAC","L1",{"R1":{"airflow_m3h":500,"source_calculation":"load-1"}})
    p=build_drawing_package([d],source_hashes={"A-101":"abc"})
    assert p["manifest_sha256"] and p["drawings"][0]["json_sha256"] and p["drawings"][0]["revision"]=="A"
    assert p["source_hashes"]["A-101"]=="abc" and p["drawings"][0]["source_calculations"]==["load-1"]

def test_drawing_package_remains_preliminary():
    b=ingest_structured_layout({"building_id":"B1","name":"Demo","floors":[{"floor_id":"L1","name":"Ground","rooms":[{"room_id":"R1","name":"Office","x_mm":100,"y_mm":100}]}]})
    d=plan_discipline_layout(b,"PLUMBING","L1",{"R1":{"fixture_type":"WC"}})
    p=build_drawing_package([d]); assert p["status"]=="preliminary" and p["human_review_required"]
