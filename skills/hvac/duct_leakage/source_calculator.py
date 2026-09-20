M2_TO_FT2=10.7639; PA_TO_INWG=1/249.089; LS_TO_CFM=2.11888
def calc(i):
    sections=i['sections']; area=0
    for s in sections:
        dia=float(s.get('diameter_mm',0)); w=float(s.get('width_mm',0)); h=float(s.get('height_mm',0)); L=float(s.get('length_m',0))
        if L<0:raise ValueError('length_m cannot be negative')
        if dia>0: per=3.141592653589793*dia/1000
        elif w>0 and h>0:per=2*(w+h)/1000
        else:raise ValueError('Each section needs diameter_mm or width_mm and height_mm')
        area+=per*L
    P=float(i['test_pressure_pa']); Q=float(i['measured_leakage_ls']); target=float(i['target_class'])
    if area<=0 or P<=0 or target<=0:raise ValueError('Area, test pressure and target class must be greater than zero')
    A=area*M2_TO_FT2; Pin=P*PA_TO_INWG; Qcfm=Q*LS_TO_CFM
    cl=(Qcfm*100)/(A*(Pin**0.65)) if Q>=0 else 0
    maxcfm=target*A*(Pin**0.65)/100; maxls=maxcfm/LS_TO_CFM
    return {'total_area_m2':round(area,3),'calculated_leakage_class':round(cl,3),'target_class':target,'pass':cl<=target,'max_allowable_leakage_ls':round(maxls,3),'max_allowable_leakage_cfm':round(maxcfm,3),'test_pressure_pa':P,'measured_leakage_ls':Q}
