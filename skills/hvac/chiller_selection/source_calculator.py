def chiller_type(tr):
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
    tr=float(i['total_load_tr']); water=i.get('water_available','yes'); space=i.get('space_available','ample'); priority=i.get('efficiency_priority','high'); eff=float(i['efficiency_kw_per_tr']); hours=float(i['annual_hours']); lf=float(i['load_factor_pct'])/100; tariff=float(i['tariff_per_kwh'])
    if tr<=0 or eff<=0 or hours<0 or tariff<0:raise ValueError('Invalid chiller advisor input')
    typ,treason=chiller_type(tr); cond,creason=condenser(water,space,priority); peak=tr*eff; kwh=peak*hours*lf; cost=kwh*tariff
    red_raw=i.get('redundancy_level','N'); red_text=str(red_raw).strip().upper()
    red=1 if red_text in ('N+1','1') else 2 if red_text in ('N+2','2') else 0
    N_raw=i.get('duty_modules')
    if N_raw is not None:
        N=int(N_raw)
        if N<=0: raise ValueError('duty_modules must be positive when supplied')
        mod=tr/N; total=N+red; inst=mod*total
        module_result={'module_capacity_tr':round(mod,2),'duty_modules':N,'total_modules':total,'installed_capacity_tr':round(inst,2),'redundancy_margin_pct':round((inst-tr)/tr*100,2)}
    else:
        module_result={'module_capacity_tr':None,'duty_modules':None,'total_modules':None,'installed_capacity_tr':None,'redundancy_margin_pct':None,'module_configuration_status':'PENDING_MODULE_CAPACITY_BASIS'}
    return {'total_load_tr':tr,'suggested_type':typ,'type_reason':treason,'condenser_type':cond,'condenser_reason':creason,'peak_kw':round(peak,2),'annual_kwh':round(kwh,2),'annual_cost':round(cost,2),'redundancy_level':red_text,**module_result}
