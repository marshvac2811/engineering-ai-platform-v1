from pathlib import Path
P=Path('/mnt/data/engineering_ai_platform_v1')

def write(path, text):
    path=P/path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

# HVAC preliminary load
write('skills/hvac/preliminary_load_estimation/source_calculator.py', r'''"""Controlled snapshot of hvac---load---estimator/calculator.py."""
import math
BUILDING_TYPES={"office":{"label":"Office / Commercial","base_sqft_per_ton":550},"retail":{"label":"Retail / Showroom","base_sqft_per_ton":450},"residential":{"label":"Residential","base_sqft_per_ton":650},"hospital":{"label":"Hospital / Healthcare","base_sqft_per_ton":400},"server_room":{"label":"Server Room / Data Center","base_sqft_per_ton":120},"restaurant":{"label":"Restaurant / F&B","base_sqft_per_ton":350},"auditorium":{"label":"Auditorium / Banquet Hall","base_sqft_per_ton":250},"hotel":{"label":"Hotel / Hospitality","base_sqft_per_ton":500},"educational":{"label":"Educational Institution","base_sqft_per_ton":500}}
CLIMATE_ZONES={"hot_dry":{"label":"Hot & Dry (e.g. Delhi NCR, Jaipur, Ahmedabad)","multiplier":1.00},"warm_humid":{"label":"Warm & Humid (e.g. Mumbai, Chennai, Kolkata)","multiplier":1.15},"composite":{"label":"Composite (e.g. Lucknow, Kanpur, Bhopal)","multiplier":1.05},"moderate":{"label":"Moderate (e.g. Bengaluru, Pune)","multiplier":0.82},"cold":{"label":"Cold (e.g. Shimla, Srinagar)","multiplier":0.60}}
STANDARD_OCCUPANCY_DENSITY={"office":1.0,"retail":1.5,"residential":0.4,"hospital":1.2,"server_room":0.1,"restaurant":2.5,"auditorium":5.0,"hotel":0.8,"educational":3.0}
TONS_PER_EXTRA_OCCUPANT=400/12000

def _round_up_to_half(value): return math.ceil(value*2)/2

def _suggest_equipment(tonnage):
    if tonnage<=5: return "Split / Ductable Split units (multiple units likely)"
    if tonnage<=20: return "Package Unit or small VRF system"
    if tonnage<=100: return "VRF/VRV system or air-cooled chiller"
    return "Water-cooled chiller plant with cooling tower"

def estimate_load(building_type, area_sqft, climate_zone, occupancy=None):
    if building_type not in BUILDING_TYPES: raise ValueError(f"Unknown building type: {building_type}")
    if climate_zone not in CLIMATE_ZONES: raise ValueError(f"Unknown climate zone: {climate_zone}")
    if area_sqft<=0: raise ValueError("Area must be greater than zero")
    bt=BUILDING_TYPES[building_type]; cz=CLIMATE_ZONES[climate_zone]
    effective_sqft_per_ton=bt["base_sqft_per_ton"]/cz["multiplier"]
    base_tonnage=area_sqft/effective_sqft_per_ton
    occupancy_addon=0.0; standard_occupants=0; extra_occupants=0
    if occupancy is not None and occupancy>0:
        standard_occupants=round((area_sqft/100)*STANDARD_OCCUPANCY_DENSITY[building_type])
        extra_occupants=max(0, occupancy-standard_occupants)
        occupancy_addon=extra_occupants*TONS_PER_EXTRA_OCCUPANT
    total_tonnage=base_tonnage+occupancy_addon
    return {"building_type_label":bt["label"],"climate_zone_label":cz["label"],"area_sqft":area_sqft,"base_sqft_per_ton":bt["base_sqft_per_ton"],"climate_multiplier":cz["multiplier"],"effective_sqft_per_ton":round(effective_sqft_per_ton,1),"base_tonnage":round(base_tonnage,2),"standard_occupants_assumed":standard_occupants,"actual_occupancy":occupancy,"extra_occupants":extra_occupants,"occupancy_addon_tons":round(occupancy_addon,2),"total_tonnage_raw":round(total_tonnage,2),"recommended_tonnage":_round_up_to_half(total_tonnage),"suggested_equipment":_suggest_equipment(_round_up_to_half(total_tonnage))}
''')
write('skills/hvac/preliminary_load_estimation/adapter.py', r'''from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context, resolve_standards_context
from . import source_calculator as engine
SOURCE_REVISION='9046682a3500d347f57353d4f6313df8ea2543d'
class PreliminaryLoadEstimationSkill:
    skill_id='preliminary_load_estimation'; version='1.0.0'
    def validate(self,r):
        e=validate_governance_context(r); i=r.inputs
        for k in ('building_type','area_sqft','climate_zone'):
            if k not in i: e.append(f'Missing required input: {k}')
        if 'area_sqft' in i:
            try:
                if float(i['area_sqft'])<=0:e.append('area_sqft must be greater than zero')
            except: e.append('area_sqft must be numeric')
        if 'occupancy' in i and i['occupancy'] is not None:
            try:
                if int(i['occupancy'])<0:e.append('occupancy must be non-negative')
            except: e.append('occupancy must be numeric')
        return e
    def run(self,r):
        e=self.validate(r)
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=SOURCE_REVISION)
        i=r.inputs
        try: out=engine.estimate_load(i['building_type'],float(i['area_sqft']),i['climate_zone'],None if i.get('occupancy') is None else int(i['occupancy']))
        except (ValueError,TypeError) as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=SOURCE_REVISION)
        warnings=['Preliminary/budgetary rule-of-thumb only; not a detailed Manual J/CLTD/HAP calculation.','Source climate labels/multipliers are preserved as source data and require project/standards validation before design use.','Final equipment selection requires detailed load calculation and local design conditions.']
        return SkillResult(self.skill_id,'draft_ready',engineering_result=out,standards=resolve_standards_context(r.standards_context),warnings=warnings,calculation_trace=[{'step':1,'operation':'select_building_type_and_base_sqft_per_ton'},{'step':2,'operation':'apply_source_climate_multiplier'},{'step':3,'operation':'apply_occupancy_addon_if_applicable'},{'step':4,'operation':'round_up_to_half_ton'}],source_revision=SOURCE_REVISION)
''')
write('skills/hvac/preliminary_load_estimation/__init__.py','from .adapter import PreliminaryLoadEstimationSkill\n')

