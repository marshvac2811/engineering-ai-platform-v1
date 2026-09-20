from pathlib import Path
P=Path('/mnt/data/engineering_ai_platform_v1')

def w(path,text):
    p=P/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')

# Cooling tower
w('skills/hvac/cooling_tower/source_calculator.py', r'''TR_TO_KW=3.517
CP_KJ_KG_K=4.186
LATENT_HEAT_KJ_KG=2260.0

def calculate(i):
    method=i.get('load_method','chiller')
    if method=='chiller':
        tr=float(i['chiller_tr']); cop=float(i['chiller_cop'])
        if tr<=0 or cop<=0: raise ValueError('Chiller TR and COP must be greater than zero')
        heat_kw=tr*TR_TO_KW*(1+1/cop)
    elif method=='direct':
        heat_kw=float(i['direct_load_kw'])
        if heat_kw<=0: raise ValueError('direct_load_kw must be greater than zero')
    else: raise ValueError('load_method must be chiller or direct')
    range_c=float(i['range_c']); wet=float(i['wet_bulb_c']); approach=float(i['approach_c'])
    coc=float(i['coc']); drift_pct=float(i['drift_pct'])
    if range_c<=0: raise ValueError('range_c must be greater than zero')
    if approach<0 or wet<0: raise ValueError('wet_bulb_c and approach_c must be non-negative')
    if coc<=1: raise ValueError('coc must be greater than 1')
    if drift_pct<0: raise ValueError('drift_pct must be non-negative')
    flow_kgs=heat_kw/(CP_KJ_KG_K*range_c); flow_m3hr=flow_kgs*3.6; flow_lpm=flow_kgs*60
    cwt=wet+approach; hwt=cwt+range_c
    evap_m3hr=(heat_kw*3600/LATENT_HEAT_KJ_KG)/1000
    drift_m3hr=flow_m3hr*drift_pct/100
    blow=max(evap_m3hr/(coc-1)-drift_m3hr,0)
    makeup=evap_m3hr+drift_m3hr+blow
    return {'heat_rejection_kw':round(heat_kw,3),'heat_rejection_tr':round(heat_kw/TR_TO_KW,3),'water_flow_m3hr':round(flow_m3hr,3),'water_flow_lpm':round(flow_lpm,2),'cold_water_temp_c':round(cwt,2),'hot_water_temp_c':round(hwt,2),'evaporation_m3hr':round(evap_m3hr,4),'drift_m3hr':round(drift_m3hr,4),'blowdown_m3hr':round(blow,4),'makeup_m3hr':round(makeup,4),'range_c':range_c,'approach_c':approach,'wet_bulb_c':wet,'coc':coc}
''')
w('skills/hvac/cooling_tower/adapter.py', r'''from skills.common import SkillRequest,SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='ed5447d4be48ebe71112f454b3c139136d4bfa9c'
class CoolingTowerSkill:
 skill_id='cooling_tower'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  for k in ['load_method','range_c','wet_bulb_c','approach_c','coc','drift_pct']:
   if k not in r.inputs: errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calculate(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  if r.inputs['load_method']=='chiller':
   for k in ['chiller_tr','chiller_cop']:
    if k not in r.inputs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=[f'Missing required input: {k}'],source_revision=REV)
  else:
   if 'direct_load_kw' not in r.inputs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=['Missing required input: direct_load_kw'],source_revision=REV)
  warns=['Preliminary cooling-tower sizing support; final tower selection requires vendor performance-curve verification.','Design wet-bulb temperature must be project/site specific.','Water-treatment and water-quality constraints are not modeled.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,human_review_required=True,source_revision=REV)
''')
w('skills/hvac/cooling_tower/__init__.py','from .adapter import CoolingTowerSkill\n')

