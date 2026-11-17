def apply(ctx):
     opening=sum(s['available'] for s in ctx['usable']);sent=sum(r['调拨数量'] for r in ctx['allocations']);left=sum(ctx['remaining'].values())
     need=sum(d['net_need'] for d in ctx['net_demands']);missing=sum(r['缺口'] for r in ctx['shortages'])
     balanced=opening==sent+left and need==sent+missing;ctx['balanced']=balanced
     rows=[{'项目':'可调拨库存','期初':opening,'发出':sent,'结余或缺口':left,'差额':opening-sent-left},{'项目':'净需求','期初':need,'发出':sent,'结余或缺口':missing,'差额':need-sent-missing}]
     return {'rows':rows,'metrics':[['库存差额',opening-sent-left,'件'],['需求差额',need-sent-missing,'件'],['收发核验','相符' if balanced else '差异','']]}
