"""Run bounded OASIS scene encounters in an isolated worker and persist real trace replay."""
import asyncio
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app.audience.world import read_json,write_json as write_full_json,parse_decision,encounter_position,encounter_conditions,validate_encounter_decision
from app.audience.cohorts import summarize
from app.audience.batched_decisions import batches,prompt_for,parse_batch,recover_batch,BATCH_SIZE
from app.audience.day_cycle import attendance
from app.audience.mobility import movement_summary,with_viewing_stop


def write_json(path,value):
    write_full_json(path,value)
    if Path(path).name=='state.json':
        write_full_json(Path(path).with_name('progress.json'),{k:value.get(k) for k in ('status','current_round','active_round','completed_decisions','total_decisions','message','decision_method','started_at','completed_at')})


async def run(directory):
    state=read_json(directory/'state.json');config=state['scene']
    locality=config.get('locality')
    regional_context=None
    if locality:
        from app.audience.locality import scoped_sources
        sources,_=scoped_sources(locality)
        regional_context={**{k:v for k,v in locality.items() if k!='sources'},'sources':[dict(id=s['id'],title=s['title'],text=s['text'][:1200],truncated=len(s['text'])>1200,url=s['url'],scope=dict(country=s['country'],city=s['city'],community=s['community'])) for s in sources], 'boundary':'地区和社区描述是场景上下文，不代表每个人的身份、文化或偏好；只引用给定资料，画像为推演。'}
    state.update(status='initializing',message='加载 OASIS Agent 与独立运行环境');write_json(directory/'state.json',state)
    os.environ['USE_TF']='0'
    import oasis
    from oasis import AgentGraph,SocialAgent,UserInfo,ActionType,ManualAction,Platform
    from oasis.social_platform.channel import Channel
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    from camel.prompts import TextPrompt
    logging.getLogger('social.agent').setLevel(logging.ERROR)
    logging.getLogger('camel').setLevel(logging.ERROR)
    if not Config.LLM_API_KEY:raise ValueError('请配置 LLM_API_KEY')
    graph=AgentGraph()
    template=TextPrompt('你是合成人群批量推演员。{persona}。必须逐人返回独立、可验证的JSON决策，不编造真实行为。')
    model_config={'max_tokens':4096,'temperature':.6}
    if 'deepseek.com' in Config.LLM_BASE_URL:
        model_config['extra_body']={'thinking':{'type':'disabled'}}
    for profile in config['agents'][:(len(config['agents'])+BATCH_SIZE-1)//BATCH_SIZE]:
        model=ModelFactory.create(model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,model_type=Config.LLM_MODEL_NAME,api_key=Config.LLM_API_KEY,url=Config.LLM_BASE_URL,model_config_dict=model_config,timeout=90,max_retries=1)
        agent=SocialAgent(agent_id=profile['id'],user_info=UserInfo(user_name=f'person_{profile["id"]}',name=profile['name'],description='批量推演员',profile={'persona':'逐人使用输入画像，不能将某一人的人设套用给其他人'}),user_info_template=template,model=model,available_actions=[ActionType.INTERVIEW],interview_record=False)
        graph.add_agent(agent)
    # Random recommendation avoids downloading an unrelated social embedding model.
    platform=Platform(db_path=str(directory/'oasis.db'),channel=Channel(),recsys_type='random')
    env=oasis.make(agent_graph=graph,platform=platform,database_path=str(directory/'oasis.db'),semaphore=8)
    await env.reset()
    state.update(llm_decisions=0,engine=f'OASIS {oasis.__version__} batched',decision_method='batched_interviews_v1',decision_batch_size=BATCH_SIZE,model=Config.LLM_MODEL_NAME,status='running',message='OASIS Agent 正在决策',started_at=time.time())
    write_json(directory/'state.json',state)
    try:
        for round_num in range(1,config['rounds']+1):
            while True:
                control=read_json(directory/'control.json')
                if control.get('stop'):
                    state.update(status='stopped',message='运行已停止');write_json(directory/'state.json',state);return
                if not control.get('paused'):break
                state.update(status='paused',message='已在轮次边界暂停');write_json(directory/'state.json',state);await asyncio.sleep(.4)
            slot=config.get('schedule',[None]*config['rounds'])[round_num-1]
            label=f'{slot["date"]} {slot["time"]} · {slot["period_label"]}' if slot else f'第 {round_num}/{config["rounds"]} 轮'
            state.update(status='running',message=f'{label}：OASIS 正在生成群体反应',active_round=round_num,active_slot=slot,completed_decisions=0,total_decisions=len(config['agents']))
            write_json(directory/'state.json',state)
            requests=[];decisions={};traces={};encounters={};conditions={};presence={}
            journeys=config['mobility_rounds'][round_num-1]
            last=state['snapshots'][-1]['agents']
            for profile in config['agents']:
                aid=profile['id'];trip=journeys.get(str(aid))
                opportunity=trip.get('encounter') if trip else None
                screen=next((s for s in config['screens'] if opportunity and s['id']==opportunity['screen_id']),None)
                presence[aid]=attendance(profile,slot,config['seed']) if slot else dict(present=True)
                encounters[aid]=screen
                if not presence[aid]['present'] or not screen:continue
                conditions[aid]=encounter_conditions(profile,screen,round_num,config['seed'],slot)
                conditions[aid].update(route=trip['origin']+' → '+' → '.join([*trip['stops'],trip['destination']]),
                                       distance_m=round(opportunity['distance']*config['neighborhood']['meters_per_unit'],1),
                                       minute=opportunity['minute'],current_task=trip['purpose']+'；'+conditions[aid]['current_task'],
                                       assumptions='实际合成步行路线进入屏幕近邻半径；屏幕假定双面；面向/注意方向与临时遮挡为种子抽样；非现场测量')
                history=[dict(round=s['round'],time={k:v for k,v in (s.get('slot') or {}).items() if k in ('time','day','period_label')},reaction=s['agents'][aid]['reaction'],reason=s['agents'][aid]['reason']) for s in state['snapshots'][1:][-3:]]
                peers=[]
                from collections import Counter
                peer_counts=Counter((p['group'],p['reaction']) for p in last if p['screen_id']==screen['id'] and p['id']!=aid)
                peers=[dict(group=g,reaction=r,representative_count=n) for (g,r),n in peer_counts.items()]
                context=dict(round=round_num,audience_profile=profile.get('audience_profile',{}),represented_population=profile.get('represented_population',1),profile_source=profile.get('profile_source','合成假设'),screen=screen,encounter=conditions[aid],previous_encounters=history,nearby_previous_reactions=peers,scenario='合成路人经过户外屏幕所在区域；经过不等于看见。没有广告创意或屏幕内容资料，不可编造屏幕上的文字、优惠或推测购买。')
                context['journey']={k:v for k,v in trip.items() if k not in ('waypoints','screen_opportunities')}
                context.update(time_context={k:v for k,v in (slot or {}).items() if k!='present_agent_ids'},activity=presence[aid])
                if regional_context:
                    context.update(regional_context=regional_context,local_audience=profile['local_context'],local_rationale=profile['local_rationale'],source_ids=profile['source_ids'])
                if not conditions[aid]['line_of_sight']:
                    decisions[aid]=dict(reaction='passing',dwell_seconds=0,reason='本轮没有视线机会，按相遇规则继续经过。')
                    traces[aid]=None
                    continue
                requests.append(dict(agent_id=aid,persona=profile['persona'],context=context))
            groups=batches(requests)
            state.update(total_decisions=len(requests),completed_decisions=0,scheduled_away=sum(not p['present'] for p in presence.values()),unexposed_agents=sum(p['present'] and encounters[aid] is None for aid,p in presence.items()))
            pending=groups
            slots=(len(config['agents'])+BATCH_SIZE-1)//BATCH_SIZE
            for attempt in range(3):
                retry=[]
                for offset in range(0,len(pending),slots):
                    wave=pending[offset:offset+slots]
                    actions={graph.get_agent(i):ManualAction(action_type=ActionType.INTERVIEW,action_args={'prompt':prompt_for(rows)}) for i,rows in enumerate(wave)}
                    if not actions:continue
                    await asyncio.wait_for(env.step(actions),timeout=240)
                    state['llm_requests']=state.get('llm_requests',0)+len(actions)
                    with sqlite3.connect(directory/'oasis.db') as db:
                        for i,rows in enumerate(wave):
                            row=db.execute('SELECT rowid,info FROM trace WHERE user_id=? AND action=? ORDER BY rowid DESC LIMIT 1',(i,ActionType.INTERVIEW.value)).fetchone()
                            if not row:raise ValueError('OASIS 未写入批量决策记录')
                            parsed,missing=recover_batch(json.loads(row[1]).get('response'),rows)
                            decisions.update(parsed)
                            traces.update({aid:row[0] for aid in parsed})
                            retry.extend([[person] for person in missing])
                if not retry:break
                pending=retry
            else:
                raise ValueError('批量决策重试后仍未通过逐人校验，请重试此屏幕')
            state['llm_decisions']+=len(requests)
            state.update(completed_decisions=len(requests))
            snapshot=[];events=[]
            with sqlite3.connect(directory/'oasis.db') as db:
                for profile in config['agents']:
                    aid=profile['id'];screen=encounters[aid];trip=journeys.get(str(aid))
                    if not presence[aid]['present']:
                        decision=dict(reaction='away',reason='本时段排程没有街区出行；未调用 LLM，不视为未注意广告。',dwell_seconds=None)
                        snapshot.append({**profile,**decision,'screen_id':None,'presence':presence[aid]})
                        events.append(dict(round=round_num,agent_id=aid,name=profile['name'],group=profile['group'],color=profile['color'],represented_population=profile.get('represented_population',1),screen_id=None,trace_id=None,decision_source='scenario_schedule',time=slot['time'],day=slot['day'],presence=presence[aid],**decision))
                        continue
                    if screen is None:
                        decision=dict(reaction='unexposed',reason='本次步行路线未进入任何屏幕的情景可见范围；继续周边活动，不计为忽略广告。',dwell_seconds=None)
                        point=trip['waypoints'][len(trip['waypoints'])//2]
                        snapshot.append({**profile,**decision,'x':point['x'],'y':point['y'],'screen_id':None,'presence':presence[aid],'journey':trip})
                        events.append(dict(round=round_num,agent_id=aid,name=profile['name'],group=profile['group'],color=profile['color'],represented_population=profile.get('represented_population',1),screen_id=None,trace_id=None,decision_source='spatial_route',time=slot['time'] if slot else None,day=slot['day'] if slot else None,**decision))
                        continue
                    decision=decisions[aid]
                    trip=with_viewing_stop(trip,decision)
                    person={**profile,'x':trip['encounter']['x'],'y':trip['encounter']['y'],**decision,'screen_id':screen['id'],'encounter':conditions[aid],'presence':presence[aid],'journey':trip}
                    snapshot.append(person)
                    events.append(dict(round=round_num,agent_id=aid,name=profile['name'],group=profile['group'],color=profile['color'],represented_population=profile.get('represented_population',1),screen_id=screen['id'],trace_id=traces[aid],decision_source='oasis_batched_interview' if traces[aid] is not None else 'encounter_visibility_rule',time=slot['time'] if slot else None,day=slot['day'] if slot else None,encounter=conditions[aid],**decision))
            state['snapshots'].append(dict(round=round_num,slot=slot,agents=snapshot,events=events,summary=summarize(snapshot),movement_summary=movement_summary(snapshot)))
            state['events'].extend(events);state.update(current_round=round_num)
            write_json(directory/'state.json',state)
        state.update(status='completed',message='OASIS 推演完成，可回放每轮行为',completed_at=time.time())
        write_json(directory/'state.json',state)
    finally:
        await env.close()


if __name__=='__main__':
    directory=Path(sys.argv[1]).resolve()
    try:asyncio.run(run(directory))
    except Exception as exc:
        state=read_json(directory/'state.json')
        status=getattr(exc,'status_code',None)
        # Never serialize provider payloads or credentials into the public replay.
        message=f'OASIS 运行失败：{type(exc).__name__}' + (f'（HTTP {status}）' if status else '')
        if isinstance(exc,ValueError):message=str(exc)[:300]
        state.update(status='failed',message=message)
        write_json(directory/'state.json',state)
        import traceback
        traceback.print_exc()
        sys.exit(1)
