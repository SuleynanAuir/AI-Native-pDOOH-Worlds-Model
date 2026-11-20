"""Evidence-labelled screen scoring and budget-constrained, discrete SOT planning."""
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import heapq
import json
import math
import re

from .engine import number
from .workbook import read_workbook, headers_and_records, write_workbook, col_name

DIMENSIONS = ('exposure', 'visibility', 'location', 'market', 'cost', 'availability')
WEIGHTS = dict(zip(DIMENSIONS, (.12, .28, .22, .22, .10, .06)))
PRESETS = {
    'balanced': WEIGHTS,
    'coverage': dict(zip(DIMENSIONS, (.10, .25, .25, .20, .10, .10))),
    'venue': dict(zip(DIMENSIONS, (.05, .30, .35, .20, .05, .05))),
    'exposure': dict(zip(DIMENSIONS, (.55, .15, .10, .05, .10, .05))),
}
ALIASES = {'SCREENID':'VIOOH_ID', 'FRAMEID':'VIOOH_ID', 'COUNTRY':'ADDRESS_COUNTRY', 'CURRENCY':'MEDIAOWNERCURRENCY', 'CPM':'FLOORCPM', 'VENUE':'VENUE_TAXONOMY_VALUE', 'VEN UETYPE':'VENUE_TAXONOMY_VALUE', 'IMAGEPATH':'FRAMEIMAGEPATH'}
COUNTRIES = {'USA':'USA', 'US':'USA', 'UNITED STATES':'USA', 'UNITED STATES OF AMERICA':'USA', 'UK':'GBR', 'GB':'GBR', 'GBR':'GBR', 'UNITED KINGDOM':'GBR', 'CN':'CHN', 'CHN':'CHN', 'CHINA':'CHN', 'FR':'FRA', 'FRANCE':'FRA', 'DE':'DEU', 'GERMANY':'DEU', 'CA':'CAN', 'CANADA':'CAN', 'AU':'AUS', 'AUSTRALIA':'AUS'}
FIELDS = 'GEOM SSP MARKET VIOOH_ID ASSETUUID VISUAL_UNIT_CODE ADDRESS_THOROUGHFARE ADDRESS_ADMINISTRATIVE_AREA ADDRESS_LOCALITY ADDRESS_POSTAL_CODE ADDRESS_COUNTRY ADDRESS_ISO3_COUNTRY_CODE LATITUDE LONGITUDE PRODUCT_FORMAT_NAME DIGITAL_SPEC_WIDTH DIGITAL_SPEC_HEIGHT WIDTHXHEIGHT ASPECT_RATIO DIGITAL_SPEC_MOTION_TYPE DIGITAL_SPEC_FPS DIGITAL_SPEC_ROTATION SLOT_DURATION VENUE_TAXONOMY_ID VENUE_TAXONOMY_VALUE FRAMEIMAGEPATH IMPRESSIONS FLOORCPM MEDIAOWNERCURRENCY VIOOHSELECTOPTIN CLOSEST_POI CLOEST_POI DISTANCE_TO_CLOSEST_POI IATA SCORE_P'.split()
SEMANTICS = {re.sub('[^A-Z0-9]', '', k): k for k in FIELDS}
SEMANTICS.update(ALIASES)
SEMANTICS['VENUETYPE'] = 'VENUE_TAXONOMY_VALUE'
PROPOSAL_HEADERS = ['Date','Country','POI','Venue type','Floor price 2026 CPM','VIOOHSELECTCPMLOCAL','Floor price 2026 CPM (VS)','MEDIAOWNERCURRENCY','Floor price 2026 CPM (USD)','VIOOHSELECTOPTIN','MARKET','Screen no.','Monthly impressions','Campaign days','Suggested screen no','Suggested SOT','Impression deliverable','Media Budget (USD)','DSP fee','Total investment']
PICS_HEADERS = ['Market','Country','VenueType','PickedImageCount','Image1','Image2','Image3']


def missing(v):
    return v is None or str(v).strip().lower() in ('', '\\n', 'null', 'none', 'n/a', 'nan')


def numeric(v):
    if missing(v) or isinstance(v, bool): return None
    try:
        n = float(str(v).replace(',', ''))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError): return None


def country(v):
    v = str(v or '').strip().upper()
    return COUNTRIES.get(v, v)


