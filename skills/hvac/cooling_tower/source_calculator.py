TR_TO_KW=3.517
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
