"""Controlled snapshot of hvac-plant-troubleshooting/diagnostic_rules.py."""
RULES={
"chl_hp_trip":{"label":"Chiller — High Pressure Trip","description":"IF Discharge Pressure > HP Limit AND CW Entering Temp > 33°C THEN Cooling Tower Performance Poor","inputs":["discharge_pressure","hp_limit","cw_entering_temp"],"conclusion":"Cooling Tower Performance Poor"},
"chl_lp_trip":{"label":"Chiller — Low Pressure Trip","description":"Low suction pressure + Low evaporator pressure + High superheat → Likely refrigerant shortage","inputs":["suction_pressure_low","evap_pressure_low","superheat_high"],"conclusion":"Likely Refrigerant Shortage"},
"ahu_dirty_filter":{"label":"AHU — Low Airflow","description":"DP Filter > Threshold AND Fan Speed Normal → Dirty Filter","inputs":["filter_dp","filter_dp_threshold","fan_speed_normal"],"conclusion":"Dirty Filter"},
"ahu_water_leak":{"label":"AHU — Water Leakage","description":"Water Leak Sensor = ON AND Drain DP High → Drain Blockage","inputs":["leak_sensor_on","drain_dp_high"],"conclusion":"Drain Blockage"},
"pump_motor_fault":{"label":"Pump — Not Starting","description":"Start Command AND Breaker ON AND No Current → Motor Fault","inputs":["start_command","breaker_on","no_current"],"conclusion":"Motor Fault"},
"pump_bypass_open":{"label":"Pump — Low Differential Pressure","description":"Flow Normal AND DP Low → Bypass Valve Open","inputs":["flow_normal","dp_low"],"conclusion":"Bypass Valve Open"},
"pump_cavitation":{"label":"Pump — Cavitation","description":"High Vibration AND Noise AND Low Suction Pressure → Cavitation","inputs":["high_vibration","noise","low_suction_pressure"],"conclusion":"Cavitation"}}

def evaluate_rule(rule_id, values):
    if rule_id not in RULES: raise ValueError(f"Unknown rule: {rule_id}")
    r=RULES[rule_id]; conditions=[]
    if rule_id=='chl_hp_trip':
        dp=float(values['discharge_pressure']); hp=float(values['hp_limit']); cw=float(values['cw_entering_temp'])
        conditions=[(f'Discharge Pressure ({dp}) > HP Limit ({hp})',dp>hp),(f'CW Entering Temp ({cw}°C) > 33°C',cw>33)]
    elif rule_id=='ahu_dirty_filter':
        dp=float(values['filter_dp']); th=float(values['filter_dp_threshold']); fan=values['fan_speed_normal']=='yes'
        conditions=[(f'Filter DP ({dp} Pa) > Threshold ({th} Pa)',dp>th),('Fan Speed Normal',fan)]
    else:
        for key in r['inputs']: conditions.append((key,values.get(key)=='yes'))
    all_true=all(x[1] for x in conditions)
    return {'rule_label':r['label'],'description':r['description'],'conditions_met':conditions,'all_conditions_met':all_true,'conclusion':r['conclusion'] if all_true else None}
