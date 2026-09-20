import math
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
