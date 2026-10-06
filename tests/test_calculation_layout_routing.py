import pytest

from engineering.building.ingest import ingest_structured_layout
from engineering.design.routing import route_calculation_outputs


def _building():
    return ingest_structured_layout({
        "building_id": "B1",
        "name": "Routing Test",
        "floors": [{"floor_id": "F1", "name": "Ground", "rooms": [
            {"room_id": "R1", "name": "Office", "area_m2": 20, "x_mm": 100, "y_mm": 200},
        ]}],
    })


def test_routes_only_explicit_room_and_calculation_reference():
    result = route_calculation_outputs(
        _building(),
        discipline="HVAC",
        floor_id="F1",
        calculation_outputs=[{"room_id": "R1", "source_calculation": "duct-task-1", "airflow_m3h": 500}],
    )
    assert result["status"] == "ready"
    assert result["inference_performed"] is False
    assert result["room_inputs"]["R1"]["airflow_m3h"] == 500


def test_missing_room_identity_is_a_blocker_not_an_inference_request():
    result = route_calculation_outputs(
        _building(),
        discipline="HVAC",
        floor_id="F1",
        calculation_outputs=[{"source_calculation": "duct-task-1", "airflow_m3h": 500}],
    )
    assert result["status"] == "blocked"
    assert "room_id" in result["blockers"][0]


def test_missing_geometry_blocks_layout_placement():
    building = ingest_structured_layout({
        "building_id": "B1",
        "name": "No Geometry",
        "floors": [{"floor_id": "F1", "name": "Ground", "rooms": [
            {"room_id": "R1", "name": "Office", "area_m2": 20},
        ]}],
    })
    result = route_calculation_outputs(
        building,
        discipline="HVAC",
        floor_id="F1",
        calculation_outputs=[{"room_id": "R1", "source_calculation": "task-1", "airflow_m3h": 500}],
    )
    assert result["status"] == "blocked"
    assert any("coordinates" in x for x in result["blockers"])


def test_routes_fire_water_storage_to_explicit_tank_location():
    result = route_calculation_outputs(_building(), discipline="FIRE", floor_id="F1", calculation_outputs=[{"room_id":"R1","source_calculation":"fire-storage-1","total_storage_m3":132.0}])
    assert result["status"] == "ready"
    assert result["room_inputs"]["R1"]["total_storage_m3"] == 132.0


def test_routes_plumbing_demand_to_explicit_service_location():
    result = route_calculation_outputs(_building(), discipline="PLUMBING", floor_id="F1", calculation_outputs=[{"room_id":"R1","source_calculation":"plumbing-demand-1","design_demand_lpm":20.0}])
    assert result["status"] == "ready"
    assert result["room_inputs"]["R1"]["design_demand_lpm"] == 20.0