def ingest(data, filename):
    sheets = read_workbook(data)
    source = next((k for k in sheets if re.sub('[^a-z]', '', k.lower()) == 'unfilteredframes'), None)
    if not source:
        raise ValueError('工作簿必须包含 UnfilteredFrames 原始库存表')
    try: headers, records = headers_and_records(sheets[source], 'VIOOHID')
    except ValueError: headers, records = headers_and_records(sheets[source], 'SCREENID')
    frames = []
    for index, original in enumerate(records, 2):
        canonical = {}
        conflicts = []
        for k, v in original.items():
            key = SEMANTICS.get(re.sub('[^A-Z0-9]', '', k.upper()), k)
            if key in canonical and canonical[key] != v: conflicts.append(f'字段语义重复冲突：{key}')
            canonical[key] = v
        if missing(canonical.get('CLOSEST_POI')):
            canonical['CLOSEST_POI'] = canonical.get('CLOEST_POI')
        elif not missing(canonical.get('CLOEST_POI')) and canonical.get('CLOEST_POI') != canonical['CLOSEST_POI']:
            conflicts.append('CLOSEST_POI 与 CLOEST_POI 不一致，使用 CLOSEST_POI')
        raw_id = canonical.get('VIOOH_ID')
        sid = '' if missing(raw_id) else str(raw_id).strip()
        frames.append(dict(key=f'row-{index}', screen_id=sid, original=original, fields=canonical, import_warnings=conflicts))
    return dict(filename=filename, headers=headers, frames=frames, source_sheets=sheets, analyses={}, photos={}, documents=[])


def clean(project, options):
    ids = Counter(f['screen_id'] for f in project['frames'] if f['screen_id'])
    selected = options.get('filters', {})
    if not isinstance(selected, dict): raise ValueError('filters 必须为对象')
    bounds = selected.get('bounds')
    if bounds is not None:
        if not isinstance(bounds, list) or len(bounds) != 4: raise ValueError('bounds 需要 [最小纬度,最小经度,最大纬度,最大经度]')
        bounds = [number(v, '区域边界', -90 if i % 2 == 0 else -180, 90 if i % 2 == 0 else 180) for i,v in enumerate(bounds)]
        if bounds[0] > bounds[2] or bounds[1] > bounds[3]: raise ValueError('区域边界顺序错误')
    excluded = options.get('exclude_ids', [])
    if not isinstance(excluded, list): raise ValueError('exclude_ids 必须为数组')
    output = []
    for frame in project['frames']:
        f = frame['fields']; reasons=[]; warnings=list(frame['import_warnings'])
        if not frame['screen_id']: reasons.append('缺少唯一屏幕 ID')
        elif ids[frame['screen_id']] > 1: reasons.append('重复屏幕 ID，所有重复行暂不参与投放')
        if frame['screen_id'] in excluded: reasons.append('用户排除 / 不可用替代资源')
        sale = str(f.get('VIOOHSELECTOPTIN', '')).strip().lower()
        if sale not in ('yes','true','1','1.0','y','是'): reasons.append('未确认可售（VIOOHSELECTOPTIN）')
        lat, lon = numeric(f.get('LATITUDE')), numeric(f.get('LONGITUDE'))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180): reasons.append('经纬度缺失或越界')
        elif bounds and not (bounds[0] <= lat <= bounds[2] and bounds[1] <= lon <= bounds[3]): reasons.append('坐标不在目标区域边界')
        geom = re.fullmatch(r'\s*POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)\s*', str(f.get('GEOM','')), re.I)
        if geom and lat is not None and lon is not None:
            glon, glat = numeric(geom[1]), numeric(geom[2])
            if glon is not None and glat is not None and (abs(glon-lon) > .01 or abs(glat-lat) > .01): reasons.append('GEOM 与经纬度冲突')
        region = country(f.get('ADDRESS_COUNTRY'))
        iso = country(f.get('ADDRESS_ISO3_COUNTRY_CODE'))
        if not region and not iso: reasons.append('国家缺失')
        if region and iso and region != iso: warnings.append('国家名称与 ISO 代码未能一致映射，请复核')
        for key, field in [('country','ADDRESS_COUNTRY'),('city','ADDRESS_LOCALITY'),('market','MARKET'),('venue','VENUE_TAXONOMY_VALUE'),('poi','CLOSEST_POI')]:
            wanted = str(selected.get(key) or '').strip()
            if wanted and (country(wanted) not in (region,iso) if key == 'country' else wanted.casefold() not in str(f.get(field) or '').casefold()): reasons.append(f'不符合区域/场所筛选：{key}')
        imp, cpm = numeric(f.get('IMPRESSIONS')), numeric(f.get('FLOORCPM'))
        if imp is None or imp <= 0: reasons.append('曝光缺失或非正数')
        if cpm is None or cpm <= 0: reasons.append('CPM 缺失或非正数')
        currency = str(f.get('MEDIAOWNERCURRENCY') or '').strip().upper()
        if not re.fullmatch('[A-Z]{3}', currency): reasons.append('媒体币种无效')
        image = project.get('photos', {}).get(frame['screen_id'])
        path = str(f.get('FRAMEIMAGEPATH') or '')
        if not image and (missing(path) or 'placehold' in path.lower() or 'unavailable' in path.lower()): warnings.append('无有效现场照片，可见性仅为未知先验')
        elif not image: warnings.append('图片路径尚未取得或分析，不代表已验证现场')
        for key in ('VENUE_TAXONOMY_VALUE','CLOSEST_POI','SLOT_DURATION'):
            if missing(f.get(key)): warnings.append(f'缺失 {key}')
        if numeric(f.get('DISTANCE_TO_CLOSEST_POI')) is not None and numeric(f['DISTANCE_TO_CLOSEST_POI']) < 0: warnings.append('POI 距离为负数，不用于评分')
        if not bounds: warnings.append('尚未用地理边界验证国家/城市与坐标的一致性')
        output.append({**frame, 'eligible':not reasons, 'reasons':reasons, 'warnings':warnings, 'impressions':imp, 'cpm':cpm, 'currency':currency, 'lat':lat, 'lon':lon})
    return output


