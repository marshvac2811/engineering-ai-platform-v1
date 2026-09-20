def calc(i):
    rows=i.get('rows',[]); total=comp=partial=dev=na=0; deviations=[]
    for r in rows:
        st=r.get('status','comply'); total+=1
        if st=='comply':comp+=1
        elif st=='partial':partial+=1; deviations.append(r)
        elif st=='deviate':dev+=1; deviations.append(r)
        elif st=='na':na+=1
        else: raise ValueError(f'Unknown status: {st}')
    applicable=total-na; pct=round(comp/applicable*100) if applicable else 0
    return {'total':total,'comply':comp,'partial':partial,'deviate':dev,'na':na,'applicable':applicable,'compliance_pct':pct,'deviations':deviations}
