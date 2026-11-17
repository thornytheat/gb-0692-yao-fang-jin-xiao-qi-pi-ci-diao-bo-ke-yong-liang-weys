from app.reader import read_rows
def apply(ctx):
    rows=read_rows(ctx)
    return {'rows':rows,'metrics':[['库存记录',sum(r['kind']=='stock' for r in rows),'条'],['需求记录',sum(r['kind']=='demand' for r in rows),'条'],['输入',ctx['input_count'],'条']]}

