def calc(i):
    capo=float(i['capacity_old']); effo=float(i['efficiency_old']); capn=float(i['capacity_new']); effn=float(i['efficiency_new']); hours=float(i['annual_hours']); lf=float(i['load_factor_pct'])/100; tariff=float(i['tariff_per_kwh']); inv=float(i['investment']); om=float(i.get('incremental_om',0)); life=max(1,min(25,int(i.get('project_life_years',10))))
    if min(capo,effo,capn,effn,hours,tariff,inv)<0 or lf<0:raise ValueError('Numeric inputs cannot be negative')
    old=capo*effo*hours*lf; new=capn*effn*hours*lf; saved=old-new; pct=(saved/old*100) if old>0 else 0; cost=saved*tariff; net=cost-om; payback=inv/net if net>0 else None; netlife=net*life-inv; roi=(netlife/inv*100) if inv>0 else 0
    cumulative=[]; cum=0
    for y in range(1,life+1):cum+=net;cumulative.append({'year':y,'annual_net_savings':round(net,2),'cumulative_savings':round(cum,2),'net_position':round(cum-inv,2)})
    return {'annual_kwh_old':round(old,2),'annual_kwh_new':round(new,2),'annual_kwh_saved':round(saved,2),'pct_saved':round(pct,3),'annual_cost_savings':round(cost,2),'incremental_om':round(om,2),'net_annual_savings':round(net,2),'payback_years':None if payback is None else round(payback,3),'net_savings_over_life':round(netlife,2),'roi_pct':round(roi,2),'project_life_years':life,'cumulative':cumulative}