# HVAC troubleshooting
write('skills/hvac/fault_diagnosis/source_calculator.py', r'''"""Controlled snapshot of hvac-plant-troubleshooting/diagnostic_rules.py."""
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
''')
write('skills/hvac/fault_diagnosis/adapter.py', r'''from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
SOURCE_REVISION='1abcf2c385280721763c2fbebcf423fd424b149c'
class HVAFaultDiagnosisSkill:
    skill_id='hvac_fault_diagnosis'; version='1.0.0'
    def validate(self,r):
        e=validate_governance_context(r); i=r.inputs
        if 'rule_id' not in i:e.append('Missing required input: rule_id')
        if 'values' not in i or not isinstance(i.get('values'),dict):e.append('values must be an object/dict')
        if 'rule_id' in i and i['rule_id'] not in engine.RULES:e.append(f"Unknown rule: {i['rule_id']}")
        return e
    def run(self,r):
        e=self.validate(r)
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=SOURCE_REVISION)
        try:out=engine.evaluate_rule(r.inputs['rule_id'],r.inputs['values'])
        except (ValueError,KeyError,TypeError) as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=SOURCE_REVISION)
        warnings=['Rule-based diagnostic support only; conclusion is the source rule result, not a final field diagnosis.','Inspect the underlying equipment, controls and measurement chain before corrective action.']
        if not out['all_conditions_met']:warnings.append('Not all rule conditions are met; no source-rule conclusion is returned.')
        return SkillResult(self.skill_id,'draft_ready',engineering_result=out,warnings=warnings,calculation_trace=[{'step':1,'operation':'evaluate_explicit_AND_conditions','rule_id':r.inputs['rule_id']}],source_revision=SOURCE_REVISION)
''')
write('skills/hvac/fault_diagnosis/__init__.py','from .adapter import HVAFaultDiagnosisSkill\n')

