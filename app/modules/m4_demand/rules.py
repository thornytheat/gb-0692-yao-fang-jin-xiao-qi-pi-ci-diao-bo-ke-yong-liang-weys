def apply(ctx):
     rows=[];demands=[]
     for d in ctx['demands']:
         need=max(0,d['qty_n']-d['frozen_n']);item={**d,'net_need':need};demands.append(item)
         rows.append({'需求单':d['record'],'门店':d['store'],'药品':d['sku'],'申请':d['qty_n'],'店内可用':d['frozen_n'],'净需求':need,'余期要求_天':d['min_days_n']})
     ctx['net_demands']=demands
     return {'rows':rows,'metrics':[['申请总量',sum(d['qty_n'] for d in demands),'件'],['净需求',sum(d['net_need'] for d in demands),'件'],['门店',len({d['store'] for d in demands}),'家']]}