def weights(value):
    if not isinstance(value, dict) or set(value) != set(DIMENSIONS): raise ValueError('权重必须包含六个评分维度')
    out = {k:number(value[k], k, 0, 100) for k in DIMENSIONS}
    total=sum(out.values())
    if total <= 0: raise ValueError('权重总和必须大于零')
    return {k:v/total for k,v in out.items()}


def financial_options(options):
    if not isinstance(options, dict): raise ValueError('规划配置必须为对象')
    budget = number(options.get('budget'), '总预算', .01, 1e12)
    currency = str(options.get('currency','')).upper().strip()
    if not re.fullmatch('[A-Z]{3}',currency): raise ValueError('请输入三位预算币种')
    rate_input = options.get('fx', {})
    if not isinstance(rate_input, dict): raise ValueError('fx 必须为币种到 USD 汇率对象')
    rates = {str(k).upper():number(v,'汇率',.00000001,1e9) for k,v in rate_input.items()}
    if 'USD' in rates and rates['USD'] != 1: raise ValueError('USD 汇率必须为 1')
    rates['USD']=1.0
    if currency not in rates: raise ValueError(f'缺少 {currency} 到 USD 汇率')
    if any(k != 'USD' for k in rates):
        if not options.get('fx_source') or not options.get('fx_date'): raise ValueError('非 USD 汇率需要来源和日期')
        try: date.fromisoformat(options['fx_date'])
        except (ValueError,TypeError): raise ValueError('汇率日期必须为 YYYY-MM-DD') from None
    days = options.get('days')
    if days not in (None,''):
        days=number(days,'投放天数',1,366)
        if not days.is_integer(): raise ValueError('投放天数必须为整数')
        days=int(days)
    else: days=None
    start=options.get('start_date')
    if start:
        try: date.fromisoformat(start)
        except (ValueError, TypeError): raise ValueError('开始日期必须为 YYYY-MM-DD') from None
    step=number(options.get('sot_step',.1),'SOT 步长',.01,1)
    maximum=number(options.get('max_sot',1),'最大 SOT',step,1)
    period=number(options.get('impression_period_days',30),'原始曝光统计周期（天）',1,366)
    planning_days=days or number(options.get('planning_days',30),'预算估算天数',1,366)
    return dict(budget=budget,currency=currency,rates=rates,days=days,start_date=start,planning_days=planning_days,period=period,fee=number(options.get('dsp_fee',0),'DSP 费率',0,1),markup=number(options.get('cpm_markup',0),'CPM 加价率',0,5),step=step,max_sot=maximum,budget_only=not(days and start),fx_source=options.get('fx_source','USD 同币种'),fx_date=options.get('fx_date'))