# VFD
write('skills/energy/vfd/source_calculator.py', r'''import math
STANDARD_VFD_SIZES_KW=[0.75,1.1,1.5,2.2,3.7,5.5,7.5,11,15,18.5,22,30,37,45,55,75,90,110,132,160,200,250,315]
RATED_AMBIENT_TEMP_C=40; RATED_ALTITUDE_M=1000; TEMP_DERATE_PCT_PER_C=2.0; ALTITUDE_DERATE_PCT_PER_100M=1.0

def calculate_energy_savings(motor_kw,speed_reduction_pct,static_head_fraction,annual_hours,tariff_per_kwh):
    if motor_kw<=0:raise ValueError('Motor power must be greater than zero')
    if not (0<speed_reduction_pct<100):raise ValueError('Speed reduction percentage must be between 0 and 100')
    if not (0<=static_head_fraction<=100):raise ValueError('Static head fraction must be between 0 and 100')
    if annual_hours<=0 or tariff_per_kwh<=0:raise ValueError('Annual hours and tariff must be greater than zero')
    sr=1-speed_reduction_pct/100; sf=static_head_fraction/100
    pure=sr**3; corr=sf+(1-sf)*sr**3
    sp=motor_kw-motor_kw*pure; sc=motor_kw-motor_kw*corr
    return {'motor_kw':motor_kw,'speed_reduction_pct':speed_reduction_pct,'speed_ratio':round(sr,3),'static_head_fraction':static_head_fraction,'reduced_power_kw_pure':round(motor_kw*pure,2),'reduced_power_kw_corrected':round(motor_kw*corr,2),'savings_pct_pure':round(sp/motor_kw*100,1),'savings_pct_corrected':round(sc/motor_kw*100,1),'annual_hours':annual_hours,'tariff_per_kwh':tariff_per_kwh,'annual_savings_kwh_pure':round(sp*annual_hours,0),'annual_savings_kwh_corrected':round(sc*annual_hours,0),'annual_savings_cost_pure':round(sp*annual_hours*tariff_per_kwh,0),'annual_savings_cost_corrected':round(sc*annual_hours*tariff_per_kwh,0)}

def _round_up(kw):
    for s in STANDARD_VFD_SIZES_KW:
        if s>=kw:return s
    return STANDARD_VFD_SIZES_KW[-1]

def calculate_sizing(motor_kw,ambient_temp_c,altitude_m):
    if motor_kw<=0:raise ValueError('Motor power must be greater than zero')
    if ambient_temp_c<-20 or ambient_temp_c>70:raise ValueError('Ambient temperature must be between -20°C and 70°C')
    if altitude_m<0 or altitude_m>5000:raise ValueError('Altitude must be between 0 and 5000 m')
    td=max(0,ambient_temp_c-40)*2; ad=max(0,(altitude_m-1000)/100)*1; total=min(td+ad,60); factor=1-total/100
    return {'motor_kw':motor_kw,'ambient_temp_c':ambient_temp_c,'altitude_m':altitude_m,'temp_derate_pct':round(td,1),'altitude_derate_pct':round(ad,1),'total_derate_pct':round(total,1),'derating_factor':round(factor,3),'required_vfd_kw':round(motor_kw/factor,2),'recommended_vfd_kw':_round_up(motor_kw/factor)}

def screen_harmonics_risk(total_vfd_kva,transformer_kva):
    if total_vfd_kva<=0 or transformer_kva<=0:raise ValueError('Loads must be greater than zero')
    p=total_vfd_kva/transformer_kva*100
    if p<20:r,g='Low','VFD load is a small fraction of transformer capacity — harmonic distortion is typically manageable without additional filtering, but this is not a guarantee.'
    elif p<40:r,g='Moderate','VFD load is a meaningful fraction of transformer capacity — consider a harmonic filter or line reactor, and recommend a proper IEEE 519 study before finalizing.'
    else:r,g='High','VFD load is a large fraction of transformer capacity — harmonic filtering (active filter or multi-pulse drive) is likely needed. A formal IEEE 519 harmonic study is strongly recommended.'
    return {'total_vfd_kva':total_vfd_kva,'transformer_kva':transformer_kva,'loading_pct':round(p,1),'risk_level':r,'guidance':g}
''')
write('skills/energy/vfd/adapters.py', r'''from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='bc5c25757ecb68bff3b7d96273340228ec368c52'
class _Base:
    def validate(self,r): return validate_governance_context(r)
class VFDEnergySavingsSkill(_Base):
    skill_id='vfd_energy_savings'
    def run(self,r):
        e=self.validate(r); keys=['motor_kw','speed_reduction_pct','static_head_fraction','annual_hours','tariff_per_kwh']
        e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.calculate_energy_savings(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Savings model uses the source static-head correction and should be validated against measured system behavior.'],calculation_trace=[{'step':1,'operation':'apply_affinity_law_cube_relationship'},{'step':2,'operation':'apply_static_head_correction'},{'step':3,'operation':'annualize_energy_and_cost'}],source_revision=REV)
class VFDDeratingSkill(_Base):
    skill_id='vfd_derating'
    def run(self,r):
        e=self.validate(r); keys=['motor_kw','ambient_temp_c','altitude_m']; e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.calculate_sizing(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Temperature/altitude factors are generic reference values from the source and must be checked against the selected VFD manufacturer/model datasheet.'],source_revision=REV)
class HarmonicScreeningSkill(_Base):
    skill_id='harmonic_screening'
    def run(self,r):
        e=self.validate(r); keys=['total_vfd_kva','transformer_kva']; e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.screen_harmonics_risk(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Screening heuristic only; not an IEEE 519 harmonic study.'],source_revision=REV)
''')
write('skills/energy/vfd/__init__.py','from .adapters import VFDEnergySavingsSkill,VFDDeratingSkill,HarmonicScreeningSkill\n')

