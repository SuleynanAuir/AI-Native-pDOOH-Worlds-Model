"""Cent-exact all-screen trial envelope, not a confirmed discrete-SOT purchase."""
from decimal import Decimal, ROUND_FLOOR
import math


def allocate_trial(rows, finance, cfg, penalty):
    from .investment import returns
    cents=lambda x:int((Decimal(str(x))*100).to_integral_value(rounding=ROUND_FLOOR))
    budget=cents(finance['budget']);target=budget
    cap=cents(Decimal(str(finance['budget']))*Decimal(str(cfg['max_screen_share'])))
    candidates=[r for r in rows if r['eligible'] and (r['full_sot_cost'] or 0)>0]
    limits={r['key']:min(cap,cents(Decimal(str(r['full_sot_cost']))*Decimal(str(finance['max_sot'])))) for r in candidates}
    candidates=[r for r in candidates if limits[r['key']]>=1]
    from .roi_calibration import assumptions
    extras={r['key']:cents(assumptions(cfg['roi'],r['screen_id'])['extra_cost']) for r in candidates}
    for r in candidates:limits[r['key']]=min(limits[r['key']],max(0,cap-extras[r['key']]))
    candidates=[r for r in candidates if limits[r['key']]>=1]
    target=max(0,budget-sum(extras[r['key']] for r in candidates))
    clusters={r['key']:(math.floor(r['lat']/.01),math.floor(r['lon']/.01)) for r in candidates}
    counts={c:list(clusters.values()).count(c) for c in set(clusters.values())}
    weights={}
    for r in candidates:
        utility=r['importance']/100 if cfg['objective']=='effect' else 1
        if cfg['objective']=='profit':
            value=returns(r['inventory_exposures'],r['full_sot_cost'],cfg['roi'],r['screen_id'])['base']
            utility=max(0,value['roi']+1) if value else 0
        weights[r['key']]=max(.000001,utility/max(.01,r['all_in_cpm']))/(1+penalty*(counts[clusters[r['key']]]-1))
    # A small seed preserves all-screen testing; additional investment must qualify.
    spent={r['key']:0 for r in candidates};remaining=min(target,sum(limits.values()))
    seed=max(1,remaining//max(1,len(candidates))//10)
    for r in sorted(candidates,key=lambda r:(-r['importance'],r['screen_id'])):
        amount=min(seed,limits[r['key']],remaining);spent[r['key']]=amount;remaining-=amount
    while remaining>0:
        active=[r['key'] for r in candidates if spent[r['key']]<limits[r['key']] and r['importance']>=cfg['minimum_importance']
                and (cfg['objective']!='profit' or (r['return_at_full_sot'] or {}).get('base') and r['return_at_full_sot']['base']['roi']>0)]
        if not active:break
        total=sum(weights[k] for k in active); pool=remaining
        grants={k:min(limits[k]-spent[k],int(pool*weights[k]/total)) for k in active}
        if not any(grants.values()):
            for k in sorted(active,key=lambda k:(-weights[k],k))[:remaining]:grants[k]=1
        for k,v in grants.items():spent[k]+=v;remaining-=v
    for r in rows:
        amount=spent.get(r['key'],0)/100
        if amount:
            sot=amount/r['full_sot_cost'];exposure=r['inventory_exposures']*sot
            r.update(recommended_amount=amount,recommended_sot=sot,recommended_exposures=exposure,budget_share=amount/finance['budget'],
                     returns=returns(exposure,amount,cfg['roi'],r['screen_id']),status='全屏试投预算')
            r['reason']+='；连续SOT预算测算，须向DSP确认最小购买份额后执行'
        else:
            r['returns']=None
            if r['eligible']:r['reason']+='；预算或库存容量不足最低0.01货币单位，无法分配'
    extra_total=sum(extras[k] for k,v in spent.items() if v>0)
    total=sum(spent.values());notes=['不设90%或其它固定投入比例，按可售容量、重要度、成本与目标约束计算；额外执行成本先从总预算预留，逐屏建议金额为含DSP的媒体投入。','全屏试投采用连续SOT预算份额，不受离散SOT步长和旧20%探索上限约束；不是已确认的购买订单。']
    if total<target:notes.append('预算余额由库存容量、单屏上限、最低重要度或利润条件决定，不按固定百分比保留。')
    if any(r['eligible'] and not r['recommended_amount'] for r in rows):notes.append('存在不能获得正金额的屏幕，请检查可售状态、价格、库存容量或提高预算。')
    return dict(total=total/100,remaining=(budget-total-extra_total)/100,exploration=sum(spent.get(r['key'],0) for r in rows if not r['attitude_available'])/100,
                screen_count=sum(v>0 for v in spent.values()),budget=finance['budget'],currency=finance['currency'],budget_only=True,
                extra_cost_total=extra_total/100,overall_total=(total+extra_total)/100,utilization=(total+extra_total)/budget if budget else 0,policy='adaptive_all_screen_trial',minimum_importance=cfg['minimum_importance'],notes=notes)
