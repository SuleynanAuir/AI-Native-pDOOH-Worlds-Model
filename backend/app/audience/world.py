"""Scene adapter around real OASIS INTERVIEW decisions (not an OASIS physics engine)."""
import json
import math
import random
from pathlib import Path

from .cohorts import representatives, summarize
from .day_cycle import validate_day_cycle, schedule, attendance

SCREEN_POSITIONS=[(190,440),(550,280),(730,280)]


def scene(population=100, rounds=4, seed=42, screens=None, total_population=10000, segments=None, day_cycle=None, locality=None, audience_template=None,mobility=None,traffic_options=None,geographic_context=None):
    rng=random.Random(seed)
    default=[dict(id='SCENE-01',name='通勤站点',venue='交通候车区',visibility=.85,obstruction=.1),dict(id='SCENE-02',name='商业街角',venue='零售步行街',visibility=.65,obstruction=.3),dict(id='SCENE-03',name='城市广场',venue='休闲公共空间',visibility=.9,obstruction=.05)]
    if locality is not None:
        from .locality import validate_locality,venue_screens
        locality=validate_locality(locality)
        default=venue_screens(locality)
    screens=screens or default
    screens=[{**s,'x':SCREEN_POSITIONS[i][0],'y':SCREEN_POSITIONS[i][1]} for i,s in enumerate(screens[:3])]
    agents,groups=representatives(population,total_population,seed,segments)
    result = dict(schema_version=2,screens=screens,agents=agents,groups=groups,rounds=rounds,seed=seed,total_population=total_population,agent_count=population,scene_label='城市商业街 · 加权人群情景',spatial_source='场景适配层提供示意位置，不是真实人流轨迹',decision_source='OASIS SocialAgent + INTERVIEW + DeepSeek',is_synthetic=True,population_method='整数最大余数分配；代表 Agent 权重和等于设定总人群',population_caveat='一个代表性 Agent 的反应按人数权重外推，不表示其代表的人真实做出了相同行为，也不是独立样本或实测客流。')


    if day_cycle is not None:
        cycle = validate_day_cycle(day_cycle)
        slots = schedule(cycle)
        for slot in slots:
            present = [a for a in agents if attendance(a, slot, seed)['present']]
            slot.update(present_agent_ids=[a['id'] for a in present], scheduled_population=sum(a['represented_population'] for a in present), scheduled_agents=len(present))
        result.update(schema_version=3, day_cycle=cycle, schedule=slots, rounds=len(slots), scene_label='城市商业街 · 24 小时时间场景')
    if locality is not None:
        result.update(schema_version=4,locality=locality,audience_template=audience_template,scene_label=f'{locality["country"]} · {locality["city"]} · {locality["community"]}')
    from .mobility import validate_mobility, neighborhood, journey
    from .traffic import validate_traffic
    traffic_options=validate_traffic(traffic_options)
    options=validate_mobility(mobility);network=neighborhood(locality)
    if geographic_context is not None:
        from .geographic_scene import geographic_network
        network,screens=geographic_network(geographic_context)
        result.update(geographic_context=geographic_context,screens=screens,scene_label=geographic_context['locality']['city']+' · '+geographic_context['locality']['community']+' · GEOM 定位')
    movement=[]
    for index in range(result['rounds']):
        slot=result.get('schedule',[dict(round=i+1,period='daytime') for i in range(result['rounds'])])[index]
        present=slot.get('present_agent_ids',[a['id'] for a in agents])
        movement.append({str(a['id']):journey(a,slot,seed,network,options,screens) for a in agents if a['id'] in present})
    result.update(schema_version=5,traffic_options=traffic_options,mobility=options,neighborhood=network,mobility_rounds=movement,
                  spatial_source=network['source'])
    return result


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path,value):
    path=Path(path);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8');temp.replace(path)


def parse_decision(raw):
    if not isinstance(raw,str): raise ValueError('Agent 未返回文本决策')
    raw=raw.strip()
    if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
    value=json.loads(raw)
    if not isinstance(value,dict) or value.get('reaction') not in ('passing','glance','watch','interest'): raise ValueError('Agent 行为不符合协议')
    reason=value.get('reason')
    if not isinstance(reason,str) or not reason.strip(): raise ValueError('Agent 缺少行为解释')
    duration=float(value.get('dwell_seconds',0))
    if not math.isfinite(duration) or not 0<=duration<=30: raise ValueError('停留时间无效')
    if value['reaction']=='passing':duration=0
    return dict(reaction=value['reaction'],reason=reason[:600],dwell_seconds=duration)


def encounter_position(screen,agent_id,round_num):
    angle=(agent_id*2.399+round_num*.4)%(2*math.pi)
    return dict(x=round(screen['x']+math.cos(angle)*(50+(agent_id%7)*12),2),y=round(screen['y']+math.sin(angle)*(40+(agent_id%7)*10),2))


def encounter_conditions(profile,screen,round_num,seed,slot=None):
    """Seeded hypothetical encounters; never sampled real traffic or reactions.

    Route/orientation are independent of income and cohort weights. The LLM still
    decides the reaction. Constraints and their source travel with the replay.
    """
    rng=random.Random(f'{seed}:{profile["id"]}:{round_num}:{screen["id"]}')
    route=rng.choice(['正面经过','侧面经过','背向屏幕经过','在屏幕附近等候'])
    blocked=rng.random()<max(0,min(1,screen.get('obstruction') or 0))
    sight=route!='背向屏幕经过' and not blocked
    p=profile.get('audience_profile',{})
    pressure=p.get('time_pressure','时间适中')
    window=rng.choice([1,2,3] if pressure=='时间较紧' else [3,5,8] if pressure=='时间适中' else [10,20,30])
    task=('等候间隙观察周边' if route=='在屏幕附近等候' else p.get('attention_habit','观察周边'))
    if profile.get('local_context'):
        task=profile['local_context']['visit_purpose']+'；'+p.get('attention_habit','注意周边')
        if slot:task+='；'+slot['period_label']
        if slot and slot['holiday_active']:task+='；节日情景：'+slot['holiday_name']+'，不预设此人参与'
    elif slot:
        if slot['period'] in ('morning','evening'):
            window=min(window, 5);task=slot['period_label']+'：通勤或生活事务途中'
        elif slot['period']=='night':
            window=max(window, 8);task='晚间餐饮、休闲或采购途中'
        if slot['holiday_active']:task+='；'+slot['holiday_name']+'活动情景（是否参与由人设决定）'
    return dict(route=route,line_of_sight=sight,temporary_occlusion=blocked,
                available_seconds=window if sight else 0,current_task=task,
                source='由场景种子抽样的合成相遇条件；非照片测量、客流统计或实际行为',
                assumptions='四种路线等概率；临时遮挡按屏幕情景遮挡率抽样；可观看时间由时间压力情景给定；不按收入设定反应')


def validate_encounter_decision(decision,conditions):
    """Invalid physical claims remain unknown; do not silently rewrite decisions."""
    if not conditions['line_of_sight'] and decision['reaction']!='passing':
        raise ValueError('无视线条件下不能声称观看')
    if decision['dwell_seconds']>conditions['available_seconds']:
        raise ValueError('观看时间不能超过本轮机会窗口')
    return decision