# BMS points and templates
write('skills/bms/points/source_calculator.py', r'''import math
EQUIPMENT_TEMPLATES={
'ahu':{'label':'AHU','prefix':'AHU','points':[('SAT','Supply Air Temperature','AI'),('RAT','Return Air Temperature','AI'),('DSP','Duct Static Pressure','AI'),('CHWV','Chilled Water Valve Command','AO'),('FSC','Fan Speed Command (VFD)','AO'),('FS','Fan Status','DI'),('FSS','Fan Start/Stop Command','DO'),('FLT','Filter Status (DP Switch)','DI'),('DMP','Outside Air Damper Command','AO'),('FRZ','Freeze Stat Alarm','DI')]},
'chiller':{'label':'Chiller','prefix':'CH','points':[('CHWST','CHW Supply Temperature','AI'),('CHWRT','CHW Return Temperature','AI'),('LOAD','% Load (via gateway)','AI'),('STAT','Chiller Run Status','DI'),('SS','Chiller Start/Stop Command','DO'),('ALM','Chiller Fault/Alarm','DI')]},
'pump':{'label':'Pump','prefix':'PP','points':[('STAT','Pump Run Status','DI'),('SS','Pump Start/Stop Command','DO'),('ALM','Pump Fault','DI'),('SPDFB','VFD Speed Feedback','AI'),('SPDCMD','VFD Speed Command','AO')]},
'vfd':{'label':'Standalone VFD','prefix':'VFD','points':[('SPDCMD','Speed Command','AO'),('SPDFB','Speed Feedback','AI'),('STAT','Run Status','DI'),('ALM','Fault Status','DI'),('SS','Run/Stop Command','DO')]},
'cooling_tower':{'label':'Cooling Tower','prefix':'CT','points':[('FS','Fan Status','DI'),('SS','Fan Start/Stop Command','DO'),('LVL','Basin Level','AI'),('LVLALM','Basin Low Level Alarm','DI')]}}

def generate_points_list(equipment_counts):
    out=[]
    for k,count in equipment_counts.items():
        if count<=0:continue
        if k not in EQUIPMENT_TEMPLATES:raise ValueError(f'Unknown equipment type: {k}')
        t=EQUIPMENT_TEMPLATES[k]
        for n in range(1,count+1):
            inst=f"{t['prefix']}-{n}"
            for suffix,desc,signal in t['points']:
                out.append({'tag_id':f"{t['prefix']}{n}-{suffix}",'equipment_instance':inst,'equipment_type':t['label'],'description':desc,'signal_type':signal})
    return out

def summarize_points(points):return {'ai_count':sum(p['signal_type']=='AI' for p in points),'ao_count':sum(p['signal_type']=='AO' for p in points),'di_count':sum(p['signal_type']=='DI' for p in points),'do_count':sum(p['signal_type']=='DO' for p in points),'total_points':len(points)}
def calculate_controller_sizing(total_points,points_per_controller,controllers_per_panel):
    if points_per_controller<=0 or controllers_per_panel<=0:raise ValueError('Controller/panel capacities must be greater than zero')
    c=math.ceil(total_points/points_per_controller) if total_points else 0; p=math.ceil(c/controllers_per_panel) if c else 0
    return {'points_per_controller':points_per_controller,'controller_count':c,'controllers_per_panel':controllers_per_panel,'panel_count':p}
def build_full_report(equipment_counts,points_per_controller,controllers_per_panel):
    if all(v<=0 for v in equipment_counts.values()):raise ValueError('Enter at least one piece of equipment')
    for k,v in equipment_counts.items():
        if v<0:raise ValueError(f'{k} count cannot be negative')
    pts=generate_points_list(equipment_counts); s=summarize_points(pts); z=calculate_controller_sizing(s['total_points'],points_per_controller,controllers_per_panel)
    g={}
    for p in pts:g.setdefault(p['equipment_instance'],[]).append(p)
    return {'points_list':pts,'grouped':g,'summary':s,'sizing':z}
''')
write('skills/bms/points/adapters.py', r'''from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='a8c28e363bb8c58bb74e40038d8ade858beefeb5'
class BMSPointsGenerationSkill:
    skill_id='bms_points_generation'
    def run(self,r):
        e=validate_governance_context(r); i=r.inputs
        if not isinstance(i.get('equipment_counts'),dict):e.append('equipment_counts must be an object')
        for k in ('points_per_controller','controllers_per_panel'):
            if k not in i:e.append(f'Missing required input: {k}')
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.build_full_report(i['equipment_counts'],int(i['points_per_controller']),int(i['controllers_per_panel']))
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Generic planning-stage points template; final points must follow project scope, sequence of operations, gateway capabilities and owner requirements.'],source_revision=REV)
class BMSControllerSizingSkill:
    skill_id='bms_controller_sizing'
    def run(self,r):
        e=validate_governance_context(r); i=r.inputs
        for k in ('total_points','points_per_controller','controllers_per_panel'):
            if k not in i:e.append(f'Missing required input: {k}')
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.calculate_controller_sizing(int(i['total_points']),int(i['points_per_controller']),int(i['controllers_per_panel']))
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Controller capacity must be checked against actual selected controller I/O and project architecture.'],source_revision=REV)
''')
write('skills/bms/points/__init__.py','from .adapters import BMSPointsGenerationSkill,BMSControllerSizingSkill\n')

