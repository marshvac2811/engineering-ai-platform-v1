import pytest
from skills.fire.preliminary_water_storage import calculate_fire_water_storage
from skills.plumbing.preliminary_water_demand import calculate_plumbing_water_demand

def test_fire_storage():
    r=calculate_fire_water_storage(required_flow_lpm=1000,duration_min=120,reserve_pct=10)
    assert r["total_storage_l"] == 132000
    assert r["human_review_required"] is True

def test_fire_rejects_missing_positive_inputs():
    with pytest.raises(ValueError):
        calculate_fire_water_storage(required_flow_lpm=0,duration_min=120)

def test_plumbing_demand():
    r=calculate_plumbing_water_demand(fixtures=[
        {"fixture_type":"WC","count":4,"flow_lpm":6},
        {"fixture_type":"Wash Basin","count":4,"flow_lpm":4},
    ], diversity_factor_pct=50)
    assert r["total_connected_flow_lpm"] == 40
    assert r["design_demand_lpm"] == 20

def test_plumbing_rejects_invalid_fixture():
    with pytest.raises(ValueError):
        calculate_plumbing_water_demand(fixtures=[{"fixture_type":"WC","count":0,"flow_lpm":6}])