def score(project, options, finance):
    frames=clean(project, options)
    for f in frames:
        if f['currency'] not in finance['rates']:
            f['eligible']=False; f['reasons'].append(f"缺少 {f['currency']} 到 USD 汇率，禁止混币计算")
        f['cpm_budget'] = (f['cpm'] * finance['rates'][f['currency']] / finance['rates'][finance['currency']] * (1+finance['markup'])) if f['cpm'] and f['currency'] in finance['rates'] else None
    pool=[f for f in frames if f['eligible']]
    max_imp=max((f['impressions'] for f in pool),default=1)
    min_cpm=min((f['cpm_budget'] for f in pool),default=1)
    w=weights(options.get('weights',WEIGHTS))
    for f in frames:
        fields=f['fields']; analysis=project.get('analyses',{}).get(f['screen_id'],{})
        dist=numeric(fields.get('DISTANCE_TO_CLOSEST_POI'))
        dimensions={
            'exposure':min(100,100*math.log1p(max(0,f['impressions'] or 0))/math.log1p(max_imp)),
            'visibility':50., 'location':100/(1+dist/1000) if dist is not None and dist>=0 else 50.,
            'market':50., 'cost':min(100,100*min_cpm/f['cpm_budget']) if f['cpm_budget'] else 0.,
            'availability':100. if f['eligible'] else 0.,
        }
        evidence={
            'exposure':{'type':'derived','source':'Excel IMPRESSIONS','reason':'100 × log(1+曝光) / log(1+候选池最大曝光)，原始曝光不是去重人数'},
            'visibility':{'type':'assumption','source':'unknown prior','reason':'缺少有效图像分析，使用中性先验 50，不代表实际可见性'},
            'location':{'type':'derived' if dist is not None and dist>=0 else 'assumption','source':'Excel DISTANCE_TO_CLOSEST_POI','reason':'100 / (1 + POI距离米/1000)，距离单位假设为米'},
            'market':{'type':'assumption','source':'unknown prior','reason':'尚无地区资料支持，使用中性先验 50'},
            'cost':{'type':'derived','source':'FLOORCPM + 用户汇率/加价','reason':'100 × 候选池最低统一币种 CPM / 本屏幕统一币种 CPM'},
            'availability':{'type':'derived','source':'库存清洗','reason':'; '.join(f['reasons']) or '通过当前可售与数据完整性校验'},
        }
        for k in ('visibility','location','market'):
            item=analysis.get('scores',{}).get(k)
            if k in analysis.get('unknown_scores',{}):
                evidence[k]['reason']='模型未评分：'+analysis['unknown_scores'][k]+'；保留中性先验/库存推导分，非模型实测。'
            if item:
                dimensions[k]=item['score']; evidence[k]={'type':'inference','source':item.get('source_ids',analysis.get('sources',[])),'reason':item['reason']}
        f.update(scores={k:round(v,4) for k,v in dimensions.items()}, total_score=round(sum(dimensions[k]*w[k] for k in DIMENSIONS),4), evidence=evidence, analysis=analysis, score_p_reference=fields.get('SCORE_P'))
    return frames,w


