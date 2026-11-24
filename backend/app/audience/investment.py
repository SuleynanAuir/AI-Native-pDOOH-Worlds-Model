"""Inventory-wide, auditable allocation. Model attitudes are never conversion rates."""
from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import math
from pathlib import Path
import re

from .engine import number
from .campaign import job_dir
from .world import read_json

WEIGHTS = dict(exposure=20, favorability=15, interest=20, visibility=15, location=15, market=10, cost=5)
LABELS = dict(exposure='库存曝光', favorability='模拟好感', interest='模拟兴趣', visibility='可见性', location='位置价值', market='市场匹配', cost='成本效率')


def valid_score(v):
    return type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 100


def summarize(base, threshold=60):
    """One observation denominator per dimension. Passenger attitudes stay unknown."""
    rows = {}
    for screen in base['screens']:
        rows[screen['id']] = dict(screen_id=screen['id'], scene_id=base['meta']['id'], title=base['meta']['title'],
            coordinate=screen.get('coordinate'),source_run_id=base['meta'].get('run_id'),observed_at=base['meta'].get('created_at'),hours=base['meta']['rounds'], total=0, pedestrian=0, vehicle=0,
            interest_sum=0, interest_rated=0, favorability_sum=0, favorability_rated=0, joint_rated=0,
            high_interest=0, high_favorability=0, joint_high=0, representatives=set(), hourly={})
    slots={s['round']:s for s in base['meta'].get('schedule',[])}
    for event in base.get('events',[]):
        row=rows.get(event.get('screen_id')); count=event.get('count')
        if row is None or type(count) not in (int,float) or not math.isfinite(count) or count<=0 or event.get('kind') not in ('pedestrian','vehicle'): continue
        row['total']+=count; row[event['kind']]+=count
        slot=slots.get(event.get('round'),{})
        hour=row['hourly'].setdefault(str(event.get('round')),dict(time=slot.get('time','未知时段'),day=slot.get('day'),total=0,interest_sum=0,interest_rated=0))
        hour['total']+=count
        if event['kind']!='pedestrian': continue
        match=re.match(r'^p-(\d+)-',str(event.get('actor_id','')))
        if not match: continue
        aid=match[1]; attitude=base.get('attitudes',{}).get('agents',{}).get(aid,{})
        row['representatives'].add(aid)
        for dim in ('interest','favorability'):
            v=attitude.get(dim)
            if not valid_score(v): continue
            row[dim+'_sum']+=v*count; row[dim+'_rated']+=count
            if v>=threshold: row['high_'+dim]+=count
            if dim=='interest': hour['interest_sum']+=v*count; hour['interest_rated']+=count
        if all(valid_score(attitude.get(d)) for d in ('interest','favorability')):
            row['joint_rated']+=count
            if min(attitude[d] for d in ('interest','favorability'))>=threshold: row['joint_high']+=count
    for row in rows.values():
        for dim in ('interest','favorability'):
            n=row[dim+'_rated']; row[dim]=row[dim+'_sum']/n if n else None
            row[dim+'_coverage']=n/row['total'] if row['total'] else 0
        row['representatives']=len(row['representatives'])
        row['peak']=sorted(row.pop('hourly').values(),key=lambda h:-h['total'])[:3]
    return rows


def campaign_evidence(root, identifier, threshold=60):
    if not identifier: return dict(campaign_id=None,campaign=None,screens={},fingerprint=None)
    directory=job_dir(Path(root)/'campaign_experiments',identifier)
    state=read_json(directory/'state.json')
    if state['status']!='completed': raise ValueError('请先完成广告实验，不能用部分结果分配预算')
    screens={}; digest=hashlib.sha256()
    for sid in state['spec']['scene_ids']:
        # IDs must not escape the experiment directory, including stored scene IDs.
        if not re.fullmatch('[0-9a-f]{32}',sid): raise ValueError('场景 ID 无效')
        raw=(directory/'scenes'/sid/'base.json').read_bytes(); digest.update(raw)
        base=json.loads(raw)
        if base.get('meta',{}).get('source_type')=='preview':continue
        for screen_id,row in summarize(base,threshold).items():
            if screen_id in screens: raise ValueError('同一屏幕存在多个实验场景，需先明确采用哪份结果，不能重复累加')
            screens[screen_id]=row
    return dict(campaign_id=identifier,campaign=state['spec']['campaign'],screens=screens,fingerprint=digest.hexdigest())


