from pathlib import Path
from code_engine.registry import CodeRegistry
from code_engine.universal import evaluate_registered_requirements, compliance_gate
ROOT = Path(__file__).resolve().parents[1]
def registry(): return CodeRegistry.from_yaml(ROOT / "standards" / "registry.yaml")
def test_office_lighting_lpd_pass_fail():
    r=registry(); ctx={"building_type":"commercial","ecbc_level":"ECBC","building_area_type":"office"}
    assert evaluate_registered_requirements(r,discipline="energy",parameter="lighting_power_density",input_value=9.2,context=ctx)[0]["status"]=="PASS"
    assert evaluate_registered_requirements(r,discipline="energy",parameter="lighting_power_density",input_value=10.1,context=ctx)[0]["status"]=="FAIL"
def test_voltage_drop_limits():
    r=registry(); feeder={"building_type":"commercial","ecbc_level":"ECBC","circuit_type":"feeder"}; branch={"building_type":"commercial","ecbc_level":"ECBC","circuit_type":"branch"}
    assert evaluate_registered_requirements(r,discipline="electrical",parameter="feeder_voltage_drop",input_value=2.0,context=feeder)[0]["status"]=="PASS"
    assert evaluate_registered_requirements(r,discipline="electrical",parameter="feeder_voltage_drop",input_value=2.1,context=feeder)[0]["status"]=="FAIL"
    assert evaluate_registered_requirements(r,discipline="electrical",parameter="branch_voltage_drop",input_value=3.0,context=branch)[0]["status"]=="PASS"
def test_metering_boolean_requirement():
    r=registry(); ctx={"building_type":"commercial","ecbc_level":"ECBC","service_capacity_band":"gt_1000_kva"}
    rows=evaluate_registered_requirements(r,discipline="bms",parameter="permanent_electrical_metering",input_value=True,context=ctx)
    assert rows[0]["status"]=="PASS"; assert compliance_gate(rows)=="COMPLIANT"
