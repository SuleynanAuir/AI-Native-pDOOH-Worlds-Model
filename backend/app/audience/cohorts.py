"""Explicit synthetic population strata and integer representative weights.

Defaults are editable scenario assumptions, never inferred personal attributes or
country demographics. No relationship between economic position and attention is
hard-coded: these are separate, inspectable profile dimensions.
"""
import copy
import math
import random

PROFILE_FIELDS = ('life_stage','purchasing_power','economic_context','household','preferences','needs','price_sensitivity','mobility','attention_context')
COLORS = ['#58a6ff','#c49bff','#ffbc66','#53d6ac','#ef8bad','#8acb88','#7dbce0','#ddb875','#b9a1eb','#e58b70','#76c8bf','#b5c66c']
_RAW = [
 ('early_career','初入职场独居者',14,'初入职场','可支配预算偏紧','收入积累阶段','独居；主要自行承担生活支出','实用、便捷、优惠','通勤、餐饮、租住生活用品','较高','步行 / 公共交通','赶路时注意力有限，等待时可能观看'),
 ('professional','品质导向职场者',11,'职业稳定期','可支配预算较充足','稳定职业收入情景','单人或双人家庭；暂无抚养负担','品质、效率、售后','通勤工具、工作装备、休闲体验','中等','公共交通 / 步行','关注清晰的信息，是否观看还取决于当时任务'),
 ('young_couple','年轻双收入家庭',10,'共同生活初期','中等可支配预算','双收入、需平衡共同开支','两位成年人；无子女情景','性价比、家居体验、周末休闲','家居、餐饮、出游','中等','步行 / 公共交通','共同出行可能交流，个人观看机会不固定'),
 ('parents','育儿家庭采购者',12,'育儿阶段','预算需在多人需求间分配','有固定家庭支出','有未成年子女的成年照护者','安全、可靠、家庭适用','家庭食品、日用品、教育服务','较高','公共交通 / 步行','照护与出行任务可能分散注意力'),
 ('value_family','预算审慎家庭',10,'家庭支出集中期','可自由支配预算有限','强调收支平衡的经济情景','多人家庭；有日常抚养支出','耐用、优惠、必需品优先','食品、家用消耗品、交通服务','较高','步行 / 公共交通','有明确采购计划；不等于对所有广告感兴趣'),
 ('caregiver','多代家庭照护者',7,'家庭照护阶段','中等预算，较多固定支出','兼顾工作与照护开支','与长辈或其他受照护者共同生活','便利、可信、节省时间','家庭服务、生活采购、出行','中等','步行 / 公共交通','任务切换较多，停留机会依场景而定'),
 ('student','成年学生群体',8,'高等教育阶段（成年人）','日常预算偏紧','奖助、兼职或家庭支持的情景假设','合住或学生住宿','价格、社交体验、便携性','餐饮、学习用品、娱乐','较高','步行 / 公共交通','同行交流或手机使用会影响观看'),
 ('flex_worker','灵活就业者',7,'灵活工作阶段','可支配预算随月份变化','收入波动情景','独居或与他人合住','实用、耐用、灵活付费','工作用品、餐饮、交通','较高','步行 / 骑行换乘','工作任务与休息时段的注意力不同'),
 ('retired','退休生活群体',6,'退休阶段','固定收入下的计划预算','退休收入情景；非实际收入判定','独居或与伴侣生活','易理解、可靠、生活便利','日用品、休闲活动、社区服务','中等','步行 / 公共交通','部分行程有较多停留时间，不能据年龄推断观看能力'),
 ('experience','体验导向消费者',6,'自主生活阶段','较充足的休闲预算','可自由支配支出较高的情景','独居或双人家庭','体验、设计、服务品质','餐饮、文化活动、旅行','较低','步行 / 公共交通','对场景环境好奇，但不保证停留或消费'),
 ('visitor','异地来访者',5,'短期到访情景','本次行程有独立预算','旅行预算不代表长期经济阶层','独自、伴侣或家庭出游的成年人','地点相关信息、便利、体验','路线、餐饮、住宿、当地活动','中等','步行 / 公共交通','在寻路时可能关注信息，也可能忽略商业屏幕'),
 ('neighborhood','社区日常生活者',4,'日常社区生活','日常消费预算中等','稳定生活开支情景','家庭成员构成待用户校正','熟悉、便利、稳定品质','社区零售、家庭服务、日用品','中等','步行','熟悉路线可能减少新奇感；并不决定其反应'),
]
_SHARES=[13,10,9,11,9,6,7,6,5,5,5,4]
DEFAULT_SEGMENTS = [dict(id=r[0],name=r[1],share=_SHARES[i],color=COLORS[i],profile=dict(zip(PROFILE_FIELDS,r[3:])),source='内置合成情景假设，非当地调研结论') for i,r in enumerate(_RAW)]