# BMS cost
write('skills/bms/cost/source_calculator.py', r'''import math
TYPICAL_POINTS_PER_UNIT={'ahu':10,'chiller':12,'pump':5,'vfd':6}
def estimate_cost(ahu_count,chiller_count,pump_count,vfd_count,misc_points,points_per_controller,controllers_per_panel,cost_per_point,cost_per_controller,cost_per_panel,bms_software_cost,engineering_pct):
    vals=[ahu_count,chiller_count,pump_count,vfd_count,misc_points]
    if any(v<0 for v in vals):raise ValueError('Equipment counts/points cannot be negative')
    if points_per_controller<=0 or controllers_per_panel<=0:raise ValueError('Controller/panel capacities must be positive')
    if min(cost_per_point,cost_per_controller,cost_per_panel,bms_software_cost)<0:raise ValueError('Costs cannot be negative')
    if not 0<=engineering_pct<=100:raise ValueError('Engineering percentage must be between 0 and 100')
    br={'AHU':ahu_count*10,'Chiller':chiller_count*12,'Pump':pump_count*5,'VFD':vfd_count*6,'Miscellaneous':misc_points}; total=sum(br.values())
    if total==0:raise ValueError('Total points is zero')
    cc=math.ceil(total/points_per_controller); pc=math.ceil(cc/controllers_per_panel)
    field=total*cost_per_point; ctrl=cc*cost_per_controller; panel=pc*cost_per_panel; hw=field+ctrl+panel; sw=hw+bms_software_cost; eng=sw*engineering_pct/100; total_cost=sw+eng
    return {'points_breakdown':br,'total_points':total,'points_per_controller':points_per_controller,'controller_count':cc,'controllers_per_panel':controllers_per_panel,'panel_count':pc,'cost_per_point':cost_per_point,'field_wiring_cost':round(field,0),'cost_per_controller':cost_per_controller,'controller_cost':round(ctrl,0),'cost_per_panel':cost_per_panel,'panel_cost':round(panel,0),'hardware_subtotal':round(hw,0),'bms_software_cost':round(bms_software_cost,0),'subtotal_with_software':round(sw,0),'engineering_pct':engineering_pct,'engineering_cost':round(eng,0),'total_project_cost':round(total_cost,0),'cost_per_point_overall':round(total_cost/total,0)}
''')
write('skills/bms/cost/adapter.py', r'''from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='5061af18947e0c37f533ff6518e68c672c088407'
class BMSCostEstimationSkill:
    skill_id='bms_cost_estimation'
    def run(self,r):
        e=validate_governance_context(r)
        keys=['ahu_count','chiller_count','pump_count','vfd_count','misc_points','points_per_controller','controllers_per_panel','cost_per_point','cost_per_controller','cost_per_panel','bms_software_cost','engineering_pct']
        e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.estimate_cost(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Budgetary framework only; market unit rates are user inputs and point counts are planning-stage estimates.'],source_revision=REV)
''')
write('skills/bms/cost/__init__.py','from .adapter import BMSCostEstimationSkill\n')