def settings(options):
    o=options.get('investment',{})
    if not isinstance(o,dict): raise ValueError('投资配置必须为对象')
    raw=o.get('weights',WEIGHTS)
    if not isinstance(raw,dict) or set(raw)!=set(WEIGHTS): raise ValueError('重要度权重需要全部七个维度')
    w={k:number(v,'重要度权重',0,100) for k,v in raw.items()}
    if sum(w.values())<=0: raise ValueError('重要度权重不能全部为零')
    total=sum(w.values()); w={k:v/total for k,v in w.items()}
    objective=o.get('objective','effect')
    if objective not in ('effect','exposure','profit'): raise ValueError('未知投资目标')
    return dict(weights=w,threshold=number(o.get('threshold',60),'高兴趣/好感阈值',0,100),
        max_screen_share=number(o.get('max_screen_share',.15),'单屏预算上限',.001,1),
        exploration_share=number(o.get('exploration_share',.2),'缺少态度证据的探索预算上限',0,1),
        objective=objective,complete_report=o.get('complete_report',False) is True,
        minimum_importance=number(o.get('minimum_importance',40),'追加投资最低重要度',0,100),
        roi=roi_settings(o.get('roi',{}),o.get('complete_report',False) is True))


def roi_settings(o, complete=False):
    if not isinstance(o,dict): raise ValueError('回报假设必须为对象')
    demo=dict(order_value=100,margin=.45,incrementality=.25,rates=dict(low=.05,base=.1,high=.2))
    o=dict(o); filled=[]
    if complete:
        for k in ('order_value','margin','incrementality'):
            if o.get(k) in (None,''):o[k]=demo[k];filled.append(k)
        rates=dict(o.get('rates',{}))
        for k in ('low','base','high'):
            if rates.get(k) in (None,''):rates[k]=demo['rates'][k];filled.append('rates.'+k)
        o['rates']=rates
    from .roi_calibration import validate_rows
    result={'demo_fields':filled,'calibration':validate_rows(o.get('calibration',{}))}
    for k,label,lo,hi in [('order_value','客单价',.01,1e9),('margin','毛利率',0,1),('incrementality','增量归因比例',0,1)]:
        result[k]=None if o.get(k) in (None,'') else number(o[k],label,lo,hi)
    def rates(value):
        if not isinstance(value,dict): raise ValueError('转化假设必须为对象')
        r={k:None if value.get(k) in (None,'') else number(value[k],'千次曝光订单假设',0,1000) for k in ('low','base','high')}
        known=[v for v in r.values() if v is not None]
        if known!=sorted(known): raise ValueError('保守/基准/乐观转化假设必须递增')
        return r
    result['rates']=rates(o.get('rates',{}))
    overrides=o.get('overrides',{})
    if not isinstance(overrides,dict) or len(overrides)>10000: raise ValueError('逐屏转化假设无效')
    result['overrides']={str(k):rates(v) for k,v in overrides.items()}
    if complete:
        for sid, values in result['overrides'].items():
            for k in ('low','base','high'):
                if values[k] is None:values[k]=result['rates'][k]
            rates(values)
    result['source']=str(o.get('source') or '用户情景假设，尚未用增量实验验证')[:1000]
    if filled:result['source']+='；未填项使用演示假设（非实测）：'+', '.join(filled)
    return result


