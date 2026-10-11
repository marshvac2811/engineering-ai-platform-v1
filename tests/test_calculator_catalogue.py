"""Hand-checked regression values for the governed calculator catalogue."""
import pytest

from skills.common import SkillRequest
from skills.calculators.catalogue import BY_ID, CALCULATORS, make_skill_class


def run(skill_id, **inputs):
    r = make_skill_class(BY_ID[skill_id])().run(SkillRequest(skill_id=skill_id, inputs=inputs))
    return r


def test_catalogue_has_21_calculators():
    assert len(CALCULATORS) == 21


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
    # hand calc: 1000 x 9.80665 x (100/3600) x 30 / 1000 = 8.172 kW; /0.70 = 11.675 kW shaft; x1.15 = 13.43 -> 15 kW motor
    ("pump_power_sizing", dict(flow_m3h=100, head_m=30), "hydraulic_power_kw", 8.172, 0.005),
    ("pump_power_sizing", dict(flow_m3h=100, head_m=30), "pump_shaft_kw", 11.675, 0.01),
    ("pump_power_sizing", dict(flow_m3h=100, head_m=30), "standard_motor_kw", 15.0, 0.001),
    # 200 kW x 0.8 / 0.8 = 200 kVA; x1.2 = 240 -> 250 kVA
    ("generator_sizing", dict(connected_load_kw=200), "required_kva", 240.0, 0.01),
    ("generator_sizing", dict(connected_load_kw=200), "standard_genset_kva", 250, 0.001),
    # 500 x 0.8 / 0.9 = 444.4 kVA; x1.25 = 555.6 -> 630 kVA
    ("transformer_sizing", dict(connected_load_kw=500), "required_kva", 555.56, 0.01),
    ("transformer_sizing", dict(connected_load_kw=500), "standard_transformer_kva", 630, 0.001),
    # 200 people x 45 L = 9000 L/day; overhead 1/3 = 3000 L
    ("domestic_water_tank_sizing", dict(occupants=200), "underground_tank_l", 9000, 0.5),
    ("domestic_water_tank_sizing", dict(occupants=200), "overhead_tank_l", 3000, 0.5),
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


def test_new_calculators_reject_nonpositive_inputs():
    for sid, inputs in (("pump_power_sizing", dict(flow_m3h=0, head_m=10)), ("generator_sizing", dict(connected_load_kw=-5)),
                        ("transformer_sizing", dict(connected_load_kw=0)), ("domestic_water_tank_sizing", dict(occupants=0))):
        assert run(sid, **inputs).status == "input_validation_failed"


def test_new_calculators_route_from_plain_sentences():
    from orchestrator.intake import build_plan
    for text, sid in (("Size a DG set for 200 kW connected load", "generator_sizing"),
                      ("Transformer sizing for 500 kW", "transformer_sizing"),
                      ("Underground tank for 200 occupants", "domestic_water_tank_sizing"),
                      ("Pump motor size for 100 m3/h at 30 m head", "pump_power_sizing")):
        assert build_plan(text).selected_skill_id == sid, text


def test_new_calculators_run_from_plain_sentences_with_disclosed_defaults():
    from jobs.service import JobService
    from jobs.store import InMemoryJobStore
    from orchestrator.intake import build_plan
    for text, key in (("Size a DG set for 200 kW connected load", "standard_genset_kva"),
                      ("Transformer sizing for 500 kW", "standard_transformer_kva"),
                      ("Pump motor size for 100 m3/h at 30 m head", "standard_motor_kw"),
                      ("Underground and overhead tank for 200 people", "underground_tank_l")):
        plan = build_plan(text)
        assert plan.status == "ready_for_execution", (text, plan.missing_inputs)
        job = JobService(InMemoryJobStore(), tenant_id="t").create_from_plan(plan)
        assert job.status.value == "human_review"
        results = job.result["engineering_result"]["results"][0]["engineering_result"]
        assert key in results, results
        assert job.result["assumptions"], "defaults must be disclosed"
