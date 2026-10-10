"""Hand-checked regression values for the governed calculator catalogue."""
import pytest

from skills.common import SkillRequest
from skills.calculators.catalogue import BY_ID, CALCULATORS, make_skill_class


def run(skill_id, **inputs):
    r = make_skill_class(BY_ID[skill_id])().run(SkillRequest(skill_id=skill_id, inputs=inputs))
    return r


def test_catalogue_has_17_calculators():
    assert len(CALCULATORS) == 17


CASES = [
    # (skill, inputs, key, expected, tolerance)  expected values hand-calculated
    ("psychrometric_properties", dict(dry_bulb_c=35, rh_pct=50), "humidity_ratio", 0.0178, 0.0002),
    ("psychrometric_properties", dict(dry_bulb_c=35, rh_pct=50), "enthalpy_kj_kg", 80.8, 0.2),
    ("cooling_coil_load", dict(airflow_m3h=10000, entering_db_c=28, entering_rh_pct=60, leaving_db_c=13, leaving_rh_pct=95), "total_cooling_kw", 92.6, 0.5),
    ("ventilation_rate", dict(floor_area_m2=100, occupants=10, space_type="office"), "zone_outdoor_air_l_s", 55.0, 0.01),
    ("fan_power_sizing", dict(airflow_m3h=36000, total_static_pressure_pa=800), "air_power_kw", 8.0, 0.01),
    ("fan_power_sizing", dict(airflow_m3h=36000, total_static_pressure_pa=800), "fan_shaft_kw", 12.31, 0.02),
    ("hydronic_flow_rate", dict(load=100, load_unit="tr", delta_t_c=5.5, chiller_cop=5), "flow_usgpm", 242.1, 1.0),
    ("hydronic_flow_rate", dict(load=100, load_unit="tr", delta_t_c=5.5, chiller_cop=5), "condenser_heat_rejection_kw", 422.0, 0.5),
    ("chiller_iplv", dict(cop_100=5, cop_75=5.5, cop_50=6, cop_25=5), "iplv_cop", 5.66, 0.005),
    ("expansion_tank_sizing", dict(system_volume_l=5000, max_temp_c=90, fill_pressure_bar_g=1, max_pressure_bar_g=4), "minimum_tank_volume_l", 301.8, 3.0),
    ("cable_voltage_drop", dict(load_kw=30, length_m=100), "full_load_current_a", 49.1, 0.2),
    ("sprinkler_demand", dict(hazard_class="ordinary_1"), "design_area_m2", 139.0, 0.5),
    ("sprinkler_demand", dict(hazard_class="ordinary_1"), "total_demand_l_min", 1794.0, 3.0),
    ("hot_water_heater_sizing", dict(storage_volume_l=500), "energy_to_heat_kwh", 17.44, 0.02),
    ("rainwater_drainage", dict(catchment_area_m2=500, rainfall_intensity_mm_h=100), "design_flow_l_s", 12.5, 0.01),
    ("solar_pv_sizing", dict(annual_consumption_kwh=150000), "required_capacity_kwp", 100.0, 0.01),
    ("duct_pressure_drop", dict(airflow_m3h=5000, length_m=30, diameter_mm=400), "velocity_ms", 11.05, 0.05),
]


@pytest.mark.parametrize("skill,inputs,key,expected,tol", CASES)
def test_hand_checked_values(skill, inputs, key, expected, tol):
    r = run(skill, **inputs)
    assert r.status == "draft_ready", r.validation_errors
    assert r.engineering_result[key] == pytest.approx(expected, abs=tol)
    assert r.calculation_trace is not None


@pytest.mark.parametrize("skill_id", sorted(BY_ID))
def test_missing_required_input_is_rejected(skill_id):
    r = run(skill_id)
    assert r.status == "input_validation_failed"