def returns(exposures, cost, roi, screen_id=None):
    from .roi_calibration import assumptions
    model=assumptions(roi,screen_id); out={}; rates=model['rates']
    cost=cost+model['extra_cost'] if cost is not None else None
    ready=all(model[k] is not None for k in ('order_value','margin','incrementality'))
    for scenario,rate in rates.items():
        if not ready or rate is None: out[scenario]=None; continue
        orders=exposures/1000*rate*model['incrementality']
        revenue=orders*model['order_value']; contribution=revenue*model['margin']
        out[scenario]=dict(orders=orders,revenue=revenue,contribution=contribution,profit=contribution-cost,
            roi=(contribution-cost)/cost if cost>0 else None,roas=revenue/cost if cost>0 else None)
    value=(model['order_value'] or 0)*(model['margin'] or 0)*(model['incrementality'] or 0)
    out['break_even_per_thousand']=cost*1000/(exposures*value) if ready and value>0 and exposures>0 else None
    out.update(rate_source=model['rate_source'],basis=model,calibrated=model['calibrated'],total_cost=cost,extra_cost=model['extra_cost'])
    return out


def report(result, evidence, options, forecasts=None):
    cfg=settings(options); w=cfg['weights']; finance=result['finance']; rows=[]; forecasts=forecasts or {}
    for sid, row in cfg['roi']['calibration'].items():
        if row['currency']!=finance['currency']:raise ValueError('逐屏历史数据币种须与预算币种一致，请先换算并注明来源')
        if sid not in {f['screen_id'] for f in result['frames']}:raise ValueError('历史数据包含不在当前库存中的屏幕ID')
    from .ad_setup import core_regions
    for f in result['frames']:
        sim=evidence['screens'].get(f['screen_id']); mismatch=False
        if sim and sim.get('coordinate'):
            from .geolocation import distance_m
            p=sim['coordinate']
            mismatch=f['lat'] is None or f['lon'] is None or distance_m(f['lat'],f['lon'],p['lat'],p['lon'])>30
            if mismatch: sim=None
        dims={k:f['scores'][k] if valid_score(f['scores'][k]) else None for k in w if k not in ('interest','favorability')}
        if options.get('simulation_only') and sim and 'exposure' in dims:
            maximum=max((v.get('total',0) for v in evidence['screens'].values()),default=0)
            dims['exposure']=100*sim['total']/maximum if maximum else 0
        prediction=forecasts.get(f['screen_id'],{}) if cfg['complete_report'] else {}
        dims.update({k:sim[k] if sim and valid_score(sim.get(k)) else prediction.get(k) for k in ('interest','favorability')})
        unknown={k for k in w if dims[k] is None or f.get('evidence',{}).get(k,{}).get('type')=='assumption'}
        if prediction:unknown.update(k for k in ('interest','favorability') if not sim or not valid_score(sim.get(k)))
        score=sum((50 if dims[k] is None else dims[k])*w[k] for k in w)
        lower=sum(dims[k]*w[k] for k in w if k not in unknown)
        upper=lower+sum(100*w[k] for k in unknown)
        inventory_exp=max(0,f['impressions'] or 0)*finance['planning_days']/finance['period']
        exp=(sim['total']*24/sim['hours']*finance['planning_days']) if options.get('simulation_only') and sim else inventory_exp
        if options.get('simulation_only') and not sim:raise ValueError('本轮缺少此屏幕完整模拟，禁止用库存或预测替代')
        cpm=f['cpm_budget']; unit_cost=exp/1000*cpm*(1+finance['fee']) if cpm is not None and cpm>0 and f['eligible'] else None
        covered=bool(sim and sim['interest_rated']>0 and sim['favorability_rated']>0)
        row=dict(key=f['key'],screen_id=f['screen_id'],address=f['fields'].get('ADDRESS_THOROUGHFARE') or f['fields'].get('CLOSEST_POI'),
            eligible=f['eligible'],reasons=list(f['reasons']),warnings=list(f['warnings']),lat=f['lat'],lon=f['lon'],
            importance=score,importance_low=lower,importance_high=upper,dimensions=dims,unknown_dimensions=sorted(unknown),
            evidence_weight=1-sum(w[k] for k in unknown),sim=sim,attitude_available=covered,
            inventory_exposures=exp,inventory_reference_exposures=inventory_exp,exposure_basis='本轮24小时几何机会按投放天数缩放，非实测观看或保证交付' if options.get('simulation_only') else '库存曝光折算',all_in_cpm=cpm*(1+finance['fee']) if cpm is not None else None,
            full_sot_cost=unit_cost,recommended_amount=0.,recommended_sot=0.,recommended_exposures=0.,budget_share=0.,
            status='待分配' if f['eligible'] else '排除',peak=sim['peak'] if sim else [],
            return_at_full_sot=returns(exp,unit_cost,cfg['roi'],f['screen_id']) if unit_cost is not None else None)
        row['metrics']=dict(total=sim['total'] if sim else exp/finance['planning_days'],hours=sim['hours'] if sim else 24,
            favorability=dims['favorability'],interest=dims['interest'],
            opportunity_source='直接模拟' if sim else '24h库存折算预测 · 非模拟',
            favorability_coverage=sim.get('favorability_coverage') if sim else None,interest_coverage=sim.get('interest_coverage') if sim else None,
            attitude_source='直接模拟' if covered else prediction.get('source','尚未预测'),prediction=prediction)
        if prediction:row['warnings'].append(prediction.get('reason',''))
        if mismatch: row['warnings'].append('同 ID 库存与模拟坐标相差超过30米，态度未关联')
        row['reason']='；'.join(f['reasons']) if not f['eligible'] else ('直接场景态度可用于相对比较，建议先试投验证' if covered else '没有本屏幕广告态度证据，仅适合探索试投与补充调查')
        if covered:
            row['reason']+=f'；模拟好感 {sim["favorability"]:.1f}、兴趣 {sim["interest"]:.1f}/100；兴趣评分覆盖 {sim["interest_coverage"]:.1%}'
            row['test_action']=('兴趣偏低，先对照测试更具体的产品诉求和当前文案，取得实测兴趣与增量订单后再扩量' if sim['interest']<40 else '将模拟高峰与非高峰做小额对照，记录广告记忆、兴趣和增量订单，验证每千次曝光订单假设')
            if sim['favorability']<40: row['test_action']='好感偏低，先调查负面反应与品牌诉求错配，再决定是否扩大投放'
        else: row['test_action']='补充本地点现场可见性和目标群体资料，完成此屏幕的广告模拟；探索试投使用对照组验证记忆与增量订单'
        if not f['eligible']: row['test_action']='先解决库存排除原因，重新确认可售、坐标、曝光、价格与币种'
        if unit_cost is not None: row['reason']+=f'；含DSP CPM {row["all_in_cpm"]:.2f} {finance["currency"]}'
        rows.append(row)
    ranked=sorted((r for r in rows if r['eligible']),key=lambda r:(-r['importance'],r['screen_id']))
    for rank,row in enumerate(ranked,1): row['rank']=rank
    from .investment_allocation import allocate_trial
    allocator=allocate_trial if cfg['complete_report'] else allocate
    allocation=allocator(rows,finance,cfg,number(options.get('overlap_penalty',.5),'区域重复惩罚',0,10))
    totals={k:None for k in ('low','base','high')}
    chosen=[r for r in rows if r['recommended_amount']>0]
    for scenario in totals:
        values=[r['returns'][scenario] for r in chosen]
        if values and all(v is not None for v in values):
            revenue=sum(v['revenue'] for v in values); contribution=sum(v['contribution'] for v in values); cost=allocation['total']+sum(r['returns'].get('extra_cost',0) for r in chosen)
            totals[scenario]=dict(orders=sum(v['orders'] for v in values),revenue=revenue,contribution=contribution,profit=contribution-cost,roi=(contribution-cost)/cost,roas=revenue/cost)
    return dict(rows=sorted(rows,key=lambda r:(not r['eligible'],r.get('rank',1e10),r['key'])),config=cfg,scenario_label=str(options.get('scenario_label') or '用户输入的规划情景')[:200],
        evidence={k:v for k,v in evidence.items() if k!='screens'},allocation=allocation,returns=totals,regions=core_regions(result['frames']),
        coverage=dict(total=len(rows),eligible=len(ranked),direct=sum(r['sim'] is not None for r in rows),attitude=sum(r['attitude_available'] for r in rows),calibrated=sum(r['screen_id'] in cfg['roi']['calibration'] for r in rows),predicted=sum(bool(r['metrics']['prediction']) for r in rows),missing=sum(r['sim'] is None for r in rows)),
        assumptions=(["本报告曝光、态度和排序来自本轮完整24小时模拟；价格取自库存。几何机会按投放天数及SOT线性缩放，是模拟预算情景，不是可保证交付的广告曝光。"] if options.get('simulation_only') else [])+allocation.get('notes',[])+[cfg['roi']['source'],'缺失直接模拟时单列LLM逐屏预测；24h机会为库存曝光÷库存周期天数，不冒充原模拟周期。','库存曝光按周期、天数和 SOT 线性缩放；模拟曝光单独列示，不替代计费库存。',
            '好感和兴趣为经过事件加权的模拟分，不是关注率、转化率或真实调查。车辆无态度不补零。',
            '重要度缺失维度用50中性先验；范围按未知维度0–100算出，是敏感性范围而非统计置信区间。',
            '评分权重、单屏上限、探索比例和区域递减均为用户可调整的规划政策，不是行业标准。',
            '排序是重要度；金额按边际目标/成本、SOT、集中度和探索上限分配，允许留存预算，非全局最优。',
            'ROAS=增量收入/广告费；ROI=(增量毛利−广告费)/广告费。仅计算广告贡献，未提供的创意、固定运营成本和税费未计入。',
            '逐屏校准使用同周期投放组与对照组订单/曝光差值，不由好感或兴趣分推导收益。额外执行成本计入ROI但不计入媒体预算；无对照数据只展示未校准情景区间。','转化假设按每千次非去重库存曝光的增量订单建模，需用同口径历史数据校准；不能由兴趣分推导。',
            '各屏幕收入相加仅作无跨屏转化重复的情景上限，正式预算需用对照实验校准重复归因。'])