# Refrigerant pipe
w('skills/hvac/refrigerant_pipe_sizing/source_calculator.py', r'''import math
PROPS={'R410A':{'refEffect':155,'vaporDensity':38,'liquidDensity':1050,'vaporVisc':13.5e-6,'liquidVisc':0.10e-3},'R32':{'refEffect':230,'vaporDensity':28,'liquidDensity':1000,'vaporVisc':13e-6,'liquidVisc':0.11e-3},'R22':{'refEffect':163,'vaporDensity':23,'liquidDensity':1150,'vaporVisc':12.5e-6,'liquidVisc':0.18e-3},'R134a':{'refEffect':148,'vaporDensity':15,'liquidDensity':1240,'vaporVisc':11.5e-6,'liquidVisc':0.19e-3}}
TUBES=[6.35,9.52,12.7,15.88,19.05,22.22,25.4,28.58,31.75,34.93,41.28,53.98,63.5,76.2]
WALL=0.9

def tube(required):
    for od in TUBES:
        bore=od-2*WALL
        if bore>=required:return od,bore
    od=TUBES[-1];return od,od-2*WALL

def ff(Re,eps,D):
    if Re<=0 or D<=0:return 0
    term=eps/(3.7*D)+5.74/(Re**0.9)
    return 0 if term<=0 else 0.25/(math.log10(term)**2)

def calc(i):
    ref=i['refrigerant']; p=PROPS[ref]; cap=float(i['capacity_kw']); sv=float(i['suction_velocity']); lv=float(i['liquid_velocity']); sl=float(i['suction_length']); ll=float(i['liquid_length'])
    if cap<=0 or sv<=0 or lv<=0:raise ValueError('capacity_kw and target velocities must be greater than zero')
    mf=cap/p['refEffect']; mfh=mf*3600; tr=cap/3.517
    svflow=mf/p['vaporDensity']; sbore=math.sqrt(4*svflow/(math.pi*sv))*1000; sod,sbore_actual=tube(sbore); sD=sbore_actual/1000; sarea=math.pi/4*sD*sD; sav=svflow/sarea
    lvflow=mf/p['liquidDensity']; lbore=math.sqrt(4*lvflow/(math.pi*lv))*1000; lod,lbore_actual=tube(lbore); lD=lbore_actual/1000; larea=math.pi/4*lD*lD; lav=lvflow/larea
    rough=0.0015e-3
    def dp(V,D,dens,mu,L):
        Re=dens*V*D/mu; f=ff(Re,rough,D); return f*(L/D)*(dens*V*V/2)/1000
    return {'refrigerant':ref,'capacity_kw':cap,'capacity_tr':round(tr,3),'mass_flow_kg_hr':round(mfh,3),'suction_required_bore_mm':round(sbore,3),'suction_standard_od_mm':sod,'suction_actual_velocity_ms':round(sav,3),'liquid_required_bore_mm':round(lbore,3),'liquid_standard_od_mm':lod,'liquid_actual_velocity_ms':round(lav,3),'suction_pressure_drop_kpa':round(dp(sav,sD,p['vaporDensity'],p['vaporVisc'],sl),4),'liquid_pressure_drop_kpa':round(dp(lav,lD,p['liquidDensity'],p['liquidVisc'],ll),4)}
''')
w('skills/hvac/refrigerant_pipe_sizing/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='1afd6bdc704c7b73daa6ca573fe07a820ed5ffd5'
class RefrigerantPipeSizingSkill:
 skill_id='refrigerant_pipe_sizing'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); req=['refrigerant','capacity_kw','suction_velocity','liquid_velocity','suction_length','liquid_length']
  for k in req:
   if k not in r.inputs:errs.append(f'Missing required input: {k}')
  if 'refrigerant' in r.inputs and r.inputs['refrigerant'] not in e.PROPS:errs.append('Unsupported refrigerant')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Preliminary sizing only; manufacturer piping guide must finalize pipe diameter, oil-return provisions and capacity corrections.','Refrigerant properties are fixed typical values from the source tool and vary with operating conditions.','Long-line, elevation and accessory effects beyond the source model are not captured.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/hvac/refrigerant_pipe_sizing/__init__.py','from .adapter import RefrigerantPipeSizingSkill\n')