def validate_segments(segments):
    if not isinstance(segments,list) or not 1<=len(segments)<=40:
        raise ValueError('请提供 1–40 类代表性人群')
    output=[];ids=set()
    for i,s in enumerate(segments):
        if not isinstance(s,dict):raise ValueError('人群配置必须为对象')
        sid=s.get('id');name=s.get('name')
        if not isinstance(sid,str) or not sid.strip() or len(sid)>80 or sid in ids:raise ValueError('人群 ID 必须唯一且非空，最多 80 字符')
        ids.add(sid)
        if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('人群名称必须为 1–100 字符')
        share=s.get('share')
        if isinstance(share,bool) or not isinstance(share,(int,float)) or not math.isfinite(share) or not 0<=share<=1000000:raise ValueError('人群占比必须是非负有限数字')
        profile=s.get('profile')
        if not isinstance(profile,dict) or any(not isinstance(profile.get(k),str) or not profile[k].strip() or len(profile[k])>1000 for k in PROFILE_FIELDS):raise ValueError('每类人群需要完整的生活阶段、消费能力、经济背景、家庭、偏好、需求、价格敏感度、移动和注意力描述')
        source=s.get('source','用户设定的情景假设')
        if not isinstance(source,str) or not source.strip() or len(source)>1000:raise ValueError('请填写有效的人群资料来源或假设说明')
        item=dict(id=sid,name=name,share=share,color=COLORS[i%len(COLORS)],profile={k:profile[k].strip() for k in PROFILE_FIELDS},source=source)
        if 'local_context' in s:
            from .locality import local_segment_fields
            item.update(local_segment_fields(s))
        output.append(item)
    if sum(s['share'] for s in output)<=0:raise ValueError('人群占比总和必须大于零')
    return output


def apportioned(total,weights):
    """Largest remainder allocation, stable ties; the output sums to total."""
    from decimal import Decimal
    w=[Decimal(str(v)) for v in weights];denominator=sum(w)
    quotas=[Decimal(total)*v/denominator for v in w]
    result=[int(v) for v in quotas]
    for i in sorted(range(len(w)),key=lambda i: (-(quotas[i]-result[i]),i))[:total-sum(result)]: result[i]+=1
    return result


