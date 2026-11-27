"""Fast policy-based simulation. It deliberately does not claim hourly LLM interviews."""
import sys,time,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app.audience.world import read_json,write_json,encounter_conditions,validate_encounter_decision
from app.audience.policy_simulation import generate_policies,decide,METHOD
from app.audience.day_cycle import attendance
from app.audience.cohorts import summarize
from app.audience.mobility import movement_summary,with_viewing_stop


def run(directory):
    state=read_json(directory/'state.json');scene=state['scene'];began=time.time()
    def progress():
        write_json(directory/'progress.json',{k:state.get(k) for k in ('status','current_round','message','decision_method','started_at','completed_at')})
    state.update(status='initializing',message='模型生成个人行为策略',engine='pDOOH policy v1',decision_method=METHOD,started_at=began)
    write_json(directory/'state.json',state);progress()
    path=directory/'policies.json'
    policies=read_json(path) if path.exists() else generate_policies(scene,{k:getattr(Config,k) for k in ('LLM_API_KEY','LLM_BASE_URL','LLM_MODEL_NAME')})
    write_json(path,policies)
    state.update(policy_generation_seconds=time.time()-began,calibration=policies['calibration'],method_note=policies['caveat'],model=Config.LLM_MODEL_NAME,policy_decisions=0,status='running')
    seen={p['id']:0 for p in scene['agents']}
    for round_num in range(1,scene['rounds']+1):
        while True:
            control=read_json(directory/'control.json')
            if control.get('stop'):
                state.update(status='stopped',message='策略仿真已停止');write_json(directory/'state.json',state);progress();return
            if not control.get('paused'):break
            state.update(status='paused',message='策略仿真已暂停');progress();time.sleep(.4)
        slot=scene['schedule'][round_num-1];journeys=scene['mobility_rounds'][round_num-1];last=state['snapshots'][-1]['agents'];people=[];events=[]
        for person in scene['agents']:
            aid=person['id'];trip=journeys.get(str(aid));presence=attendance(person,slot,scene['seed'])
            encounter=trip.get('encounter') if trip else None
            screen=next((s for s in scene['screens'] if encounter and s['id']==encounter['screen_id']),None)
            conditions=None
            if not presence['present']:
                decision=dict(reaction='away',dwell_seconds=None,reason='本时段排程无街区出行。');screen=None;source='scenario_schedule'
            elif screen is None:
                decision=dict(reaction='unexposed',dwell_seconds=None,reason='本轮路线没有进入屏幕相遇范围。');source='spatial_route'
            else:
                conditions=encounter_conditions(person,screen,round_num,scene['seed'],slot)
                conditions.update(distance_m=round(encounter['distance']*scene['neighborhood']['meters_per_unit'],1),minute=encounter['minute'])
                previous=[p for p in last if p.get('screen_id')==screen['id'] and p['id']!=aid]
                peers=sum(p.get('reaction') in ('glance','watch','interest') for p in previous)/max(1,len(previous))
                decision=validate_encounter_decision(decide(policies['policies'][str(aid)],conditions,scene['seed'],aid,round_num,seen[aid],peers),conditions)
                seen[aid]+=int(decision['reaction']!='passing');state['policy_decisions']+=1
                trip=with_viewing_stop(trip,decision);source=METHOD
            row={**person,**decision,'presence':presence,'screen_id':screen['id'] if screen else None}
            if presence['present'] and trip:
                point=trip['encounter'] if screen else trip['waypoints'][len(trip['waypoints'])//2]
                row.update(x=point['x'],y=point['y'],journey=trip)
            if conditions:row['encounter']=conditions
            people.append(row)
            event=dict(round=round_num,agent_id=aid,name=person['name'],group=person['group'],color=person['color'],represented_population=person.get('represented_population',1),screen_id=row['screen_id'],trace_id=None,decision_source=source,time=slot['time'],day=slot['day'],**decision)
            if conditions:event.update(encounter=conditions,policy_agent_id=aid)
            events.append(event)
        state['snapshots'].append(dict(round=round_num,slot=slot,agents=people,events=events,summary=summarize(people),movement_summary=movement_summary(people)))
        state['events'].extend(events);state.update(status='running',current_round=round_num,message=f'策略仿真完成第 {round_num}/{scene["rounds"]} 小时')
        if round_num%4==0:write_json(directory/'state.json',state)
        progress()
    state.update(status='completed',completed_at=time.time(),message='24小时策略仿真完成；非逐小时LLM独立决策')
    write_json(directory/'state.json',state);progress()


if __name__=='__main__':
    directory=Path(sys.argv[1]).resolve()
    try:run(directory)
    except Exception as exc:
        state=read_json(directory/'state.json');state.update(status='failed',message=str(exc)[:300] if isinstance(exc,ValueError) else '策略仿真失败：'+type(exc).__name__)
        write_json(directory/'state.json',state);write_json(directory/'progress.json',{k:state.get(k) for k in ('status','current_round','message')})
        import traceback
        traceback.print_exc();sys.exit(1)
