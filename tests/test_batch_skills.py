from skills.common import SkillRequest
from orchestrator.engine import execute, registered_skills
from orchestrator.registry_loader import load_registry

def req(sid,inputs): return SkillRequest(skill_id=sid,inputs=inputs)

def test_registry_has_all_audited_entries():
    skills=load_registry()["skills"]
    ids={s["skill_id"] for s in skills}
    for sid in [
        "preliminary_load_estimation","duct_sizing","pump_head","hvac_fault_diagnosis",
        "cooling_tower","refrigerant_pipe_sizing","vrf_sizing","cleanroom_ach","duct_leakage","chiller_selection_advisor",
        "bms_points_generation","bms_controller_sizing","bms_cost_estimation","bms_alarm_evaluation",
        "vfd_energy_savings","vfd_derating","harmonic_screening","hvac_decarbonisation","energy_payback","hvac_boq","deviation_statement"
    ]:
        assert sid in ids

def test_load_and_hvac_skills():
    r=execute(req("preliminary_load_estimation",{"building_type":"office","area_sqft":5500,"climate_zone":"composite","occupancy":60})); assert r.status=="draft_ready" and r.engineering_result["recommended_tonnage"]>0
    r=execute(req("cooling_tower",{"load_method":"chiller","chiller_tr":200,"chiller_cop":5,"range_c":5.5,"wet_bulb_c":28,"approach_c":4.5,"coc":4,"drift_pct":0.02})); assert r.engineering_result["makeup_m3hr"]>0
    r=execute(req("refrigerant_pipe_sizing",{"refrigerant":"R410A","capacity_kw":14,"suction_velocity":10,"liquid_velocity":1.2,"suction_length":25,"liquid_length":25})); assert r.engineering_result["suction_standard_od_mm"]>0
    r=execute(req("vrf_sizing",{"zones":[{"name":"A","area":40,"load_factor":130},{"name":"B","area":120,"load_factor":150}],"combination_ratio":120,"total_pipe_length_m":100,"farthest_branch_length_m":40,"odu_idu_height_diff_m":20,"idu_idu_height_diff_m":8})); assert r.engineering_result["required_odu_hp"]>0
    r=execute(req("cleanroom_ach",{"room_type":"Operating Room","length_m":7,"width_m":6,"height_m":3.2})); assert r.engineering_result["supply_cmh"]>0
    r=execute(req("duct_leakage",{"sections":[{"width_mm":600,"height_mm":400,"length_m":20}],"test_pressure_pa":1000,"measured_leakage_ls":20,"target_class":6})); assert "calculated_leakage_class" in r.engineering_result
    r=execute(req("chiller_selection_advisor",{"total_load_tr":300,"efficiency_kw_per_tr":0.7,"annual_hours":3000,"load_factor_pct":70,"tariff_per_kwh":8.5,"duty_modules":2,"redundancy_level":1,"water_available":"yes","space_available":"ample","efficiency_priority":"high"})); assert r.engineering_result["suggested_type"]
    r=execute(req("hvac_fault_diagnosis",{"rule_id":"pump_cavitation","values":{"high_vibration":"yes","noise":"yes","low_suction_pressure":"yes"}})); assert r.engineering_result["conclusion"]=="Cavitation"

def test_energy_skills():
    r=execute(req("vfd_energy_savings",{"motor_kw":22,"speed_reduction_pct":20,"static_head_fraction":20,"annual_hours":4000,"tariff_per_kwh":9})); assert r.engineering_result["annual_savings_kwh_corrected"]>0
    r=execute(req("vfd_derating",{"motor_kw":15,"ambient_temp_c":50,"altitude_m":1200})); assert r.engineering_result["recommended_vfd_kw"]>=15
    r=execute(req("harmonic_screening",{"total_vfd_kva":200,"transformer_kva":800})); assert r.engineering_result["risk_level"]=="Moderate"
    r=execute(req("hvac_decarbonisation",{"annual_energy_kwh":100000,"tariff":10,"efficiency_gain_pct":10,"om_program_cost":100000,"capacity_tr":100,"replacement_cost":5000000,"life_extension_years":3})); assert r.engineering_result["annual_energy_saved_kwh"]==10000.0
    r=execute(req("energy_payback",{"capacity_old":200,"efficiency_old":0.8,"capacity_new":180,"efficiency_new":0.6,"annual_hours":3000,"load_factor_pct":70,"tariff_per_kwh":8.5,"investment":2000000,"incremental_om":50000,"project_life_years":10})); assert r.engineering_result["net_annual_savings"]>0

def test_bms_skills():
    r=execute(req("bms_points_generation",{"equipment_counts":{"ahu":2,"pump":1},"points_per_controller":32,"controllers_per_panel":4})); assert r.engineering_result["summary"]["total_points"]==25
    r=execute(req("bms_cost_estimation",{"ahu_count":2,"chiller_count":1,"pump_count":2,"vfd_count":2,"misc_points":4,"points_per_controller":32,"controllers_per_panel":4,"cost_per_point":100,"cost_per_controller":20000,"cost_per_panel":15000,"bms_software_cost":50000,"engineering_pct":10})); assert r.engineering_result["total_project_cost"]>0
    r=execute(req("bms_alarm_evaluation",{"point_type":"analog","point_id":"AHU1_SAT","value":20})); assert r.engineering_result["alarm_status"]=="Alarm"

def test_commercial_skills():
    r=execute(req("hvac_boq",{"categories":[{"name":"Duct","items":[{"description":"GI duct","unit":"kg","qty":100,"rate":200}]}],"contingency_pct":5,"overhead_pct":10,"tax_pct":18})); assert r.engineering_result["grand_total"]>0
    r=execute(req("deviation_statement",{"rows":[{"clause":"A","specified":"100","offered":"100","status":"comply","remarks":""},{"clause":"B","specified":"200","offered":"180","status":"deviate","remarks":"Alternative"},{"clause":"C","specified":"-","offered":"-","status":"na","remarks":""}]})); assert r.engineering_result["deviate"]==1 and r.engineering_result["compliance_pct"]==50

def test_registered_executable_count():
    assert len(registered_skills())==24
