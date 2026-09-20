ANALOG=[{'id':'AHU1_SAT','normal_min':12,'normal_max':16,'alarm_low':10,'alarm_high':18},{'id':'AHU1_RAT','normal_min':22,'normal_max':26,'alarm_low':18,'alarm_high':30},{'id':'AHU2_SAT','normal_min':12,'normal_max':16,'alarm_low':10,'alarm_high':18},{'id':'AHU2_RAT','normal_min':22,'normal_max':26,'alarm_low':18,'alarm_high':30},{'id':'CH1_CHWST','normal_min':6,'normal_max':8,'alarm_low':4,'alarm_high':12},{'id':'CH1_CHWRT','normal_min':11,'normal_max':14,'alarm_low':8,'alarm_high':18},{'id':'CH2_CHWST','normal_min':6,'normal_max':8,'alarm_low':4,'alarm_high':12},{'id':'PP1_DP','normal_min':2.5,'normal_max':3.5,'alarm_low':1.5,'alarm_high':4.5},{'id':'DUCT_SP','normal_min':200,'normal_max':350,'alarm_low':100,'alarm_high':450},{'id':'CT_LEVEL','normal_min':60,'normal_max':90,'alarm_low':30,'alarm_high':95}]
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
