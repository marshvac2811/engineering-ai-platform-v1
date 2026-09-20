import math
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