def allocate(rows, finance, cfg, penalty):
    D=lambda v:Decimal(str(v))
    cents=lambda v:int((D(v)*100).to_integral_value(rounding=ROUND_FLOOR))
    budget=cents(finance['budget']); screen_cap=cents(D(finance['budget'])*D(cfg['max_screen_share']))
    explore_cap=cents(D(finance['budget'])*D(cfg['exploration_share'])); spent=explored=0
    units=int((D(finance['max_sot'])/D(finance['step'])).to_integral_value(rounding=ROUND_FLOOR))
    chosen=Counter(); regions=Counter(); candidates=[]
    for row in rows:
        if not row['eligible'] or row['full_sot_cost'] is None: continue
        exposures=row['inventory_exposures']*finance['step']
        cost=max(1,int((D(row['full_sot_cost'])*D(finance['step'])*100).to_integral_value(rounding=ROUND_CEILING)))
        utility=exposures*row['importance']/100 if cfg['objective']=='effect' else exposures
        if cfg['objective']=='profit':
            value=returns(exposures,cost/100,cfg['roi'],row['screen_id'])['base']
            utility=value['profit'] if value else 0
        cluster=(math.floor(row['lat']/.01),math.floor(row['lon']/.01))
        candidates.append((row,cost,exposures,utility,cluster))
    # Recompute all feasible marginal choices: finite, deterministic and auditable.
    while True:
        feasible=[]
        for row,cost,exposures,utility,cluster in candidates:
            key=row['key']; n=chosen[key]
            if utility<=0 or n>=units or spent+cost>budget or (n+1)*cost>screen_cap: continue
            if not row['attitude_available'] and explored+cost>explore_cap: continue
            value=utility/cost/(1+penalty*regions[cluster])/(1+n*finance['step'])
            feasible.append((value,row['screen_id'],key,row,cost,exposures,cluster))
        if not feasible: break
        _,_,key,row,cost,exposures,cluster=max(feasible,key=lambda c:(c[0],c[1],c[2]))
        chosen[key]+=1;regions[cluster]+=1;spent+=cost
        if not row['attitude_available']: explored+=cost
    for row,cost,exposures,utility,cluster in candidates:
        n=chosen[row['key']]; amount=cost*n/100
        row.update(recommended_amount=amount,recommended_sot=float(D(n)*D(finance['step'])),recommended_exposures=exposures*n,budget_share=amount/finance['budget'])
        row['returns']=returns(exposures*n,amount,cfg['roi'],row['screen_id']) if n else None
        if n:
            row['status']='建议试投' if row['attitude_available'] else '探索试投'
            row['reason']+=f'；分配 {row["recommended_sot"]:.0%} SOT，单屏预算上限 {cfg["max_screen_share"]:.0%}'
        else:
            row['status']='暂不投入'
            if cfg['objective']=='profit' and utility<=0: row['reason']+='；基准转化假设缺失或增量毛利不足以覆盖广告费'
            elif cost>screen_cap: row['reason']+='；最小SOT成本超过单屏预算上限'
            elif not row['attitude_available'] and explored+cost>explore_cap: row['reason']+='；探索预算上限不足以再买一个步长'
            else: row['reason']+='；预算/SOT/集中度约束下未获追加分配'
    return dict(total=spent/100,remaining=(budget-spent)/100,exploration=explored/100,screen_count=len(chosen),budget=finance['budget'],currency=finance['currency'],budget_only=finance['budget_only'])


