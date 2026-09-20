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
    tr=float(i['total_load_tr']); water=i.get('water_available','yes'); space=i.get('space_available','ample'); priority=i.get('efficiency_priority','high'); eff=float(i['efficiency_kw_per_tr']); hours=float(i['annual_hours']); lf=float(i['load_factor_pct'])/100; tariff=float(i['tariff_per_kwh']); N=int(i['duty_modules']); red=int(i['redundancy_level'])
    if tr<=0 or eff<=0 or hours<0 or tariff<0 or N<=0 or red<0:raise ValueError('Invalid chiller advisor input')
    typ,treason=chiller_type(tr); cond,creason=condenser(water,space,priority); peak=tr*eff; kwh=peak*hours*lf; cost=kwh*tariff; mod=tr/N; total=N+red; inst=mod*total
    return {'total_load_tr':tr,'suggested_type':typ,'type_reason':treason,'condenser_type':cond,'condenser_reason':creason,'peak_kw':round(peak,2),'annual_kwh':round(kwh,2),'annual_cost':round(cost,2),'module_capacity_tr':round(mod,2),'total_modules':total,'installed_capacity_tr':round(inst,2),'redundancy_margin_pct':round((inst-tr)/tr*100,2)}
