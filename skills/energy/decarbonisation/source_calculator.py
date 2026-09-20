GRID_EMISSION_FACTOR=0.716; EMBODIED_CARBON_PER_TR=150.0; TREE_ABSORPTION_RATE=21.0
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