def representatives(agent_count,total_population,seed=42,segments=None):
    if isinstance(agent_count,bool) or not isinstance(agent_count,int) or not 4<=agent_count<=200:raise ValueError('代表性 Agent 数必须为 4–200 的整数')
    if isinstance(total_population,bool) or not isinstance(total_population,int) or not agent_count<=total_population<=1000000:raise ValueError('总人群必须为不小于 Agent 数且不超过 100 万的整数')
    groups=validate_segments(copy.deepcopy(DEFAULT_SEGMENTS) if segments is None else segments)
    pops=apportioned(total_population,[g['share'] for g in groups]);active=[i for i,p in enumerate(pops) if p>0]
    if len(active)>agent_count:raise ValueError('代表性 Agent 数不能少于非空人群类别数')
    counts=[int(p>0) for p in pops]
    for _ in range(agent_count-sum(counts)):
        i=max((i for i in active if counts[i]<pops[i]),key=lambda i:(agent_count*pops[i]/total_population-counts[i],-i))
        counts[i]+=1
    rng=random.Random(seed);agents=[]
    for index,g in enumerate(groups):
        g.update(population=pops[index],agent_count=counts[index],population_share=pops[index]/total_population)
        for variant,weight in enumerate(apportioned(pops[index],[1]*counts[index]) if counts[index] else []):
            profile=copy.deepcopy(g['profile'])
            profile.update(time_pressure=['时间较紧','时间适中','时间较宽裕'][variant%3],attention_habit=['主要观察周边','容易被手机分散注意力','正在与同行者交流','专注于出行任务'][(variant//3)%4],purchase_planning=['有明确采购清单','先收集信息再决定','此次出行没有购买计划'][(variant//12)%3])
            profile['decision_style']=['快速筛选关键信息','先确认用途与可信度','倾向比较不同方案'][(variant//36)%3]
            profile['purchase_channel']=['线上比较后决定','偏好到店了解','渠道随需求而定'][(variant//108)%3]
            profile['current_need']=profile['needs'].split('、')[variant%len(profile['needs'].split('、'))]
            persona='；'.join(f'{k}：{v}' for k,v in profile.items())+'。以上为合成人群画像，不是真实个人；不依据经济条件直接决定观看反应。'
            if g.get('local_context'):
                persona+='区域场所画像（推演）：'+'；'.join(f'{k}：{v}' for k,v in g['local_context'].items())
            aid=len(agents)
            agents.append(dict(id=aid,name=f'{g["name"]} {variant+1:02d}',group=g['id'],color=g['color'],persona=persona,audience_profile=profile,profile_source=g['source'],represented_population=weight,weight=weight/total_population,x=80+rng.random()*840,y=130+rng.random()*350,reaction='passing',reason='尚未开始场景推演',screen_id=None,dwell_seconds=0))
            if g.get('local_context'):
                agents[-1].update({k:copy.deepcopy(g[k]) for k in ('local_context','source_ids','local_rationale','activity_factors','share_basis')})
    return agents,groups


def summarize(agents,observed=True):
    """Weighted scenario estimates; not independent individual observations."""
    reactions=('passing','glance','watch','interest','unknown','away','unexposed')
    total=sum(a.get('represented_population',1) for a in agents)
    counts={r:0 for r in reactions};agent_counts={r:0 for r in reactions};groups={};screens={}
    seconds=0.
    for a in agents:
        weight=a.get('represented_population',1);reaction=a.get('reaction','unknown') if observed else 'unknown'
        if reaction not in counts:reaction='unknown'
        counts[reaction]+=weight;agent_counts[reaction]+=1
        group=groups.setdefault(a['group'],dict(population=0,agents=0,weighted_counts={r:0 for r in reactions}))
        group['population']+=weight;group['agents']+=1;group['weighted_counts'][reaction]+=weight
        if observed and reaction not in ('unknown','away','unexposed'): seconds+=(a.get('dwell_seconds') or 0)*weight
        if observed and a.get('screen_id'):
            target=screens.setdefault(a['screen_id'],dict(population=0,weighted_counts={r:0 for r in reactions}))
            target['population']+=weight;target['weighted_counts'][reaction]+=weight
    noticed=sum(counts[r] for r in ('glance','watch','interest'))
    return dict(total_population=total,active_population=total-counts['away'] if observed else None,agent_count=len(agents),weighted_counts=counts,agent_counts=agent_counts,noticed_population=noticed,notice_rate=noticed/total if total else 0,weighted_dwell_person_seconds=round(seconds,2),weighted_mean_dwell_seconds=round(seconds/(total-counts['unknown']-counts['away']-counts['unexposed']),2) if total>counts['unknown']+counts['away']+counts['unexposed'] else None,groups=groups,screens=screens,method='sum(represented_population × representative outcome); scenario expansion, not measured reach')
