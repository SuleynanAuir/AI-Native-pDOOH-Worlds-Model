"""Explicitly approximate, model-parameterized policy simulation; not hourly LLM interviews."""
from concurrent.futures import ThreadPoolExecutor
import json,math,random
from .campaign_research import llm_json

METHOD='policy_simulation_v1'
PROMPT='''为每个合成代表生成一组24小时行为仿真的策略参数。这些参数是未校准的模型情景假设，不是真实统计、因果推断或逐小时本人回答。仅按任务、行动与注意力条件推演，不按国籍、种族、收入或家庭背景决定注意力；不能编造屏幕创意或购买。interest_probability指对屏幕本身的好奇，不是对广告或购买的概率。
返回 {"policies":[{"agent_id":0,"notice_probability":0.3,"interest_probability":0.2,"preferred_dwell_seconds":3,"fatigue":0.1,"peer_influence":0,"reason":"策略依据与不确定性，最多40字"}]}。
恰好每个agent_id一次。两个probability在0到1，preferred_dwell_seconds在0到30，fatigue在0到1，peer_influence在-0.2到0.2。允许完全不关注；不要人为追求多样性或一致反应。'''
BOUNDS={'notice_probability':(0,1),'interest_probability':(0,1),'preferred_dwell_seconds':(0,30),'fatigue':(0,1),'peer_influence':(-.2,.2)}


def validate_policies(value,people):
    rows=value.get('policies') if isinstance(value,dict) else None
    ids={p['id'] for p in people};out={}
    if not isinstance(rows,list) or len(rows)!=len(ids):raise ValueError('行为策略未覆盖所有代表')
    for row in rows:
        if not isinstance(row,dict):raise ValueError('行为策略格式无效')
        aid=row.get('agent_id')
        if type(aid) is not int or aid not in ids or aid in out:raise ValueError('行为策略代表ID缺失或重复')
        for key,(low,high) in BOUNDS.items():
            v=row.get(key)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:raise ValueError('行为策略参数超出范围：'+key)
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('行为策略缺少依据')
        out[str(aid)]={**row,'reason':row['reason'][:300]}
    return out


def generate_policies(scene,config,model=llm_json):
    people=scene['agents'];locality=scene.get('locality',{})
    def one(batch):
        payload={'scenario':'无创意内容的户外屏幕相遇，条件策略不是实测','location':{k:locality.get(k) for k in ('city','community','venue_type')},'agents':[{'agent_id':p['id'],'task':p.get('local_context',{}).get('visit_purpose',''),'profile':{k:p.get('audience_profile',{}).get(k) for k in ('attention_context','mobility','preferences','needs')}} for p in batch]}
        for attempt in range(2):
            try:return validate_policies(model(config,PROMPT,payload,max_tokens=5000),batch)
            except ValueError:
                if attempt:raise
    policies={}
    with ThreadPoolExecutor(max_workers=4,thread_name_prefix='policy-generation') as pool:
        for value in pool.map(one,[people[i:i+25] for i in range(0,len(people),25)]):policies.update(value)
    return {'method':METHOD,'model':config['LLM_MODEL_NAME'],'policies':policies,'calibration':'uncalibrated_model_assumptions','caveat':'模型一次生成个人策略，本地算法执行24小时演化；并非逐小时LLM独立决策，不是实测概率。'}


def decide(policy,conditions,seed,agent_id,round_num,seen=0,peer_notice=0):
    rng=random.Random(f'policy:{seed}:{agent_id}:{round_num}')
    available=max(0,min(30,conditions['available_seconds']))
    if not conditions['line_of_sight'] or available==0:
        return dict(reaction='passing',dwell_seconds=0,reason='策略仿真：本轮无视线或可用观看时间，继续经过。')
    probability=policy['notice_probability']*min(1,available/5)/(1+policy['fatigue']*seen)
    probability=max(0,min(1,probability+policy['peer_influence']*peer_notice))
    if rng.random()>=probability:
        return dict(reaction='passing',dwell_seconds=0,reason='策略仿真：结合任务窗口、过往接触和注意参数，本轮未观看。')
    dwell=round(min(available,policy['preferred_dwell_seconds']*rng.uniform(.6,1.4)),3)
    if dwell<=0:return dict(reaction='passing',dwell_seconds=0,reason='策略仿真：本轮策略未分配观看时间。')
    reaction='interest' if rng.random()<policy['interest_probability'] else 'watch' if dwell>=2 else 'glance'
    return dict(reaction=reaction,dwell_seconds=dwell,reason='策略仿真：'+policy['reason'])
