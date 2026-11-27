import importlib.util,json,math
from pathlib import Path
import pytest
from app.audience.policy_simulation import validate_policies,decide,generate_policies,METHOD
from app.audience.world import scene,write_json,read_json
from app.audience.simulation_workflow import full_day


def policy(aid):return dict(agent_id=aid,notice_probability=.6,interest_probability=.2,preferred_dwell_seconds=5,fatigue=.1,peer_influence=.05,reason='任务与注意机会的未校准假设')


def test_strategy_covers_every_person_once():
    calls=[]
    def model(config,prompt,payload,**kwargs):
        calls.append(payload)
        return {'policies':[policy(row['agent_id']) for row in payload['agents']]}
    result=generate_policies({'agents':[{'id':i} for i in range(100)]},{'LLM_MODEL_NAME':'fake'},model=model)
    assert set(result['policies'])=={str(i) for i in range(100)}
    assert len(calls)==4 and result['calibration']=='uncalibrated_model_assumptions'


@pytest.mark.parametrize('change',[{'notice_probability':float('nan')},{'fatigue':-1},{'peer_influence':1},{'preferred_dwell_seconds':True},{'agent_id':2}])
def test_invalid_parameters_never_become_defaults(change):
    with pytest.raises(ValueError):validate_policies({'policies':[{**policy(0),**change}]},[{'id':0}])


def test_policy_respects_visibility_time_and_seed():
    p=policy(0);condition={'line_of_sight':False,'available_seconds':0}
    assert decide(p,condition,42,0,1)['reaction']=='passing'
    condition={'line_of_sight':True,'available_seconds':1}
    for hour in range(24):
        value=decide(p,condition,42,0,hour)
        assert value==decide(p,condition,42,0,hour)
        assert 0<=value['dwell_seconds']<=1


def test_complete_policy_day_keeps_all_representatives_and_provenance(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[1]/'scripts/run_audience_policy.py'
    spec=importlib.util.spec_from_file_location('policy_worker',path);worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    config=scene(population=100,total_population=30000,day_cycle={})
    generated={'policies':{str(p['id']):policy(p['id']) for p in config['agents']},'calibration':'uncalibrated_model_assumptions','caveat':'policy simulation'}
    monkeypatch.setattr(worker,'generate_policies',lambda *args:generated)
    write_json(tmp_path/'state.json',dict(id='p',scene=config,current_round=0,status='queued',events=[],snapshots=[dict(round=0,agents=config['agents'])]))
    write_json(tmp_path/'control.json',dict(paused=False,stop=False))
    worker.run(tmp_path)
    state=read_json(tmp_path/'state.json')
    assert full_day(state) and state['decision_method']==METHOD
    assert len(state['events'])==2400
    assert all(len(s['agents'])==100 for s in state['snapshots'])
    assert {e['decision_source'] for e in state['events']}<={'scenario_schedule','spatial_route',METHOD}
    assert all(e['trace_id'] is None for e in state['events'])
    state['current_round']=23
    assert not full_day(state)