# Decarb
write('skills/energy/decarbonisation/source_calculator.py', r'''GRID_EMISSION_FACTOR=0.716; EMBODIED_CARBON_PER_TR=150.0; TREE_ABSORPTION_RATE=21.0
def _get(d,k,default=0.0):
    try:return float(d.get(k,default))
    except:return default

def compute_impact(inputs):
    annual_energy=_get(inputs,'annual_energy_kwh'); tariff=_get(inputs,'tariff'); gain=_get(inputs,'efficiency_gain_pct'); om=_get(inputs,'om_program_cost'); cap=_get(inputs,'capacity_tr'); repl=_get(inputs,'replacement_cost'); life=_get(inputs,'life_extension_years'); gf=_get(inputs,'grid_emission_factor',GRID_EMISSION_FACTOR) or GRID_EMISSION_FACTOR; h=int(_get(inputs,'horizon_years',10) or 10)
    saved=annual_energy*gain/100; cost=saved*tariff; co2=saved*gf/1000; net=cost-om; payback=om/cost if cost>0 else None; proj=[]; cc=0; ck=0
    for y in range(1,h+1): cc+=net; ck+=co2; proj.append({'year':y,'annual_cost_saved':round(cost,2),'cumulative_cost_saved':round(cc,2),'annual_co2_avoided_tonnes':round(co2,3),'cumulative_co2_avoided_tonnes':round(ck,3)})
    return {'inputs_used':{'annual_energy_kwh':annual_energy,'tariff':tariff,'efficiency_gain_pct':gain,'om_program_cost':om,'capacity_tr':cap,'replacement_cost':repl,'life_extension_years':life,'grid_emission_factor':gf,'horizon_years':h},'annual_energy_saved_kwh':round(saved,1),'annual_cost_saved':round(cost,2),'annual_co2_avoided_kg':round(saved*gf,1),'annual_co2_avoided_tonnes':round(co2,3),'trees_equivalent':round(saved*gf/TREE_ABSORPTION_RATE,1),'net_annual_saving':round(net,2),'payback_years':round(payback,2) if payback is not None else None,'deferred_capex':round(repl,2),'life_extension_years':life,'embodied_carbon_avoided_tonnes':round(cap*EMBODIED_CARBON_PER_TR/1000,3),'horizon_years':h,'projection':proj}

def compute_scenarios(inputs):
    annual=_get(inputs,'annual_energy_kwh'); tariff=_get(inputs,'tariff'); gf=_get(inputs,'grid_emission_factor',GRID_EMISSION_FACTOR) or GRID_EMISSION_FACTOR; h=int(_get(inputs,'horizon_years',10) or 10); om=_get(inputs,'om_program_cost'); gain=_get(inputs,'efficiency_gain_pct'); repl=_get(inputs,'replacement_cost'); creep=_get(inputs,'neglect_creep_pct',4); fy=int(_get(inputs,'failure_year',5) or 5); prem=_get(inputs,'emergency_premium_pct',25); rg=_get(inputs,'retrofit_efficiency_gain_pct',35); rc=_get(inputs,'retrofit_cost',repl); ro=_get(inputs,'retrofit_om_cost',om*.4)
    def co2(k):return k*gf/1000
    dn=[]; cumc=0; cumco=0
    for y in range(1,h+1):
        e=annual*((1+creep/100)**(y-1)); c=e*tariff+(repl*(1+prem/100) if y==fy else 0); cumc+=c; cumco+=co2(e); dn.append({'year':y,'cost':round(c,2),'cumulative_cost':round(cumc,2),'cumulative_co2_tonnes':round(cumco,3)})
    omr=[]; cumc=0; cumco=0; oe=annual*(1-gain/100); pry=min(h,fy*2)
    for y in range(1,h+1):
        c=oe*tariff+om+(repl if y==pry else 0); cumc+=c; cumco+=co2(oe); omr.append({'year':y,'cost':round(c,2),'cumulative_cost':round(cumc,2),'cumulative_co2_tonnes':round(cumco,3)})
    rr=[]; cumc=0; cumco=0; re=annual*(1-rg/100)
    for y in range(1,h+1):
        c=re*tariff+ro+(rc if y==1 else 0); cumc+=c; cumco+=co2(re); rr.append({'year':y,'cost':round(c,2),'cumulative_cost':round(cumc,2),'cumulative_co2_tonnes':round(cumco,3)})
    totals={'do_nothing':{'total_cost':dn[-1]['cumulative_cost'],'total_co2_tonnes':dn[-1]['cumulative_co2_tonnes']},'om':{'total_cost':omr[-1]['cumulative_cost'],'total_co2_tonnes':omr[-1]['cumulative_co2_tonnes']},'retrofit':{'total_cost':rr[-1]['cumulative_cost'],'total_co2_tonnes':rr[-1]['cumulative_co2_tonnes']}}
    return {'horizon_years':h,'do_nothing':dn,'om':omr,'retrofit':rr,'totals':totals,'lowest_cost_scenario':min(totals,key=lambda k:totals[k]['total_cost']),'lowest_co2_scenario':min(totals,key=lambda k:totals[k]['total_co2_tonnes']),'assumptions':{'neglect_creep_pct':creep,'failure_year':fy,'emergency_premium_pct':prem,'retrofit_efficiency_gain_pct':rg,'retrofit_cost':rc,'retrofit_om_cost':round(ro,2)}}
''')
write('skills/energy/decarbonisation/adapter.py', r'''from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='9e617d33020beb18de05754940e37214f8616b8d'
class HVACDecarbonisationSkill:
    skill_id='hvac_decarbonisation'
    def run(self,r):
        e=validate_governance_context(r); i=r.inputs
        mode=i.get('mode','impact'); fn=engine.compute_scenarios if mode=='scenarios' else engine.compute_impact
        required=['annual_energy_kwh','tariff']
        e += [f'Missing required input: {k}' for k in required if k not in i]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=fn(i)
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Scenario/impact model is assumption-driven; site data, current tariffs and governed emission factors should be verified before proposal use.'],source_revision=REV)
''')
write('skills/energy/decarbonisation/__init__.py','from .adapter import HVACDecarbonisationSkill\n')

