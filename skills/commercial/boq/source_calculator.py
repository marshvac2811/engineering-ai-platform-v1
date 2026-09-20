def calc(i):
    subtotal=0; cats=[]
    for c in i.get('categories',[]):
        s=0; rows=[]
        for row in c.get('items',[]):
            q=row.get('qty'); rate=row.get('rate')
            amt=float(q)*float(rate) if q is not None and rate is not None and q!='' and rate!='' else 0
            s+=amt; rows.append({'description':row.get('description',''),'unit':row.get('unit',''),'qty':q,'rate':rate,'amount':round(amt,2)})
        subtotal+=s;cats.append({'name':c.get('name',''),'subtotal':round(s,2),'items':rows})
    cp=float(i.get('contingency_pct',5)); op=float(i.get('overhead_pct',10)); taxp=float(i.get('tax_pct',18)); cont=subtotal*cp/100; oh=subtotal*op/100; pretax=subtotal+cont+oh; tax=pretax*taxp/100; grand=pretax+tax
    return {'categories':cats,'subtotal':round(subtotal,2),'contingency':round(cont,2),'overhead_profit':round(oh,2),'pretax':round(pretax,2),'tax':round(tax,2),'grand_total':round(grand,2),'contingency_pct':cp,'overhead_pct':op,'tax_pct':taxp}
