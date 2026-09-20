import math
TYPICAL_POINTS_PER_UNIT={'ahu':10,'chiller':12,'pump':5,'vfd':6}
def estimate_cost(ahu_count,chiller_count,pump_count,vfd_count,misc_points,points_per_controller,controllers_per_panel,cost_per_point,cost_per_controller,cost_per_panel,bms_software_cost,engineering_pct):
    vals=[ahu_count,chiller_count,pump_count,vfd_count,misc_points]
    if any(v<0 for v in vals):raise ValueError('Equipment counts/points cannot be negative')
    if points_per_controller<=0 or controllers_per_panel<=0:raise ValueError('Controller/panel capacities must be positive')
    if min(cost_per_point,cost_per_controller,cost_per_panel,bms_software_cost)<0:raise ValueError('Costs cannot be negative')
    if not 0<=engineering_pct<=100:raise ValueError('Engineering percentage must be between 0 and 100')
    br={'AHU':ahu_count*10,'Chiller':chiller_count*12,'Pump':pump_count*5,'VFD':vfd_count*6,'Miscellaneous':misc_points}; total=sum(br.values())
    if total==0:raise ValueError('Total points is zero')
    cc=math.ceil(total/points_per_controller); pc=math.ceil(cc/controllers_per_panel)
    field=total*cost_per_point; ctrl=cc*cost_per_controller; panel=pc*cost_per_panel; hw=field+ctrl+panel; sw=hw+bms_software_cost; eng=sw*engineering_pct/100; total_cost=sw+eng
    return {'points_breakdown':br,'total_points':total,'points_per_controller':points_per_controller,'controller_count':cc,'controllers_per_panel':controllers_per_panel,'panel_count':pc,'cost_per_point':cost_per_point,'field_wiring_cost':round(field,0),'cost_per_controller':cost_per_controller,'controller_cost':round(ctrl,0),'cost_per_panel':cost_per_panel,'panel_cost':round(panel,0),'hardware_subtotal':round(hw,0),'bms_software_cost':round(bms_software_cost,0),'subtotal_with_software':round(sw,0),'engineering_pct':engineering_pct,'engineering_cost':round(eng,0),'total_project_cost':round(total_cost,0),'cost_per_point_overall':round(total_cost/total,0)}