# Registry and orchestrator
registry='''version: 2\nregistry_name: engineering_skill_registry\nstatus: batch_registered\n\nskills:\n'''
entries=[
('preliminary_load_estimation','HVAC','hvac---load---estimator','.','deterministic_python','preliminary','integrated'),('duct_sizing','HVAC','duct-sizing-calculator','.','deterministic_python','preliminary','integrated'),('pump_head','HVAC','hvac-boq-generator','pump-head','deterministic_python_adapter','preliminary','integrated'),('hvac_fault_diagnosis','HVAC','hvac-plant-troubleshooting','.','deterministic_rule_engine','diagnostic_support','integrated'),('cooling_tower','HVAC','hvac-boq-generator','cooling-tower-calculator','deterministic_browser_adapter','preliminary_vendor_verification_required','source_adapter_pending'),('refrigerant_pipe_sizing','HVAC','hvac-boq-generator','refrigerant-pipe-sizing','deterministic_browser_adapter','preliminary_manufacturer_verification_required','source_adapter_pending'),('vrf_sizing','HVAC','hvac-boq-generator','vrf-sizing-tool','deterministic_browser_adapter','preliminary_manufacturer_verification_required','source_adapter_pending'),('cleanroom_ach','HVAC','hvac-boq-generator','cleanroom-ach-calculator','deterministic_browser_adapter','compliance_support','source_adapter_pending'),('duct_leakage','HVAC','hvac-boq-generator','duct-leakage-calculator','deterministic_browser_adapter','compliance_support','source_adapter_pending'),('chiller_selection_advisor','HVAC','hvac-boq-generator','chiller-selection-advisor','deterministic_browser_adapter','advisory','source_adapter_pending'),('chiller_efficiency','HVAC','chiller-efficiency-calculator','.','deterministic_calculation','pending','source_audit_pending'),('bms_points_generation','BMS','BMS-points-list','.','deterministic_python','planning','integrated'),('bms_controller_sizing','BMS','BMS-points-list','.','deterministic_python','planning','integrated'),('bms_cost_estimation','BMS','bms-cost-estimator','.','deterministic_python','budgetary','integrated'),('bms_alarm_evaluation','BMS','bms-dashboard','.','deterministic_rule_engine','monitoring_prototype','source_adapter_pending'),('vfd_energy_savings','ENERGY','vfd-toolkit','.','deterministic_python','engineering_estimate','integrated'),('vfd_derating','ENERGY','vfd-toolkit','.','deterministic_python','manufacturer_dependent','integrated'),('harmonic_screening','ENERGY','vfd-toolkit','.','deterministic_python','screening_only','integrated'),('hvac_decarbonisation','ENERGY','hvac-decarb-tool','.','deterministic_python','scenario_model','integrated'),('energy_payback','ENERGY','hvac-boq-generator','energy-savings-payback-calculator','deterministic_browser_adapter','financial_estimate','source_adapter_pending'),('hvac_boq','COMMERCIAL','hvac-boq-generator','boq','deterministic_browser_calculation','commercial','source_adapter_pending'),('deviation_statement','COMMERCIAL','hvac-boq-generator','deviation-statement-generator','deterministic_browser_calculation','commercial','source_adapter_pending')]
for e in entries:
    sid,dom,repo,path,exe,cls,status=e
    registry += f"  - skill_id: {sid}\n    domain: {dom}\n    source_repository: {repo}\n    source_path: {path}\n    execution: {exe}\n    classification: {cls}\n    integration_status: {status}\n    human_review_required: true\n\n"
write('skill_registry/registry.yaml',registry)

# Orchestrator imports all executable adapters
write('orchestrator/engine.py', r'''from __future__ import annotations
from typing import Dict
from skills.common import SkillRequest, SkillResult
from skills.hvac.duct_sizing.adapter import DuctSizingSkill
from skills.hvac.pump_head.adapter import PumpHeadSkill
from skills.hvac.preliminary_load_estimation.adapter import PreliminaryLoadEstimationSkill
from skills.hvac.fault_diagnosis.adapter import HVAFaultDiagnosisSkill
from skills.bms.points.adapters import BMSPointsGenerationSkill,BMSControllerSizingSkill
from skills.bms.cost.adapter import BMSCostEstimationSkill
from skills.energy.vfd.adapters import VFDEnergySavingsSkill,VFDDeratingSkill,HarmonicScreeningSkill
from skills.energy.decarbonisation.adapter import HVACDecarbonisationSkill
SKILLS={
'duct_sizing':DuctSizingSkill(),'pump_head':PumpHeadSkill(),'preliminary_load_estimation':PreliminaryLoadEstimationSkill(),'hvac_fault_diagnosis':HVAFaultDiagnosisSkill(),
'bms_points_generation':BMSPointsGenerationSkill(),'bms_controller_sizing':BMSControllerSizingSkill(),'bms_cost_estimation':BMSCostEstimationSkill(),
'vfd_energy_savings':VFDEnergySavingsSkill(),'vfd_derating':VFDDeratingSkill(),'harmonic_screening':HarmonicScreeningSkill(),'hvac_decarbonisation':HVACDecarbonisationSkill()}
def execute(request:SkillRequest)->SkillResult:
    skill=SKILLS.get(request.skill_id)
    if skill is None:return SkillResult(request.skill_id,'skill_not_registered',validation_errors=[f'Skill is not executable in current batch adapter set: {request.skill_id}'])
    return skill.run(request)
def registered_skills():return sorted(SKILLS)
''')

