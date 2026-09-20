import math
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