def attach_plan(result):
    decision=result['investment']; items=[]; finance=result['finance']
    for row in decision['rows']:
        if not row['recommended_amount']: continue
        media=row['recommended_exposures']/1000*row['all_in_cpm']/(1+finance['fee'])
        fee=media*finance['fee']; amount=row['recommended_amount']
        items.append(dict(key=row['key'],screen_id=row['screen_id'],sot=row['recommended_sot'],impressions=row['recommended_exposures'],media_budget=media,dsp_cost=fee,rounding_reserve=max(0,amount-media-fee),total=amount,score=row['importance'],reason=row['reason'],cluster=[math.floor(row['lat']/.01),math.floor(row['lon']/.01)]))
    if result.get('options',{}).get('simulation_only'):result['plans']=[]
    result['plans'].append(dict(strategy='investment',items=items,**decision['allocation'],impressions=sum(i['impressions'] for i in items),region_cells=len({tuple(i['cluster']) for i in items}),weights=result['weights'],excluded_ids=[],risks=['七维重要度与独立的投资约束用于本方案；原六维库存评分保留供对照。']))
    if decision['config'].get('complete_report'):
        result['formulas']['trial_allocation']='不设固定使用率；在预算、库存、单屏上限内分配试投种子，再按目标/CPM与区域重复惩罚加权；低重要度或利润目标下非正回报停止追加。连续SOT预算级测算'
    result['formulas'].update(importance='Σ(七维分数 × 归一权重)，缺少态度=50先验，仅用于重要度，不填入原态度列',investment='每步库存曝光 × 重要度 / 成本，按区域与单屏投入递减；受探索上限、单屏上限与总预算约束',orders='库存计划曝光 / 1000 × 用户千次订单假设 × 增量归因比例',roas='增量订单 × 客单价 / 广告费',roi='(增量订单 × 客单价 × 毛利率 − 广告费) / 广告费')

    if decision['config'].get('complete_report'):
        result['formulas']['investment']=result['formulas']['trial_allocation']