def allocate(frames, finance, w, strategy, penalty, exclude=()):
    """Greedy marginal utility per cost on a discrete SOT grid; not a global optimum.

    A heap lazily re-evaluates declining regional utility. Cost is rounded UP per
    increment to cents, avoiding cumulative floating-point budget overruns.
    """
    D=lambda x:Decimal(str(x))
    budget_cents=int((D(finance['budget'])*100).to_integral_value(rounding=ROUND_FLOOR))
    units=int((D(finance['max_sot'])/D(finance['step'])).to_integral_value(rounding=ROUND_FLOOR))
    candidates={}; heap=[]; counts=Counter(); chosen=Counter(); spent=0
    for f in frames:
        if not f['eligible'] or f['screen_id'] in exclude: continue
        sid=f['screen_id']; fields=f['fields']
        # Approximate 0.01-degree cells; geographical overlap is a penalty, not reach deduplication.
        cluster=(country(fields.get('ADDRESS_COUNTRY')), math.floor(f['lat']/.01), math.floor(f['lon']/.01))
        impressions=D(f['impressions'])*D(finance['planning_days'])/D(finance['period'])*D(finance['step'])
        cpm=D(f['cpm'])*D(finance['rates'][f['currency']])/D(finance['rates'][finance['currency']])*(1+D(finance['markup']))
        media=impressions/1000*cpm
        fee=media*D(finance['fee'])
        cost=int(((media+fee)*100).to_integral_value(rounding=ROUND_CEILING))
        cost=max(cost,1)
        utility=sum(f['scores'][k]*w[k] for k in DIMENSIONS)
        candidates[sid]=dict(frame=f,cluster=cluster,cost=cost,media=media,fee=fee,impressions=impressions,utility=utility)
        heapq.heappush(heap,(-utility/cost,sid,0))
    while heap:
        _,sid,version=heapq.heappop(heap); c=candidates[sid]; cluster=c['cluster']
        if chosen[sid]>=units or spent+c['cost']>budget_cents: continue
        if version!=counts[cluster]:
            priority=c['utility']/c['cost']/(1+penalty*counts[cluster])
            # Coverage rewards a first screen in each cluster, then diminishes additions.
            heapq.heappush(heap,(-priority,sid,counts[cluster])); continue
        chosen[sid]+=1; counts[cluster]+=1; spent+=c['cost']
        priority=c['utility']/c['cost']/(1+penalty*counts[cluster])
        heapq.heappush(heap,(-priority,sid,counts[cluster]))
    items=[]
    for sid,n in chosen.items():
        c=candidates[sid]; f=c['frame']
        media=c['media']*n; fee=c['fee']*n; total=Decimal(c['cost']*n)/100
        items.append(dict(screen_id=sid,key=f['key'],sot=float(D(finance['step'])*n),impressions=float(c['impressions']*n),media_budget=float(media),dsp_cost=float(fee),rounding_reserve=float(total-media-fee),total=float(total),score=round(c['utility'],4),reason=f'{strategy}：按分项加权收益/成本逐步分配 SOT；同区域递减惩罚 {penalty}',cluster=list(c['cluster'])))
    return dict(strategy=strategy,items=items,screen_count=len(items),region_cells=len({tuple(x['cluster']) for x in items}),total=spent/100,remaining=(budget_cents-spent)/100,impressions=sum(x['impressions'] for x in items),weights=w,excluded_ids=list(exclude),budget_only=finance['budget_only'],risks=[] if items else ['预算不足以购买一个 SOT 步长，或没有通过筛选且有汇率的屏幕'])


def plan(project, options):
    finance=financial_options(options)
    frames,w=score(project,options,finance)
    penalty=number(options.get('overlap_penalty',.5),'区域重复惩罚',0,10)
    plans=[]
    for strategy,preset in PRESETS.items():
        current=w if strategy=='balanced' else weights(preset)
        plans.append(allocate(frames,finance,current,strategy,max(penalty,2) if strategy=='coverage' else penalty))
    custom=options.get('custom_weights')
    if custom is not None: plans.append(allocate(frames,finance,weights(custom),'custom',penalty))
    balanced=next(p for p in plans if p['strategy']=='balanced')
    unavailable=options.get('alternative_exclude_ids')
    if unavailable is None:
        top=max(balanced['items'],key=lambda x:x['total'],default=None)
        unavailable=[top['screen_id']] if top else []
    if not isinstance(unavailable,list): raise ValueError('替代屏幕排除 ID 必须为数组')
    plans.append(allocate(frames,finance,w,'alternative',penalty,unavailable))
    risks=['这是基于输入库存与情景推断的规划，不是实测广告效果或购买预测。','IMPRESSIONS 线性按天数及 SOT 缩放，需确认库存统计周期与可售 SOT；不代表去重触达。','区域重复按约 0.01 度网格惩罚，不是真实人群交集模型。','离散 SOT 贪心方案可复算，但不保证全局最优；未计入未提供的税费或最低起订金额。','图片中的人物不被识别；群体为可能经过的代表性情景，绝不据图估计客流。']
    if finance['budget_only']: risks.append('缺少开始日期或投放天数：仅输出预算级建议，估算曝光不是交付承诺。')
    if not project.get('documents'): risks.append('未提供区域社会学资料或消费者调研，市场相关性采用未知先验。')
    if not project.get('analyses'): risks.append('尚未运行多模态分析，屏幕可见性采用未知先验。')
    return dict(frames=frames,weights=w,finance=finance,plans=plans,risks=risks,options=options,summary=dict(total=len(frames),eligible=sum(f['eligible'] for f in frames),rejected=sum(not f['eligible'] for f in frames)),formulas=dict(exposure='IMPRESSIONS × 规划天数 / 原始曝光周期天数 × SOT',cpm='FLOORCPM × (1 + CPM加价率) × USD每原币 / USD每预算币',media='估算曝光 / 1000 × 预算币种CPM',dsp='媒体预算 × DSP费率',total='每个 SOT 步长的 (媒体预算 + DSP费用) 向上取整到分，再求和',score='Σ(分项分数 × 归一化权重)'))


