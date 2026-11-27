import json
from pathlib import Path
import pytest
from app.audience.world import read_json,write_json
from app.audience.simulation_workflow import full_day,signature,begin,inspect
from app.audience import store


def run():
    return dict(id='r',engine='OASIS 0.2.5',status='completed',current_round=24,scene=dict(rounds=24,schedule=[dict(hour=h,round=h+1) for h in range(24)]),snapshots=[dict(round=h) for h in range(25)])


def test_midnight_complete_not_partial_or_shifted():
    value=run();assert full_day(value)
    value['current_round']=23;assert not full_day(value)
    value=run();value['scene']['schedule'][0]['hour']=8;assert not full_day(value)
    value=run();value['snapshots'].pop();assert not full_day(value)


def test_empty_json_is_actionable_not_decoder_trace(tmp_path):
    p=tmp_path/'hour-9.json';p.write_text('')
    with pytest.raises(ValueError,match='为空或损坏') as exc:read_json(p)
    assert 'Expecting value' not in str(exc.value)


def test_fresh_batch_excludes_history_and_blocks_report(tmp_path):
    project=store.create(tmp_path,dict(frames=[{'screen_id':'s'}],ad_setup={'campaign':{'brand':'Nike'}},result={'old':'report'}))
    batch=begin(tmp_path,project['id'])
    with store.locked(tmp_path,project['id']) as (_,p):
        assert p['result'] is None
        state,evidence=inspect(tmp_path,p)
        assert state['done']==0 and state['total']==1 and not state['ready']
        with pytest.raises(ValueError,match='历史结果或预测'):inspect(tmp_path,p,require_ready=True)
    assert begin(tmp_path,project['id'])['id']==batch['id']
    with store.locked(tmp_path,project['id']) as (path,p):
        p['ad_setup']['campaign']['brand']='Changed';store.save(path,p)
    assert begin(tmp_path,project['id'])['id']!=batch['id']


def test_server_rejects_report_without_fresh_simulation(tmp_path):
    from app import create_app
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path))
    project=store.create(tmp_path,dict(frames=[{'screen_id':'s'}],ad_setup={'campaign':{'brand':'Nike'}}))
    r=app.test_client().post('/api/planning/'+project['id']+'/plan',json={'budget':1000,'currency':'USD','campaign_id':'old-history'})
    assert r.status_code==400 and '全天模拟尚未完成' in r.json['error']


def test_completed_current_day_unlocks_but_missing_hour_revokes(tmp_path):
    from test_investment import base
    project=store.create(tmp_path,dict(frames=[{'screen_id':'s'}],ad_setup={'campaign':{'brand':'Nike'}}))
    batch=begin(tmp_path,project['id']);rid='c'*32;sid='a'*32
    value=run();value.update(id=rid,started_at=batch['created_at']+1)
    rp=tmp_path/'worlds'/rid;rp.mkdir(parents=True);write_json(rp/'state.json',value)
    coverage=store.directory(tmp_path,project['id'])/('coverage-'+batch['id']);scene=coverage/'scenes'/sid;scene.mkdir(parents=True)
    b=base();b['meta']['run_id']=rid;write_json(scene/'base.json',b)
    for h in range(1,25):write_json(scene/f'hour-{h}.json',dict(round=h))
    write_json(coverage/'state.json',dict(status='completed',items={'s':dict(status='completed',scene_id=sid,run_id=rid)}))
    with store.locked(tmp_path,project['id']) as (_,p):
        summary,evidence=inspect(tmp_path,p,require_ready=True)
        assert summary['ready'] and summary['direct']==1 and evidence['screens']['s']['total']==100
        (scene/'hour-24.json').write_text('')
        with pytest.raises(ValueError,match='全天模拟尚未完成'):inspect(tmp_path,p,require_ready=True)


def test_replay_recovers_same_hour_and_original_vehicle_parameters(tmp_path,monkeypatch):
    from app.audience import replay_repair
    sid='a'*32;rid='c'*32;target=tmp_path/'campaign';target.mkdir()
    source=tmp_path/'scene_library'/sid;source.mkdir(parents=True)
    rp=tmp_path/'worlds'/rid;rp.mkdir(parents=True)
    write_json(rp/'state.json',dict(status='completed',scene=dict(schedule=[dict(round=h,hour=h-1) for h in range(1,25)],seed=42)))
    write_json(target/'base.json',dict(meta=dict(id=sid,run_id=rid),network={},traffic=dict(hourly=[dict(round=9,vehicles=100,requested_vehicles=200,absolute_hourly=False)])))
    write_json(source/'hour-9.json',dict(round=9,pedestrians=[{'id':'original'}]))
    (target/'hour-9.json').write_text('')
    monkeypatch.setattr(replay_repair,'route_pool',lambda *args:[])
    def cars(slot,seed,count,network,policies,pool,absolute_count):
        assert slot['hour']==8 and count==200 and absolute_count is False
        return [{'id':'recovered'}]
    monkeypatch.setattr(replay_repair,'connected_vehicles',cars)
    value=replay_repair.campaign_hour(target,9,tmp_path)
    assert value['round']==9 and value['pedestrians']==[{'id':'original'}] and value['recovered_from_run']==rid
    assert read_json(target/'hour-9.json')==value


def test_partial_progress_does_not_decode_completed_traffic(tmp_path,monkeypatch):
    from app.audience import simulation_workflow
    project=store.create(tmp_path,dict(frames=[{'screen_id':'a'},{'screen_id':'b'}],ad_setup={'campaign':{'brand':'Nike'}}))
    batch=begin(tmp_path,project['id'])
    coverage=store.directory(tmp_path,project['id'])/('coverage-'+batch['id']);coverage.mkdir()
    write_json(coverage/'state.json',dict(status='interrupted',items={'a':dict(status='completed',scene_id='s',run_id='r')}))
    monkeypatch.setattr(simulation_workflow,'validated_screen',lambda *args:pytest.fail('partial poll must not decode traffic'))
    with store.locked(tmp_path,project['id']) as (_,p):
        summary,_=inspect(tmp_path,p,progress_only=True)
    assert summary['done']==1 and summary['total']==2 and not summary['ready']
    assert summary['scene_ids']==['s']


def test_lightweight_engine_requires_complete_day_and_explicit_provenance():
    value=run();value.update(engine='pDOOH batch v2',decision_method='batched_interviews_v2')
    assert full_day(value)
    value['current_round']=23
    assert not full_day(value)
    value['current_round']=24;value['decision_method']='unknown'
    assert not full_day(value)