# VRF
w('skills/hvac/vrf_sizing/source_calculator.py', r'''import math
IDU=[0.8,1,1.5,2,2.5,3,4,5,6,8,10]; ODU=[8,10,12,14,16,18,20,22,24,26,28,30]; HP_TO_KW=2.8
def step(v,a):
    for x in a:
        if x>=v:return x
    return a[-1]
def calc(i):
    zones=i['zones']; cr=float(i.get('combination_ratio',100)); total_kw=0; total_hp=0
    details=[]
    for z in zones:
        area=float(z['area']); lf=float(z['load_factor']); kw=area*lf/1000; hp=kw/HP_TO_KW; shp=step(hp,IDU) if hp>0 else 0
        total_kw+=kw; total_hp+=shp; details.append({'name':z.get('name','zone'),'area':area,'load_factor':lf,'load_kw':round(kw,3),'suggested_idu_hp':shp})
    if cr<=0:raise ValueError('combination_ratio must be greater than zero')
    req=total_hp/(cr/100)
    selected='–'
    if req>0:
        if req<=ODU[-1]:selected=f'{step(req,ODU)} HP (single module)'
        else:
            n=math.ceil(req/ODU[-1]); per=step(req/n,ODU); selected=f'{n} × {per} HP (combined modules)'
    limits=[('total_pipe_length_m',300),('farthest_branch_length_m',90),('odu_idu_height_diff_m',50),('idu_idu_height_diff_m',15)]
    checks={k:{'value':float(i.get(k,0)),'typical_max':m,'within_typical_range':abs(float(i.get(k,0)))<=m} for k,m in limits}
    return {'zones':details,'zone_count':len(zones),'total_load_kw':round(total_kw,3),'total_idu_hp':round(total_hp,3),'required_odu_hp':round(req,3),'selected_odu':selected,'combination_ratio_pct':cr,'checks':checks}
''')
w('skills/hvac/vrf_sizing/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='a06eb9135305c86e097ffeadcb49f122679e32db'
class VRFSizingSkill:
 skill_id='vrf_sizing'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  if not isinstance(r.inputs.get('zones'),list) or not r.inputs.get('zones'):errs.append('zones must be a non-empty list')
  if 'combination_ratio' not in r.inputs:errs.append('Missing required input: combination_ratio')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Generic VRF sizing conventions only; final indoor/outdoor models and piping limits require manufacturer selection software.','Source method rounds each zone to an IDU capacity step before summing connected HP, which can differ from raw thermal load.','Typical piping limits are reference values, not model-specific approvals.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/hvac/vrf_sizing/__init__.py','from .adapter import VRFSizingSkill\n')

# Cleanroom ACH
w('skills/hvac/cleanroom_ach/source_calculator.py', r'''ROOM_TYPES={
'Operating Room':{'achMin':20,'achMax':25,'achDefault':20,'oaAch':4,'pressure':'positive'},'Delivery Room':{'achMin':20,'achMax':25,'achDefault':20,'oaAch':4,'pressure':'positive'},'ICU':{'achMin':6,'achMax':6,'achDefault':6,'oaAch':2,'pressure':'positive'},'Isolation Room (Airborne)':{'achMin':12,'achMax':12,'achDefault':12,'oaAch':2,'pressure':'negative'},'Patient Room (General)':{'achMin':6,'achMax':6,'achDefault':6,'oaAch':2,'pressure':'neutral'},'Emergency / Trauma':{'achMin':6,'achMax':6,'achDefault':6,'oaAch':2,'pressure':'neutral'},'Laboratory':{'achMin':6,'achMax':12,'achDefault':8,'oaAch':2,'pressure':'negative'},'Nursery':{'achMin':6,'achMax':6,'achDefault':6,'oaAch':2,'pressure':'positive'},'Pharmacy — Sterile Compounding':{'achMin':20,'achMax':40,'achDefault':30,'oaAch':None,'pressure':'positive'},'Corridor (Public)':{'achMin':2,'achMax':2,'achDefault':2,'oaAch':None,'pressure':'neutral'},'Cleanroom — ISO 5':{'achMin':240,'achMax':480,'achDefault':350,'oaAch':None,'pressure':'positive'},'Cleanroom — ISO 6':{'achMin':150,'achMax':240,'achDefault':190,'oaAch':None,'pressure':'positive'},'Cleanroom — ISO 7':{'achMin':60,'achMax':90,'achDefault':75,'oaAch':None,'pressure':'positive'},'Cleanroom — ISO 8':{'achMin':20,'achMax':40,'achDefault':30,'oaAch':None,'pressure':'positive'}}
CFM_PER_CMH=0.589
def calc(i):
    typ=i['room_type']; ref=ROOM_TYPES[typ]; L=float(i['length_m']); W=float(i['width_m']); H=float(i['height_m']); ach=float(i.get('ach',ref['achDefault']))
    if min(L,W,H,ach)<=0:raise ValueError('Dimensions and ACH must be greater than zero')
    vol=L*W*H; cmh=ach*vol; cfm=cmh*CFM_PER_CMH; oa=None if ref['oaAch'] is None else ref['oaAch']*vol
    return {'room_type':typ,'volume_m3':round(vol,3),'ach':ach,'supply_cmh':round(cmh,2),'supply_cfm':round(cfm,2),'minimum_oa_cmh':None if oa is None else round(oa,2),'pressure_relationship':ref['pressure'],'reference_ach_min':ref['achMin'],'reference_ach_max':ref['achMax']}
''')
w('skills/hvac/cleanroom_ach/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='bd163a0f7e51971c613172c5f768b682027d2b05'
class CleanroomACHSKill:
 skill_id='cleanroom_ach'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['room_type','length_m','width_m','height_m']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if 'room_type' in i and i['room_type'] not in e.ROOM_TYPES:errs.append('Unknown room_type')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Reference ACH values are source-tool planning data and must be verified against the applicable standard/edition and project authority.','This tool does not establish cleanroom classification compliance by itself.','Pressure relationship and outdoor-air values require project sequence/authority confirmation.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/hvac/cleanroom_ach/__init__.py','from .adapter import CleanroomACHSKill\n')

# Duct leakage
w('skills/hvac/duct_leakage/source_calculator.py', r'''M2_TO_FT2=10.7639; PA_TO_INWG=1/249.089; LS_TO_CFM=2.11888
def calc(i):
    sections=i['sections']; area=0
    for s in sections:
        dia=float(s.get('diameter_mm',0)); w=float(s.get('width_mm',0)); h=float(s.get('height_mm',0)); L=float(s.get('length_m',0))
        if L<0:raise ValueError('length_m cannot be negative')
        if dia>0: per=3.141592653589793*dia/1000
        elif w>0 and h>0:per=2*(w+h)/1000
        else:raise ValueError('Each section needs diameter_mm or width_mm and height_mm')
        area+=per*L
    P=float(i['test_pressure_pa']); Q=float(i['measured_leakage_ls']); target=float(i['target_class'])
    if area<=0 or P<=0 or target<=0:raise ValueError('Area, test pressure and target class must be greater than zero')
    A=area*M2_TO_FT2; Pin=P*PA_TO_INWG; Qcfm=Q*LS_TO_CFM
    cl=(Qcfm*100)/(A*(Pin**0.65)) if Q>=0 else 0
    maxcfm=target*A*(Pin**0.65)/100; maxls=maxcfm/LS_TO_CFM
    return {'total_area_m2':round(area,3),'calculated_leakage_class':round(cl,3),'target_class':target,'pass':cl<=target,'max_allowable_leakage_ls':round(maxls,3),'max_allowable_leakage_cfm':round(maxcfm,3),'test_pressure_pa':P,'measured_leakage_ls':Q}
''')
w('skills/hvac/duct_leakage/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='aa6e95dbce04dfe71c99af16f07d7fc105193785'
class DuctLeakageSkill:
 skill_id='duct_leakage'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['sections','test_pressure_pa','measured_leakage_ls','target_class']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Leakage class is calculated using the source-tool SMACNA-formula implementation.','Project specification should govern the required leakage class over generic reference ranges.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/hvac/duct_leakage/__init__.py','from .adapter import DuctLeakageSkill\n')

# Chiller advisor
w('skills/hvac/chiller_selection/source_calculator.py', r'''def chiller_type(tr):
    if tr<=0:return ('–','Enter a total cooling load to see guidance.')
    if tr<50:return ('Scroll chiller (air-cooled)','Small loads are well served by modular scroll compressors.')
    if tr<150:return ('Scroll (modular) or Screw chiller','Either modular scroll units or a screw chiller may fit this range.')
    if tr<500:return ('Screw chiller (air or water-cooled)','Screw compressors are a common choice at this capacity.')
    if tr<1000:return ('Screw or Centrifugal chiller','Compare both on lifecycle and project requirements.')
    return ('Centrifugal chiller','Large capacities often suit centrifugal configurations.')
def condenser(water,space,priority):
    if water=='no':return ('Air-cooled','No water source available.')
    if space=='limited':return ('Air-cooled','Limited space for tower/plant room.')
    if priority=='high':return ('Water-cooled','Water is available, space allows tower, efficiency is priority.')
    return ('Water-cooled or Air-cooled — both viable','Compare efficiency, capex and O&M requirements.')
def calc(i):
    tr=float(i['total_load_tr']); water=i.get('water_available','yes'); space=i.get('space_available','ample'); priority=i.get('efficiency_priority','high'); eff=float(i['efficiency_kw_per_tr']); hours=float(i['annual_hours']); lf=float(i['load_factor_pct'])/100; tariff=float(i['tariff_per_kwh']); N=int(i['duty_modules']); red=int(i['redundancy_level'])
    if tr<=0 or eff<=0 or hours<0 or tariff<0 or N<=0 or red<0:raise ValueError('Invalid chiller advisor input')
    typ,treason=chiller_type(tr); cond,creason=condenser(water,space,priority); peak=tr*eff; kwh=peak*hours*lf; cost=kwh*tariff; mod=tr/N; total=N+red; inst=mod*total
    return {'total_load_tr':tr,'suggested_type':typ,'type_reason':treason,'condenser_type':cond,'condenser_reason':creason,'peak_kw':round(peak,2),'annual_kwh':round(kwh,2),'annual_cost':round(cost,2),'module_capacity_tr':round(mod,2),'total_modules':total,'installed_capacity_tr':round(inst,2),'redundancy_margin_pct':round((inst-tr)/tr*100,2)}
''')
w('skills/hvac/chiller_selection/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='75eedd78305e88e8fc2440559cb94f3839db515d'
class ChillerSelectionAdvisorSkill:
 skill_id='chiller_selection_advisor'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['total_load_tr','efficiency_kw_per_tr','annual_hours','load_factor_pct','tariff_per_kwh','duty_modules','redundancy_level']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Generic advisory only; final model, sound, footprint, part-load and certified performance require manufacturer selection data.','Efficiency benchmark values are source-tool user inputs, not live market data.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/hvac/chiller_selection/__init__.py','from .adapter import ChillerSelectionAdvisorSkill\n')

# Energy payback
w('skills/energy/payback/source_calculator.py', r'''def calc(i):
    capo=float(i['capacity_old']); effo=float(i['efficiency_old']); capn=float(i['capacity_new']); effn=float(i['efficiency_new']); hours=float(i['annual_hours']); lf=float(i['load_factor_pct'])/100; tariff=float(i['tariff_per_kwh']); inv=float(i['investment']); om=float(i.get('incremental_om',0)); life=max(1,min(25,int(i.get('project_life_years',10))))
    if min(capo,effo,capn,effn,hours,tariff,inv)<0 or lf<0:raise ValueError('Numeric inputs cannot be negative')
    old=capo*effo*hours*lf; new=capn*effn*hours*lf; saved=old-new; pct=(saved/old*100) if old>0 else 0; cost=saved*tariff; net=cost-om; payback=inv/net if net>0 else None; netlife=net*life-inv; roi=(netlife/inv*100) if inv>0 else 0
    cumulative=[]; cum=0
    for y in range(1,life+1):cum+=net;cumulative.append({'year':y,'annual_net_savings':round(net,2),'cumulative_savings':round(cum,2),'net_position':round(cum-inv,2)})
    return {'annual_kwh_old':round(old,2),'annual_kwh_new':round(new,2),'annual_kwh_saved':round(saved,2),'pct_saved':round(pct,3),'annual_cost_savings':round(cost,2),'incremental_om':round(om,2),'net_annual_savings':round(net,2),'payback_years':None if payback is None else round(payback,3),'net_savings_over_life':round(netlife,2),'roi_pct':round(roi,2),'project_life_years':life,'cumulative':cumulative}
''')
w('skills/energy/payback/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='e51a1c9603fe8da53b0cf68fcc1ebada93d38e0c'
class EnergyPaybackSkill:
 skill_id='energy_payback'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); req=['capacity_old','efficiency_old','capacity_new','efficiency_new','annual_hours','load_factor_pct','tariff_per_kwh','investment']
  for k in req:
   if k not in r.inputs:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Financial estimate only; tariff, operating hours, load factor and incremental O&M are user assumptions.','Does not include financing, discount rate, degradation, escalation or taxes beyond the simple source model.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/energy/payback/__init__.py','from .adapter import EnergyPaybackSkill\n')

# Commercial BOQ
w('skills/commercial/boq/source_calculator.py', r'''def calc(i):
    subtotal=0; cats=[]
    for c in i.get('categories',[]):
        s=0; rows=[]
        for row in c.get('items',[]):
            q=row.get('qty'); rate=row.get('rate')
            amt=float(q)*float(rate) if q is not None and rate is not None and q!='' and rate!='' else 0
            s+=amt; rows.append({'description':row.get('description',''),'unit':row.get('unit',''),'qty':q,'rate':rate,'amount':round(amt,2)})
        subtotal+=s;cats.append({'name':c.get('name',''),'subtotal':round(s,2),'items':rows})
    cp=float(i.get('contingency_pct',5)); op=float(i.get('overhead_pct',10)); taxp=float(i.get('tax_pct',18)); cont=subtotal*cp/100; oh=subtotal*op/100; pretax=subtotal+cont+oh; tax=pretax*taxp/100; grand=pretax+tax
    return {'categories':cats,'subtotal':round(subtotal,2),'contingency':round(cont,2),'overhead_profit':round(oh,2),'pretax':round(pretax,2),'tax':round(tax,2),'grand_total':round(grand,2),'contingency_pct':cp,'overhead_pct':op,'tax_pct':taxp}
''')
w('skills/commercial/boq/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='4eb8a9514431f0ede94df31824e539f23ee49ea'
class HVACBOQSkill:
 skill_id='hvac_boq'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  if not isinstance(r.inputs.get('categories'),list):errs.append('categories must be a list')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Commercial estimate; quantities and rates are preparer inputs.','Tax/markup calculations follow the source tool and do not validate commercial or tax compliance.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/commercial/boq/__init__.py','from .adapter import HVACBOQSkill\n')

# Deviation statement
w('skills/commercial/deviation/source_calculator.py', r'''def calc(i):
    rows=i.get('rows',[]); total=comp=partial=dev=na=0; deviations=[]
    for r in rows:
        st=r.get('status','comply'); total+=1
        if st=='comply':comp+=1
        elif st=='partial':partial+=1; deviations.append(r)
        elif st=='deviate':dev+=1; deviations.append(r)
        elif st=='na':na+=1
        else: raise ValueError(f'Unknown status: {st}')
    applicable=total-na; pct=round(comp/applicable*100) if applicable else 0
    return {'total':total,'comply':comp,'partial':partial,'deviate':dev,'na':na,'applicable':applicable,'compliance_pct':pct,'deviations':deviations}
''')
w('skills/commercial/deviation/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='babc94e0dba720cdcc04edec52bdfafb12d9deb'
class DeviationStatementSkill:
 skill_id='deviation_statement'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  if not isinstance(r.inputs.get('rows'),list):errs.append('rows must be a list')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Compliance percentage is a document-control metric, not a substitute for technical or contractual review.','Clause interpretation remains subject to the tender/project specification.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/commercial/deviation/__init__.py','from .adapter import DeviationStatementSkill\n')

# BMS alarm evaluation
w('skills/bms/alarm/source_calculator.py', r'''ANALOG=[{'id':'AHU1_SAT','normal_min':12,'normal_max':16,'alarm_low':10,'alarm_high':18},{'id':'AHU1_RAT','normal_min':22,'normal_max':26,'alarm_low':18,'alarm_high':30},{'id':'AHU2_SAT','normal_min':12,'normal_max':16,'alarm_low':10,'alarm_high':18},{'id':'AHU2_RAT','normal_min':22,'normal_max':26,'alarm_low':18,'alarm_high':30},{'id':'CH1_CHWST','normal_min':6,'normal_max':8,'alarm_low':4,'alarm_high':12},{'id':'CH1_CHWRT','normal_min':11,'normal_max':14,'alarm_low':8,'alarm_high':18},{'id':'CH2_CHWST','normal_min':6,'normal_max':8,'alarm_low':4,'alarm_high':12},{'id':'PP1_DP','normal_min':2.5,'normal_max':3.5,'alarm_low':1.5,'alarm_high':4.5},{'id':'DUCT_SP','normal_min':200,'normal_max':350,'alarm_low':100,'alarm_high':450},{'id':'CT_LEVEL','normal_min':60,'normal_max':90,'alarm_low':30,'alarm_high':95}]
DIGITAL={'AHU1_FAN':('Run',['Run','Stop','Fault']),'AHU2_FAN':('Run',['Run','Stop','Fault']),'CH1_STATUS':('Run',['Run','Standby','Fault']),'CH2_STATUS':('Standby',['Run','Standby','Fault']),'PP1_STATUS':('Run',['Run','Standby','Fault']),'PP2_STATUS':('Standby',['Run','Standby','Fault'])}
def calc(i):
    typ=i['point_type']; pid=i['point_id']; val=i['value']
    if typ=='analog':
        p=next((x for x in ANALOG if x['id']==pid),None)
        if not p:raise ValueError('Unknown analog point_id')
        v=float(val); status='Alarm' if v<p['alarm_low'] or v>p['alarm_high'] else ('Marginal' if v<p['normal_min'] or v>p['normal_max'] else 'Normal')
        return {'point_id':pid,'value':v,'alarm_status':status,'limits':p}
    p=DIGITAL.get(pid)
    if not p:raise ValueError('Unknown digital point_id')
    state=str(val); status='Alarm' if state=='Fault' else ('Marginal' if state!=p[0] else 'Normal')
    return {'point_id':pid,'value':state,'alarm_status':status,'expected_state':p[0],'possible_states':p[1]}
''')
w('skills/bms/alarm/adapter.py', r'''from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='20d5a695a5304ba2f110bbaa89c9820743a23f0a'
class BMSAlarmEvaluationSkill:
 skill_id='bms_alarm_evaluation'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['point_type','point_id','value']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Thresholds are example planning values from the source dashboard, not project-specific alarm setpoints.','For production BMS use, thresholds should come from the actual equipment sequence/controls specification.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
''')
w('skills/bms/alarm/__init__.py','from .adapter import BMSAlarmEvaluationSkill\n')