def export_plan(project, result, strategy, project_dir=None):
    selected=next((p for p in result['plans'] if p['strategy']==strategy),None)
    if selected is None: raise ValueError('找不到所选方案')
    f=result['finance']; item_map={i['key']:i for i in selected['items']}
    extra=['Planning key','Candidate','Selected','Total score','Exposure','Visibility','Location','Market','Cost','Availability','Reasons','Risks','Evidence','Screen Context']
    rows=[]; score_rows=[]
    for frame in result['frames']:
        row=[frame['original'].get(k) for k in project['headers']]
        row += [frame['key'],frame['eligible'],frame['key'] in item_map,round(sum(frame['scores'][k]*selected['weights'][k] for k in DIMENSIONS),4)]+[frame['scores'][k] for k in DIMENSIONS]+['; '.join(frame['reasons']),'; '.join(frame['warnings']),json.dumps(frame['evidence'],ensure_ascii=False),json.dumps(frame['analysis'],ensure_ascii=False)]
        rows.append(row)
        for k in DIMENSIONS:
            score_rows.append([frame['screen_id'],k,frame['scores'][k],selected['weights'][k],frame['evidence'][k]['type'],json.dumps(frame['evidence'][k]['source'],ensure_ascii=False),frame['evidence'][k]['reason'],frame['score_p_reference']])
    source=project['source_sheets']
    proposal_headers=list(source.get('Proposal',[PROPOSAL_HEADERS])[0])
    if not all(k in proposal_headers for k in PROPOSAL_HEADERS): proposal_headers=PROPOSAL_HEADERS[:]
    additional=['Screen ID','Strategy','Budget currency','Media Budget (budget currency)','DSP cost (budget currency)','Total investment (USD)','Rounding reserve','Planning days','Impression period days','CPM markup','FX USD per media currency','FX USD per budget currency','CPM (budget currency)','Estimated impressions','Budget only','Recommendation','FX source','FX date']
    proposal_headers += [k for k in additional if k not in proposal_headers]
    proposal_rows=[]
    for frame in result['frames']:
        item=item_map.get(frame['key'])
        if not item: continue
        fields=frame['fields']; rate=f['rates'][frame['currency']]; budget_rate=f['rates'][f['currency']]
        values={'Date':f['start_date'],'Country':fields.get('ADDRESS_COUNTRY'),'POI':fields.get('CLOSEST_POI'),'Venue type':fields.get('VENUE_TAXONOMY_VALUE'),'Floor price 2026 CPM':frame['cpm'],'VIOOHSELECTCPMLOCAL':frame['cpm'],'Floor price 2026 CPM (VS)':frame['cpm']*(1+f['markup']),'MEDIAOWNERCURRENCY':frame['currency'],'Floor price 2026 CPM (USD)':frame['cpm']*(1+f['markup'])*rate,'VIOOHSELECTOPTIN':fields.get('VIOOHSELECTOPTIN'),'MARKET':fields.get('MARKET'),'Screen no.':1,'Monthly impressions':frame['impressions']*30/f['period'],'Campaign days':f['days'],'Suggested screen no':1,'Suggested SOT':item['sot'],'Impression deliverable':None if f['budget_only'] else item['impressions'],'Media Budget (USD)':item['media_budget']*budget_rate,'DSP fee':f['fee'],'Total investment':item['total'],'Screen ID':frame['screen_id'],'Strategy':strategy,'Budget currency':f['currency'],'Media Budget (budget currency)':item['media_budget'],'DSP cost (budget currency)':item['dsp_cost'],'Total investment (USD)':item['total']*budget_rate,'Rounding reserve':item['rounding_reserve'],'Planning days':f['planning_days'],'Impression period days':f['period'],'CPM markup':f['markup'],'FX USD per media currency':rate,'FX USD per budget currency':budget_rate,'CPM (budget currency)':frame['cpm_budget'],'Estimated impressions':item['impressions'],'Budget only':f['budget_only'],'Recommendation':item['reason'],'FX source':f['fx_source'],'FX date':f['fx_date']}
        ri=len(proposal_rows)+2
        cell=lambda key:f'{col_name(proposal_headers.index(key)+1)}{ri}'
        formulas={
            'Estimated impressions':f'{cell("Monthly impressions")}*{cell("Planning days")}/30*{cell("Suggested SOT")}',
            'CPM (budget currency)':f'{cell("Floor price 2026 CPM")}*(1+{cell("CPM markup")})*{cell("FX USD per media currency")}/{cell("FX USD per budget currency")}',
            'Media Budget (budget currency)':f'{cell("Estimated impressions")}/1000*{cell("CPM (budget currency)")}',
            'DSP cost (budget currency)':f'{cell("Media Budget (budget currency)")}*{cell("DSP fee")}',
            'Total investment':f'{cell("Media Budget (budget currency)")}+{cell("DSP cost (budget currency)")}+{cell("Rounding reserve")}',
            'Media Budget (USD)':f'{cell("Media Budget (budget currency)")}*{cell("FX USD per budget currency")}',
            'Total investment (USD)':f'{cell("Total investment")}*{cell("FX USD per budget currency")}',
        }
        for key,formula in formulas.items(): values[key]={'formula':formula,'value':values[key]}
        proposal_rows.append([values.get(k) for k in proposal_headers])
    pics={}
    for frame in result['frames']:
        if frame['key'] not in item_map: continue
        fields=frame['fields']; key=(str(fields.get('MARKET') or ''),str(fields.get('ADDRESS_COUNTRY') or ''),str(fields.get('VENUE_TAXONOMY_VALUE') or ''))
        photo=project.get('photos',{}).get(frame['screen_id']); path=photo.get('source') if photo else fields.get('FRAMEIMAGEPATH')
        pics.setdefault(key,[])
        if path and 'placehold' not in str(path).lower() and path not in pics[key]: pics[key].append(path)
    pic_rows=[list(k)+[min(len(v),3)]+v[:3]+[None]*max(0,3-len(v)) for k,v in pics.items()]
    audit=[['Source workbook',project['filename']],['Strategy',strategy],['Selected weights',json.dumps(selected['weights'])],['Budget',f['budget']],['Budget currency',f['currency']],['Total investment',selected['total']],['Remaining budget',selected['remaining']],['Options',json.dumps(result['options'],ensure_ascii=False)],['Sources',json.dumps(project.get('documents',[]),ensure_ascii=False)]]
    audit += [[k,v] for k,v in result['formulas'].items()]+[['Risk',r] for r in result['risks']]
    sheets=[('FilteredFrames',project['headers']+extra,rows),('Screen Scorecard',['Screen ID','Dimension','Score','Weight','Evidence type','Source','Reason','SCORE_P reference'],score_rows),('Proposal',proposal_headers,proposal_rows),('PICS',PICS_HEADERS,pic_rows),('Audit',['Item','Value'],audit)]
    if source.get('POI'): sheets.append(('POI',source['POI'][0],source['POI'][1:]))
    images=[]
    if project_dir is not None:
        for ri,(key,paths) in enumerate(pics.items(),2):
            for ci,source_path in enumerate(paths[:3],5):
                photo=next((photo for photo in project.get('photos',{}).values() if photo.get('source')==source_path and photo.get('file')),None)
                if photo:
                    images.append(dict(sheet='PICS',row=ri,column=ci,data=(project_dir/photo['file']).read_bytes(),mime=photo['mime']))
    return write_workbook(sheets,images)