def export_sheets(result):
    """Append to the existing export contract; formula cells keep cached results."""
    decision=result.get('investment')
    if not decision: return []
    roi=decision['config']['roi']; currency=result['finance']['currency']; rows=[]; scenario_rows=[]
    for r in decision['rows']:
        metrics=r.get('metrics') or {}
        sim=metrics if decision['config'].get('complete_report') else (r['sim'] or {})
        rows.append([r.get('rank'),r['screen_id'],r['address'],r['status'],r['importance'],r['importance_low'],r['importance_high'],
            r['inventory_exposures'],sim.get('total'),sim.get('hours'),sim.get('favorability'),sim.get('interest'),sim.get('favorability_coverage'),sim.get('interest_coverage'),
            r['all_in_cpm'],r['recommended_sot'],r['recommended_exposures'],r['recommended_amount'],r['budget_share'],currency,
            '；'.join(f"第{h['day']}天 {h['time']}" for h in r['peak']),r['reason'],'；'.join(r['warnings']),
            json.dumps(r['dimensions'],ensure_ascii=False),','.join(r['unknown_dimensions']),decision['evidence']['campaign_id'],decision['evidence']['fingerprint'],r['test_action'],metrics.get('opportunity_source'),metrics.get('attitude_source'),json.dumps(metrics.get('prediction'),ensure_ascii=False)])
        from .roi_calibration import assumptions
        model=assumptions(roi,r['screen_id']);rates=model['rates']
        for scenario in ('low','base','high'):
            values=(r.get('returns') or {}).get(scenario); index=len(scenario_rows)+2
            entry=[r['screen_id'],scenario,r['recommended_exposures'],r['recommended_amount'],rates[scenario],model['incrementality'],model['order_value'],model['margin']]
            formulas=[f'C{index}/1000*E{index}*F{index}',f'I{index}*G{index}',f'J{index}*H{index}',f'K{index}-D{index}-S{index}',f'L{index}/(D{index}+S{index})',f'J{index}/(D{index}+S{index})']
            entry += [dict(formula=formula,value=values[key]) if values and (key not in ('roi','roas') or r['recommended_amount']>0) else None for key,formula in zip(('orders','revenue','contribution','profit','roi','roas'),formulas)]
            entry += [currency,model['source'],model['rate_source'],decision['evidence']['campaign_id'],model['extra_cost'],model.get('period'),model['calibrated']]
            scenario_rows.append(entry)
    return [('Investment Ranking',['Rank','Screen ID','Address','Recommendation status','Importance','Unknown lower bound','Unknown upper bound','Inventory opportunities full SOT','Simulated or forecast opportunities','Observation or forecast hours','Favorability /100','Interest /100','Favorability coverage','Interest coverage','All-in CPM','Recommended SOT','Planned opportunities','Recommended investment','Budget share','Currency','Simulation peak','Reason','Risks','Dimensions','Missing dimensions','Campaign ID','Simulation fingerprint','Validation plan','Opportunity source','Attitude source','Prediction provenance'],rows),
        ('Return Scenarios',['Screen ID','Scenario','Planned opportunities','Advertising cost','Orders per 1000 opportunities','Incrementality','Order value','Gross margin','Incremental orders','Incremental revenue','Incremental gross profit','Contribution after ads','ROI','ROAS','Currency','Assumption source','Rate scope','Campaign ID','Extra execution cost','Observation period','Calibrated from test-control'],scenario_rows),
        ('Investment Assumptions',['Item','Value'],[['Scenario',decision['scenario_label']],['Scope','Investment Ranking and Return Scenarios describe the investment strategy, independently of the selected comparison Proposal strategy.'],['Coverage',json.dumps(decision['coverage'])],['Configuration',json.dumps(decision['config'],ensure_ascii=False)],['Allocation',json.dumps(decision['allocation'])]]+[['Assumption',s] for s in decision['assumptions']])]