# Batch tests
write('tests/test_batch_skills.py', r'''from skills.common import SkillRequest
from orchestrator.engine import execute, registered_skills
from orchestrator.registry_loader import load_registry

def req(sid,inputs): return SkillRequest(skill_id=sid,inputs=inputs)

def test_registry_has_all_audited_entries():
    skills=load_registry()['skills']
    ids={s['skill_id'] for s in skills}
    for sid in ['preliminary_load_estimation','duct_sizing','pump_head','hvac_fault_diagnosis','bms_points_generation','bms_controller_sizing','bms_cost_estimation','bms_alarm_evaluation','vfd_energy_savings','vfd_derating','harmonic_screening','hvac_decarbonisation','energy_payback','hvac_boq','deviation_statement']:
        assert sid in ids

def test_load_skill_executes():
    r=execute(req('preliminary_load_estimation',{'building_type':'office','area_sqft':5500,'climate_zone':'composite','occupancy':60}))
    assert r.status=='draft_ready'; assert r.engineering_result['recommended_tonnage']>0

def test_fault_rule_executes():
    r=execute(req('hvac_fault_diagnosis',{'rule_id':'pump_cavitation','values':{'high_vibration':'yes','noise':'yes','low_suction_pressure':'yes'}}))
    assert r.engineering_result['conclusion']=='Cavitation'

def test_vfd_energy_executes():
    r=execute(req('vfd_energy_savings',{'motor_kw':22,'speed_reduction_pct':20,'static_head_fraction':20,'annual_hours':4000,'tariff_per_kwh':9}))
    assert r.status=='draft_ready'; assert r.engineering_result['annual_savings_kwh_corrected']>0

def test_vfd_derating_executes():
    r=execute(req('vfd_derating',{'motor_kw':15,'ambient_temp_c':50,'altitude_m':1200}))
    assert r.engineering_result['recommended_vfd_kw']>=15

def test_harmonic_screen_executes():
    r=execute(req('harmonic_screening',{'total_vfd_kva':200,'transformer_kva':800}))
    assert r.engineering_result['risk_level']=='Moderate'

def test_bms_points_executes():
    r=execute(req('bms_points_generation',{'equipment_counts':{'ahu':2,'pump':1},'points_per_controller':32,'controllers_per_panel':4}))
    assert r.engineering_result['summary']['total_points']==25

def test_bms_cost_executes():
    r=execute(req('bms_cost_estimation',{'ahu_count':2,'chiller_count':1,'pump_count':2,'vfd_count':2,'misc_points':4,'points_per_controller':32,'controllers_per_panel':4,'cost_per_point':100,'cost_per_controller':20000,'cost_per_panel':15000,'bms_software_cost':50000,'engineering_pct':10}))
    assert r.engineering_result['total_project_cost']>0

def test_decarb_executes():
    r=execute(req('hvac_decarbonisation',{'annual_energy_kwh':100000,'tariff':10,'efficiency_gain_pct':10,'om_program_cost':100000,'capacity_tr':100,'replacement_cost':5000000,'life_extension_years':3}))
    assert r.engineering_result['annual_energy_saved_kwh']==10000.0

def test_registered_executable_count():
    assert len(registered_skills())==11
''')

# README append batch status
readme=P/'README.md'
text=readme.read_text(encoding='utf-8') if readme.exists() else ''
text += '''\n\n## Batch skill integration checkpoint\n\nThe registry now represents the audited skill inventory together. The following audited skills have executable local adapters in this checkpoint: preliminary_load_estimation, duct_sizing, pump_head, hvac_fault_diagnosis, bms_points_generation, bms_controller_sizing, bms_cost_estimation, vfd_energy_savings, vfd_derating, harmonic_screening, hvac_decarbonisation.\n\nSeveral audited browser/HTML skills remain registered but intentionally marked `source_adapter_pending` because their deterministic JavaScript source has not yet been extracted into the common Python execution contract. This avoids inventing or rewriting engineering formulas.\n\nNo GitHub repository is modified by this package.\n'''
readme.write_text(text,encoding='utf-8')
