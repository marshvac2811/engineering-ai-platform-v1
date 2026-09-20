import math
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
